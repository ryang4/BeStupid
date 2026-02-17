import SwiftUI

struct SettingsView: View {
    @Environment(AppState.self) private var appState
    @State private var viewModel = SettingsViewModel()

    var body: some View {
        NavigationStack {
            Form {
                dataSyncSection
                aiAssistantSection
                healthDataSection
                dataManagementSection
                aboutSection
            }
            .navigationTitle("Settings")
            .task { await viewModel.loadSettings() }
            .alert("Export Complete", isPresented: $viewModel.showExportSuccess) {
                Button("OK", role: .cancel) {}
            } message: {
                Text("All data has been exported successfully.")
            }
        }
    }

    // MARK: - Data Sync Section

    private var dataSyncSection: some View {
        Section {
            NavigationLink {
                GitSettingsView(
                    repoURL: $viewModel.repoURL,
                    isAuthenticated: viewModel.isGitAuthenticated,
                    syncStatus: viewModel.syncStatus,
                    lastSyncDate: viewModel.lastSyncDate,
                    pendingChanges: viewModel.pendingChanges,
                    onAuthenticate: { Task { await viewModel.authenticateGitHub() } },
                    onSync: { Task { await viewModel.syncNow() } },
                    onSignOut: { Task { await viewModel.signOutGitHub() } }
                )
            } label: {
                HStack(spacing: 12) {
                    SettingsIcon(systemImage: "arrow.triangle.2.circlepath", color: .blue)

                    VStack(alignment: .leading, spacing: 2) {
                        Text("Data Sync")
                            .font(.body)
                        Text(viewModel.syncStatusText)
                            .font(.caption)
                            .foregroundStyle(syncStatusColor)
                    }

                    Spacer()

                    if viewModel.pendingChanges > 0 {
                        Text("\(viewModel.pendingChanges)")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(.white)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 3)
                            .background(.red, in: Capsule())
                    }
                }
            }

            if !viewModel.syncStatus.isSyncing {
                Button {
                    Task { await viewModel.syncNow() }
                } label: {
                    HStack {
                        Label("Sync Now", systemImage: "arrow.clockwise")
                        Spacer()
                        if viewModel.syncStatus.isSyncing {
                            ProgressView()
                                .controlSize(.small)
                        }
                    }
                }
                .disabled(viewModel.syncStatus.isSyncing || !viewModel.isGitAuthenticated)
            } else {
                HStack {
                    Label("Syncing...", systemImage: "arrow.clockwise")
                        .foregroundStyle(.secondary)
                    Spacer()
                    ProgressView()
                        .controlSize(.small)
                }
            }
        } header: {
            Text("Data Sync")
        } footer: {
            if let date = viewModel.lastSyncDate {
                Text("Last synced: \(date, format: .dateTime.month().day().hour().minute())")
            }
        }
    }

    // MARK: - AI Assistant Section

    private var aiAssistantSection: some View {
        Section {
            NavigationLink {
                AISettingsView(
                    useOnDevice: $viewModel.useOnDeviceAI,
                    providerType: $viewModel.cloudProviderType,
                    apiKey: $viewModel.cloudAPIKey,
                    model: $viewModel.cloudModel,
                    isTestingConnection: viewModel.isTestingConnection,
                    testResult: viewModel.connectionTestResult,
                    onTest: { Task { await viewModel.testAIConnection() } },
                    onSave: { viewModel.saveAISettings() }
                )
            } label: {
                HStack(spacing: 12) {
                    SettingsIcon(systemImage: "brain.head.profile", color: .purple)

                    VStack(alignment: .leading, spacing: 2) {
                        Text("AI Assistant")
                            .font(.body)
                        Text(viewModel.useOnDeviceAI ? "On-device AI" : viewModel.cloudProviderType)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
        } header: {
            Text("AI Assistant")
        }
    }

    // MARK: - Health Data Section

    private var healthDataSection: some View {
        Section {
            NavigationLink {
                HealthKitSettingsView(
                    isAuthorized: viewModel.isHealthKitAuthorized,
                    syncWorkouts: $viewModel.syncWorkoutsToHealth,
                    importSleep: $viewModel.importSleepFromHealth,
                    importWeight: $viewModel.importWeightFromHealth,
                    importHeartRate: $viewModel.importHeartRateFromHealth,
                    onRequestAccess: { Task { await viewModel.requestHealthKitAccess() } }
                )
            } label: {
                HStack(spacing: 12) {
                    SettingsIcon(systemImage: "heart.fill", color: .red)

                    VStack(alignment: .leading, spacing: 2) {
                        Text("Health Data")
                            .font(.body)
                        Text(viewModel.isHealthKitAuthorized ? "Connected" : "Not connected")
                            .font(.caption)
                            .foregroundStyle(viewModel.isHealthKitAuthorized ? .green : .secondary)
                    }
                }
            }
        } header: {
            Text("Health Data")
        }
    }

    // MARK: - Data Management Section

    private var dataManagementSection: some View {
        Section {
            HStack {
                Label("Cached Logs", systemImage: "doc.text")
                Spacer()
                Text("\(viewModel.cacheLogCount)")
                    .foregroundStyle(.secondary)
                    .font(.body.monospacedDigit())
            }

            HStack {
                Label("Cached Metrics", systemImage: "chart.bar")
                Spacer()
                Text("\(viewModel.cacheMetricCount)")
                    .foregroundStyle(.secondary)
                    .font(.body.monospacedDigit())
            }

            Button {
                Task { await viewModel.rebuildCache() }
            } label: {
                HStack {
                    Label("Rebuild Cache", systemImage: "arrow.counterclockwise")
                    Spacer()
                    if viewModel.isRebuildingCache {
                        ProgressView()
                            .controlSize(.small)
                    }
                }
            }
            .disabled(viewModel.isRebuildingCache)

            Button {
                Task { await viewModel.exportData() }
            } label: {
                HStack {
                    Label("Export All Data", systemImage: "square.and.arrow.up")
                    Spacer()
                    if viewModel.isExportingData {
                        ProgressView()
                            .controlSize(.small)
                    }
                }
            }
            .disabled(viewModel.isExportingData)
        } header: {
            Text("Data Management")
        } footer: {
            Text("Rebuilding the cache re-indexes all logs and metrics from local storage.")
        }
    }

    // MARK: - About Section

    private var aboutSection: some View {
        Section {
            HStack {
                Text("Version")
                Spacer()
                Text(viewModel.appVersion)
                    .foregroundStyle(.secondary)
            }

            HStack {
                Text("Built with")
                Spacer()
                Text("SwiftUI + Claude")
                    .foregroundStyle(.secondary)
            }
        } header: {
            Text("About")
        } footer: {
            VStack(spacing: 4) {
                Text("BeStupid")
                    .font(.footnote.weight(.semibold))
                Text("Your personal productivity and fitness system.")
                    .font(.caption2)
            }
            .frame(maxWidth: .infinity)
            .padding(.top, 8)
        }
    }

    // MARK: - Helpers

    private var syncStatusColor: Color {
        switch viewModel.syncStatus {
        case .idle: return .secondary
        case .syncing: return .blue
        case .success: return .green
        case .error: return .red
        }
    }
}

// MARK: - SettingsIcon

private struct SettingsIcon: View {
    let systemImage: String
    let color: Color

    var body: some View {
        Image(systemName: systemImage)
            .font(.system(size: 14, weight: .semibold))
            .foregroundStyle(.white)
            .frame(width: 30, height: 30)
            .background(color, in: RoundedRectangle(cornerRadius: 7))
    }
}

// MARK: - Preview

#Preview("Settings") {
    SettingsView()
        .environment(AppState())
}
