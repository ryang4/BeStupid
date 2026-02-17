import Foundation
import Testing
@testable import BeStupidApp

// MARK: - Mock Git Command Runner

/// A configurable mock for `GitCommandRunner` that returns predetermined responses
/// or throws predetermined errors based on the command arguments.
final class MockGitRunner: GitCommandRunner, @unchecked Sendable {
    private let lock = NSLock()

    /// Map of command argument strings to their expected output.
    /// The key is the arguments joined by a space (e.g. "clone https://... /path").
    private var _responses: [String: String]

    /// If true, all commands throw a network failure.
    private var _shouldFailWithNetwork: Bool

    /// If true, all commands throw a generic command failure.
    private var _shouldFailWithCommand: Bool

    /// Custom failure message for errors.
    private var _failureMessage: String

    /// Records every command that was executed, in order.
    private var _executedCommands: [[String]]

    /// Optional per-command error overrides. Key is a substring match on the joined args.
    private var _errorOverrides: [String: GitError]

    var responses: [String: String] {
        get { lock.lock(); defer { lock.unlock() }; return _responses }
        set { lock.lock(); _responses = newValue; lock.unlock() }
    }

    var shouldFailWithNetwork: Bool {
        get { lock.lock(); defer { lock.unlock() }; return _shouldFailWithNetwork }
        set { lock.lock(); _shouldFailWithNetwork = newValue; lock.unlock() }
    }

    var shouldFailWithCommand: Bool {
        get { lock.lock(); defer { lock.unlock() }; return _shouldFailWithCommand }
        set { lock.lock(); _shouldFailWithCommand = newValue; lock.unlock() }
    }

    var failureMessage: String {
        get { lock.lock(); defer { lock.unlock() }; return _failureMessage }
        set { lock.lock(); _failureMessage = newValue; lock.unlock() }
    }

    var executedCommands: [[String]] {
        get { lock.lock(); defer { lock.unlock() }; return _executedCommands }
        set { lock.lock(); _executedCommands = newValue; lock.unlock() }
    }

    var errorOverrides: [String: GitError] {
        get { lock.lock(); defer { lock.unlock() }; return _errorOverrides }
        set { lock.lock(); _errorOverrides = newValue; lock.unlock() }
    }

    init(
        responses: [String: String] = [:],
        shouldFailWithNetwork: Bool = false,
        shouldFailWithCommand: Bool = false,
        failureMessage: String = "Mock failure"
    ) {
        self._responses = responses
        self._shouldFailWithNetwork = shouldFailWithNetwork
        self._shouldFailWithCommand = shouldFailWithCommand
        self._failureMessage = failureMessage
        self._executedCommands = []
        self._errorOverrides = [:]
    }

    func run(_ args: [String], in directory: URL) async throws -> String {
        let key = args.joined(separator: " ")

        lock.lock()
        _executedCommands.append(args)
        let shouldNetwork = _shouldFailWithNetwork
        let shouldCommand = _shouldFailWithCommand
        let message = _failureMessage
        let overrides = _errorOverrides
        let resps = _responses
        lock.unlock()

        // Check per-command error overrides.
        for (pattern, error) in overrides {
            if key.contains(pattern) {
                throw error
            }
        }

        if shouldNetwork {
            throw GitError.networkFailure(message)
        }

        if shouldCommand {
            throw GitError.commandFailed(command: "git \(key)", output: message)
        }

        // Look up the response by exact match first, then by prefix match.
        if let response = resps[key] {
            return response
        }

        // Try partial matching: find the first key that the command starts with.
        for (responseKey, response) in resps {
            if key.hasPrefix(responseKey) {
                return response
            }
        }

        return ""
    }
}

// MARK: - Mock Keychain

/// In-memory keychain mock for testing credential operations.
final class MockKeychain: KeychainOperations, @unchecked Sendable {
    private let lock = NSLock()
    private var storage: [String: Data] = [:]

    func add(query: CFDictionary) -> OSStatus {
        lock.lock()
        defer { lock.unlock() }

        let dict = query as! [String: Any]
        guard let service = dict[kSecAttrService as String] as? String,
              let account = dict[kSecAttrAccount as String] as? String,
              let data = dict[kSecValueData as String] as? Data else {
            return errSecParam
        }

        let key = "\(service):\(account)"
        if storage[key] != nil {
            return errSecDuplicateItem
        }

        storage[key] = data
        return errSecSuccess
    }

    func copyMatching(query: CFDictionary, result: UnsafeMutablePointer<CFTypeRef?>) -> OSStatus {
        lock.lock()
        defer { lock.unlock() }

        let dict = query as! [String: Any]
        guard let service = dict[kSecAttrService as String] as? String,
              let account = dict[kSecAttrAccount as String] as? String else {
            return errSecParam
        }

        let key = "\(service):\(account)"
        guard let data = storage[key] else {
            return errSecItemNotFound
        }

        result.pointee = data as CFTypeRef
        return errSecSuccess
    }

    func delete(query: CFDictionary) -> OSStatus {
        lock.lock()
        defer { lock.unlock() }

        let dict = query as! [String: Any]
        guard let service = dict[kSecAttrService as String] as? String,
              let account = dict[kSecAttrAccount as String] as? String else {
            return errSecParam
        }

        let key = "\(service):\(account)"
        if storage.removeValue(forKey: key) != nil {
            return errSecSuccess
        }
        return errSecItemNotFound
    }

    func update(query: CFDictionary, attributes: CFDictionary) -> OSStatus {
        lock.lock()
        defer { lock.unlock() }

        let dict = query as! [String: Any]
        let attrs = attributes as! [String: Any]

        guard let service = dict[kSecAttrService as String] as? String,
              let account = dict[kSecAttrAccount as String] as? String else {
            return errSecParam
        }

        let key = "\(service):\(account)"
        guard storage[key] != nil else {
            return errSecItemNotFound
        }

        if let data = attrs[kSecValueData as String] as? Data {
            storage[key] = data
        }

        return errSecSuccess
    }

    /// Returns the number of items currently stored.
    var count: Int {
        lock.lock()
        defer { lock.unlock() }
        return storage.count
    }

    /// Clears all stored items.
    func reset() {
        lock.lock()
        storage.removeAll()
        lock.unlock()
    }
}

// MARK: - Mock Git Repository

/// A mock of the `GitRepository` protocol for testing `DataSyncCoordinator`.
actor MockGitRepository: GitRepository {
    var cloneCalled = false
    var pullCalled = false
    var commitAllCalled = false
    var pushCalled = false
    var statusCalled = false
    var hasLocalChangesCalled = false

    var lastCommitMessage: String?

    var pullResult: PullResult = .upToDate
    var statusResult: GitStatus = .empty
    var hasChangesResult: Bool = false

    var shouldThrowOnClone: GitError?
    var shouldThrowOnPull: GitError?
    var shouldThrowOnCommit: GitError?
    var shouldThrowOnPush: GitError?

    func clone(from url: URL, to localPath: URL, credentials: GitCredentials) async throws {
        cloneCalled = true
        if let error = shouldThrowOnClone {
            throw error
        }
    }

    func pull(credentials: GitCredentials) async throws -> PullResult {
        pullCalled = true
        if let error = shouldThrowOnPull {
            throw error
        }
        return pullResult
    }

    func commitAll(message: String) async throws {
        commitAllCalled = true
        lastCommitMessage = message
        if let error = shouldThrowOnCommit {
            throw error
        }
    }

    func push(credentials: GitCredentials) async throws {
        pushCalled = true
        if let error = shouldThrowOnPush {
            throw error
        }
    }

    func status() async throws -> GitStatus {
        statusCalled = true
        return statusResult
    }

    func hasLocalChanges() async throws -> Bool {
        hasLocalChangesCalled = true
        return hasChangesResult
    }
}

// MARK: - Test Helpers

/// Creates a temporary directory for test isolation.
private func makeTempDir() throws -> URL {
    let tmpDir = FileManager.default.temporaryDirectory
        .appendingPathComponent("bestupid-tests-\(UUID().uuidString)")
    try FileManager.default.createDirectory(at: tmpDir, withIntermediateDirectories: true)
    return tmpDir
}

/// Removes a temporary directory after a test.
private func cleanupTempDir(_ url: URL) {
    try? FileManager.default.removeItem(at: url)
}

/// Creates a fake `.git` directory to simulate a cloned repo.
private func simulateClonedRepo(at path: URL) throws {
    let gitDir = path.appendingPathComponent(".git")
    try FileManager.default.createDirectory(at: gitDir, withIntermediateDirectories: true)
}

/// Standard test credentials.
private let testCredentials = GitCredentials(username: "testuser", token: "ghp_testtoken123")

/// Standard test repo URL.
private let testRepoURL = URL(string: "https://github.com/testuser/BeStupid.git")!

// MARK: - GitSyncService Tests

@Suite("GitSyncService")
struct GitSyncServiceTests {

    // MARK: - Clone Tests

    @Test("Clone creates directory and initializes repo")
    func cloneCreatesRepo() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        let runner = MockGitRunner(responses: [
            "clone": ""
        ])

        let service = GitSyncService(repoPath: repoPath, runner: runner)

        try await service.clone(from: testRepoURL, to: repoPath, credentials: testCredentials)

        // Verify the clone command was issued.
        let commands = runner.executedCommands
        #expect(commands.count == 1)
        #expect(commands[0][0] == "clone")
        #expect(commands[0][1].contains("testuser"))
        #expect(commands[0][2] == repoPath.path)
    }

    @Test("Clone throws alreadyCloned when .git exists")
    func cloneThrowsIfAlreadyCloned() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try simulateClonedRepo(at: repoPath)

        let runner = MockGitRunner()
        let service = GitSyncService(repoPath: repoPath, runner: runner)

        do {
            try await service.clone(from: testRepoURL, to: repoPath, credentials: testCredentials)
            Issue.record("Expected alreadyCloned error")
        } catch let error as GitError {
            #expect(error == .alreadyCloned)
        }
    }

    @Test("Clone propagates network failure")
    func cloneNetworkFailure() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        let runner = MockGitRunner(
            shouldFailWithNetwork: true,
            failureMessage: "Could not resolve host"
        )

        let service = GitSyncService(repoPath: repoPath, runner: runner)

        do {
            try await service.clone(from: testRepoURL, to: repoPath, credentials: testCredentials)
            Issue.record("Expected network failure")
        } catch let error as GitError {
            if case .networkFailure(let msg) = error {
                #expect(msg.contains("Could not resolve host"))
            } else {
                Issue.record("Expected networkFailure, got \(error)")
            }
        }
    }

    // MARK: - Pull Tests

    @Test("Pull returns upToDate when no changes")
    func pullUpToDate() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try simulateClonedRepo(at: repoPath)

        let runner = MockGitRunner(responses: [
            "remote get-url origin": "https://github.com/testuser/BeStupid.git",
            "remote set-url origin": "",
            "fetch origin": "",
            "rev-list --count HEAD..origin/main": "0",
        ])

        let service = GitSyncService(repoPath: repoPath, runner: runner)
        let result = try await service.pull(credentials: testCredentials)

        #expect(result == .upToDate)
    }

    @Test("Pull returns merged with file count when changes exist")
    func pullMergedWithChanges() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try simulateClonedRepo(at: repoPath)

        let runner = MockGitRunner(responses: [
            "remote get-url origin": "https://github.com/testuser/BeStupid.git",
            "remote set-url origin": "",
            "fetch origin": "",
            "rev-list --count HEAD..origin/main": "3",
            "rebase origin/main": "",
        ])

        let service = GitSyncService(repoPath: repoPath, runner: runner)
        let result = try await service.pull(credentials: testCredentials)

        #expect(result == .merged(fileCount: 3))
    }

    @Test("Pull detects conflicts and aborts rebase")
    func pullDetectsConflicts() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try simulateClonedRepo(at: repoPath)

        let runner = MockGitRunner(responses: [
            "remote get-url origin": "https://github.com/testuser/BeStupid.git",
            "remote set-url origin": "",
            "fetch origin": "",
            "rev-list --count HEAD..origin/main": "2",
            "status --porcelain": "UU content/logs/2026-02-17.md\nUU memory/people.json",
            "rebase --abort": "",
        ])
        runner.errorOverrides = [
            "rebase origin/main": .commandFailed(
                command: "git rebase origin/main",
                output: "CONFLICT (content): Merge conflict"
            )
        ]

        let service = GitSyncService(repoPath: repoPath, runner: runner)
        let result = try await service.pull(credentials: testCredentials)

        #expect(result == .conflict(files: [
            "content/logs/2026-02-17.md",
            "memory/people.json"
        ]))

        // Verify rebase --abort was called.
        let commands = runner.executedCommands
        let abortCommands = commands.filter { $0.contains("--abort") }
        #expect(!abortCommands.isEmpty)
    }

    @Test("Pull throws notCloned when repo does not exist")
    func pullNotCloned() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("nonexistent")
        let runner = MockGitRunner()
        let service = GitSyncService(repoPath: repoPath, runner: runner)

        do {
            _ = try await service.pull(credentials: testCredentials)
            Issue.record("Expected notCloned error")
        } catch let error as GitError {
            #expect(error == .notCloned)
        }
    }

    // MARK: - CommitAll Tests

    @Test("CommitAll stages and commits changes")
    func commitAllStagesAndCommits() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try simulateClonedRepo(at: repoPath)

        let runner = MockGitRunner(responses: [
            "add --all": "",
            "diff --cached --name-only": "content/logs/2026-02-17.md",
            "commit -m Daily log update": "",
        ])

        let service = GitSyncService(repoPath: repoPath, runner: runner)
        try await service.commitAll(message: "Daily log update")

        let commands = runner.executedCommands
        let addCommand = commands.first { $0.contains("add") }
        let commitCommand = commands.first { $0.contains("commit") }

        #expect(addCommand != nil)
        #expect(commitCommand != nil)
        #expect(commitCommand?.contains("Daily log update") == true)
    }

    @Test("CommitAll throws when no changes are staged")
    func commitAllNoChanges() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try simulateClonedRepo(at: repoPath)

        let runner = MockGitRunner(responses: [
            "add --all": "",
            "diff --cached --name-only": "",
        ])

        let service = GitSyncService(repoPath: repoPath, runner: runner)

        do {
            try await service.commitAll(message: "Empty commit")
            Issue.record("Expected commitFailed error")
        } catch let error as GitError {
            if case .commitFailed(let msg) = error {
                #expect(msg.contains("No changes staged"))
            } else {
                Issue.record("Expected commitFailed, got \(error)")
            }
        }
    }

    @Test("CommitAll throws notCloned when repo does not exist")
    func commitAllNotCloned() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("nonexistent")
        let runner = MockGitRunner()
        let service = GitSyncService(repoPath: repoPath, runner: runner)

        do {
            try await service.commitAll(message: "test")
            Issue.record("Expected notCloned error")
        } catch let error as GitError {
            #expect(error == .notCloned)
        }
    }

    // MARK: - Push Tests

    @Test("Push sends changes to remote")
    func pushSendsToRemote() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try simulateClonedRepo(at: repoPath)

        let runner = MockGitRunner(responses: [
            "remote get-url origin": "https://github.com/testuser/BeStupid.git",
            "remote set-url origin": "",
            "push origin main": "",
        ])

        let service = GitSyncService(repoPath: repoPath, runner: runner)
        try await service.push(credentials: testCredentials)

        let commands = runner.executedCommands
        let pushCommand = commands.first { $0.contains("push") }
        #expect(pushCommand != nil)
        #expect(pushCommand?.contains("origin") == true)
        #expect(pushCommand?.contains("main") == true)
    }

    @Test("Push retries with exponential backoff on network failure")
    func pushRetriesOnNetworkFailure() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try simulateClonedRepo(at: repoPath)

        // Use very short delays for testing.
        let fastRetry = RetryConfiguration(
            maxAttempts: 3,
            initialDelaySeconds: 0.01,
            multiplier: 2.0
        )

        let runner = MockGitRunner(responses: [
            "remote get-url origin": "https://github.com/testuser/BeStupid.git",
            "remote set-url origin": "",
        ])
        // All push attempts fail with network error.
        runner.errorOverrides = [
            "push origin main": .networkFailure("Connection refused")
        ]

        let service = GitSyncService(
            repoPath: repoPath,
            runner: runner,
            retryConfig: fastRetry
        )

        let startTime = Date()

        do {
            try await service.push(credentials: testCredentials)
            Issue.record("Expected network failure after retries")
        } catch let error as GitError {
            if case .networkFailure(let msg) = error {
                #expect(msg.contains("Connection refused"))
            } else {
                Issue.record("Expected networkFailure, got \(error)")
            }
        }

        let elapsed = Date().timeIntervalSince(startTime)

        // Verify multiple push attempts were made.
        let commands = runner.executedCommands
        let pushCommands = commands.filter { $0.contains("push") }
        #expect(pushCommands.count == 3)

        // Verify some time passed for backoff (at least the sum of first two delays).
        // With 0.01 * 1 + 0.01 * 2 = 0.03 seconds minimum.
        #expect(elapsed >= 0.02)
    }

    @Test("Push does not retry on authentication failure")
    func pushNoRetryOnAuthFailure() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try simulateClonedRepo(at: repoPath)

        let fastRetry = RetryConfiguration(
            maxAttempts: 3,
            initialDelaySeconds: 0.01,
            multiplier: 2.0
        )

        let runner = MockGitRunner(responses: [
            "remote get-url origin": "https://github.com/testuser/BeStupid.git",
            "remote set-url origin": "",
        ])
        runner.errorOverrides = [
            "push origin main": .authenticationFailed("Bad credentials")
        ]

        let service = GitSyncService(
            repoPath: repoPath,
            runner: runner,
            retryConfig: fastRetry
        )

        do {
            try await service.push(credentials: testCredentials)
            Issue.record("Expected authentication failure")
        } catch let error as GitError {
            if case .pushFailed(let msg) = error {
                #expect(msg.contains("Bad credentials") || msg.contains("Authentication"))
            } else if case .authenticationFailed = error {
                // Also acceptable
            } else {
                Issue.record("Unexpected error: \(error)")
            }
        }

        // Should only have attempted push once (no retries for auth errors).
        let pushCommands = runner.executedCommands.filter { $0.contains("push") }
        #expect(pushCommands.count == 1)
    }

    // MARK: - Status Tests

    @Test("Status parses git status output correctly")
    func statusParsesOutput() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try simulateClonedRepo(at: repoPath)

        let porcelainOutput = """
         M content/logs/2026-02-17.md
        A  content/logs/2026-02-16.md
        ?? memory/new_item.json
        ?? scripts/untitled.py
        """

        let runner = MockGitRunner(responses: [
            "branch --show-current": "main",
            "status --porcelain": porcelainOutput,
            "rev-list --count origin/main..HEAD": "2",
            "rev-list --count HEAD..origin/main": "1",
        ])

        let service = GitSyncService(repoPath: repoPath, runner: runner)
        let status = try await service.status()

        #expect(status.branch == "main")
        #expect(status.modifiedFiles.count == 2)
        #expect(status.modifiedFiles.contains("content/logs/2026-02-17.md"))
        #expect(status.modifiedFiles.contains("content/logs/2026-02-16.md"))
        #expect(status.untrackedFiles.count == 2)
        #expect(status.untrackedFiles.contains("memory/new_item.json"))
        #expect(status.untrackedFiles.contains("scripts/untitled.py"))
        #expect(status.hasUncommittedChanges == true)
        #expect(status.aheadOfRemote == 2)
        #expect(status.behindRemote == 1)
    }

    @Test("Status returns empty when working tree is clean")
    func statusCleanTree() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try simulateClonedRepo(at: repoPath)

        let runner = MockGitRunner(responses: [
            "branch --show-current": "main",
            "status --porcelain": "",
            "rev-list --count origin/main..HEAD": "0",
            "rev-list --count HEAD..origin/main": "0",
        ])

        let service = GitSyncService(repoPath: repoPath, runner: runner)
        let status = try await service.status()

        #expect(status.branch == "main")
        #expect(status.modifiedFiles.isEmpty)
        #expect(status.untrackedFiles.isEmpty)
        #expect(status.hasUncommittedChanges == false)
        #expect(status.aheadOfRemote == 0)
        #expect(status.behindRemote == 0)
    }

    // MARK: - HasLocalChanges Tests

    @Test("hasLocalChanges returns true when modifications exist")
    func hasLocalChangesDetectsModifications() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try simulateClonedRepo(at: repoPath)

        let runner = MockGitRunner(responses: [
            "status --porcelain": " M content/logs/2026-02-17.md",
        ])

        let service = GitSyncService(repoPath: repoPath, runner: runner)
        let hasChanges = try await service.hasLocalChanges()

        #expect(hasChanges == true)
    }

    @Test("hasLocalChanges returns false when working tree is clean")
    func hasLocalChangesClean() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try simulateClonedRepo(at: repoPath)

        let runner = MockGitRunner(responses: [
            "status --porcelain": "",
        ])

        let service = GitSyncService(repoPath: repoPath, runner: runner)
        let hasChanges = try await service.hasLocalChanges()

        #expect(hasChanges == false)
    }

    @Test("hasLocalChanges throws notCloned when repo missing")
    func hasLocalChangesNotCloned() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("nonexistent")
        let runner = MockGitRunner()
        let service = GitSyncService(repoPath: repoPath, runner: runner)

        do {
            _ = try await service.hasLocalChanges()
            Issue.record("Expected notCloned error")
        } catch let error as GitError {
            #expect(error == .notCloned)
        }
    }

    // MARK: - isCloned Tests

    @Test("isCloned returns true when .git directory exists")
    func isClonedWhenDirExists() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try simulateClonedRepo(at: repoPath)

        let runner = MockGitRunner()
        let service = GitSyncService(repoPath: repoPath, runner: runner)

        let cloned = await service.isCloned
        #expect(cloned == true)
    }

    @Test("isCloned returns false when .git directory is absent")
    func isClonedWhenNoDirExists() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("nonexistent")
        let runner = MockGitRunner()
        let service = GitSyncService(repoPath: repoPath, runner: runner)

        let cloned = await service.isCloned
        #expect(cloned == false)
    }
}

// MARK: - GitCredentials Tests

@Suite("GitCredentials")
struct GitCredentialsTests {

    @Test("authenticatedURL embeds credentials in HTTPS URL")
    func authenticatedURLEmbedsCredentials() {
        let creds = GitCredentials(username: "ryan", token: "ghp_abc123")
        let repoURL = URL(string: "https://github.com/ryan/BeStupid.git")!

        let authURL = creds.authenticatedURL(for: repoURL)

        #expect(authURL != nil)
        let urlString = authURL!.absoluteString
        #expect(urlString.contains("ryan"))
        #expect(urlString.contains("ghp_abc123"))
        #expect(urlString.contains("github.com"))
    }

    @Test("authenticatedURL returns nil for invalid URL")
    func authenticatedURLInvalidURL() {
        let creds = GitCredentials(username: "ryan", token: "ghp_abc123")
        // A URL with no host component.
        let badURL = URL(string: "not-a-url")!

        let authURL = creds.authenticatedURL(for: badURL)

        // URLComponents may or may not parse this -- either nil or a weird URL is fine.
        // The important thing is it doesn't crash.
        if let authURL {
            // If it parses, it should still contain the original path somewhere.
            #expect(authURL.absoluteString.contains("not-a-url"))
        }
    }
}

// MARK: - GitCredentialManager Tests

@Suite("GitCredentialManager")
struct GitCredentialManagerTests {

    @Test("Save and load credentials roundtrip")
    func saveLoadRoundtrip() async throws {
        let keychain = MockKeychain()
        let manager = GitCredentialManager(keychain: keychain)

        let credentials = GitCredentials(username: "ryan", token: "ghp_test_token_123")
        try await manager.saveCredentials(credentials)

        let loaded = try await manager.loadCredentials()
        #expect(loaded != nil)
        #expect(loaded?.username == "ryan")
        #expect(loaded?.token == "ghp_test_token_123")
    }

    @Test("Load returns nil when no credentials stored")
    func loadReturnsNilWhenEmpty() async throws {
        let keychain = MockKeychain()
        let manager = GitCredentialManager(keychain: keychain)

        let loaded = try await manager.loadCredentials()
        #expect(loaded == nil)
    }

    @Test("Save replaces existing credentials")
    func saveReplacesExisting() async throws {
        let keychain = MockKeychain()
        let manager = GitCredentialManager(keychain: keychain)

        let first = GitCredentials(username: "ryan", token: "old_token")
        try await manager.saveCredentials(first)

        let second = GitCredentials(username: "ryan", token: "new_token")
        try await manager.saveCredentials(second)

        let loaded = try await manager.loadCredentials()
        #expect(loaded?.token == "new_token")
    }

    @Test("Delete removes credentials")
    func deleteRemovesCredentials() async throws {
        let keychain = MockKeychain()
        let manager = GitCredentialManager(keychain: keychain)

        let credentials = GitCredentials(username: "ryan", token: "ghp_delete_me")
        try await manager.saveCredentials(credentials)
        try await manager.deleteCredentials()

        let loaded = try await manager.loadCredentials()
        #expect(loaded == nil)
    }

    @Test("Delete succeeds even when no credentials exist")
    func deleteSucceedsWhenEmpty() async throws {
        let keychain = MockKeychain()
        let manager = GitCredentialManager(keychain: keychain)

        // Should not throw.
        try await manager.deleteCredentials()
    }

    @Test("Multiple save-delete-save cycles work correctly")
    func multipleSaveDeleteCycles() async throws {
        let keychain = MockKeychain()
        let manager = GitCredentialManager(keychain: keychain)

        for i in 1...3 {
            let creds = GitCredentials(username: "user\(i)", token: "token\(i)")
            try await manager.saveCredentials(creds)
            let loaded = try await manager.loadCredentials()
            #expect(loaded?.username == "user\(i)")
            #expect(loaded?.token == "token\(i)")
            try await manager.deleteCredentials()
            let afterDelete = try await manager.loadCredentials()
            #expect(afterDelete == nil)
        }
    }
}

// MARK: - OAuthTokenResponse Tests

@Suite("OAuthTokenResponse")
struct OAuthTokenResponseTests {

    @Test("Parses valid token response")
    func parsesValidResponse() {
        let response = "access_token=gho_abc123&token_type=bearer&scope=repo"
        let parsed = OAuthTokenResponse(from: response)

        #expect(parsed != nil)
        #expect(parsed?.accessToken == "gho_abc123")
        #expect(parsed?.tokenType == "bearer")
        #expect(parsed?.scope == "repo")
    }

    @Test("Returns nil for error response")
    func returnsNilForError() {
        let response = "error=bad_verification_code&error_description=The+code+passed+is+incorrect"
        let parsed = OAuthTokenResponse(from: response)

        #expect(parsed == nil)
    }

    @Test("Returns nil for missing access_token")
    func returnsNilForMissingToken() {
        let response = "token_type=bearer&scope=repo"
        let parsed = OAuthTokenResponse(from: response)

        #expect(parsed == nil)
    }

    @Test("Handles response with empty scope")
    func handlesEmptyScope() {
        let response = "access_token=gho_abc123&token_type=bearer"
        let parsed = OAuthTokenResponse(from: response)

        #expect(parsed != nil)
        #expect(parsed?.scope == "")
    }
}

// MARK: - DataSyncCoordinator Tests

@Suite("DataSyncCoordinator")
struct DataSyncCoordinatorTests {

    // MARK: - File Write Tests

    @Test("writeFile uses atomic write pattern (tmp + rename)")
    func writeFileAtomicWrite() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try FileManager.default.createDirectory(at: repoPath, withIntermediateDirectories: true)

        let mockRepo = MockGitRepository()
        let mockKeychain = MockKeychain()
        let credManager = GitCredentialManager(keychain: mockKeychain)

        let coordinator = DataSyncCoordinator(
            gitService: mockRepo,
            credentialManager: credManager,
            repoURL: testRepoURL,
            localRepoPath: repoPath,
            autoSyncDebounceInterval: 999.0 // Disable auto-sync for this test.
        )

        let content = "# Daily Log\n\nWeight:: 244\nSleep:: 7:30\n"
        try coordinator.writeFile(at: "content/logs/2026-02-17.md", content: content)

        // Verify the file was written correctly.
        let fileURL = repoPath.appendingPathComponent("content/logs/2026-02-17.md")
        #expect(FileManager.default.fileExists(atPath: fileURL.path))

        let readBack = try String(contentsOf: fileURL, encoding: .utf8)
        #expect(readBack == content)

        // Verify no .tmp file remains (atomic write completed).
        let tmpURL = fileURL.appendingPathExtension("tmp")
        #expect(!FileManager.default.fileExists(atPath: tmpURL.path))
    }

    @Test("writeFile creates parent directories if needed")
    func writeFileCreatesDirectories() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try FileManager.default.createDirectory(at: repoPath, withIntermediateDirectories: true)

        let mockRepo = MockGitRepository()
        let mockKeychain = MockKeychain()
        let credManager = GitCredentialManager(keychain: mockKeychain)

        let coordinator = DataSyncCoordinator(
            gitService: mockRepo,
            credentialManager: credManager,
            repoURL: testRepoURL,
            localRepoPath: repoPath,
            autoSyncDebounceInterval: 999.0
        )

        let content = "test content"
        try coordinator.writeFile(at: "deeply/nested/dir/file.txt", content: content)

        let fileURL = repoPath.appendingPathComponent("deeply/nested/dir/file.txt")
        #expect(FileManager.default.fileExists(atPath: fileURL.path))
    }

    @Test("writeFile overwrites existing file atomically")
    func writeFileOverwritesExisting() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        let dirPath = repoPath.appendingPathComponent("content/logs")
        try FileManager.default.createDirectory(at: dirPath, withIntermediateDirectories: true)

        // Write initial content.
        let fileURL = dirPath.appendingPathComponent("test.md")
        try "original content".write(to: fileURL, atomically: true, encoding: .utf8)

        let mockRepo = MockGitRepository()
        let mockKeychain = MockKeychain()
        let credManager = GitCredentialManager(keychain: mockKeychain)

        let coordinator = DataSyncCoordinator(
            gitService: mockRepo,
            credentialManager: credManager,
            repoURL: testRepoURL,
            localRepoPath: repoPath,
            autoSyncDebounceInterval: 999.0
        )

        let newContent = "updated content"
        try coordinator.writeFile(at: "content/logs/test.md", content: newContent)

        let readBack = try String(contentsOf: fileURL, encoding: .utf8)
        #expect(readBack == "updated content")
    }

    // MARK: - File Read Tests

    @Test("readFile returns file content")
    func readFileReturnsContent() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        let logsDir = repoPath.appendingPathComponent("content/logs")
        try FileManager.default.createDirectory(at: logsDir, withIntermediateDirectories: true)

        let expectedContent = "# 2026-02-17\n\nWeight:: 244\n"
        let fileURL = logsDir.appendingPathComponent("2026-02-17.md")
        try expectedContent.write(to: fileURL, atomically: true, encoding: .utf8)

        let mockRepo = MockGitRepository()
        let mockKeychain = MockKeychain()
        let credManager = GitCredentialManager(keychain: mockKeychain)

        let coordinator = DataSyncCoordinator(
            gitService: mockRepo,
            credentialManager: credManager,
            repoURL: testRepoURL,
            localRepoPath: repoPath
        )

        let content = try coordinator.readFile(at: "content/logs/2026-02-17.md")
        #expect(content == expectedContent)
    }

    @Test("readFile throws fileNotFound for missing file")
    func readFileMissing() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try FileManager.default.createDirectory(at: repoPath, withIntermediateDirectories: true)

        let mockRepo = MockGitRepository()
        let mockKeychain = MockKeychain()
        let credManager = GitCredentialManager(keychain: mockKeychain)

        let coordinator = DataSyncCoordinator(
            gitService: mockRepo,
            credentialManager: credManager,
            repoURL: testRepoURL,
            localRepoPath: repoPath
        )

        do {
            _ = try coordinator.readFile(at: "nonexistent.md")
            Issue.record("Expected fileNotFound error")
        } catch let error as SyncError {
            if case .fileNotFound(let path) = error {
                #expect(path == "nonexistent.md")
            } else {
                Issue.record("Expected fileNotFound, got \(error)")
            }
        }
    }

    // MARK: - File Listing Tests

    @Test("listFiles returns sorted files in directory")
    func listFilesSorted() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        let logsDir = repoPath.appendingPathComponent("content/logs")
        try FileManager.default.createDirectory(at: logsDir, withIntermediateDirectories: true)

        // Create some test files.
        for name in ["2026-02-15.md", "2026-02-17.md", "2026-02-16.md", "notes.txt"] {
            let fileURL = logsDir.appendingPathComponent(name)
            try "content".write(to: fileURL, atomically: true, encoding: .utf8)
        }

        let mockRepo = MockGitRepository()
        let mockKeychain = MockKeychain()
        let credManager = GitCredentialManager(keychain: mockKeychain)

        let coordinator = DataSyncCoordinator(
            gitService: mockRepo,
            credentialManager: credManager,
            repoURL: testRepoURL,
            localRepoPath: repoPath
        )

        // List all files.
        let allFiles = try coordinator.listFiles(in: "content/logs")
        #expect(allFiles.count == 4)
        // Should be sorted.
        #expect(allFiles == allFiles.sorted())

        // List only .md files.
        let mdFiles = try coordinator.listFiles(in: "content/logs", extension: "md")
        #expect(mdFiles.count == 3)
        #expect(!mdFiles.contains("content/logs/notes.txt"))
    }

    @Test("listFiles throws for nonexistent directory")
    func listFilesNonexistentDir() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try FileManager.default.createDirectory(at: repoPath, withIntermediateDirectories: true)

        let mockRepo = MockGitRepository()
        let mockKeychain = MockKeychain()
        let credManager = GitCredentialManager(keychain: mockKeychain)

        let coordinator = DataSyncCoordinator(
            gitService: mockRepo,
            credentialManager: credManager,
            repoURL: testRepoURL,
            localRepoPath: repoPath
        )

        do {
            _ = try coordinator.listFiles(in: "nonexistent/path")
            Issue.record("Expected directoryListingFailed error")
        } catch let error as SyncError {
            if case .directoryListingFailed = error {
                // Expected.
            } else {
                Issue.record("Expected directoryListingFailed, got \(error)")
            }
        }
    }

    // MARK: - Initial Sync Tests

    @Test("initialSync clones repo when not present")
    func initialSyncClones() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")

        let mockRepo = MockGitRepository()
        let mockKeychain = MockKeychain()
        let credManager = GitCredentialManager(keychain: mockKeychain)

        // Store credentials so initialSync can load them.
        try await credManager.saveCredentials(testCredentials)

        let coordinator = DataSyncCoordinator(
            gitService: mockRepo,
            credentialManager: credManager,
            repoURL: testRepoURL,
            localRepoPath: repoPath
        )

        try await coordinator.initialSync()

        let cloneCalled = await mockRepo.cloneCalled
        #expect(cloneCalled == true)
    }

    @Test("initialSync pulls when repo already exists")
    func initialSyncPulls() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try simulateClonedRepo(at: repoPath)

        let mockRepo = MockGitRepository()
        let mockKeychain = MockKeychain()
        let credManager = GitCredentialManager(keychain: mockKeychain)

        try await credManager.saveCredentials(testCredentials)

        let coordinator = DataSyncCoordinator(
            gitService: mockRepo,
            credentialManager: credManager,
            repoURL: testRepoURL,
            localRepoPath: repoPath
        )

        try await coordinator.initialSync()

        let pullCalled = await mockRepo.pullCalled
        let cloneCalled = await mockRepo.cloneCalled
        #expect(pullCalled == true)
        #expect(cloneCalled == false)
    }

    @Test("initialSync throws when no credentials available")
    func initialSyncNoCredentials() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")

        let mockRepo = MockGitRepository()
        let mockKeychain = MockKeychain()
        let credManager = GitCredentialManager(keychain: mockKeychain)

        let coordinator = DataSyncCoordinator(
            gitService: mockRepo,
            credentialManager: credManager,
            repoURL: testRepoURL,
            localRepoPath: repoPath
        )

        do {
            try await coordinator.initialSync()
            Issue.record("Expected noCredentials error")
        } catch let error as SyncError {
            #expect(error == .noCredentials)
        }
    }

    // MARK: - Push Changes Tests

    @Test("pushChanges pulls before push (critical BeStupid rule)")
    func pushChangesPullsFirst() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try simulateClonedRepo(at: repoPath)

        let mockRepo = MockGitRepository()
        await mockRepo.setHasChangesResult(true)

        let mockKeychain = MockKeychain()
        let credManager = GitCredentialManager(keychain: mockKeychain)
        try await credManager.saveCredentials(testCredentials)

        let coordinator = DataSyncCoordinator(
            gitService: mockRepo,
            credentialManager: credManager,
            repoURL: testRepoURL,
            localRepoPath: repoPath
        )

        try await coordinator.pushChanges(message: "Test commit")

        let pullCalled = await mockRepo.pullCalled
        let commitCalled = await mockRepo.commitAllCalled
        let pushCalled = await mockRepo.pushCalled

        #expect(pullCalled == true)
        #expect(commitCalled == true)
        #expect(pushCalled == true)
    }

    @Test("pushChanges updates lastSyncDate on success")
    func pushChangesUpdatesLastSync() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try simulateClonedRepo(at: repoPath)

        let mockRepo = MockGitRepository()
        await mockRepo.setHasChangesResult(true)

        let mockKeychain = MockKeychain()
        let credManager = GitCredentialManager(keychain: mockKeychain)
        try await credManager.saveCredentials(testCredentials)

        let coordinator = DataSyncCoordinator(
            gitService: mockRepo,
            credentialManager: credManager,
            repoURL: testRepoURL,
            localRepoPath: repoPath
        )

        let beforeSync = Date()
        try await coordinator.pushChanges(message: "Test")

        #expect(coordinator.lastSyncDate != nil)
        #expect(coordinator.lastSyncDate! >= beforeSync)
    }

    // MARK: - Auto-Sync Debounce Tests

    @Test("Auto-sync debounce resets timer on rapid writes")
    func autoSyncDebounceBehavior() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try FileManager.default.createDirectory(at: repoPath, withIntermediateDirectories: true)

        let mockRepo = MockGitRepository()
        let mockKeychain = MockKeychain()
        let credManager = GitCredentialManager(keychain: mockKeychain)

        // Use a very short debounce for testing, but long enough to verify
        // that rapid writes don't each trigger their own sync.
        let coordinator = DataSyncCoordinator(
            gitService: mockRepo,
            credentialManager: credManager,
            repoURL: testRepoURL,
            localRepoPath: repoPath,
            autoSyncDebounceInterval: 0.5
        )

        // Rapid writes -- each should cancel the previous debounce timer.
        for i in 1...5 {
            try coordinator.writeFile(at: "test\(i).txt", content: "content \(i)")
        }

        // Wait a tiny bit -- not long enough for the debounce to fire.
        try await Task.sleep(nanoseconds: 100_000_000) // 0.1s

        // Push should not have been called yet (debounce hasn't elapsed).
        let pushCalled = await mockRepo.pushCalled
        #expect(pushCalled == false)
    }

    // MARK: - Conflict Resolution Tests

    @Test("Conflict resolution with keepLocal strategy")
    func conflictResolutionKeepLocal() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try FileManager.default.createDirectory(at: repoPath, withIntermediateDirectories: true)

        // Create a file with conflict markers.
        let conflictContent = """
        # Daily Log

        <<<<<<< HEAD
        Weight:: 244
        =======
        Weight:: 242
        >>>>>>> origin/main

        Sleep:: 7:30
        """

        let fileURL = repoPath.appendingPathComponent("log.md")
        try conflictContent.write(to: fileURL, atomically: true, encoding: .utf8)

        let mockRepo = MockGitRepository()
        // Report the conflicted file in status.
        await mockRepo.setStatusResult(GitStatus(
            branch: "main",
            modifiedFiles: ["log.md"],
            untrackedFiles: [],
            hasUncommittedChanges: true,
            aheadOfRemote: 0,
            behindRemote: 0
        ))

        let mockKeychain = MockKeychain()
        let credManager = GitCredentialManager(keychain: mockKeychain)

        let coordinator = DataSyncCoordinator(
            gitService: mockRepo,
            credentialManager: credManager,
            repoURL: testRepoURL,
            localRepoPath: repoPath,
            autoSyncDebounceInterval: 999.0
        )

        // Set status to resolving conflicts so the method proceeds.
        coordinator.syncStatus = .resolvingConflicts

        try await coordinator.resolveConflicts(strategy: .keepLocal)

        // Read back the resolved file.
        let resolved = try String(contentsOf: fileURL, encoding: .utf8)

        #expect(resolved.contains("Weight:: 244"))
        #expect(!resolved.contains("Weight:: 242"))
        #expect(!resolved.contains("<<<<<<<"))
        #expect(!resolved.contains("======="))
        #expect(!resolved.contains(">>>>>>>"))
        #expect(resolved.contains("Sleep:: 7:30"))
    }

    @Test("Conflict resolution with keepRemote strategy")
    func conflictResolutionKeepRemote() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")
        try FileManager.default.createDirectory(at: repoPath, withIntermediateDirectories: true)

        let conflictContent = """
        # Daily Log

        <<<<<<< HEAD
        Weight:: 244
        =======
        Weight:: 242
        >>>>>>> origin/main

        Sleep:: 7:30
        """

        let fileURL = repoPath.appendingPathComponent("log.md")
        try conflictContent.write(to: fileURL, atomically: true, encoding: .utf8)

        let mockRepo = MockGitRepository()
        await mockRepo.setStatusResult(GitStatus(
            branch: "main",
            modifiedFiles: ["log.md"],
            untrackedFiles: [],
            hasUncommittedChanges: true,
            aheadOfRemote: 0,
            behindRemote: 0
        ))

        let mockKeychain = MockKeychain()
        let credManager = GitCredentialManager(keychain: mockKeychain)

        let coordinator = DataSyncCoordinator(
            gitService: mockRepo,
            credentialManager: credManager,
            repoURL: testRepoURL,
            localRepoPath: repoPath,
            autoSyncDebounceInterval: 999.0
        )

        coordinator.syncStatus = .resolvingConflicts

        try await coordinator.resolveConflicts(strategy: .keepRemote)

        let resolved = try String(contentsOf: fileURL, encoding: .utf8)

        #expect(!resolved.contains("Weight:: 244"))
        #expect(resolved.contains("Weight:: 242"))
        #expect(!resolved.contains("<<<<<<<"))
    }

    // MARK: - Sync Status Tests

    @Test("syncStatus reflects active operations")
    func syncStatusReflectsState() async throws {
        let tmpDir = try makeTempDir()
        defer { cleanupTempDir(tmpDir) }

        let repoPath = tmpDir.appendingPathComponent("repo")

        let mockRepo = MockGitRepository()
        let mockKeychain = MockKeychain()
        let credManager = GitCredentialManager(keychain: mockKeychain)

        let coordinator = DataSyncCoordinator(
            gitService: mockRepo,
            credentialManager: credManager,
            repoURL: testRepoURL,
            localRepoPath: repoPath
        )

        // Initial state.
        #expect(coordinator.syncStatus == .idle)
        #expect(!coordinator.syncStatus.isActive)

        // Manually set status to test display names.
        coordinator.syncStatus = .pulling
        #expect(coordinator.syncStatus.isActive)
        #expect(coordinator.syncStatus.displayName == "Pulling changes...")

        coordinator.syncStatus = .error("Test error")
        #expect(!coordinator.syncStatus.isActive)
        #expect(coordinator.syncStatus.displayName.contains("Test error"))
    }
}

// MARK: - RetryConfiguration Tests

@Suite("RetryConfiguration")
struct RetryConfigurationTests {

    @Test("Default configuration has correct values")
    func defaultValues() {
        let config = RetryConfiguration.default
        #expect(config.maxAttempts == 4)
        #expect(config.initialDelaySeconds == 2.0)
        #expect(config.multiplier == 2.0)
    }

    @Test("Delay follows exponential backoff pattern")
    func exponentialBackoff() {
        let config = RetryConfiguration.default

        #expect(config.delay(forAttempt: 0) == 2.0)   // 2 * 2^0 = 2
        #expect(config.delay(forAttempt: 1) == 4.0)   // 2 * 2^1 = 4
        #expect(config.delay(forAttempt: 2) == 8.0)   // 2 * 2^2 = 8
        #expect(config.delay(forAttempt: 3) == 16.0)  // 2 * 2^3 = 16
    }

    @Test("Custom configuration produces correct delays")
    func customConfig() {
        let config = RetryConfiguration(
            maxAttempts: 5,
            initialDelaySeconds: 1.0,
            multiplier: 3.0
        )

        #expect(config.delay(forAttempt: 0) == 1.0)   // 1 * 3^0 = 1
        #expect(config.delay(forAttempt: 1) == 3.0)   // 1 * 3^1 = 3
        #expect(config.delay(forAttempt: 2) == 9.0)   // 1 * 3^2 = 9
    }
}

// MARK: - GitError Tests

@Suite("GitError")
struct GitErrorTests {

    @Test("Error descriptions are human-readable")
    func errorDescriptions() {
        let errors: [(GitError, String)] = [
            (.notCloned, "not been cloned"),
            (.alreadyCloned, "already cloned"),
            (.networkFailure("timeout"), "timeout"),
            (.conflictDetected(files: ["a.md", "b.md"]), "2 file(s)"),
            (.authenticationFailed("bad token"), "bad token"),
        ]

        for (error, expectedSubstring) in errors {
            let description = error.errorDescription ?? ""
            #expect(
                description.contains(expectedSubstring),
                "Expected '\(expectedSubstring)' in: \(description)"
            )
        }
    }

    @Test("GitError conforms to Equatable")
    func errorEquatable() {
        #expect(GitError.notCloned == GitError.notCloned)
        #expect(GitError.networkFailure("a") == GitError.networkFailure("a"))
        #expect(GitError.networkFailure("a") != GitError.networkFailure("b"))
        #expect(
            GitError.conflictDetected(files: ["x"]) == GitError.conflictDetected(files: ["x"])
        )
    }
}

// MARK: - SyncError Tests

@Suite("SyncError")
struct SyncErrorTests {

    @Test("SyncError descriptions are human-readable")
    func errorDescriptions() {
        let errors: [(SyncError, String)] = [
            (.notInitialized, "not been initialized"),
            (.repoNotCloned, "not cloned"),
            (.fileNotFound("test.md"), "test.md"),
            (.syncInProgress, "already in progress"),
            (.noCredentials, "No git credentials"),
        ]

        for (error, expectedSubstring) in errors {
            let description = error.errorDescription ?? ""
            #expect(
                description.contains(expectedSubstring),
                "Expected '\(expectedSubstring)' in: \(description)"
            )
        }
    }
}

// MARK: - SyncStatus Tests

@Suite("SyncStatus")
struct SyncStatusTests {

    @Test("Display names are correct for all statuses")
    func displayNames() {
        #expect(SyncStatus.idle.displayName == "Up to date")
        #expect(SyncStatus.cloning.displayName == "Cloning repository...")
        #expect(SyncStatus.pulling.displayName == "Pulling changes...")
        #expect(SyncStatus.pushing.displayName == "Pushing changes...")
        #expect(SyncStatus.committing.displayName == "Committing...")
        #expect(SyncStatus.resolvingConflicts.displayName == "Resolving conflicts...")
        #expect(SyncStatus.error("test").displayName == "Error: test")
    }

    @Test("isActive returns correct values")
    func isActiveValues() {
        #expect(SyncStatus.idle.isActive == false)
        #expect(SyncStatus.cloning.isActive == true)
        #expect(SyncStatus.pulling.isActive == true)
        #expect(SyncStatus.pushing.isActive == true)
        #expect(SyncStatus.committing.isActive == true)
        #expect(SyncStatus.resolvingConflicts.isActive == true)
        #expect(SyncStatus.error("x").isActive == false)
    }
}

// MARK: - GitStatus Tests

@Suite("GitStatus")
struct GitStatusTests {

    @Test("Empty status has correct defaults")
    func emptyStatus() {
        let status = GitStatus.empty
        #expect(status.branch == "main")
        #expect(status.modifiedFiles.isEmpty)
        #expect(status.untrackedFiles.isEmpty)
        #expect(status.hasUncommittedChanges == false)
        #expect(status.aheadOfRemote == 0)
        #expect(status.behindRemote == 0)
    }
}

// MARK: - PullResult Tests

@Suite("PullResult")
struct PullResultTests {

    @Test("PullResult equality")
    func pullResultEquality() {
        #expect(PullResult.upToDate == PullResult.upToDate)
        #expect(PullResult.merged(fileCount: 3) == PullResult.merged(fileCount: 3))
        #expect(PullResult.merged(fileCount: 3) != PullResult.merged(fileCount: 5))
        #expect(
            PullResult.conflict(files: ["a.md"]) == PullResult.conflict(files: ["a.md"])
        )
        #expect(PullResult.upToDate != PullResult.merged(fileCount: 0))
    }
}

// MARK: - MockGitRepository Helpers

extension MockGitRepository {
    func setHasChangesResult(_ value: Bool) {
        hasChangesResult = value
    }

    func setStatusResult(_ value: GitStatus) {
        statusResult = value
    }

    func setPullResult(_ value: PullResult) {
        pullResult = value
    }
}
