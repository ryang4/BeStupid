import SwiftUI

struct GitSettingsView: View {
    @Binding var repoURL: String
    let isAuthenticated: Bool
    let syncStatus: SyncStatus
    let lastSyncDate: Date?
    let pendingChanges: Int
    let onAuthenticate: () -> Void
    let onSync: () -> Void
    let onSignOut: () -> Void

    var body: some View {
        Form {
            repositorySection
            authenticationSection
            syncStatusSection
            actionsSection
        }
        .navigationTitle("Data Sync")
        .navigationBarTitleDisplayMode(.inline)
    }

    // MARK: - Repository

    private var repositorySection: some View {
        Section {
            VStack(alignment: .leading, spacing: 8) {
                Text("Repository URL")
                    .font(.caption)
                    .foregroundStyle(.secondary)

                TextField("https://github.com/user/repo.git", text: $repoURL)
                    .font(.system(.body, design: .monospaced))
                    .textContentType(.URL)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)
            }
        } header: {
            Text("Repository")
        } footer: {
            Text("The Git repository containing your BeStupid data files.")
        }
    }

    // MARK: - Authentication

    private var authenticationSection: some View {
        Section {
            HStack(spacing: 12) {
                Image(systemName: isAuthenticated ? "checkmark.shield.fill" : "shield.slash")
                    .font(.title2)
                    .foregroundStyle(isAuthenticated ? .green : .orange)
                    .frame(width: 36, height: 36)

                VStack(alignment: .leading, spacing: 2) {
                    Text(isAuthenticated ? "Authenticated" : "Not Authenticated")
                        .font(.subheadline.weight(.semibold))
                    Text(isAuthenticated
                        ? "Connected to GitHub via OAuth"
                        : "Sign in to enable sync")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                if isAuthenticated {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                }
            }

            if isAuthenticated {
                Button(role: .destructive) {
                    onSignOut()
                } label: {
                    Label("Sign Out of GitHub", systemImage: "rectangle.portrait.and.arrow.right")
                }
            } else {
                Button {
                    onAuthenticate()
                } label: {
                    HStack {
                        Image(systemName: "person.badge.key")
                        Text("Sign in with GitHub")
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .listRowInsets(EdgeInsets(top: 8, leading: 16, bottom: 8, trailing: 16))
            }
        } header: {
            Text("Authentication")
        } footer: {
            if !isAuthenticated {
                Text("Authentication uses GitHub OAuth. Your credentials are stored securely in the device Keychain.")
            }
        }
    }

    // MARK: - Sync Status

    private var syncStatusSection: some View {
        Section {
            HStack {
                Label("Status", systemImage: statusIconName)
                Spacer()
                HStack(spacing: 6) {
                    if syncStatus.isSyncing {
                        ProgressView()
                            .controlSize(.small)
                    }
                    Text(statusText)
                        .foregroundStyle(statusColor)
                }
            }

            if let date = lastSyncDate {
                HStack {
                    Label("Last Sync", systemImage: "clock")
                    Spacer()
                    Text(date, format: .dateTime.month().day().hour().minute())
                        .foregroundStyle(.secondary)
                }
            }

            HStack {
                Label("Pending Changes", systemImage: "doc.badge.ellipsis")
                Spacer()
                Text("\(pendingChanges)")
                    .foregroundStyle(pendingChanges > 0 ? .orange : .secondary)
                    .font(.body.weight(pendingChanges > 0 ? .semibold : .regular).monospacedDigit())
            }

            if let errorMessage = syncStatus.errorMessage {
                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(.red)
                    Text(errorMessage)
                        .font(.caption)
                        .foregroundStyle(.red)
                }
                .padding(.vertical, 4)
            }
        } header: {
            Text("Sync Status")
        }
    }

    // MARK: - Actions

    private var actionsSection: some View {
        Section {
            Button {
                onSync()
            } label: {
                HStack {
                    Label("Sync Now", systemImage: "arrow.clockwise")
                    Spacer()
                    if syncStatus.isSyncing {
                        ProgressView()
                            .controlSize(.small)
                    }
                }
            }
            .disabled(syncStatus.isSyncing || !isAuthenticated)
        } header: {
            Text("Actions")
        } footer: {
            Text("Syncing pulls the latest changes from the remote, commits any local modifications, and pushes them upstream. Conflicts are detected and reported.")
        }
    }

    // MARK: - Helpers

    private var statusIconName: String {
        switch syncStatus {
        case .idle: return "circle.dashed"
        case .syncing: return "arrow.triangle.2.circlepath"
        case .success: return "checkmark.circle.fill"
        case .error: return "exclamationmark.triangle.fill"
        }
    }

    private var statusText: String {
        switch syncStatus {
        case .idle: return "Idle"
        case .syncing: return "Syncing..."
        case .success: return "Up to date"
        case .error: return "Error"
        }
    }

    private var statusColor: Color {
        switch syncStatus {
        case .idle: return .secondary
        case .syncing: return .blue
        case .success: return .green
        case .error: return .red
        }
    }
}

// MARK: - Preview

#Preview("Git Settings - Authenticated") {
    @Previewable @State var repoURL = "https://github.com/ryan-galliher/BeStupid.git"
    NavigationStack {
        GitSettingsView(
            repoURL: $repoURL,
            isAuthenticated: true,
            syncStatus: .success(Date().addingTimeInterval(-3600)),
            lastSyncDate: Date().addingTimeInterval(-3600),
            pendingChanges: 2,
            onAuthenticate: {},
            onSync: {},
            onSignOut: {}
        )
    }
}

#Preview("Git Settings - Not Authenticated") {
    @Previewable @State var repoURL = ""
    NavigationStack {
        GitSettingsView(
            repoURL: $repoURL,
            isAuthenticated: false,
            syncStatus: .idle,
            lastSyncDate: nil,
            pendingChanges: 0,
            onAuthenticate: {},
            onSync: {},
            onSignOut: {}
        )
    }
}

#Preview("Git Settings - Error") {
    @Previewable @State var repoURL = "https://github.com/ryan-galliher/BeStupid.git"
    NavigationStack {
        GitSettingsView(
            repoURL: $repoURL,
            isAuthenticated: true,
            syncStatus: .error("Network connection failed. Unable to reach github.com."),
            lastSyncDate: Date().addingTimeInterval(-86400),
            pendingChanges: 5,
            onAuthenticate: {},
            onSync: {},
            onSignOut: {}
        )
    }
}
