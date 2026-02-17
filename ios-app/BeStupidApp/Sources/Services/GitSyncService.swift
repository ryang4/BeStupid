import Foundation

// MARK: - Error Types

enum GitError: Error, Sendable, Equatable, LocalizedError {
    case notCloned
    case alreadyCloned
    case cloneFailed(String)
    case pullFailed(String)
    case commitFailed(String)
    case pushFailed(String)
    case statusFailed(String)
    case networkFailure(String)
    case conflictDetected(files: [String])
    case invalidRepository(String)
    case commandFailed(command: String, output: String)
    case directoryNotFound(String)
    case authenticationFailed(String)

    var errorDescription: String? {
        switch self {
        case .notCloned:
            return "Repository has not been cloned yet."
        case .alreadyCloned:
            return "Repository is already cloned at the specified path."
        case .cloneFailed(let detail):
            return "Clone failed: \(detail)"
        case .pullFailed(let detail):
            return "Pull failed: \(detail)"
        case .commitFailed(let detail):
            return "Commit failed: \(detail)"
        case .pushFailed(let detail):
            return "Push failed: \(detail)"
        case .statusFailed(let detail):
            return "Status failed: \(detail)"
        case .networkFailure(let detail):
            return "Network failure: \(detail)"
        case .conflictDetected(let files):
            return "Merge conflict detected in \(files.count) file(s): \(files.joined(separator: ", "))"
        case .invalidRepository(let detail):
            return "Invalid repository: \(detail)"
        case .commandFailed(let command, let output):
            return "Command '\(command)' failed: \(output)"
        case .directoryNotFound(let path):
            return "Directory not found: \(path)"
        case .authenticationFailed(let detail):
            return "Authentication failed: \(detail)"
        }
    }
}

// MARK: - Git Data Types

struct GitCredentials: Sendable, Equatable {
    let username: String
    let token: String

    /// Builds the authenticated HTTPS URL for a given repository URL.
    /// Embeds the username and token directly into the URL for command-line git auth.
    func authenticatedURL(for repoURL: URL) -> URL? {
        guard var components = URLComponents(url: repoURL, resolvingAgainstBaseURL: false) else {
            return nil
        }
        components.user = username
        components.password = token
        return components.url
    }
}

enum PullResult: Sendable, Equatable {
    case upToDate
    case merged(fileCount: Int)
    case conflict(files: [String])
}

struct GitStatus: Sendable, Equatable {
    let branch: String
    let modifiedFiles: [String]
    let untrackedFiles: [String]
    let hasUncommittedChanges: Bool
    let aheadOfRemote: Int
    let behindRemote: Int

    static let empty = GitStatus(
        branch: "main",
        modifiedFiles: [],
        untrackedFiles: [],
        hasUncommittedChanges: false,
        aheadOfRemote: 0,
        behindRemote: 0
    )
}

// MARK: - Git Operations Protocol (SOLID: Dependency Inversion)

protocol GitRepository: Sendable {
    func clone(from url: URL, to localPath: URL, credentials: GitCredentials) async throws
    func pull(credentials: GitCredentials) async throws -> PullResult
    func commitAll(message: String) async throws
    func push(credentials: GitCredentials) async throws
    func status() async throws -> GitStatus
    func hasLocalChanges() async throws -> Bool
}

// MARK: - Git Command Runner Protocol (SOLID: Interface Segregation)

protocol GitCommandRunner: Sendable {
    /// Runs a git command with the given arguments in the specified directory.
    /// Returns the trimmed stdout output.
    func run(_ args: [String], in directory: URL) async throws -> String
}

// MARK: - ProcessGitRunner (macOS development/testing)

/// Uses Foundation.Process to invoke the system `git` binary.
/// Suitable for macOS development and CI testing only -- not available on iOS.
final class ProcessGitRunner: GitCommandRunner, Sendable {
    func run(_ args: [String], in directory: URL) async throws -> String {
        #if os(macOS)
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/git")
        process.arguments = args
        process.currentDirectoryURL = directory

        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        try process.run()
        process.waitUntilExit()

        let stdoutData = stdoutPipe.fileHandleForReading.readDataToEndOfFile()
        let stderrData = stderrPipe.fileHandleForReading.readDataToEndOfFile()
        let stdout = String(data: stdoutData, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let stderr = String(data: stderrData, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

        guard process.terminationStatus == 0 else {
            let combined = stderr.isEmpty ? stdout : stderr
            let commandStr = "git \(args.joined(separator: " "))"

            if combined.contains("Could not resolve host")
                || combined.contains("unable to access")
                || combined.contains("Connection refused")
                || combined.contains("Network is unreachable")
            {
                throw GitError.networkFailure(combined)
            }

            if combined.contains("Authentication failed")
                || combined.contains("Invalid username or password")
                || combined.contains("403")
            {
                throw GitError.authenticationFailed(combined)
            }

            throw GitError.commandFailed(command: commandStr, output: combined)
        }

        return stdout
        #else
        let commandStr = "git \(args.joined(separator: " "))"
        throw GitError.commandFailed(
            command: commandStr,
            output: "ProcessGitRunner is only available on macOS. Use LibGit2GitRunner on iOS."
        )
        #endif
    }
}

// MARK: - LibGit2GitRunner (iOS production placeholder)

/// Placeholder for an iOS-native git implementation using SwiftGitX/libgit2.
/// Each `run` call maps to the equivalent libgit2 C function:
///
/// - `clone` -> `git_clone()`
/// - `fetch` -> `git_remote_fetch()`
/// - `merge` -> `git_merge()` / `git_rebase()`
/// - `add` -> `git_index_add_all()` / `git_index_write()`
/// - `commit` -> `git_commit_create()`
/// - `push` -> `git_remote_push()`
/// - `status` -> `git_status_list_new()`
/// - `rev-list` -> `git_revwalk_new()` / `git_revwalk_push()` / `git_revwalk_next()`
///
/// When integrating SwiftGitX, replace the body of each case with the corresponding
/// SwiftGitX API call. The `args` array follows standard git CLI argument conventions
/// so the mapping is straightforward.
final class LibGit2GitRunner: GitCommandRunner, Sendable {
    func run(_ args: [String], in directory: URL) async throws -> String {
        let commandStr = "git \(args.joined(separator: " "))"
        throw GitError.commandFailed(
            command: commandStr,
            output: "LibGit2GitRunner requires SwiftGitX/libgit2 integration. "
                + "Replace this implementation with native libgit2 calls for iOS."
        )
    }
}

// MARK: - Retry Configuration

struct RetryConfiguration: Sendable {
    let maxAttempts: Int
    let initialDelaySeconds: Double
    let multiplier: Double

    static let `default` = RetryConfiguration(
        maxAttempts: 4,
        initialDelaySeconds: 2.0,
        multiplier: 2.0
    )

    /// Returns the delay in seconds for a given attempt number (0-indexed).
    func delay(forAttempt attempt: Int) -> Double {
        initialDelaySeconds * pow(multiplier, Double(attempt))
    }
}

// MARK: - GitSyncService Actor

actor GitSyncService: GitRepository {
    private let repoPath: URL
    private let runner: GitCommandRunner
    private let fileManager: FileManager
    private let retryConfig: RetryConfiguration

    /// Whether the repository has been cloned (a `.git` directory exists at repoPath).
    var isCloned: Bool {
        fileManager.fileExists(atPath: repoPath.appendingPathComponent(".git").path)
    }

    init(
        repoPath: URL,
        runner: GitCommandRunner,
        fileManager: FileManager = .default,
        retryConfig: RetryConfiguration = .default
    ) {
        self.repoPath = repoPath
        self.runner = runner
        self.fileManager = fileManager
        self.retryConfig = retryConfig
    }

    // MARK: - Clone

    func clone(from url: URL, to localPath: URL, credentials: GitCredentials) async throws {
        let targetGitDir = localPath.appendingPathComponent(".git")
        if fileManager.fileExists(atPath: targetGitDir.path) {
            throw GitError.alreadyCloned
        }

        // Create the parent directory if it does not exist.
        let parentDir = localPath.deletingLastPathComponent()
        if !fileManager.fileExists(atPath: parentDir.path) {
            try fileManager.createDirectory(at: parentDir, withIntermediateDirectories: true)
        }

        guard let authURL = credentials.authenticatedURL(for: url) else {
            throw GitError.cloneFailed("Could not build authenticated URL for \(url.absoluteString)")
        }

        do {
            _ = try await runner.run(
                ["clone", authURL.absoluteString, localPath.path],
                in: parentDir
            )
        } catch let error as GitError {
            switch error {
            case .networkFailure:
                throw error
            case .authenticationFailed:
                throw error
            default:
                throw GitError.cloneFailed(error.localizedDescription)
            }
        }
    }

    // MARK: - Pull

    func pull(credentials: GitCredentials) async throws -> PullResult {
        guard isCloned else { throw GitError.notCloned }

        // Configure the remote URL with credentials for the fetch.
        let currentRemote = try await runner.run(["remote", "get-url", "origin"], in: repoPath)
        guard let remoteURL = URL(string: currentRemote),
              let authURL = credentials.authenticatedURL(for: remoteURL) else {
            throw GitError.pullFailed("Could not parse remote URL: \(currentRemote)")
        }

        // Temporarily set authenticated URL, then restore the clean URL after.
        try await runner.run(["remote", "set-url", "origin", authURL.absoluteString], in: repoPath)

        defer {
            // Fire-and-forget: restore clean remote URL to avoid storing credentials on disk.
            Task { [runner, repoPath, currentRemote] in
                _ = try? await runner.run(
                    ["remote", "set-url", "origin", currentRemote],
                    in: repoPath
                )
            }
        }

        return try await withNetworkRetry { [runner, repoPath] in
            // Fetch the latest remote state.
            _ = try await runner.run(["fetch", "origin"], in: repoPath)

            // Check if there are incoming changes.
            let behindCount = try await runner.run(
                ["rev-list", "--count", "HEAD..origin/main"],
                in: repoPath
            )

            let behind = Int(behindCount.trimmingCharacters(in: .whitespacesAndNewlines)) ?? 0
            if behind == 0 {
                return .upToDate
            }

            // Attempt a rebase for clean history.
            do {
                _ = try await runner.run(["rebase", "origin/main"], in: repoPath)
            } catch {
                // Check for conflicts.
                let statusOutput = try await runner.run(["status", "--porcelain"], in: repoPath)
                let conflictFiles = Self.parseConflictFiles(from: statusOutput)

                if !conflictFiles.isEmpty {
                    // Abort the rebase so the working tree is usable.
                    _ = try? await runner.run(["rebase", "--abort"], in: repoPath)
                    return .conflict(files: conflictFiles)
                }

                // If no conflict markers but rebase still failed, abort and report.
                _ = try? await runner.run(["rebase", "--abort"], in: repoPath)
                throw GitError.pullFailed("Rebase failed: \(error.localizedDescription)")
            }

            return .merged(fileCount: behind)
        }
    }

    // MARK: - Commit All

    func commitAll(message: String) async throws {
        guard isCloned else { throw GitError.notCloned }

        // Stage all changes (new, modified, deleted).
        _ = try await runner.run(["add", "--all"], in: repoPath)

        // Check if there is anything staged.
        let diffOutput = try await runner.run(["diff", "--cached", "--name-only"], in: repoPath)
        if diffOutput.isEmpty {
            throw GitError.commitFailed("No changes staged for commit.")
        }

        do {
            _ = try await runner.run(["commit", "-m", message], in: repoPath)
        } catch let error as GitError {
            throw GitError.commitFailed(error.localizedDescription)
        }
    }

    // MARK: - Push

    func push(credentials: GitCredentials) async throws {
        guard isCloned else { throw GitError.notCloned }

        let currentRemote = try await runner.run(["remote", "get-url", "origin"], in: repoPath)
        guard let remoteURL = URL(string: currentRemote),
              let authURL = credentials.authenticatedURL(for: remoteURL) else {
            throw GitError.pushFailed("Could not parse remote URL: \(currentRemote)")
        }

        // Temporarily set authenticated URL.
        try await runner.run(["remote", "set-url", "origin", authURL.absoluteString], in: repoPath)

        defer {
            Task { [runner, repoPath, currentRemote] in
                _ = try? await runner.run(
                    ["remote", "set-url", "origin", currentRemote],
                    in: repoPath
                )
            }
        }

        try await withNetworkRetry { [runner, repoPath] in
            do {
                _ = try await runner.run(["push", "origin", "main"], in: repoPath)
            } catch let error as GitError {
                switch error {
                case .networkFailure:
                    throw error
                case .authenticationFailed:
                    throw error
                default:
                    throw GitError.pushFailed(error.localizedDescription)
                }
            }
        }
    }

    // MARK: - Status

    func status() async throws -> GitStatus {
        guard isCloned else { throw GitError.notCloned }

        let branchOutput = try await runner.run(["branch", "--show-current"], in: repoPath)
        let branch = branchOutput.isEmpty ? "main" : branchOutput

        let porcelainOutput = try await runner.run(["status", "--porcelain"], in: repoPath)

        var modifiedFiles: [String] = []
        var untrackedFiles: [String] = []

        for line in porcelainOutput.split(separator: "\n") {
            let lineStr = String(line)
            guard lineStr.count >= 3 else { continue }

            let statusCode = String(lineStr.prefix(2))
            let filePath = String(lineStr.dropFirst(3))

            if statusCode == "??" {
                untrackedFiles.append(filePath)
            } else {
                modifiedFiles.append(filePath)
            }
        }

        // Count ahead/behind. If the remote tracking branch doesn't exist, default to 0.
        var aheadCount = 0
        var behindCount = 0

        let aheadOutput = try? await runner.run(
            ["rev-list", "--count", "origin/\(branch)..HEAD"],
            in: repoPath
        )
        if let aheadOutput {
            aheadCount = Int(aheadOutput.trimmingCharacters(in: .whitespacesAndNewlines)) ?? 0
        }

        let behindOutput = try? await runner.run(
            ["rev-list", "--count", "HEAD..origin/\(branch)"],
            in: repoPath
        )
        if let behindOutput {
            behindCount = Int(behindOutput.trimmingCharacters(in: .whitespacesAndNewlines)) ?? 0
        }

        return GitStatus(
            branch: branch,
            modifiedFiles: modifiedFiles,
            untrackedFiles: untrackedFiles,
            hasUncommittedChanges: !modifiedFiles.isEmpty || !untrackedFiles.isEmpty,
            aheadOfRemote: aheadCount,
            behindRemote: behindCount
        )
    }

    // MARK: - Has Local Changes

    func hasLocalChanges() async throws -> Bool {
        guard isCloned else { throw GitError.notCloned }

        let porcelainOutput = try await runner.run(["status", "--porcelain"], in: repoPath)
        return !porcelainOutput.isEmpty
    }

    // MARK: - Private Helpers

    /// Parses `git status --porcelain` output to extract files with merge conflicts.
    /// Conflict markers in porcelain format: UU, AA, DD, AU, UA, DU, UD.
    private static func parseConflictFiles(from statusOutput: String) -> [String] {
        var conflictFiles: [String] = []
        let conflictPrefixes: Set<String> = ["UU", "AA", "DD", "AU", "UA", "DU", "UD"]

        for line in statusOutput.split(separator: "\n") {
            let lineStr = String(line)
            guard lineStr.count >= 3 else { continue }

            let statusCode = String(lineStr.prefix(2))
            if conflictPrefixes.contains(statusCode) {
                let filePath = String(lineStr.dropFirst(3))
                conflictFiles.append(filePath)
            }
        }

        return conflictFiles
    }

    /// Retries the given async operation with exponential backoff on network failures.
    /// Uses the actor's `retryConfig` for timing parameters.
    private func withNetworkRetry<T: Sendable>(
        _ operation: @escaping @Sendable () async throws -> T
    ) async throws -> T {
        var lastError: Error?

        for attempt in 0..<retryConfig.maxAttempts {
            do {
                return try await operation()
            } catch let error as GitError {
                switch error {
                case .networkFailure:
                    lastError = error
                    if attempt < retryConfig.maxAttempts - 1 {
                        let delay = retryConfig.delay(forAttempt: attempt)
                        try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                    }
                default:
                    throw error
                }
            }
        }

        throw lastError ?? GitError.networkFailure("All \(retryConfig.maxAttempts) retry attempts exhausted.")
    }
}
