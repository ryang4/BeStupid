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
                WorkoutListView()
            }
            .badge(appState.hasActiveWorkout ? "Live" : nil)

            Tab("Logs", systemImage: AppTab.logs.systemImage, value: .logs) {
                LogListView()
            }

            Tab("Charts", systemImage: AppTab.charts.systemImage, value: .charts) {
                ChartsContainerView()
            }

            Tab("Settings", systemImage: AppTab.settings.systemImage, value: .settings) {
                SettingsView()
            }
            .badge(appState.pendingChanges > 0 ? "\(appState.pendingChanges)" : nil)
        }
    }
}

#Preview {
    ContentView()
        .environment(AppState())
}
