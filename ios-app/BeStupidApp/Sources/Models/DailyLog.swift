import Foundation

struct DailyLog: Identifiable, Codable, Sendable, Equatable {
    let id: UUID
    var date: Date
    var title: String
    var tags: [String]

    // MARK: - Quick Log Metrics

    var weight: Double?
    var sleep: Double?
    var sleepQuality: Double?
    var moodAM: Double?
    var moodPM: Double?
    var energy: Double?
    var focus: Double?

    // MARK: - Training

    var plannedWorkout: String?
    var trainingActivities: [TrainingActivity]
    var strengthExercises: [StrengthEntry]

    // MARK: - Todos & Habits

    var todos: [TodoItem]
    var habits: [HabitEntry]

    // MARK: - Nutrition

    var caloriesSoFar: Int?
    var proteinSoFar: Int?
    var nutritionLineItems: [NutritionEntry]

    // MARK: - Planning

    var topThreeForTomorrow: [String]
    var dailyBriefing: String?

    init(
        id: UUID = UUID(),
        date: Date = Date(),
        title: String? = nil,
        tags: [String] = [],
        weight: Double? = nil,
        sleep: Double? = nil,
        sleepQuality: Double? = nil,
        moodAM: Double? = nil,
        moodPM: Double? = nil,
        energy: Double? = nil,
        focus: Double? = nil,
        plannedWorkout: String? = nil,
        trainingActivities: [TrainingActivity] = [],
        strengthExercises: [StrengthEntry] = [],
        todos: [TodoItem] = [],
        habits: [HabitEntry] = [],
        caloriesSoFar: Int? = nil,
        proteinSoFar: Int? = nil,
        nutritionLineItems: [NutritionEntry] = [],
        topThreeForTomorrow: [String] = [],
        dailyBriefing: String? = nil
    ) {
        self.id = id
        self.date = date
        self.title = title ?? DateFormatting.logFileName(for: date)
        self.tags = tags
        self.weight = weight
        self.sleep = sleep
        self.sleepQuality = sleepQuality
        self.moodAM = moodAM
        self.moodPM = moodPM
        self.energy = energy
        self.focus = focus
        self.plannedWorkout = plannedWorkout
        self.trainingActivities = trainingActivities
        self.strengthExercises = strengthExercises
        self.todos = todos
        self.habits = habits
        self.caloriesSoFar = caloriesSoFar
        self.proteinSoFar = proteinSoFar
        self.nutritionLineItems = nutritionLineItems
        self.topThreeForTomorrow = topThreeForTomorrow
        self.dailyBriefing = dailyBriefing
    }

    // MARK: - Computed Properties

    /// Fraction of todos completed (0.0 - 1.0). Returns nil if no todos exist.
    var todoCompletionRate: Double? {
        guard !todos.isEmpty else { return nil }
        let completed = todos.filter(\.isCompleted).count
        return Double(completed) / Double(todos.count)
    }

    /// Fraction of habits completed (0.0 - 1.0). Returns nil if no habits exist.
    var habitCompletionRate: Double? {
        guard !habits.isEmpty else { return nil }
        let completed = habits.filter(\.isCompleted).count
        return Double(completed) / Double(habits.count)
    }

    /// Total calories from all nutrition line items.
    var totalCaloriesFromItems: Int {
        nutritionLineItems.compactMap(\.calories).reduce(0, +)
    }

    /// Total protein grams from all nutrition line items.
    var totalProteinFromItems: Int {
        nutritionLineItems.compactMap(\.proteinG).reduce(0, +)
    }

    /// Total strength volume across all exercises.
    var totalStrengthVolume: Double {
        strengthExercises.reduce(0.0) { $0 + $1.totalVolume }
    }
}
