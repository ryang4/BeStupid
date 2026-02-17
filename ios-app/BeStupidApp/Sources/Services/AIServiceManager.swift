import Foundation
import Observation

/// Manages AI provider selection and automatic fallback.
///
/// Default behavior: prefer on-device (free, private, offline).
/// If on-device is unavailable, fall back to a configured cloud provider.
/// When ``preferOnDevice`` is false, cloud is tried first with on-device as fallback.
@Observable
final class AIServiceManager: @unchecked Sendable {
    // MARK: - Providers

    private var onDeviceProvider: OnDeviceAIProvider
    private var cloudProvider: CloudAIProvider?

    /// The provider that will be tried first based on current preference.
    var activeProvider: any AIService {
        if preferOnDevice {
            return onDeviceProvider
        }
        return (cloudProvider as (any AIService)?) ?? onDeviceProvider
    }

    /// Whether to prefer on-device AI (default: true).
    /// When true, on-device is tried first and cloud is fallback.
    /// When false, cloud is tried first and on-device is fallback.
    var preferOnDevice: Bool = true

    /// The currently configured cloud provider type, if any.
    private(set) var cloudProviderType: CloudAIProvider.Provider?

    /// Human-readable name of the active provider.
    var activeProviderName: String {
        if preferOnDevice {
            return onDeviceProvider.providerName
        }
        return cloudProvider?.providerName ?? onDeviceProvider.providerName
    }

    /// Whether a cloud provider is configured.
    var hasCloudProvider: Bool {
        cloudProvider != nil
    }

    // MARK: - Initialization

    init() {
        self.onDeviceProvider = OnDeviceAIProvider()
    }

    /// Initializer for dependency injection (testing).
    init(onDeviceProvider: OnDeviceAIProvider, cloudProvider: CloudAIProvider? = nil) {
        self.onDeviceProvider = onDeviceProvider
        self.cloudProvider = cloudProvider
        self.cloudProviderType = cloudProvider != nil ? .custom : nil
    }

    // MARK: - Configuration

    /// Configure a cloud AI provider.
    func configureCloudProvider(
        provider: CloudAIProvider.Provider,
        apiKey: String,
        model: String? = nil,
        endpoint: URL? = nil
    ) {
        self.cloudProvider = CloudAIProvider(
            provider: provider,
            apiKey: apiKey,
            model: model,
            endpoint: endpoint
        )
        self.cloudProviderType = provider
    }

    /// Remove cloud provider configuration.
    func removeCloudProvider() {
        self.cloudProvider = nil
        self.cloudProviderType = nil
    }

    // MARK: - AI Operations (with fallback)

    /// Generate a morning briefing with automatic fallback.
    func generateBriefing(context: BriefingContext) async throws -> String {
        try await executeWithFallback { provider in
            try await provider.generateBriefing(context: context)
        }
    }

    /// Analyze metrics with automatic fallback.
    func analyzeMetrics(metrics: [MetricSummary], query: String) async throws -> String {
        try await executeWithFallback { provider in
            try await provider.analyzeMetrics(metrics: metrics, query: query)
        }
    }

    /// Suggest workout modifications with automatic fallback.
    func suggestWorkout(protocol proto: ProtocolContext, recovery: RecoveryContext) async throws -> String {
        try await executeWithFallback { provider in
            try await provider.suggestWorkout(protocol: proto, recovery: recovery)
        }
    }

    /// Free-form query with automatic fallback.
    func query(_ question: String, context: QueryContext) async throws -> String {
        try await executeWithFallback { provider in
            try await provider.query(question, context: context)
        }
    }

    // MARK: - Fallback Logic

    /// Execute an AI operation with automatic provider fallback.
    ///
    /// Strategy:
    /// 1. Check if preferred provider is available; if so, try it.
    /// 2. If preferred provider fails or is unavailable, try the fallback.
    /// 3. If both fail, throw the last error (or providerUnavailable).
    private func executeWithFallback(
        _ operation: @Sendable (any AIService) async throws -> String
    ) async throws -> String {
        let primary: any AIService
        let fallback: (any AIService)?

        if preferOnDevice {
            primary = onDeviceProvider
            fallback = cloudProvider
        } else {
            primary = cloudProvider ?? onDeviceProvider
            fallback = cloudProvider != nil ? onDeviceProvider : nil
        }

        // Try primary
        if await primary.isAvailable {
            do {
                return try await operation(primary)
            } catch {
                // Primary failed, attempt fallback
                if let fallback, await fallback.isAvailable {
                    return try await operation(fallback)
                }
                throw error
            }
        }

        // Primary not available, try fallback directly
        if let fallback, await fallback.isAvailable {
            return try await operation(fallback)
        }

        throw AIError.providerUnavailable("No AI provider available")
    }
}
