import Foundation

// MARK: - AI Service Protocol (SOLID: Interface Segregation, Dependency Inversion)

/// Core AI capability that all providers must conform to.
/// Designed to be provider-agnostic: on-device, cloud, or custom backends
/// all implement this same interface.
protocol AIService: Sendable {
    /// Generate a daily briefing from context.
    func generateBriefing(context: BriefingContext) async throws -> String

    /// Analyze metrics and answer a question.
    func analyzeMetrics(metrics: [MetricSummary], query: String) async throws -> String

    /// Suggest workout modifications based on protocol and recovery state.
    func suggestWorkout(
        protocol: ProtocolContext,
        recovery: RecoveryContext
    ) async throws -> String

    /// Free-form query about the user's data.
    func query(_ question: String, context: QueryContext) async throws -> String

    /// Human-readable name for this provider (e.g., "Apple On-Device", "Anthropic").
    var providerName: String { get }

    /// Whether this provider can function without network connectivity.
    var isAvailableOffline: Bool { get }

    /// Whether the provider is currently ready to accept requests.
    var isAvailable: Bool { get async }
}

// MARK: - Context Types (value types for AI prompts)

/// All context needed to generate a morning briefing.
struct BriefingContext: Sendable, Equatable {
    let todayDate: Date
    let dayOfWeek: String
    let plannedWorkout: String?
    let recentMetrics: [MetricSummary]
    let todosForToday: [String]
    let activeGoals: [String]
    let recoveryStatus: String?
    let streaks: [String: Int]
}

/// Summary of a single day's metrics for AI analysis.
struct MetricSummary: Sendable, Equatable {
    let date: Date
    let weight: Double?
    let sleep: Double?
    let sleepQuality: Double?
    let moodAM: Double?
    let energy: Double?
    let workoutType: String?
    let workoutCompleted: Bool
    let todoCompletionRate: Double?
}

/// Current training protocol context for workout suggestions.
struct ProtocolContext: Sendable, Equatable {
    let currentPhase: String
    let todayWorkout: String
    let weeklySchedule: [ScheduleEntry]
    let trainingGoals: [String]

    /// A single entry in the weekly schedule, used instead of a tuple for Sendable conformance.
    struct ScheduleEntry: Sendable, Equatable {
        let day: String
        let type: String
        let workout: String
    }
}

/// Recovery and readiness data from Garmin or manual entry.
struct RecoveryContext: Sendable, Equatable {
    let recoveryScore: Double?
    let recoveryStatus: String?
    let hrvStatus: String?
    let sleepScore: Int?
    let bodyBattery: Int?
    let trainingReadiness: Int?
    let recentTrainingLoad: String?
}

/// Context for free-form natural language queries.
struct QueryContext: Sendable, Equatable {
    let recentLogs: [String]
    let currentProtocol: String?
    let activeGoals: [String]
    let memoryItems: [String]
}

// MARK: - AI Errors

enum AIError: Error, LocalizedError, Sendable {
    case providerUnavailable(String)
    case modelNotLoaded
    case generationFailed(String)
    case rateLimited
    case invalidAPIKey
    case networkError(String)
    case contextTooLarge
    case invalidResponse

    var errorDescription: String? {
        switch self {
        case .providerUnavailable(let name):
            return "AI provider '\(name)' is not available"
        case .modelNotLoaded:
            return "On-device model is not loaded"
        case .generationFailed(let msg):
            return "Generation failed: \(msg)"
        case .rateLimited:
            return "API rate limit reached. Try again later."
        case .invalidAPIKey:
            return "Invalid API key"
        case .networkError(let msg):
            return "Network error: \(msg)"
        case .contextTooLarge:
            return "Context too large for model"
        case .invalidResponse:
            return "Received an invalid response from the AI provider"
        }
    }
}
