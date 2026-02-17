import Foundation
import SwiftData

@Model
final class CachedDailyLog {

    // MARK: - Unique Key

    /// Date string in "yyyy-MM-dd" format, used as the unique key for upsert.
    @Attribute(.unique) var dateString: String

    /// The actual date value for range queries and sorting.
    var date: Date

    /// Log title (typically the markdown file name).
    var title: String

    /// Tags associated with this day's log.
    var tags: [String]

    // MARK: - Denormalized Metrics (for fast chart queries)

    var weight: Double?
    var sleep: Double?
    var sleepQuality: Double?
    var moodAM: Double?
    var moodPM: Double?
    var energy: Double?
    var focus: Double?

    // MARK: - Workout Summary (denormalized)

    /// Primary workout type for the day (e.g. "Swim", "Bike", "Strength").
    var workoutType: String?

    /// Whether any workout was completed for this day.
    var workoutCompleted: Bool

    /// Total training duration in minutes across all activities.
    var totalTrainingMinutes: Double?

    // MARK: - Completion Rates

    var todoTotal: Int
    var todoCompleted: Int
    var habitTotal: Int
    var habitCompleted: Int

    // MARK: - Nutrition

    var calories: Int?
    var protein: Int?

    // MARK: - Cache Invalidation

    /// SHA-256 hash of the source markdown content. When this matches,
    /// we skip re-caching to avoid unnecessary writes.
    var contentHash: String

    // MARK: - Full Serialized Log

    /// JSON-encoded `DailyLog` for the detail view so we don't re-parse markdown.
    var serializedLog: Data?

    // MARK: - Init

    init(from log: DailyLog, contentHash: String) {
        let formatter = DateFormatting.dailyLogFormatter
        self.dateString = formatter.string(from: log.date)
        self.date = log.date
        self.title = log.title
        self.tags = log.tags

        self.weight = log.weight
        self.sleep = log.sleep
        self.sleepQuality = log.sleepQuality
        self.moodAM = log.moodAM
        self.moodPM = log.moodPM
        self.energy = log.energy
        self.focus = log.focus

        // Workout summary: use the first training activity type if present
        self.workoutType = log.trainingActivities.first?.type ?? log.plannedWorkout
        self.workoutCompleted = !log.trainingActivities.isEmpty || !log.strengthExercises.isEmpty
        self.totalTrainingMinutes = Self.computeTotalTrainingMinutes(from: log)

        self.todoTotal = log.todos.count
        self.todoCompleted = log.todos.filter(\.isCompleted).count
        self.habitTotal = log.habits.count
        self.habitCompleted = log.habits.filter(\.isCompleted).count

        self.calories = log.caloriesSoFar
        self.protein = log.proteinSoFar

        self.contentHash = contentHash

        self.serializedLog = try? JSONEncoder().encode(log)
    }

    // MARK: - Conversion

    /// Deserializes the cached `DailyLog` from the stored JSON blob.
    func toDailyLog() -> DailyLog? {
        guard let data = serializedLog else { return nil }
        return try? JSONDecoder().decode(DailyLog.self, from: data)
    }

    // MARK: - Computed Properties

    /// Fraction of todos completed (0.0 - 1.0). Returns 0 if no todos exist.
    var todoCompletionRate: Double {
        guard todoTotal > 0 else { return 0 }
        return Double(todoCompleted) / Double(todoTotal)
    }

    /// Fraction of habits completed (0.0 - 1.0). Returns 0 if no habits exist.
    var habitCompletionRate: Double {
        guard habitTotal > 0 else { return 0 }
        return Double(habitCompleted) / Double(habitTotal)
    }

    // MARK: - Private Helpers

    private static func computeTotalTrainingMinutes(from log: DailyLog) -> Double? {
        let activityMinutes = log.trainingActivities.compactMap(\.durationMinutes)
        guard !activityMinutes.isEmpty else { return nil }
        return activityMinutes.reduce(0, +)
    }
}
