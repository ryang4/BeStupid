import Foundation

// MARK: - ProtocolDay

struct ProtocolDay: Identifiable, Codable, Sendable, Equatable {
    let id: UUID
    var dayOfWeek: String
    var workoutType: String
    var workout: String

    init(
        id: UUID = UUID(),
        dayOfWeek: String,
        workoutType: String,
        workout: String
    ) {
        self.id = id
        self.dayOfWeek = dayOfWeek
        self.workoutType = workoutType
        self.workout = workout
    }
}

// MARK: - WeeklyProtocol

struct WeeklyProtocol: Identifiable, Codable, Sendable, Equatable {
    let id: UUID
    var date: Date
    var title: String
    var weekNumber: String
    var phase: String
    var focus: String
    var targetCompliance: Double
    var schedule: [ProtocolDay]
    var trainingGoals: [String]
    var cardioTargets: [String: String]
    var strengthTargets: [String]
    var aiRationale: String?

    init(
        id: UUID = UUID(),
        date: Date,
        title: String,
        weekNumber: String,
        phase: String,
        focus: String,
        targetCompliance: Double = 0.8,
        schedule: [ProtocolDay] = [],
        trainingGoals: [String] = [],
        cardioTargets: [String: String] = [:],
        strengthTargets: [String] = [],
        aiRationale: String? = nil
    ) {
        self.id = id
        self.date = date
        self.title = title
        self.weekNumber = weekNumber
        self.phase = phase
        self.focus = focus
        self.targetCompliance = targetCompliance
        self.schedule = schedule
        self.trainingGoals = trainingGoals
        self.cardioTargets = cardioTargets
        self.strengthTargets = strengthTargets
        self.aiRationale = aiRationale
    }

    /// Number of scheduled workout days.
    var totalWorkoutDays: Int {
        schedule.count
    }

    /// Returns the ProtocolDay for a given day-of-week string, if it exists.
    func day(for dayOfWeek: String) -> ProtocolDay? {
        schedule.first { $0.dayOfWeek.lowercased() == dayOfWeek.lowercased() }
    }
}
