import SwiftUI

struct ContentView: View {
    @Environment(AppState.self) private var appState

    var body: some View {
        @Bindable var state = appState

        TabView(selection: $state.selectedTab) {
            Tab("Dashboard", systemImage: AppTab.dashboard.systemImage, value: .dashboard) {
                DashboardView()
            }

            Tab("Workout", systemImage: AppTab.workout.systemImage, value: .workout) {
                WorkoutPlaceholderView()
            }
            .badge(appState.hasActiveWorkout ? "Live" : nil)

            Tab("Logs", systemImage: AppTab.logs.systemImage, value: .logs) {
                LogsPlaceholderView()
            }

            Tab("Charts", systemImage: AppTab.charts.systemImage, value: .charts) {
                ChartsPlaceholderView()
            }

            Tab("Settings", systemImage: AppTab.settings.systemImage, value: .settings) {
                SettingsPlaceholderView()
            }
            .badge(appState.pendingChanges > 0 ? "\(appState.pendingChanges)" : nil)
        }
    }
}

// MARK: - Placeholder Views

/// Placeholder view for the Dashboard tab. Will be replaced with real implementation.
struct DashboardPlaceholderView: View {
    var body: some View {
        NavigationStack {
            Text("Dashboard coming soon")
                .font(.title2)
                .foregroundStyle(.secondary)
                .navigationTitle("Dashboard")
        }
    }
}

/// Placeholder view for the Workout tab. Will be replaced with real implementation.
struct WorkoutPlaceholderView: View {
    var body: some View {
        NavigationStack {
            Text("Workout tracking coming soon")
                .font(.title2)
                .foregroundStyle(.secondary)
                .navigationTitle("Workout")
        }
    }
}

/// Placeholder view for the Logs tab. Will be replaced with real implementation.
struct LogsPlaceholderView: View {
    var body: some View {
        NavigationStack {
            Text("Daily logs coming soon")
                .font(.title2)
                .foregroundStyle(.secondary)
                .navigationTitle("Logs")
        }
    }
}

/// Placeholder view for the Charts tab. Will be replaced with real implementation.
struct ChartsPlaceholderView: View {
    var body: some View {
        NavigationStack {
            Text("Charts coming soon")
                .font(.title2)
                .foregroundStyle(.secondary)
                .navigationTitle("Charts")
        }
    }
}

/// Placeholder view for the Settings tab. Will be replaced with real implementation.
struct SettingsPlaceholderView: View {
    var body: some View {
        NavigationStack {
            Text("Settings coming soon")
                .font(.title2)
                .foregroundStyle(.secondary)
                .navigationTitle("Settings")
        }
    }
}
