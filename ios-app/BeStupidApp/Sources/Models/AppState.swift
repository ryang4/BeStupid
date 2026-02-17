import SwiftUI

// MARK: - SyncStatus

enum SyncStatus: Sendable, Equatable {
    case idle
    case syncing
    case success(Date)
    case error(String)

    var isIdle: Bool {
        if case .idle = self { return true }
        return false
    }

    var isSyncing: Bool {
        if case .syncing = self { return true }
        return false
    }

    var isError: Bool {
        if case .error = self { return true }
        return false
    }

    var errorMessage: String? {
        if case .error(let message) = self { return message }
        return nil
    }
}

// MARK: - AppTab

enum AppTab: String, Sendable, CaseIterable, Equatable {
    case dashboard
    case workout
    case logs
    case charts
    case settings

    var displayName: String {
        switch self {
        case .dashboard: return "Dashboard"
        case .workout: return "Workout"
        case .logs: return "Logs"
        case .charts: return "Charts"
        case .settings: return "Settings"
        }
    }

    var systemImage: String {
        switch self {
        case .dashboard: return "square.grid.2x2"
        case .workout: return "figure.run"
        case .logs: return "doc.text"
        case .charts: return "chart.xyaxis.line"
        case .settings: return "gear"
        }
    }
}

// MARK: - AppState

@Observable
final class AppState: @unchecked Sendable {
    var isOnline: Bool = true
    var lastSyncDate: Date?
    var syncStatus: SyncStatus = .idle
    var selectedTab: AppTab = .dashboard
    var currentWorkout: WorkoutSession?

    // Repository state
    var isRepoCloned: Bool = false
    var repoPath: URL?
    var pendingChanges: Int = 0

    /// Whether a live workout session is currently in progress.
    var hasActiveWorkout: Bool {
        currentWorkout?.isActive ?? false
    }
}
