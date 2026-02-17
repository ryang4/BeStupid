import Foundation

// MARK: - MetricField

enum MetricField: String, Codable, Sendable, CaseIterable, Equatable {
    case weight
    case sleep
    case sleepQuality
    case moodAM
    case moodPM
    case energy
    case focus
    case swimDistance
    case bikeDistance
    case runDistance
    case swimDuration
    case bikeDuration
    case runDuration
    case calories
    case protein
    case todoCompletion
    case habitCompletion

    var displayName: String {
        switch self {
        case .weight: return "Weight"
        case .sleep: return "Sleep"
        case .sleepQuality: return "Sleep Quality"
        case .moodAM: return "Mood (AM)"
        case .moodPM: return "Mood (PM)"
        case .energy: return "Energy"
        case .focus: return "Focus"
        case .swimDistance: return "Swim Distance"
        case .bikeDistance: return "Bike Distance"
        case .runDistance: return "Run Distance"
        case .swimDuration: return "Swim Duration"
        case .bikeDuration: return "Bike Duration"
        case .runDuration: return "Run Duration"
        case .calories: return "Calories"
        case .protein: return "Protein"
        case .todoCompletion: return "Todo Completion"
        case .habitCompletion: return "Habit Completion"
        }
    }

    /// The unit suffix for display (e.g., "lbs", "hrs", "/10").
    var unitSuffix: String {
        switch self {
        case .weight: return "lbs"
        case .sleep: return "hrs"
        case .sleepQuality, .moodAM, .moodPM, .energy, .focus: return "/10"
        case .swimDistance: return "m"
        case .bikeDistance, .runDistance: return "km"
        case .swimDuration, .bikeDuration, .runDuration: return "min"
        case .calories: return "kcal"
        case .protein: return "g"
        case .todoCompletion, .habitCompletion: return "%"
        }
    }
}

// MARK: - MetricSource

enum MetricSource: String, Codable, Sendable, Equatable {
    case manual
    case garmin
    case healthkit
    case parsed

    var displayName: String {
        switch self {
        case .manual: return "Manual"
        case .garmin: return "Garmin"
        case .healthkit: return "HealthKit"
        case .parsed: return "Parsed"
        }
    }
}

// MARK: - MetricDataPoint

struct MetricDataPoint: Identifiable, Codable, Sendable, Equatable {
    let id: UUID
    var date: Date
    var field: MetricField
    var value: Double
    var source: MetricSource

    init(
        id: UUID = UUID(),
        date: Date,
        field: MetricField,
        value: Double,
        source: MetricSource = .manual
    ) {
        self.id = id
        self.date = date
        self.field = field
        self.value = value
        self.source = source
    }
}
