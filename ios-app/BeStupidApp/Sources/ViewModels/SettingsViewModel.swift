import Foundation
import Observation

@Observable
@MainActor
final class SettingsViewModel {

    // MARK: - Git Settings

    var repoURL: String = ""
    var isRepoCloned: Bool = false
    var lastSyncDate: Date?
    var pendingChanges: Int = 0
    var syncStatus: SyncStatus = .idle
    var isGitAuthenticated: Bool = false

    // MARK: - AI Settings

    var useOnDeviceAI: Bool = true
    var cloudProviderType: String = CloudAIProvider.Provider.anthropic.rawValue
    var cloudAPIKey: String = ""
    var cloudModel: String = CloudAIProvider.Provider.anthropic.defaultModel
    var isTestingConnection: Bool = false
    var connectionTestResult: String?

    // MARK: - HealthKit Settings

    var isHealthKitAuthorized: Bool = false
    var syncWorkoutsToHealth: Bool = true
    var importSleepFromHealth: Bool = true
    var importWeightFromHealth: Bool = true
    var importHeartRateFromHealth: Bool = true

    // MARK: - Cache

    var cacheLogCount: Int = 0
    var cacheMetricCount: Int = 0

    // MARK: - UI State

    var isRebuildingCache: Bool = false
    var isExportingData: Bool = false
    var showExportSuccess: Bool = false

    // MARK: - Computed Properties

    var syncStatusText: String {
        switch syncStatus {
        case .idle:
            return "Not synced"
        case .syncing:
            return "Syncing..."
        case .success(let date):
            return "Last synced \(Self.relativeFormatter.localizedString(for: date, relativeTo: Date()))"
        case .error(let message):
            return "Error: \(message)"
        }
    }

    var syncStatusColor: String {
        switch syncStatus {
        case .idle: return "secondary"
        case .syncing: return "blue"
        case .success: return "green"
        case .error: return "red"
        }
    }

    var selectedProvider: CloudAIProvider.Provider {
        CloudAIProvider.Provider(rawValue: cloudProviderType) ?? .anthropic
    }

    var appVersion: String {
        let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
        let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1"
        return "\(version) (\(build))"
    }

    // MARK: - Actions

    func loadSettings() async {
        // In production: load from UserDefaults / Keychain / DataSyncCoordinator.
        try? await Task.sleep(for: .milliseconds(400))

        repoURL = "https://github.com/ryan-galliher/BeStupid.git"
        isRepoCloned = true
        isGitAuthenticated = true
        lastSyncDate = Date().addingTimeInterval(-3600)
        pendingChanges = 2
        syncStatus = .success(Date().addingTimeInterval(-3600))

        useOnDeviceAI = true
        cloudProviderType = CloudAIProvider.Provider.anthropic.rawValue
        cloudModel = CloudAIProvider.Provider.anthropic.defaultModel

        isHealthKitAuthorized = true

        cacheLogCount = 127
        cacheMetricCount = 893
    }

    func authenticateGitHub() async {
        // In production: trigger ASWebAuthenticationSession OAuth flow.
        syncStatus = .syncing
        try? await Task.sleep(for: .milliseconds(1500))
        isGitAuthenticated = true
        syncStatus = .success(Date())
    }

    func syncNow() async {
        guard !syncStatus.isSyncing else { return }

        syncStatus = .syncing
        try? await Task.sleep(for: .milliseconds(2000))

        // In production: call DataSyncCoordinator.pullAndPush()
        lastSyncDate = Date()
        pendingChanges = 0
        syncStatus = .success(Date())
    }

    func signOutGitHub() async {
        // In production: clear credentials from Keychain via GitCredentialManager.
        try? await Task.sleep(for: .milliseconds(300))
        isGitAuthenticated = false
        syncStatus = .idle
    }

    func testAIConnection() async {
        isTestingConnection = true
        connectionTestResult = nil

        try? await Task.sleep(for: .milliseconds(1500))

        // In production: instantiate CloudAIProvider and call a lightweight test query.
        if cloudAPIKey.isEmpty {
            connectionTestResult = "Please enter an API key."
        } else {
            connectionTestResult = "Connection successful. Model: \(cloudModel)"
        }

        isTestingConnection = false
    }

    func saveAISettings() {
        // In production: persist to UserDefaults/Keychain.
        // Update AIServiceManager to use new settings.
    }

    func requestHealthKitAccess() async {
        // In production: call HealthKitService.requestAuthorization()
        try? await Task.sleep(for: .milliseconds(800))
        isHealthKitAuthorized = true
    }

    func rebuildCache() async {
        isRebuildingCache = true

        // In production: call CacheManager.rebuildAll()
        try? await Task.sleep(for: .milliseconds(2000))

        cacheLogCount = 127
        cacheMetricCount = 893
        isRebuildingCache = false
    }

    func exportData() async {
        isExportingData = true

        // In production: zip all content/ and memory/ files, present share sheet.
        try? await Task.sleep(for: .milliseconds(1500))

        isExportingData = false
        showExportSuccess = true
    }

    func updateProviderDefaults() {
        let provider = selectedProvider
        cloudModel = provider.defaultModel
    }

    // MARK: - Private

    private static let relativeFormatter: RelativeDateTimeFormatter = {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter
    }()
}
