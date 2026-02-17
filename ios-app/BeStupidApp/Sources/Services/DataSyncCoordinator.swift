import Foundation
import Observation
import Network

// MARK: - Sync Error Types

enum SyncError: Error, Sendable, Equatable, LocalizedError {
    case notInitialized
    case repoNotCloned
    case fileNotFound(String)
    case fileWriteFailed(String)
    case fileReadFailed(String)
    case directoryListingFailed(String)
    case syncInProgress
    case noCredentials
    case conflictResolutionFailed(String)

    var errorDescription: String? {
        switch self {
        case .notInitialized:
            return "DataSyncCoordinator has not been initialized. Call initialSync() first."
        case .repoNotCloned:
            return "Local repository is not cloned."
        case .fileNotFound(let path):
            return "File not found: \(path)"
        case .fileWriteFailed(let detail):
            return "File write failed: \(detail)"
        case .fileReadFailed(let detail):
            return "File read failed: \(detail)"
        case .directoryListingFailed(let detail):
            return "Directory listing failed: \(detail)"
        case .syncInProgress:
            return "A sync operation is already in progress."
        case .noCredentials:
            return "No git credentials available. Please authenticate first."
        case .conflictResolutionFailed(let detail):
            return "Conflict resolution failed: \(detail)"
        }
    }
}

// MARK: - Sync Status

enum SyncStatus: Sendable, Equatable {
    case idle
    case cloning
    case pulling
    case pushing
    case committing
    case resolvingConflicts
    case error(String)

    var displayName: String {
        switch self {
        case .idle: return "Up to date"
        case .cloning: return "Cloning repository..."
        case .pulling: return "Pulling changes..."
        case .pushing: return "Pushing changes..."
        case .committing: return "Committing..."
        case .resolvingConflicts: return "Resolving conflicts..."
        case .error(let message): return "Error: \(message)"
        }
    }

    var isActive: Bool {
        switch self {
        case .idle, .error: return false
        default: return true
        }
    }
}

// MARK: - Conflict Resolution Strategy

enum ConflictStrategy: Sendable {
    /// The phone's local data wins on all conflicts.
    case keepLocal
    /// The remote (bot's) data wins on all conflicts.
    case keepRemote
    /// Merge at the section level: workout data from phone, briefings from bot.
    case perSection
}

// MARK: - DataSyncCoordinator

@Observable
final class DataSyncCoordinator: @unchecked Sendable {
    // MARK: - Dependencies

    private let gitService: any GitRepository
    private let credentialManager: GitCredentialManager
    private let repoURL: URL
    private let localRepoPath: URL
    private let fileManager: FileManager

    // MARK: - Observable State

    var syncStatus: SyncStatus = .idle
    var lastSyncDate: Date?
    var pendingChanges: Int = 0
    var isOnline: Bool = true

    // MARK: - Internal State (thread-safe via lock)

    private let lock = NSLock()
    private var autoSyncTask: Task<Void, Never>?
    private var networkMonitor: NWPathMonitor?
    private var monitorQueue: DispatchQueue?
    private var offlineChangesPending: Bool = false

    /// Debounce interval for auto-sync after writes.
    private let autoSyncDebounceInterval: TimeInterval

    // MARK: - Init

    init(
        gitService: any GitRepository,
        credentialManager: GitCredentialManager,
        repoURL: URL,
        localRepoPath: URL,
        fileManager: FileManager = .default,
        autoSyncDebounceInterval: TimeInterval = 30.0
    ) {
        self.gitService = gitService
        self.credentialManager = credentialManager
        self.repoURL = repoURL
        self.localRepoPath = localRepoPath
        self.fileManager = fileManager
        self.autoSyncDebounceInterval = autoSyncDebounceInterval
    }

    deinit {
        autoSyncTask?.cancel()
        networkMonitor?.cancel()
    }

    // MARK: - Public API

    /// Initial setup: clones the repo if not present, otherwise pulls latest changes.
    /// Also starts network monitoring for offline/online transitions.
    func initialSync() async throws {
        guard !syncStatus.isActive else {
            throw SyncError.syncInProgress
        }

        let credentials = try await loadRequiredCredentials()

        startNetworkMonitoring()

        let gitDirPath = localRepoPath.appendingPathComponent(".git").path
        if fileManager.fileExists(atPath: gitDirPath) {
            // Repo exists, pull latest.
            try await pull()
        } else {
            // First time: clone the repo.
            syncStatus = .cloning
            do {
                try await gitService.clone(from: repoURL, to: localRepoPath, credentials: credentials)
                lastSyncDate = Date()
                syncStatus = .idle
            } catch {
                syncStatus = .error(error.localizedDescription)
                throw error
            }
        }

        await updatePendingChangesCount()
    }

    /// Pulls the latest changes from the remote repository.
    func pull() async throws {
        guard !syncStatus.isActive else {
            throw SyncError.syncInProgress
        }

        let credentials = try await loadRequiredCredentials()

        syncStatus = .pulling
        do {
            let result = try await gitService.pull(credentials: credentials)
            lastSyncDate = Date()

            switch result {
            case .upToDate:
                syncStatus = .idle
            case .merged:
                syncStatus = .idle
            case .conflict(let files):
                syncStatus = .resolvingConflicts
                throw GitError.conflictDetected(files: files)
            }
        } catch let error as GitError {
            if case .conflictDetected = error {
                syncStatus = .resolvingConflicts
            } else {
                syncStatus = .error(error.localizedDescription)
            }
            throw error
        } catch {
            syncStatus = .error(error.localizedDescription)
            throw error
        }

        await updatePendingChangesCount()
    }

    /// Commits all local changes and pushes to the remote repository.
    func pushChanges(message: String) async throws {
        guard !syncStatus.isActive else {
            throw SyncError.syncInProgress
        }

        let credentials = try await loadRequiredCredentials()

        // Pull first to avoid non-fast-forward (critical BeStupid rule: always pull before push).
        syncStatus = .pulling
        do {
            let pullResult = try await gitService.pull(credentials: credentials)
            if case .conflict(let files) = pullResult {
                syncStatus = .resolvingConflicts
                throw GitError.conflictDetected(files: files)
            }
        } catch let error as GitError {
            if case .conflictDetected = error {
                throw error
            }
            // Network errors during pull should not block a commit of local changes,
            // but we still can't push. Record the error but continue to commit.
            if case .networkFailure = error {
                syncStatus = .committing
            } else {
                syncStatus = .error(error.localizedDescription)
                throw error
            }
        }

        // Commit local changes.
        syncStatus = .committing
        do {
            let hasChanges = try await gitService.hasLocalChanges()
            if hasChanges {
                try await gitService.commitAll(message: message)
            }
        } catch {
            syncStatus = .error(error.localizedDescription)
            throw error
        }

        // Push to remote.
        syncStatus = .pushing
        do {
            try await gitService.push(credentials: credentials)
            lastSyncDate = Date()
            syncStatus = .idle
            lock.lock()
            offlineChangesPending = false
            lock.unlock()
        } catch let error as GitError {
            if case .networkFailure = error {
                // Changes are committed locally; will push when back online.
                lock.lock()
                offlineChangesPending = true
                lock.unlock()
                syncStatus = .idle
            } else {
                syncStatus = .error(error.localizedDescription)
                throw error
            }
        }

        await updatePendingChangesCount()
    }

    // MARK: - File Operations

    /// Writes a file to the local repository using the atomic tmp+rename pattern.
    /// - Parameters:
    ///   - relativePath: Path relative to the repo root (e.g. "content/logs/2026-02-17.md").
    ///   - content: The string content to write.
    func writeFile(at relativePath: String, content: String) throws {
        let targetURL = localRepoPath.appendingPathComponent(relativePath)

        // Ensure parent directory exists.
        let parentDir = targetURL.deletingLastPathComponent()
        if !fileManager.fileExists(atPath: parentDir.path) {
            try fileManager.createDirectory(at: parentDir, withIntermediateDirectories: true)
        }

        guard let data = content.data(using: .utf8) else {
            throw SyncError.fileWriteFailed("Could not encode content as UTF-8 for \(relativePath)")
        }

        // Atomic write: write to tmp file, then rename (POSIX atomic rename).
        let tmpURL = targetURL.appendingPathExtension("tmp")

        do {
            try data.write(to: tmpURL, options: [.atomic])
        } catch {
            // Clean up the temp file if it was partially written.
            try? fileManager.removeItem(at: tmpURL)
            throw SyncError.fileWriteFailed(
                "Failed to write temp file for \(relativePath): \(error.localizedDescription)"
            )
        }

        // If the tmp file was written with .atomic, it's already atomically placed.
        // But to be fully consistent with the project's tmp+rename contract, we
        // ensure the rename explicitly in case the platform doesn't honor .atomic.
        do {
            // Remove existing file if present (rename won't overwrite on all platforms).
            if fileManager.fileExists(atPath: targetURL.path) {
                try fileManager.removeItem(at: targetURL)
            }
            try fileManager.moveItem(at: tmpURL, to: targetURL)
        } catch {
            // The .atomic write already placed the file correctly, so if rename
            // fails it's likely because the file is already in place.
            if !fileManager.fileExists(atPath: targetURL.path) {
                throw SyncError.fileWriteFailed(
                    "Failed to rename temp file for \(relativePath): \(error.localizedDescription)"
                )
            }
        }

        // Schedule auto-sync after write.
        scheduleAutoSync()
    }

    /// Reads a file from the local repository.
    /// - Parameter relativePath: Path relative to the repo root.
    /// - Returns: The file content as a string.
    func readFile(at relativePath: String) throws -> String {
        let fileURL = localRepoPath.appendingPathComponent(relativePath)

        guard fileManager.fileExists(atPath: fileURL.path) else {
            throw SyncError.fileNotFound(relativePath)
        }

        do {
            return try String(contentsOf: fileURL, encoding: .utf8)
        } catch {
            throw SyncError.fileReadFailed(
                "Could not read \(relativePath): \(error.localizedDescription)"
            )
        }
    }

    /// Lists files in the specified directory within the local repository.
    /// - Parameters:
    ///   - directory: Relative path to the directory (e.g. "content/logs").
    ///   - ext: Optional file extension filter (e.g. "md"). Pass nil for all files.
    /// - Returns: Array of relative file paths.
    func listFiles(in directory: String, extension ext: String? = nil) throws -> [String] {
        let dirURL = localRepoPath.appendingPathComponent(directory)

        guard fileManager.fileExists(atPath: dirURL.path) else {
            throw SyncError.directoryListingFailed("Directory not found: \(directory)")
        }

        do {
            let contents = try fileManager.contentsOfDirectory(
                at: dirURL,
                includingPropertiesForKeys: [.isRegularFileKey],
                options: [.skipsHiddenFiles]
            )

            var results: [String] = []
            for url in contents {
                // Filter by extension if specified.
                if let ext, url.pathExtension.lowercased() != ext.lowercased() {
                    continue
                }

                // Check that it's a regular file, not a directory.
                let resourceValues = try url.resourceValues(forKeys: [.isRegularFileKey])
                if resourceValues.isRegularFile == true {
                    // Return the path relative to the repo root.
                    let relativePath = directory.isEmpty
                        ? url.lastPathComponent
                        : "\(directory)/\(url.lastPathComponent)"
                    results.append(relativePath)
                }
            }

            return results.sorted()
        } catch let error as SyncError {
            throw error
        } catch {
            throw SyncError.directoryListingFailed(
                "Failed to list \(directory): \(error.localizedDescription)"
            )
        }
    }

    // MARK: - Auto-Sync (Debounced)

    /// Schedules an auto-sync after a debounce interval.
    /// Calling this again within the debounce window resets the timer.
    func scheduleAutoSync() {
        lock.lock()
        autoSyncTask?.cancel()

        let debounceInterval = autoSyncDebounceInterval
        autoSyncTask = Task { [weak self] in
            guard let self else { return }

            do {
                try await Task.sleep(nanoseconds: UInt64(debounceInterval * 1_000_000_000))
            } catch {
                // Task was cancelled (new write came in, resetting the debounce).
                return
            }

            guard !Task.isCancelled else { return }

            let online = self.isOnline
            guard online else {
                self.lock.lock()
                self.offlineChangesPending = true
                self.lock.unlock()
                return
            }

            do {
                let timestamp = Self.formatTimestamp(Date())
                try await self.pushChanges(message: "Auto-sync from iOS app at \(timestamp)")
            } catch {
                // Auto-sync failures are non-fatal; changes remain committed locally.
                // The next manual sync or online transition will retry.
            }
        }
        lock.unlock()
    }

    // MARK: - Conflict Resolution

    /// Resolves merge conflicts using the specified strategy.
    /// - Parameter strategy: How to resolve each conflict.
    func resolveConflicts(strategy: ConflictStrategy) async throws {
        guard syncStatus == .resolvingConflicts else {
            throw SyncError.conflictResolutionFailed("No conflicts to resolve.")
        }

        let status = try await gitService.status()
        let conflictFiles = status.modifiedFiles

        for relativePath in conflictFiles {
            let filePath = localRepoPath.appendingPathComponent(relativePath)
            guard fileManager.fileExists(atPath: filePath.path) else { continue }

            let content: String
            do {
                content = try String(contentsOf: filePath, encoding: .utf8)
            } catch {
                throw SyncError.conflictResolutionFailed(
                    "Could not read conflicted file \(relativePath): \(error.localizedDescription)"
                )
            }

            // Only process files that actually have conflict markers.
            guard content.contains("<<<<<<<") else { continue }

            let resolved = resolveFileConflict(content: content, strategy: strategy)

            // Atomic write of resolved content.
            try writeFile(at: relativePath, content: resolved)
        }

        // Stage and commit the resolution.
        do {
            try await gitService.commitAll(message: "Resolve merge conflicts (strategy: \(strategy))")
            syncStatus = .idle
        } catch {
            throw SyncError.conflictResolutionFailed(
                "Failed to commit conflict resolution: \(error.localizedDescription)"
            )
        }
    }

    // MARK: - Network Monitoring

    /// Starts monitoring network connectivity via NWPathMonitor.
    /// When the device comes back online and there are pending changes, triggers a push.
    private func startNetworkMonitoring() {
        lock.lock()
        networkMonitor?.cancel()

        let monitor = NWPathMonitor()
        let queue = DispatchQueue(label: "com.bestupid.network-monitor", qos: .utility)
        monitorQueue = queue
        networkMonitor = monitor

        monitor.pathUpdateHandler = { [weak self] path in
            guard let self else { return }
            let wasOnline = self.isOnline
            let nowOnline = path.status == .satisfied

            self.isOnline = nowOnline

            // If we just came back online and have pending changes, push them.
            if !wasOnline && nowOnline {
                self.lock.lock()
                let hasPending = self.offlineChangesPending
                self.lock.unlock()

                if hasPending {
                    Task {
                        try? await self.pushChanges(
                            message: "Sync offline changes from iOS app"
                        )
                    }
                }
            }
        }

        lock.unlock()

        monitor.start(queue: queue)
    }

    // MARK: - Private Helpers

    /// Loads credentials from the credential manager, throwing if none exist.
    private func loadRequiredCredentials() async throws -> GitCredentials {
        guard let credentials = try await credentialManager.loadCredentials() else {
            throw SyncError.noCredentials
        }
        return credentials
    }

    /// Updates the pendingChanges count by querying git status.
    private func updatePendingChangesCount() async {
        do {
            let status = try await gitService.status()
            pendingChanges = status.modifiedFiles.count + status.untrackedFiles.count
        } catch {
            // Non-fatal: just leave the count as-is.
        }
    }

    /// Resolves git conflict markers in file content based on the given strategy.
    ///
    /// Git conflict markers look like:
    /// ```
    /// <<<<<<< HEAD
    /// local content
    /// =======
    /// remote content
    /// >>>>>>> origin/main
    /// ```
    private func resolveFileConflict(content: String, strategy: ConflictStrategy) -> String {
        var result = ""
        var inConflict = false
        var inLocalSection = false
        var inRemoteSection = false
        var localBlock = ""
        var remoteBlock = ""

        for line in content.components(separatedBy: "\n") {
            if line.hasPrefix("<<<<<<<") {
                inConflict = true
                inLocalSection = true
                inRemoteSection = false
                localBlock = ""
                remoteBlock = ""
                continue
            }

            if line.hasPrefix("=======") && inConflict {
                inLocalSection = false
                inRemoteSection = true
                continue
            }

            if line.hasPrefix(">>>>>>>") && inConflict {
                // End of conflict block; apply strategy.
                switch strategy {
                case .keepLocal:
                    result += localBlock
                case .keepRemote:
                    result += remoteBlock
                case .perSection:
                    // For perSection, keep both blocks concatenated.
                    // A more sophisticated implementation would merge at the markdown
                    // section level, but for now we keep local (phone data wins).
                    result += localBlock
                }

                inConflict = false
                inLocalSection = false
                inRemoteSection = false
                continue
            }

            if inConflict {
                if inLocalSection {
                    localBlock += line + "\n"
                } else if inRemoteSection {
                    remoteBlock += line + "\n"
                }
            } else {
                result += line + "\n"
            }
        }

        // Remove trailing newline added by the loop if the original didn't have one.
        if !content.hasSuffix("\n") && result.hasSuffix("\n") {
            result = String(result.dropLast())
        }

        return result
    }

    /// Formats a date as an ISO-8601 timestamp string for commit messages.
    private static func formatTimestamp(_ date: Date) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withFullDate, .withFullTime, .withTimeZone]
        return formatter.string(from: date)
    }
}
