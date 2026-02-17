import Foundation
import SwiftData
import CryptoKit

/// Statistics about the current state of the SwiftData cache.
struct CacheStats: Sendable {
    let dailyLogCount: Int
    let metricCount: Int
    let workoutCount: Int
    let exerciseCount: Int
    let oldestLogDate: Date?
    let newestLogDate: Date?
}

/// Actor-isolated service that manages the SwiftData read cache.
///
/// All writes go through this actor to ensure thread safety. The cache is
/// purely a performance optimization -- it can always be rebuilt by re-parsing
/// the git repository's markdown files.
@ModelActor
actor CacheManager {

    // MARK: - Daily Logs

    /// Upserts a daily log into the cache.
    ///
    /// If a cached entry already exists for this date with the same content hash,
    /// the write is skipped entirely. This avoids unnecessary churn on unchanged files.
    ///
    /// - Parameters:
    ///   - log: The parsed `DailyLog` domain model.
    ///   - markdownContent: The raw markdown source, used to compute the content hash.
    func cacheDailyLog(_ log: DailyLog, markdownContent: String) throws {
        let hash = Self.sha256Hex(markdownContent)
        let dateString = DateFormatting.dailyLogFormatter.string(from: log.date)

        let predicate = #Predicate<CachedDailyLog> { cached in
            cached.dateString == dateString
        }
        let descriptor = FetchDescriptor(predicate: predicate)
        let existing = try modelContext.fetch(descriptor)

        if let cached = existing.first {
            // Already cached with identical content -- skip
            if cached.contentHash == hash {
                return
            }
            // Content changed -- update in place
            updateCachedLog(cached, from: log, hash: hash)
        } else {
            // New entry
            let cached = CachedDailyLog(from: log, contentHash: hash)
            modelContext.insert(cached)
        }

        try modelContext.save()
    }

    /// Fetches cached logs within a date range, sorted by date descending.
    ///
    /// - Parameters:
    ///   - startDate: Inclusive start of the range.
    ///   - endDate: Inclusive end of the range.
    /// - Returns: Array of `CachedDailyLog` models.
    func fetchLogs(from startDate: Date, to endDate: Date) throws -> [CachedDailyLog] {
        let predicate = #Predicate<CachedDailyLog> { cached in
            cached.date >= startDate && cached.date <= endDate
        }
        var descriptor = FetchDescriptor(predicate: predicate)
        descriptor.sortBy = [SortDescriptor(\.date, order: .reverse)]
        return try modelContext.fetch(descriptor)
    }

    /// Fetches a single cached log by date string.
    ///
    /// - Parameter date: The date to look up.
    /// - Returns: The cached log, or `nil` if not found.
    func fetchLog(for date: Date) throws -> CachedDailyLog? {
        let dateString = DateFormatting.dailyLogFormatter.string(from: date)
        let predicate = #Predicate<CachedDailyLog> { cached in
            cached.dateString == dateString
        }
        let descriptor = FetchDescriptor(predicate: predicate)
        return try modelContext.fetch(descriptor).first
    }

    // MARK: - Metrics

    /// Caches an array of metric data points, upserting by composite key.
    ///
    /// - Parameter metrics: The data points to cache.
    func cacheMetrics(_ metrics: [MetricDataPoint]) throws {
        for dataPoint in metrics {
            let key = CachedMetric.makeCompositeKey(date: dataPoint.date, field: dataPoint.field)
            let predicate = #Predicate<CachedMetric> { cached in
                cached.compositeKey == key
            }
            let descriptor = FetchDescriptor(predicate: predicate)
            let existing = try modelContext.fetch(descriptor)

            if let cached = existing.first {
                cached.value = dataPoint.value
                cached.source = dataPoint.source.rawValue
                cached.date = dataPoint.date
            } else {
                let cached = CachedMetric(from: dataPoint)
                modelContext.insert(cached)
            }
        }

        try modelContext.save()
    }

    /// Fetches metrics for a specific field within a date range, sorted by date ascending.
    ///
    /// - Parameters:
    ///   - field: The metric field to query (e.g. `.weight`, `.sleep`).
    ///   - startDate: Inclusive start of the range.
    ///   - endDate: Inclusive end of the range.
    /// - Returns: Array of `CachedMetric` models.
    func fetchMetrics(
        field: MetricField,
        from startDate: Date,
        to endDate: Date
    ) throws -> [CachedMetric] {
        let fieldRaw = field.rawValue
        let predicate = #Predicate<CachedMetric> { cached in
            cached.field == fieldRaw && cached.date >= startDate && cached.date <= endDate
        }
        var descriptor = FetchDescriptor(predicate: predicate)
        descriptor.sortBy = [SortDescriptor(\.date, order: .forward)]
        return try modelContext.fetch(descriptor)
    }

    /// Fetches the most recent cached value for a given metric field.
    ///
    /// - Parameter field: The metric field to query.
    /// - Returns: The most recent `CachedMetric`, or `nil` if none exists.
    func latestMetric(field: MetricField) throws -> CachedMetric? {
        let fieldRaw = field.rawValue
        let predicate = #Predicate<CachedMetric> { cached in
            cached.field == fieldRaw
        }
        var descriptor = FetchDescriptor(predicate: predicate)
        descriptor.sortBy = [SortDescriptor(\.date, order: .reverse)]
        descriptor.fetchLimit = 1
        return try modelContext.fetch(descriptor).first
    }

    // MARK: - Workouts

    /// Caches a workout session, upserting by workout ID.
    ///
    /// - Parameter session: The `WorkoutSession` to cache.
    func cacheWorkout(_ session: WorkoutSession) throws {
        let sessionId = session.id.uuidString
        let predicate = #Predicate<CachedWorkout> { cached in
            cached.workoutId == sessionId
        }
        let descriptor = FetchDescriptor(predicate: predicate)
        let existing = try modelContext.fetch(descriptor)

        if let cached = existing.first {
            updateCachedWorkout(cached, from: session)
        } else {
            let cached = CachedWorkout(from: session)
            modelContext.insert(cached)
        }

        try modelContext.save()
    }

    /// Fetches recent workouts, optionally filtered by type.
    ///
    /// - Parameters:
    ///   - limit: Maximum number of results to return.
    ///   - type: Optional workout type filter (e.g. "Swim"). Pass `nil` for all types.
    /// - Returns: Array of `CachedWorkout` models sorted by start time descending.
    func fetchWorkouts(limit: Int, type: String? = nil) throws -> [CachedWorkout] {
        let predicate: Predicate<CachedWorkout>?
        if let type {
            predicate = #Predicate<CachedWorkout> { cached in
                cached.workoutType == type
            }
        } else {
            predicate = nil
        }

        var descriptor: FetchDescriptor<CachedWorkout>
        if let predicate {
            descriptor = FetchDescriptor(predicate: predicate)
        } else {
            descriptor = FetchDescriptor<CachedWorkout>()
        }
        descriptor.sortBy = [SortDescriptor(\.startTime, order: .reverse)]
        descriptor.fetchLimit = limit
        return try modelContext.fetch(descriptor)
    }

    // MARK: - Exercises

    /// Caches an exercise, upserting by name.
    ///
    /// - Parameter exercise: The `Exercise` to cache.
    func cacheExercise(_ exercise: Exercise) throws {
        let exerciseName = exercise.name
        let predicate = #Predicate<CachedExercise> { cached in
            cached.name == exerciseName
        }
        let descriptor = FetchDescriptor(predicate: predicate)
        let existing = try modelContext.fetch(descriptor)

        if let cached = existing.first {
            cached.category = exercise.category.rawValue
            cached.muscleGroup = exercise.muscleGroup
            cached.equipment = exercise.equipment
            cached.isCustom = exercise.isCustom
        } else {
            let cached = CachedExercise(from: exercise)
            modelContext.insert(cached)
        }

        try modelContext.save()
    }

    /// Fetches all exercises, optionally filtered by category.
    ///
    /// - Parameter category: Optional category filter. Pass `nil` for all categories.
    /// - Returns: Array of `CachedExercise` models sorted by name.
    func fetchExercises(category: ExerciseCategory? = nil) throws -> [CachedExercise] {
        let predicate: Predicate<CachedExercise>?
        if let category {
            let categoryRaw = category.rawValue
            predicate = #Predicate<CachedExercise> { cached in
                cached.category == categoryRaw
            }
        } else {
            predicate = nil
        }

        var descriptor: FetchDescriptor<CachedExercise>
        if let predicate {
            descriptor = FetchDescriptor(predicate: predicate)
        } else {
            descriptor = FetchDescriptor<CachedExercise>()
        }
        descriptor.sortBy = [SortDescriptor(\.name, order: .forward)]
        return try modelContext.fetch(descriptor)
    }

    /// Updates an exercise's personal records by name.
    ///
    /// Only updates a PR field if the new value exceeds the current record.
    ///
    /// - Parameters:
    ///   - name: The exercise name to look up.
    ///   - weight: New weight value (nil to skip).
    ///   - reps: New reps value (nil to skip).
    ///   - volume: New volume value (nil to skip).
    func updateExercisePR(
        name: String,
        weight: Double?,
        reps: Int?,
        volume: Double?
    ) throws {
        let predicate = #Predicate<CachedExercise> { cached in
            cached.name == name
        }
        let descriptor = FetchDescriptor(predicate: predicate)
        guard let cached = try modelContext.fetch(descriptor).first else {
            return
        }

        cached.updatePR(weight: weight, reps: reps, volume: volume, date: Date())
        try modelContext.save()
    }

    // MARK: - Cache Management

    /// Rebuilds the entire daily log and metric cache from scratch.
    ///
    /// This deletes all existing cached daily logs and metrics, then re-caches
    /// everything from the provided parsed data. Workouts and exercises are
    /// intentionally left untouched as they have independent lifecycles.
    ///
    /// - Parameters:
    ///   - logs: All parsed `DailyLog` instances.
    ///   - markdownContents: A dictionary mapping date strings ("yyyy-MM-dd") to
    ///     the raw markdown content for content hash computation.
    func rebuildCache(logs: [DailyLog], markdownContents: [String: String]) throws {
        // Clear existing cached data
        try modelContext.delete(model: CachedDailyLog.self)
        try modelContext.delete(model: CachedMetric.self)

        // Re-cache all logs
        for log in logs {
            let dateString = DateFormatting.dailyLogFormatter.string(from: log.date)
            let content = markdownContents[dateString] ?? ""
            let hash = Self.sha256Hex(content)
            let cached = CachedDailyLog(from: log, contentHash: hash)
            modelContext.insert(cached)
        }

        try modelContext.save()
    }

    /// Returns statistics about the current state of the cache.
    func cacheStats() throws -> CacheStats {
        let logCount = try modelContext.fetchCount(FetchDescriptor<CachedDailyLog>())
        let metricCount = try modelContext.fetchCount(FetchDescriptor<CachedMetric>())
        let workoutCount = try modelContext.fetchCount(FetchDescriptor<CachedWorkout>())
        let exerciseCount = try modelContext.fetchCount(FetchDescriptor<CachedExercise>())

        // Find oldest and newest log dates
        var oldestDescriptor = FetchDescriptor<CachedDailyLog>()
        oldestDescriptor.sortBy = [SortDescriptor(\.date, order: .forward)]
        oldestDescriptor.fetchLimit = 1
        let oldest = try modelContext.fetch(oldestDescriptor).first?.date

        var newestDescriptor = FetchDescriptor<CachedDailyLog>()
        newestDescriptor.sortBy = [SortDescriptor(\.date, order: .reverse)]
        newestDescriptor.fetchLimit = 1
        let newest = try modelContext.fetch(newestDescriptor).first?.date

        return CacheStats(
            dailyLogCount: logCount,
            metricCount: metricCount,
            workoutCount: workoutCount,
            exerciseCount: exerciseCount,
            oldestLogDate: oldest,
            newestLogDate: newest
        )
    }

    // MARK: - Private Helpers

    /// Updates an existing `CachedDailyLog` with new values from a `DailyLog`.
    private func updateCachedLog(_ cached: CachedDailyLog, from log: DailyLog, hash: String) {
        cached.date = log.date
        cached.title = log.title
        cached.tags = log.tags

        cached.weight = log.weight
        cached.sleep = log.sleep
        cached.sleepQuality = log.sleepQuality
        cached.moodAM = log.moodAM
        cached.moodPM = log.moodPM
        cached.energy = log.energy
        cached.focus = log.focus

        cached.workoutType = log.trainingActivities.first?.type ?? log.plannedWorkout
        cached.workoutCompleted = !log.trainingActivities.isEmpty || !log.strengthExercises.isEmpty
        cached.totalTrainingMinutes = log.trainingActivities
            .compactMap(\.durationMinutes)
            .reduce(0, +)
        if cached.totalTrainingMinutes == 0 {
            cached.totalTrainingMinutes = nil
        }

        cached.todoTotal = log.todos.count
        cached.todoCompleted = log.todos.filter(\.isCompleted).count
        cached.habitTotal = log.habits.count
        cached.habitCompleted = log.habits.filter(\.isCompleted).count

        cached.calories = log.caloriesSoFar
        cached.protein = log.proteinSoFar

        cached.contentHash = hash
        cached.serializedLog = try? JSONEncoder().encode(log)
    }

    /// Updates an existing `CachedWorkout` with new values from a `WorkoutSession`.
    private func updateCachedWorkout(_ cached: CachedWorkout, from session: WorkoutSession) {
        cached.workoutType = session.workoutType
        cached.startTime = session.startTime
        cached.endTime = session.endTime
        cached.notes = session.notes
        cached.totalDistance = session.totalDistance
        cached.distanceUnit = session.distanceUnit?.rawValue
        cached.exerciseCount = session.exercises.count

        if let end = session.endTime {
            cached.durationMinutes = end.timeIntervalSince(session.startTime) / 60.0
        } else {
            cached.durationMinutes = nil
        }

        let volumes = session.exercises.compactMap(\.volume)
        cached.totalVolume = volumes.isEmpty ? nil : volumes.reduce(0, +)

        cached.serializedSession = try? JSONEncoder().encode(session)
    }

    /// Computes the SHA-256 hex string for the given content.
    static func sha256Hex(_ content: String) -> String {
        let digest = SHA256.hash(data: Data(content.utf8))
        return digest.compactMap { String(format: "%02x", $0) }.joined()
    }
}
