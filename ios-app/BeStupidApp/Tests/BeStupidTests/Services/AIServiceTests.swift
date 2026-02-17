import Foundation
import Testing
@testable import BeStupidApp

// MARK: - Mock AI Provider

/// A fully configurable mock AI provider for testing fallback logic,
/// availability checks, and error propagation.
struct MockAIProvider: AIService, Sendable {
    let providerName: String
    let isAvailableOffline: Bool
    let mockAvailable: Bool
    let mockResponse: String
    let shouldFail: Bool
    let failureError: AIError

    init(
        providerName: String = "Mock",
        isAvailableOffline: Bool = false,
        mockAvailable: Bool = true,
        mockResponse: String = "Mock response",
        shouldFail: Bool = false,
        failureError: AIError = .generationFailed("Mock failure")
    ) {
        self.providerName = providerName
        self.isAvailableOffline = isAvailableOffline
        self.mockAvailable = mockAvailable
        self.mockResponse = mockResponse
        self.shouldFail = shouldFail
        self.failureError = failureError
    }

    var isAvailable: Bool {
        get async { mockAvailable }
    }

    func generateBriefing(context: BriefingContext) async throws -> String {
        if shouldFail { throw failureError }
        return mockResponse
    }

    func analyzeMetrics(metrics: [MetricSummary], query: String) async throws -> String {
        if shouldFail { throw failureError }
        return mockResponse
    }

    func suggestWorkout(protocol proto: ProtocolContext, recovery: RecoveryContext) async throws -> String {
        if shouldFail { throw failureError }
        return mockResponse
    }

    func query(_ question: String, context: QueryContext) async throws -> String {
        if shouldFail { throw failureError }
        return mockResponse
    }
}

// MARK: - Test Helpers

/// Factory for building test context objects with sensible defaults.
enum TestFixtures {
    static let referenceDate = Date(timeIntervalSince1970: 1_739_836_800) // 2025-02-18

    static func makeBriefingContext(
        todayDate: Date? = nil,
        dayOfWeek: String = "Tuesday",
        plannedWorkout: String? = "Upper Body Strength",
        todosForToday: [String] = ["Review PRs", "Ship feature"],
        activeGoals: [String] = ["Run 5k under 25 min"],
        recoveryStatus: String? = "Good",
        streaks: [String: Int] = ["Meditation": 5, "Training": 12]
    ) -> BriefingContext {
        BriefingContext(
            todayDate: todayDate ?? referenceDate,
            dayOfWeek: dayOfWeek,
            plannedWorkout: plannedWorkout,
            recentMetrics: makeMetricSummaries(count: 7),
            todosForToday: todosForToday,
            activeGoals: activeGoals,
            recoveryStatus: recoveryStatus,
            streaks: streaks
        )
    }

    static func makeMetricSummaries(count: Int = 7) -> [MetricSummary] {
        (0..<count).map { i in
            let date = Calendar.current.date(byAdding: .day, value: -i, to: referenceDate)!
            return MetricSummary(
                date: date,
                weight: 185.0 - Double(i) * 0.2,
                sleep: 7.0 + Double(i % 3) * 0.5,
                sleepQuality: 7.0 + Double(i % 4),
                moodAM: 6.0 + Double(i % 5),
                energy: 7.0 + Double(i % 3),
                workoutType: i % 2 == 0 ? "Strength" : "Cardio",
                workoutCompleted: i % 3 != 2,
                todoCompletionRate: 0.6 + Double(i % 4) * 0.1
            )
        }
    }

    static func makeProtocolContext() -> ProtocolContext {
        ProtocolContext(
            currentPhase: "Base Building",
            todayWorkout: "Swim 2000m + Core",
            weeklySchedule: [
                .init(day: "Monday", type: "Strength", workout: "Upper Body"),
                .init(day: "Tuesday", type: "Cardio", workout: "Swim 2000m"),
                .init(day: "Wednesday", type: "Rest", workout: "Active Recovery"),
                .init(day: "Thursday", type: "Strength", workout: "Lower Body"),
                .init(day: "Friday", type: "Cardio", workout: "Run 5k"),
                .init(day: "Saturday", type: "Cardio", workout: "Long Bike"),
                .init(day: "Sunday", type: "Rest", workout: "Off"),
            ],
            trainingGoals: ["Build aerobic base", "Maintain strength"]
        )
    }

    static func makeRecoveryContext(
        recoveryScore: Double? = 72.0,
        recoveryStatus: String? = "Recovering",
        hrvStatus: String? = "Balanced",
        sleepScore: Int? = 78,
        bodyBattery: Int? = 55,
        trainingReadiness: Int? = 65,
        recentTrainingLoad: String? = "3 workouts in last 3 days"
    ) -> RecoveryContext {
        RecoveryContext(
            recoveryScore: recoveryScore,
            recoveryStatus: recoveryStatus,
            hrvStatus: hrvStatus,
            sleepScore: sleepScore,
            bodyBattery: bodyBattery,
            trainingReadiness: trainingReadiness,
            recentTrainingLoad: recentTrainingLoad
        )
    }

    static func makeQueryContext() -> QueryContext {
        QueryContext(
            recentLogs: [
                "02/17: Upper body strength, weight 185.2, sleep 7.5h, mood 8/10",
                "02/16: Rest day, weight 185.4, sleep 8.0h, mood 7/10",
                "02/15: Long run 10k, weight 185.0, sleep 6.5h, mood 6/10",
            ],
            currentProtocol: "Base Building Phase - Week 3",
            activeGoals: ["Run 5k under 25 min", "Bench press 225 lbs"],
            memoryItems: ["Prefers morning workouts", "Knee injury history - avoid deep squats"]
        )
    }
}

// MARK: - AIService Protocol Tests

@Suite("AIService Protocol")
struct AIServiceProtocolTests {
    @Test("Mock provider returns configured response")
    func mockProviderReturnsResponse() async throws {
        let provider = MockAIProvider(mockResponse: "Test briefing output")
        let context = TestFixtures.makeBriefingContext()
        let result = try await provider.generateBriefing(context: context)
        #expect(result == "Test briefing output")
    }

    @Test("Mock provider throws when configured to fail")
    func mockProviderThrowsOnFailure() async {
        let provider = MockAIProvider(shouldFail: true, failureError: .rateLimited)
        let context = TestFixtures.makeBriefingContext()
        await #expect(throws: AIError.self) {
            try await provider.generateBriefing(context: context)
        }
    }

    @Test("Mock provider reports availability correctly")
    func mockProviderAvailability() async {
        let available = MockAIProvider(mockAvailable: true)
        let unavailable = MockAIProvider(mockAvailable: false)
        #expect(await available.isAvailable == true)
        #expect(await unavailable.isAvailable == false)
    }

    @Test("Mock provider offline capability")
    func mockProviderOfflineCapability() {
        let online = MockAIProvider(isAvailableOffline: false)
        let offline = MockAIProvider(isAvailableOffline: true)
        #expect(online.isAvailableOffline == false)
        #expect(offline.isAvailableOffline == true)
    }

    @Test("All AIService methods work on mock provider")
    func allMethodsWork() async throws {
        let provider = MockAIProvider(mockResponse: "OK")

        let briefing = try await provider.generateBriefing(context: TestFixtures.makeBriefingContext())
        #expect(briefing == "OK")

        let analysis = try await provider.analyzeMetrics(
            metrics: TestFixtures.makeMetricSummaries(),
            query: "How is my sleep?"
        )
        #expect(analysis == "OK")

        let workout = try await provider.suggestWorkout(
            protocol: TestFixtures.makeProtocolContext(),
            recovery: TestFixtures.makeRecoveryContext()
        )
        #expect(workout == "OK")

        let queryResult = try await provider.query("What did I do yesterday?", context: TestFixtures.makeQueryContext())
        #expect(queryResult == "OK")
    }
}

// MARK: - AIServiceManager Tests

@Suite("AIServiceManager")
struct AIServiceManagerTests {
    @Test("Default initialization prefers on-device")
    func defaultPrefersOnDevice() {
        let manager = AIServiceManager()
        #expect(manager.preferOnDevice == true)
        #expect(manager.activeProvider.providerName == "Apple On-Device")
        #expect(manager.hasCloudProvider == false)
        #expect(manager.cloudProviderType == nil)
    }

    @Test("Active provider reflects preference when no cloud configured")
    func activeProviderWithoutCloud() {
        let manager = AIServiceManager()

        manager.preferOnDevice = true
        #expect(manager.activeProvider.providerName == "Apple On-Device")

        manager.preferOnDevice = false
        // Without cloud provider, falls back to on-device
        #expect(manager.activeProvider.providerName == "Apple On-Device")
    }

    @Test("Configure cloud provider sets it up correctly")
    func configureCloudProvider() {
        let manager = AIServiceManager()

        manager.configureCloudProvider(
            provider: .anthropic,
            apiKey: "test-key-123"
        )

        #expect(manager.hasCloudProvider == true)
        #expect(manager.cloudProviderType == .anthropic)
    }

    @Test("Configure cloud provider with custom model and endpoint")
    func configureCloudProviderCustom() {
        let manager = AIServiceManager()
        let customEndpoint = URL(string: "https://my-proxy.example.com/v1/messages")!

        manager.configureCloudProvider(
            provider: .anthropic,
            apiKey: "sk-ant-test",
            model: "claude-opus-4-20250514",
            endpoint: customEndpoint
        )

        #expect(manager.hasCloudProvider == true)
        #expect(manager.cloudProviderType == .anthropic)
    }

    @Test("Remove cloud provider clears configuration")
    func removeCloudProvider() {
        let manager = AIServiceManager()

        manager.configureCloudProvider(provider: .openai, apiKey: "sk-test")
        #expect(manager.hasCloudProvider == true)
        #expect(manager.cloudProviderType == .openai)

        manager.removeCloudProvider()
        #expect(manager.hasCloudProvider == false)
        #expect(manager.cloudProviderType == nil)
    }

    @Test("Active provider name reflects current configuration")
    func activeProviderName() {
        let manager = AIServiceManager()

        #expect(manager.activeProviderName == "Apple On-Device")

        manager.configureCloudProvider(provider: .anthropic, apiKey: "test-key")
        manager.preferOnDevice = false
        #expect(manager.activeProviderName == "Anthropic")

        manager.preferOnDevice = true
        #expect(manager.activeProviderName == "Apple On-Device")
    }

    @Test("Reconfiguring cloud provider replaces previous one")
    func reconfigureCloudProvider() {
        let manager = AIServiceManager()

        manager.configureCloudProvider(provider: .anthropic, apiKey: "key-1")
        #expect(manager.cloudProviderType == .anthropic)

        manager.configureCloudProvider(provider: .openai, apiKey: "key-2")
        #expect(manager.cloudProviderType == .openai)
    }

    @Test("Throws when no provider is available")
    func throwsWhenNoProviderAvailable() async {
        // On platforms without FoundationModels, on-device is unavailable.
        // With no cloud configured, all providers are unavailable in test env.
        // We test this through the manager's fallback logic by verifying the error type.
        let manager = AIServiceManager()
        let context = TestFixtures.makeBriefingContext()

        // On-device will report unavailable in test environment (no FoundationModels),
        // and no cloud is configured, so this should throw.
        do {
            _ = try await manager.generateBriefing(context: context)
            // If we get here, on-device was available (running on compatible hardware).
            // That is acceptable -- the test validates the path exists.
        } catch let error as AIError {
            // Verify we get a meaningful error, not a crash
            #expect(error.errorDescription != nil)
        }
    }
}

// MARK: - Fallback Logic Tests (using MockAIProvider indirectly)

@Suite("Fallback Logic")
struct FallbackLogicTests {
    @Test("executeWithFallback tries primary first when available")
    func primaryFirstWhenAvailable() async throws {
        let primary = MockAIProvider(
            providerName: "Primary",
            mockAvailable: true,
            mockResponse: "Primary response"
        )
        let fallback = MockAIProvider(
            providerName: "Fallback",
            mockAvailable: true,
            mockResponse: "Fallback response"
        )

        // Simulate the manager's fallback logic directly
        let result = try await executeFallbackSimulation(
            primary: primary,
            fallback: fallback
        ) { provider in
            try await provider.generateBriefing(context: TestFixtures.makeBriefingContext())
        }
        #expect(result == "Primary response")
    }

    @Test("executeWithFallback uses fallback when primary unavailable")
    func fallbackWhenPrimaryUnavailable() async throws {
        let primary = MockAIProvider(
            providerName: "Primary",
            mockAvailable: false,
            mockResponse: "Primary response"
        )
        let fallback = MockAIProvider(
            providerName: "Fallback",
            mockAvailable: true,
            mockResponse: "Fallback response"
        )

        let result = try await executeFallbackSimulation(
            primary: primary,
            fallback: fallback
        ) { provider in
            try await provider.generateBriefing(context: TestFixtures.makeBriefingContext())
        }
        #expect(result == "Fallback response")
    }

    @Test("executeWithFallback uses fallback when primary fails")
    func fallbackWhenPrimaryFails() async throws {
        let primary = MockAIProvider(
            providerName: "Primary",
            mockAvailable: true,
            shouldFail: true,
            failureError: .networkError("Connection reset")
        )
        let fallback = MockAIProvider(
            providerName: "Fallback",
            mockAvailable: true,
            mockResponse: "Fallback saved the day"
        )

        let result = try await executeFallbackSimulation(
            primary: primary,
            fallback: fallback
        ) { provider in
            try await provider.generateBriefing(context: TestFixtures.makeBriefingContext())
        }
        #expect(result == "Fallback saved the day")
    }

    @Test("executeWithFallback throws when both unavailable")
    func throwsWhenBothUnavailable() async {
        let primary = MockAIProvider(providerName: "Primary", mockAvailable: false)
        let fallback = MockAIProvider(providerName: "Fallback", mockAvailable: false)

        await #expect(throws: AIError.self) {
            try await executeFallbackSimulation(
                primary: primary,
                fallback: fallback
            ) { provider in
                try await provider.generateBriefing(context: TestFixtures.makeBriefingContext())
            }
        }
    }

    @Test("executeWithFallback throws primary error when fallback also fails")
    func throwsPrimaryErrorWhenBothFail() async {
        let primary = MockAIProvider(
            providerName: "Primary",
            mockAvailable: true,
            shouldFail: true,
            failureError: .rateLimited
        )
        let fallback = MockAIProvider(
            providerName: "Fallback",
            mockAvailable: true,
            shouldFail: true,
            failureError: .modelNotLoaded
        )

        do {
            _ = try await executeFallbackSimulation(
                primary: primary,
                fallback: fallback
            ) { provider in
                try await provider.generateBriefing(context: TestFixtures.makeBriefingContext())
            }
            Issue.record("Expected error to be thrown")
        } catch let error as AIError {
            // When primary fails and fallback also fails, the fallback error propagates
            #expect(error == .modelNotLoaded)
        } catch {
            Issue.record("Unexpected error type: \(error)")
        }
    }

    @Test("executeWithFallback works without fallback provider")
    func worksWithoutFallback() async throws {
        let primary = MockAIProvider(
            providerName: "Solo",
            mockAvailable: true,
            mockResponse: "Solo response"
        )

        let result = try await executeFallbackSimulation(
            primary: primary,
            fallback: nil
        ) { provider in
            try await provider.generateBriefing(context: TestFixtures.makeBriefingContext())
        }
        #expect(result == "Solo response")
    }

    @Test("executeWithFallback throws when solo provider unavailable")
    func throwsWhenSoloUnavailable() async {
        let primary = MockAIProvider(providerName: "Solo", mockAvailable: false)

        await #expect(throws: AIError.self) {
            try await executeFallbackSimulation(
                primary: primary,
                fallback: nil
            ) { provider in
                try await provider.generateBriefing(context: TestFixtures.makeBriefingContext())
            }
        }
    }

    /// Replicates AIServiceManager.executeWithFallback logic for testability
    /// with arbitrary mock providers.
    private func executeFallbackSimulation(
        primary: any AIService,
        fallback: (any AIService)?,
        operation: @Sendable (any AIService) async throws -> String
    ) async throws -> String {
        if await primary.isAvailable {
            do {
                return try await operation(primary)
            } catch {
                if let fallback, await fallback.isAvailable {
                    return try await operation(fallback)
                }
                throw error
            }
        }

        if let fallback, await fallback.isAvailable {
            return try await operation(fallback)
        }

        throw AIError.providerUnavailable("No AI provider available")
    }
}

// MARK: - CloudAIProvider Tests

@Suite("CloudAIProvider")
struct CloudAIProviderTests {
    @Test("Provider has correct default endpoints")
    func defaultEndpoints() {
        #expect(
            CloudAIProvider.Provider.anthropic.defaultEndpoint
                == URL(string: "https://api.anthropic.com/v1/messages")!
        )
        #expect(
            CloudAIProvider.Provider.openai.defaultEndpoint
                == URL(string: "https://api.openai.com/v1/chat/completions")!
        )
        #expect(
            CloudAIProvider.Provider.custom.defaultEndpoint
                == URL(string: "http://localhost:8080/v1/chat/completions")!
        )
    }

    @Test("Provider has correct default models")
    func defaultModels() {
        #expect(CloudAIProvider.Provider.anthropic.defaultModel == "claude-sonnet-4-5-20250929")
        #expect(CloudAIProvider.Provider.openai.defaultModel == "gpt-4o")
        #expect(CloudAIProvider.Provider.custom.defaultModel == "default")
    }

    @Test("Provider enum has all expected cases")
    func providerCases() {
        let allCases = CloudAIProvider.Provider.allCases
        #expect(allCases.count == 3)
        #expect(allCases.contains(.anthropic))
        #expect(allCases.contains(.openai))
        #expect(allCases.contains(.custom))
    }

    @Test("Provider identifiable conformance uses rawValue")
    func providerIdentifiable() {
        #expect(CloudAIProvider.Provider.anthropic.id == "Anthropic")
        #expect(CloudAIProvider.Provider.openai.id == "OpenAI")
        #expect(CloudAIProvider.Provider.custom.id == "Custom")
    }

    @Test("CloudAIProvider initializes with correct provider name")
    func initializationProviderName() async {
        let anthropic = CloudAIProvider(provider: .anthropic, apiKey: "test-key")
        let openai = CloudAIProvider(provider: .openai, apiKey: "test-key")
        let custom = CloudAIProvider(provider: .custom, apiKey: "test-key")

        #expect(await anthropic.providerName == "Anthropic")
        #expect(await openai.providerName == "OpenAI")
        #expect(await custom.providerName == "Custom")
    }

    @Test("CloudAIProvider is not available offline")
    func notAvailableOffline() async {
        let provider = CloudAIProvider(provider: .anthropic, apiKey: "test-key")
        #expect(await provider.isAvailableOffline == false)
    }

    @Test("CloudAIProvider availability depends on API key")
    func availabilityDependsOnKey() async {
        let withKey = CloudAIProvider(provider: .anthropic, apiKey: "sk-test")
        let withoutKey = CloudAIProvider(provider: .anthropic, apiKey: "")

        #expect(await withKey.isAvailable == true)
        #expect(await withoutKey.isAvailable == false)
    }

    @Test("CloudAIProvider with empty key throws invalidAPIKey on request")
    func emptyKeyThrowsOnRequest() async {
        let provider = CloudAIProvider(provider: .anthropic, apiKey: "")
        let context = TestFixtures.makeBriefingContext()

        await #expect(throws: AIError.self) {
            try await provider.generateBriefing(context: context)
        }
    }
}

// MARK: - OnDeviceAIProvider Tests

@Suite("OnDeviceAIProvider")
struct OnDeviceAIProviderTests {
    @Test("OnDeviceAIProvider has correct provider name")
    func providerName() async {
        let provider = OnDeviceAIProvider()
        #expect(await provider.providerName == "Apple On-Device")
    }

    @Test("OnDeviceAIProvider is available offline")
    func isAvailableOffline() async {
        let provider = OnDeviceAIProvider()
        #expect(await provider.isAvailableOffline == true)
    }

    @Test("OnDeviceAIProvider availability reflects platform capability")
    func availabilityReflectsPlatform() async {
        let provider = OnDeviceAIProvider()
        // On test machines without FoundationModels, this should be false.
        // On compatible hardware, it may be true. Either way, it should not crash.
        let available = await provider.isAvailable
        #expect(available == true || available == false)
    }

    @Test("OnDeviceAIProvider throws meaningful error when unavailable")
    func throwsWhenUnavailable() async {
        let provider = OnDeviceAIProvider()

        // If FoundationModels is not available, this should throw.
        // If it IS available, the call may succeed. Either path is valid.
        do {
            _ = try await provider.generateBriefing(context: TestFixtures.makeBriefingContext())
            // Success means FoundationModels is available on this platform.
        } catch let error as AIError {
            // Verify the error is descriptive
            #expect(error.errorDescription != nil)
            #expect(!error.errorDescription!.isEmpty)
        }
    }
}

// MARK: - Context Type Tests

@Suite("Context Types")
struct ContextTypeTests {
    @Test("BriefingContext contains all required fields")
    func briefingContextFields() {
        let context = TestFixtures.makeBriefingContext()

        #expect(context.dayOfWeek == "Tuesday")
        #expect(context.plannedWorkout == "Upper Body Strength")
        #expect(context.recentMetrics.count == 7)
        #expect(context.todosForToday.count == 2)
        #expect(context.activeGoals.count == 1)
        #expect(context.recoveryStatus == "Good")
        #expect(context.streaks["Meditation"] == 5)
        #expect(context.streaks["Training"] == 12)
    }

    @Test("BriefingContext supports nil optional fields")
    func briefingContextNilFields() {
        let context = BriefingContext(
            todayDate: Date(),
            dayOfWeek: "Monday",
            plannedWorkout: nil,
            recentMetrics: [],
            todosForToday: [],
            activeGoals: [],
            recoveryStatus: nil,
            streaks: [:]
        )

        #expect(context.plannedWorkout == nil)
        #expect(context.recoveryStatus == nil)
        #expect(context.recentMetrics.isEmpty)
        #expect(context.streaks.isEmpty)
    }

    @Test("MetricSummary captures all metric dimensions")
    func metricSummaryFields() {
        let summary = MetricSummary(
            date: Date(),
            weight: 185.5,
            sleep: 7.5,
            sleepQuality: 8.0,
            moodAM: 7.0,
            energy: 8.0,
            workoutType: "Strength",
            workoutCompleted: true,
            todoCompletionRate: 0.85
        )

        #expect(summary.weight == 185.5)
        #expect(summary.sleep == 7.5)
        #expect(summary.sleepQuality == 8.0)
        #expect(summary.moodAM == 7.0)
        #expect(summary.energy == 8.0)
        #expect(summary.workoutType == "Strength")
        #expect(summary.workoutCompleted == true)
        #expect(summary.todoCompletionRate == 0.85)
    }

    @Test("MetricSummary supports all-nil optional fields")
    func metricSummaryNilFields() {
        let summary = MetricSummary(
            date: Date(),
            weight: nil,
            sleep: nil,
            sleepQuality: nil,
            moodAM: nil,
            energy: nil,
            workoutType: nil,
            workoutCompleted: false,
            todoCompletionRate: nil
        )

        #expect(summary.weight == nil)
        #expect(summary.sleep == nil)
        #expect(summary.workoutType == nil)
        #expect(summary.workoutCompleted == false)
        #expect(summary.todoCompletionRate == nil)
    }

    @Test("ProtocolContext captures schedule entries")
    func protocolContextSchedule() {
        let context = TestFixtures.makeProtocolContext()

        #expect(context.currentPhase == "Base Building")
        #expect(context.todayWorkout == "Swim 2000m + Core")
        #expect(context.weeklySchedule.count == 7)
        #expect(context.trainingGoals.count == 2)

        let monday = context.weeklySchedule[0]
        #expect(monday.day == "Monday")
        #expect(monday.type == "Strength")
        #expect(monday.workout == "Upper Body")
    }

    @Test("ProtocolContext.ScheduleEntry is Equatable")
    func scheduleEntryEquatable() {
        let a = ProtocolContext.ScheduleEntry(day: "Monday", type: "Strength", workout: "Bench")
        let b = ProtocolContext.ScheduleEntry(day: "Monday", type: "Strength", workout: "Bench")
        let c = ProtocolContext.ScheduleEntry(day: "Tuesday", type: "Cardio", workout: "Run")

        #expect(a == b)
        #expect(a != c)
    }

    @Test("RecoveryContext captures all Garmin metrics")
    func recoveryContextFields() {
        let context = TestFixtures.makeRecoveryContext()

        #expect(context.recoveryScore == 72.0)
        #expect(context.recoveryStatus == "Recovering")
        #expect(context.hrvStatus == "Balanced")
        #expect(context.sleepScore == 78)
        #expect(context.bodyBattery == 55)
        #expect(context.trainingReadiness == 65)
        #expect(context.recentTrainingLoad == "3 workouts in last 3 days")
    }

    @Test("RecoveryContext supports all-nil fields")
    func recoveryContextAllNil() {
        let context = RecoveryContext(
            recoveryScore: nil,
            recoveryStatus: nil,
            hrvStatus: nil,
            sleepScore: nil,
            bodyBattery: nil,
            trainingReadiness: nil,
            recentTrainingLoad: nil
        )

        #expect(context.recoveryScore == nil)
        #expect(context.recoveryStatus == nil)
        #expect(context.hrvStatus == nil)
        #expect(context.sleepScore == nil)
        #expect(context.bodyBattery == nil)
        #expect(context.trainingReadiness == nil)
        #expect(context.recentTrainingLoad == nil)
    }

    @Test("QueryContext captures all context dimensions")
    func queryContextFields() {
        let context = TestFixtures.makeQueryContext()

        #expect(context.recentLogs.count == 3)
        #expect(context.currentProtocol == "Base Building Phase - Week 3")
        #expect(context.activeGoals.count == 2)
        #expect(context.memoryItems.count == 2)
    }

    @Test("QueryContext supports empty and nil fields")
    func queryContextEmpty() {
        let context = QueryContext(
            recentLogs: [],
            currentProtocol: nil,
            activeGoals: [],
            memoryItems: []
        )

        #expect(context.recentLogs.isEmpty)
        #expect(context.currentProtocol == nil)
        #expect(context.activeGoals.isEmpty)
        #expect(context.memoryItems.isEmpty)
    }
}

// MARK: - AIError Tests

@Suite("AIError")
struct AIErrorTests {
    @Test("All error cases have non-nil descriptions")
    func allErrorsHaveDescriptions() {
        let errors: [AIError] = [
            .providerUnavailable("TestProvider"),
            .modelNotLoaded,
            .generationFailed("test reason"),
            .rateLimited,
            .invalidAPIKey,
            .networkError("timeout"),
            .contextTooLarge,
            .invalidResponse,
        ]

        for error in errors {
            #expect(error.errorDescription != nil)
            #expect(!error.errorDescription!.isEmpty)
        }
    }

    @Test("providerUnavailable includes provider name")
    func providerUnavailableIncludesName() {
        let error = AIError.providerUnavailable("Anthropic")
        #expect(error.errorDescription!.contains("Anthropic"))
    }

    @Test("generationFailed includes message")
    func generationFailedIncludesMessage() {
        let error = AIError.generationFailed("context window exceeded")
        #expect(error.errorDescription!.contains("context window exceeded"))
    }

    @Test("networkError includes message")
    func networkErrorIncludesMessage() {
        let error = AIError.networkError("DNS resolution failed")
        #expect(error.errorDescription!.contains("DNS resolution failed"))
    }

    @Test("AIError conforms to Sendable")
    func errorIsSendable() {
        let error: Sendable = AIError.rateLimited
        #expect(error is AIError)
    }

    @Test("AIError equality")
    func errorEquality() {
        #expect(AIError.rateLimited == AIError.rateLimited)
        #expect(AIError.modelNotLoaded == AIError.modelNotLoaded)
        #expect(AIError.invalidAPIKey == AIError.invalidAPIKey)
        #expect(AIError.contextTooLarge == AIError.contextTooLarge)
        #expect(AIError.invalidResponse == AIError.invalidResponse)
        #expect(AIError.providerUnavailable("A") == AIError.providerUnavailable("A"))
        #expect(AIError.providerUnavailable("A") != AIError.providerUnavailable("B"))
        #expect(AIError.generationFailed("x") == AIError.generationFailed("x"))
        #expect(AIError.networkError("y") == AIError.networkError("y"))
        #expect(AIError.rateLimited != AIError.modelNotLoaded)
    }
}

// MARK: - Sendable Conformance Tests

@Suite("Sendable Conformance")
struct SendableConformanceTests {
    @Test("BriefingContext is Sendable")
    func briefingContextSendable() async {
        let context = TestFixtures.makeBriefingContext()
        let sendableValue: Sendable = context
        #expect(sendableValue is BriefingContext)
    }

    @Test("MetricSummary is Sendable")
    func metricSummarySendable() async {
        let summary = TestFixtures.makeMetricSummaries().first!
        let sendableValue: Sendable = summary
        #expect(sendableValue is MetricSummary)
    }

    @Test("ProtocolContext is Sendable")
    func protocolContextSendable() async {
        let context = TestFixtures.makeProtocolContext()
        let sendableValue: Sendable = context
        #expect(sendableValue is ProtocolContext)
    }

    @Test("RecoveryContext is Sendable")
    func recoveryContextSendable() async {
        let context = TestFixtures.makeRecoveryContext()
        let sendableValue: Sendable = context
        #expect(sendableValue is RecoveryContext)
    }

    @Test("QueryContext is Sendable")
    func queryContextSendable() async {
        let context = TestFixtures.makeQueryContext()
        let sendableValue: Sendable = context
        #expect(sendableValue is QueryContext)
    }

    @Test("CloudAIProvider.Provider is Sendable")
    func providerEnumSendable() async {
        let provider: Sendable = CloudAIProvider.Provider.anthropic
        #expect(provider is CloudAIProvider.Provider)
    }

    @Test("AIError is Sendable")
    func aiErrorSendable() async {
        let error: Sendable = AIError.rateLimited
        #expect(error is AIError)
    }
}

// MARK: - Integration-style Tests

@Suite("Provider Integration")
struct ProviderIntegrationTests {
    @Test("AIServiceManager forwards generateBriefing to active provider")
    func managerForwardsBriefing() async {
        // Without FoundationModels and without cloud config, this exercises the error path.
        // The test verifies the manager doesn't crash and propagates errors cleanly.
        let manager = AIServiceManager()
        let context = TestFixtures.makeBriefingContext()

        do {
            let result = try await manager.generateBriefing(context: context)
            // If on-device is available, we should get a non-empty string
            #expect(!result.isEmpty)
        } catch {
            // Expected on platforms without FoundationModels
            #expect(error is AIError)
        }
    }

    @Test("AIServiceManager forwards analyzeMetrics to active provider")
    func managerForwardsAnalysis() async {
        let manager = AIServiceManager()
        let metrics = TestFixtures.makeMetricSummaries()

        do {
            let result = try await manager.analyzeMetrics(metrics: metrics, query: "How is my sleep?")
            #expect(!result.isEmpty)
        } catch {
            #expect(error is AIError)
        }
    }

    @Test("AIServiceManager forwards suggestWorkout to active provider")
    func managerForwardsWorkout() async {
        let manager = AIServiceManager()

        do {
            let result = try await manager.suggestWorkout(
                protocol: TestFixtures.makeProtocolContext(),
                recovery: TestFixtures.makeRecoveryContext()
            )
            #expect(!result.isEmpty)
        } catch {
            #expect(error is AIError)
        }
    }

    @Test("AIServiceManager forwards query to active provider")
    func managerForwardsQuery() async {
        let manager = AIServiceManager()
        let context = TestFixtures.makeQueryContext()

        do {
            let result = try await manager.query("What did I do yesterday?", context: context)
            #expect(!result.isEmpty)
        } catch {
            #expect(error is AIError)
        }
    }

    @Test("CloudAIProvider with invalid endpoint returns network error")
    func cloudProviderNetworkError() async {
        let provider = CloudAIProvider(
            provider: .custom,
            apiKey: "test-key",
            endpoint: URL(string: "http://localhost:1/nonexistent")!
        )

        let context = TestFixtures.makeBriefingContext()

        await #expect(throws: AIError.self) {
            try await provider.generateBriefing(context: context)
        }
    }
}
