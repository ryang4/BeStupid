import Foundation
import SwiftData
import Testing
@testable import BeStupidApp

// MARK: - Test Helpers

/// Creates an in-memory `ModelContainer` for isolated test use.
private func makeTestContainer() throws -> ModelContainer {
    try PersistenceConfiguration.createContainer(inMemory: true)
}

/// Creates a `CacheManager` backed by an in-memory container.
private func makeTestCacheManager() throws -> CacheManager {
    let container = try makeTestContainer()
    return CacheManager(modelContainer: container)
}

/// Creates a sample `DailyLog` with configurable fields for testing.
private func makeSampleDailyLog(
    date: Date = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!,
    title: String = "2026-02-17.md",
    tags: [String] = ["triathlon", "strength"],
    weight: Double? = 175.5,
    sleep: Double? = 7.5,
    sleepQuality: Double? = 8.0,
    moodAM: Double? = 7.0,
    moodPM: Double? = 8.0,
    energy: Double? = 7.5,
    focus: Double? = 8.0,
    plannedWorkout: String? = "Swim + Strength",
    trainingActivities: [TrainingActivity] = [
        TrainingActivity(type: "Swim", distance: 2000, distanceUnit: .meters, durationMinutes: 45),
    ],
    strengthExercises: [StrengthEntry] = [
        StrengthEntry(exerciseName: "Bench Press", sets: 3, reps: 10, weightLbs: 185),
    ],
    todos: [TodoItem] = [
        TodoItem(text: "Morning swim", isCompleted: true),
        TodoItem(text: "Read chapter 5", isCompleted: false),
        TodoItem(text: "Meal prep", isCompleted: true),
    ],
    habits: [HabitEntry] = [
        HabitEntry(habitId: "meditate", name: "Meditate", isCompleted: true),
        HabitEntry(habitId: "journal", name: "Journal", isCompleted: false),
    ],
    caloriesSoFar: Int? = 2100,
    proteinSoFar: Int? = 160
) -> DailyLog {
    DailyLog(
        date: date,
        title: title,
        tags: tags,
        weight: weight,
        sleep: sleep,
        sleepQuality: sleepQuality,
        moodAM: moodAM,
        moodPM: moodPM,
        energy: energy,
        focus: focus,
        plannedWorkout: plannedWorkout,
        trainingActivities: trainingActivities,
        strengthExercises: strengthExercises,
        todos: todos,
        habits: habits,
        caloriesSoFar: caloriesSoFar,
        proteinSoFar: proteinSoFar
    )
}

/// Creates a sample `WorkoutSession` for testing.
private func makeSampleWorkoutSession(
    workoutType: String = "Strength",
    startTime: Date = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!,
    endTime: Date? = nil,
    exercises: [ExerciseSet] = [
        ExerciseSet(exerciseName: "Bench Press", setNumber: 1, reps: 10, weightLbs: 185),
        ExerciseSet(exerciseName: "Bench Press", setNumber: 2, reps: 8, weightLbs: 195),
        ExerciseSet(exerciseName: "Squat", setNumber: 1, reps: 5, weightLbs: 225),
    ],
    totalDistance: Double? = nil,
    distanceUnit: DistanceUnit? = nil
) -> WorkoutSession {
    let end = endTime ?? startTime.addingTimeInterval(3600) // 1 hour default
    return WorkoutSession(
        workoutType: workoutType,
        startTime: startTime,
        endTime: end,
        isActive: false,
        exercises: exercises,
        notes: "Good session",
        totalDistance: totalDistance,
        distanceUnit: distanceUnit
    )
}

/// Creates a sample `Exercise` for testing.
private func makeSampleExercise(
    name: String = "Bench Press",
    category: ExerciseCategory = .strength,
    muscleGroup: String? = "Chest",
    equipment: String? = "Barbell"
) -> Exercise {
    Exercise(
        name: name,
        category: category,
        muscleGroup: muscleGroup,
        equipment: equipment,
        isCustom: false
    )
}

/// Creates a sample `MetricDataPoint` for testing.
private func makeSampleMetric(
    date: Date = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!,
    field: MetricField = .weight,
    value: Double = 175.5,
    source: MetricSource = .manual
) -> MetricDataPoint {
    MetricDataPoint(date: date, field: field, value: value, source: source)
}

// MARK: - CachedDailyLog Tests

@Suite("CachedDailyLog")
struct CachedDailyLogTests {

    @Test("Roundtrip: create from DailyLog, convert back, verify equality")
    func roundtrip() throws {
        let container = try makeTestContainer()
        let context = ModelContext(container)

        let log = makeSampleDailyLog()
        let cached = CachedDailyLog(from: log, contentHash: "abc123")
        context.insert(cached)
        try context.save()

        let restored = cached.toDailyLog()
        #expect(restored != nil)
        let unwrapped = try #require(restored)

        #expect(unwrapped.date == log.date)
        #expect(unwrapped.title == log.title)
        #expect(unwrapped.tags == log.tags)
        #expect(unwrapped.weight == log.weight)
        #expect(unwrapped.sleep == log.sleep)
        #expect(unwrapped.sleepQuality == log.sleepQuality)
        #expect(unwrapped.moodAM == log.moodAM)
        #expect(unwrapped.moodPM == log.moodPM)
        #expect(unwrapped.energy == log.energy)
        #expect(unwrapped.focus == log.focus)
        #expect(unwrapped.plannedWorkout == log.plannedWorkout)
        #expect(unwrapped.todos.count == log.todos.count)
        #expect(unwrapped.habits.count == log.habits.count)
        #expect(unwrapped.trainingActivities.count == log.trainingActivities.count)
        #expect(unwrapped.strengthExercises.count == log.strengthExercises.count)
        #expect(unwrapped.caloriesSoFar == log.caloriesSoFar)
        #expect(unwrapped.proteinSoFar == log.proteinSoFar)
    }

    @Test("Content hash is stored correctly")
    func contentHashStored() throws {
        let container = try makeTestContainer()
        let context = ModelContext(container)

        let log = makeSampleDailyLog()
        let hash = "deadbeef1234567890"
        let cached = CachedDailyLog(from: log, contentHash: hash)
        context.insert(cached)
        try context.save()

        #expect(cached.contentHash == hash)
    }

    @Test("todoCompletionRate computed correctly")
    func todoCompletionRate() throws {
        let log = makeSampleDailyLog(
            todos: [
                TodoItem(text: "A", isCompleted: true),
                TodoItem(text: "B", isCompleted: true),
                TodoItem(text: "C", isCompleted: false),
                TodoItem(text: "D", isCompleted: false),
            ]
        )
        let cached = CachedDailyLog(from: log, contentHash: "test")

        // 2 of 4 = 0.5
        #expect(cached.todoCompletionRate == 0.5)
    }

    @Test("todoCompletionRate returns 0 when no todos")
    func todoCompletionRateEmpty() throws {
        let log = makeSampleDailyLog(todos: [])
        let cached = CachedDailyLog(from: log, contentHash: "test")

        #expect(cached.todoCompletionRate == 0)
    }

    @Test("habitCompletionRate computed correctly")
    func habitCompletionRate() throws {
        let log = makeSampleDailyLog(
            habits: [
                HabitEntry(habitId: "a", name: "A", isCompleted: true),
                HabitEntry(habitId: "b", name: "B", isCompleted: true),
                HabitEntry(habitId: "c", name: "C", isCompleted: true),
            ]
        )
        let cached = CachedDailyLog(from: log, contentHash: "test")

        // 3 of 3 = 1.0
        #expect(cached.habitCompletionRate == 1.0)
    }

    @Test("habitCompletionRate returns 0 when no habits")
    func habitCompletionRateEmpty() throws {
        let log = makeSampleDailyLog(habits: [])
        let cached = CachedDailyLog(from: log, contentHash: "test")

        #expect(cached.habitCompletionRate == 0)
    }

    @Test("Denormalized fields are set correctly")
    func denormalizedFields() throws {
        let log = makeSampleDailyLog()
        let cached = CachedDailyLog(from: log, contentHash: "test")

        #expect(cached.dateString == "2026-02-17")
        #expect(cached.weight == 175.5)
        #expect(cached.sleep == 7.5)
        #expect(cached.workoutType == "Swim")
        #expect(cached.workoutCompleted == true)
        #expect(cached.totalTrainingMinutes == 45)
        #expect(cached.todoTotal == 3)
        #expect(cached.todoCompleted == 2)
        #expect(cached.habitTotal == 2)
        #expect(cached.habitCompleted == 1)
        #expect(cached.calories == 2100)
        #expect(cached.protein == 160)
    }

    @Test("Workout type falls back to plannedWorkout when no activities")
    func workoutTypeFallback() throws {
        let log = makeSampleDailyLog(
            plannedWorkout: "Rest Day",
            trainingActivities: [],
            strengthExercises: []
        )
        let cached = CachedDailyLog(from: log, contentHash: "test")

        #expect(cached.workoutType == "Rest Day")
        #expect(cached.workoutCompleted == false)
        #expect(cached.totalTrainingMinutes == nil)
    }

    @Test("serializedLog is nil when DailyLog cannot be encoded returns nil from toDailyLog")
    func toDailyLogReturnsNilWhenNoData() throws {
        let container = try makeTestContainer()
        let context = ModelContext(container)

        let log = makeSampleDailyLog()
        let cached = CachedDailyLog(from: log, contentHash: "test")
        cached.serializedLog = nil
        context.insert(cached)
        try context.save()

        #expect(cached.toDailyLog() == nil)
    }
}

// MARK: - CachedMetric Tests

@Suite("CachedMetric")
struct CachedMetricTests {

    @Test("Roundtrip: create from MetricDataPoint, convert back")
    func roundtrip() throws {
        let container = try makeTestContainer()
        let context = ModelContext(container)

        let metric = makeSampleMetric(field: .weight, value: 175.5, source: .manual)
        let cached = CachedMetric(from: metric)
        context.insert(cached)
        try context.save()

        let restored = cached.toMetricDataPoint()
        #expect(restored.date == metric.date)
        #expect(restored.field == metric.field)
        #expect(restored.value == metric.value)
        #expect(restored.source == metric.source)
    }

    @Test("compositeKey is unique per date+field combination")
    func compositeKeyFormat() throws {
        let date = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!
        let key = CachedMetric.makeCompositeKey(date: date, field: .weight)
        #expect(key == "2026-02-17:weight")

        let key2 = CachedMetric.makeCompositeKey(date: date, field: .sleep)
        #expect(key2 == "2026-02-17:sleep")
        #expect(key != key2)
    }

    @Test("Different dates produce different composite keys")
    func compositeKeyDifferentDates() throws {
        let date1 = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!
        let date2 = DateFormatting.dailyLogFormatter.date(from: "2026-02-18")!

        let key1 = CachedMetric.makeCompositeKey(date: date1, field: .weight)
        let key2 = CachedMetric.makeCompositeKey(date: date2, field: .weight)

        #expect(key1 != key2)
    }

    @Test("Stored field and source are raw string values")
    func rawValueStorage() throws {
        let metric = makeSampleMetric(field: .sleepQuality, source: .garmin)
        let cached = CachedMetric(from: metric)

        #expect(cached.field == "sleepQuality")
        #expect(cached.source == "garmin")
    }
}

// MARK: - CachedWorkout Tests

@Suite("CachedWorkout")
struct CachedWorkoutTests {

    @Test("Roundtrip: create from WorkoutSession, convert back")
    func roundtrip() throws {
        let container = try makeTestContainer()
        let context = ModelContext(container)

        let session = makeSampleWorkoutSession()
        let cached = CachedWorkout(from: session)
        context.insert(cached)
        try context.save()

        let restored = cached.toWorkoutSession()
        #expect(restored != nil)
        let unwrapped = try #require(restored)

        #expect(unwrapped.workoutType == session.workoutType)
        #expect(unwrapped.startTime == session.startTime)
        #expect(unwrapped.endTime == session.endTime)
        #expect(unwrapped.exercises.count == session.exercises.count)
        #expect(unwrapped.notes == session.notes)
    }

    @Test("Denormalized fields are computed correctly")
    func denormalizedFields() throws {
        let start = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!
        let end = start.addingTimeInterval(90 * 60) // 90 minutes

        let session = makeSampleWorkoutSession(startTime: start, endTime: end)
        let cached = CachedWorkout(from: session)

        #expect(cached.workoutType == "Strength")
        #expect(cached.durationMinutes == 90.0)
        #expect(cached.exerciseCount == 3)
        #expect(cached.workoutId == session.id.uuidString)
    }

    @Test("totalVolume is computed from exercise sets")
    func totalVolume() throws {
        let exercises = [
            ExerciseSet(exerciseName: "Bench", setNumber: 1, reps: 10, weightLbs: 185),
            ExerciseSet(exerciseName: "Bench", setNumber: 2, reps: 8, weightLbs: 195),
        ]
        let session = makeSampleWorkoutSession(exercises: exercises)
        let cached = CachedWorkout(from: session)

        // volume = (10 * 185) + (8 * 195) = 1850 + 1560 = 3410
        #expect(cached.totalVolume == 3410.0)
    }

    @Test("totalVolume is nil when exercises have no weight/reps")
    func totalVolumeNil() throws {
        let exercises = [
            ExerciseSet(exerciseName: "Plank", setNumber: 1, durationSeconds: 60),
        ]
        let session = makeSampleWorkoutSession(exercises: exercises)
        let cached = CachedWorkout(from: session)

        #expect(cached.totalVolume == nil)
    }

    @Test("durationMinutes is nil when endTime is nil")
    func durationNilWhenNoEnd() throws {
        let session = WorkoutSession(
            workoutType: "Run",
            startTime: Date(),
            endTime: nil,
            isActive: true
        )
        let cached = CachedWorkout(from: session)

        #expect(cached.durationMinutes == nil)
    }

    @Test("toWorkoutSession returns nil when serializedSession is nil")
    func toSessionReturnsNilWhenNoData() throws {
        let session = makeSampleWorkoutSession()
        let cached = CachedWorkout(from: session)
        cached.serializedSession = nil

        #expect(cached.toWorkoutSession() == nil)
    }
}

// MARK: - CachedExercise Tests

@Suite("CachedExercise")
struct CachedExerciseTests {

    @Test("Roundtrip: create from Exercise, convert back")
    func roundtrip() throws {
        let exercise = makeSampleExercise()
        let cached = CachedExercise(from: exercise)
        let restored = cached.toExercise()

        #expect(restored.name == exercise.name)
        #expect(restored.category == exercise.category)
        #expect(restored.muscleGroup == exercise.muscleGroup)
        #expect(restored.equipment == exercise.equipment)
        #expect(restored.isCustom == exercise.isCustom)
    }

    @Test("updatePR only updates when new value exceeds current")
    func updatePROnlyExceeds() throws {
        let exercise = makeSampleExercise()
        let cached = CachedExercise(from: exercise)
        let date = Date()

        // Initial PR set
        cached.updatePR(weight: 200, reps: 10, volume: 2000, date: date)
        #expect(cached.prWeight == 200)
        #expect(cached.prReps == 10)
        #expect(cached.prVolume == 2000)

        // Lower values should NOT update
        cached.updatePR(weight: 180, reps: 8, volume: 1500, date: date)
        #expect(cached.prWeight == 200)
        #expect(cached.prReps == 10)
        #expect(cached.prVolume == 2000)

        // Higher values SHOULD update
        cached.updatePR(weight: 225, reps: 12, volume: 2700, date: date)
        #expect(cached.prWeight == 225)
        #expect(cached.prReps == 12)
        #expect(cached.prVolume == 2700)
    }

    @Test("updatePR with nil values does not clear existing PRs")
    func updatePRNilPreservesExisting() throws {
        let exercise = makeSampleExercise()
        let cached = CachedExercise(from: exercise)
        let date = Date()

        cached.updatePR(weight: 200, reps: 10, volume: 2000, date: date)

        // Pass nil for all -- should not clear existing PRs
        cached.updatePR(weight: nil, reps: nil, volume: nil, date: date)
        #expect(cached.prWeight == 200)
        #expect(cached.prReps == 10)
        #expect(cached.prVolume == 2000)
    }

    @Test("updatePR updates lastUsedDate")
    func updatePRUpdatesLastUsed() throws {
        let exercise = makeSampleExercise()
        let cached = CachedExercise(from: exercise)

        #expect(cached.lastUsedDate == nil)

        let date1 = DateFormatting.dailyLogFormatter.date(from: "2026-02-15")!
        cached.updatePR(weight: 100, reps: nil, volume: nil, date: date1)
        #expect(cached.lastUsedDate == date1)

        // Earlier date should NOT update lastUsedDate
        let date0 = DateFormatting.dailyLogFormatter.date(from: "2026-02-10")!
        cached.updatePR(weight: nil, reps: nil, volume: nil, date: date0)
        #expect(cached.lastUsedDate == date1)

        // Later date SHOULD update lastUsedDate
        let date2 = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!
        cached.updatePR(weight: nil, reps: nil, volume: nil, date: date2)
        #expect(cached.lastUsedDate == date2)
    }

    @Test("Initial PRs are all nil")
    func initialPRsNil() throws {
        let exercise = makeSampleExercise()
        let cached = CachedExercise(from: exercise)

        #expect(cached.prWeight == nil)
        #expect(cached.prReps == nil)
        #expect(cached.prVolume == nil)
        #expect(cached.lastUsedDate == nil)
    }

    @Test("Category stored as raw value string")
    func categoryRawValue() throws {
        let exercise = makeSampleExercise(category: .cardio)
        let cached = CachedExercise(from: exercise)

        #expect(cached.category == "cardio")
    }
}

// MARK: - CacheManager Tests

@Suite("CacheManager")
struct CacheManagerTests {

    @Test("cacheDailyLog inserts new log")
    func insertNewLog() async throws {
        let manager = try makeTestCacheManager()
        let log = makeSampleDailyLog()
        let markdown = "# 2026-02-17\nSome content"

        try await manager.cacheDailyLog(log, markdownContent: markdown)

        let stats = try await manager.cacheStats()
        #expect(stats.dailyLogCount == 1)

        let fetched = try await manager.fetchLog(for: log.date)
        #expect(fetched != nil)
        #expect(fetched?.dateString == "2026-02-17")
        #expect(fetched?.weight == 175.5)
    }

    @Test("cacheDailyLog skips when hash matches")
    func skipWhenHashMatches() async throws {
        let manager = try makeTestCacheManager()
        let log = makeSampleDailyLog()
        let markdown = "# 2026-02-17\nSame content"

        // Cache the first time
        try await manager.cacheDailyLog(log, markdownContent: markdown)

        // Cache again with identical content -- should be a no-op
        try await manager.cacheDailyLog(log, markdownContent: markdown)

        let stats = try await manager.cacheStats()
        #expect(stats.dailyLogCount == 1)
    }

    @Test("cacheDailyLog updates when hash differs")
    func updateWhenHashDiffers() async throws {
        let manager = try makeTestCacheManager()
        let date = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!

        let log1 = makeSampleDailyLog(date: date, weight: 175.0)
        try await manager.cacheDailyLog(log1, markdownContent: "version 1")

        let log2 = makeSampleDailyLog(date: date, weight: 176.0)
        try await manager.cacheDailyLog(log2, markdownContent: "version 2")

        let stats = try await manager.cacheStats()
        #expect(stats.dailyLogCount == 1) // Still just one entry, not two

        let fetched = try await manager.fetchLog(for: date)
        #expect(fetched?.weight == 176.0) // Updated value
    }

    @Test("fetchLogs returns correct date range")
    func fetchLogsDateRange() async throws {
        let manager = try makeTestCacheManager()

        let dates = ["2026-02-15", "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19"]
        for dateStr in dates {
            let date = DateFormatting.dailyLogFormatter.date(from: dateStr)!
            let log = makeSampleDailyLog(date: date, title: "\(dateStr).md")
            try await manager.cacheDailyLog(log, markdownContent: "content for \(dateStr)")
        }

        let start = DateFormatting.dailyLogFormatter.date(from: "2026-02-16")!
        let end = DateFormatting.dailyLogFormatter.date(from: "2026-02-18")!
        let results = try await manager.fetchLogs(from: start, to: end)

        #expect(results.count == 3)
        // Should be sorted descending by date
        #expect(results[0].dateString == "2026-02-18")
        #expect(results[1].dateString == "2026-02-17")
        #expect(results[2].dateString == "2026-02-16")
    }

    @Test("fetchLog returns nil for non-existent date")
    func fetchLogNonExistent() async throws {
        let manager = try makeTestCacheManager()
        let date = DateFormatting.dailyLogFormatter.date(from: "2099-01-01")!
        let result = try await manager.fetchLog(for: date)
        #expect(result == nil)
    }

    @Test("cacheMetrics inserts and upserts correctly")
    func cacheMetrics() async throws {
        let manager = try makeTestCacheManager()
        let date = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!

        let metrics = [
            makeSampleMetric(date: date, field: .weight, value: 175.5),
            makeSampleMetric(date: date, field: .sleep, value: 7.5),
        ]
        try await manager.cacheMetrics(metrics)

        let stats = try await manager.cacheStats()
        #expect(stats.metricCount == 2)

        // Upsert with updated value
        let updated = [makeSampleMetric(date: date, field: .weight, value: 176.0)]
        try await manager.cacheMetrics(updated)

        // Should still be 2 metrics, not 3
        let stats2 = try await manager.cacheStats()
        #expect(stats2.metricCount == 2)
    }

    @Test("fetchMetrics filters by field and date range")
    func fetchMetricsFiltered() async throws {
        let manager = try makeTestCacheManager()

        let date1 = DateFormatting.dailyLogFormatter.date(from: "2026-02-15")!
        let date2 = DateFormatting.dailyLogFormatter.date(from: "2026-02-16")!
        let date3 = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!

        let metrics = [
            makeSampleMetric(date: date1, field: .weight, value: 174.0),
            makeSampleMetric(date: date2, field: .weight, value: 175.0),
            makeSampleMetric(date: date3, field: .weight, value: 176.0),
            makeSampleMetric(date: date2, field: .sleep, value: 7.0), // different field
        ]
        try await manager.cacheMetrics(metrics)

        // Query weight from 2/16 to 2/17
        let results = try await manager.fetchMetrics(
            field: .weight,
            from: date2,
            to: date3
        )

        #expect(results.count == 2)
        // Sorted ascending by date
        #expect(results[0].value == 175.0)
        #expect(results[1].value == 176.0)
    }

    @Test("latestMetric returns most recent value")
    func latestMetric() async throws {
        let manager = try makeTestCacheManager()

        let date1 = DateFormatting.dailyLogFormatter.date(from: "2026-02-15")!
        let date2 = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!
        let date3 = DateFormatting.dailyLogFormatter.date(from: "2026-02-16")!

        let metrics = [
            makeSampleMetric(date: date1, field: .weight, value: 174.0),
            makeSampleMetric(date: date2, field: .weight, value: 176.0),
            makeSampleMetric(date: date3, field: .weight, value: 175.0),
        ]
        try await manager.cacheMetrics(metrics)

        let latest = try await manager.latestMetric(field: .weight)
        #expect(latest != nil)
        #expect(latest?.value == 176.0)
    }

    @Test("latestMetric returns nil when no metrics exist for field")
    func latestMetricNil() async throws {
        let manager = try makeTestCacheManager()

        let latest = try await manager.latestMetric(field: .swimDistance)
        #expect(latest == nil)
    }

    @Test("cacheWorkout inserts and upserts")
    func cacheWorkout() async throws {
        let manager = try makeTestCacheManager()

        var session = makeSampleWorkoutSession()
        try await manager.cacheWorkout(session)

        let stats = try await manager.cacheStats()
        #expect(stats.workoutCount == 1)

        // Update the session (same ID, different notes)
        session.notes = "Updated notes"
        try await manager.cacheWorkout(session)

        let stats2 = try await manager.cacheStats()
        #expect(stats2.workoutCount == 1) // Still 1, not 2
    }

    @Test("fetchWorkouts returns results sorted by start time descending")
    func fetchWorkoutsSorted() async throws {
        let manager = try makeTestCacheManager()

        let date1 = DateFormatting.dailyLogFormatter.date(from: "2026-02-15")!
        let date2 = DateFormatting.dailyLogFormatter.date(from: "2026-02-16")!
        let date3 = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!

        try await manager.cacheWorkout(makeSampleWorkoutSession(startTime: date2))
        try await manager.cacheWorkout(makeSampleWorkoutSession(startTime: date1))
        try await manager.cacheWorkout(makeSampleWorkoutSession(startTime: date3))

        let results = try await manager.fetchWorkouts(limit: 10)
        #expect(results.count == 3)
        #expect(results[0].startTime == date3)
        #expect(results[1].startTime == date2)
        #expect(results[2].startTime == date1)
    }

    @Test("fetchWorkouts filters by type")
    func fetchWorkoutsFilteredByType() async throws {
        let manager = try makeTestCacheManager()

        try await manager.cacheWorkout(makeSampleWorkoutSession(workoutType: "Swim"))
        try await manager.cacheWorkout(makeSampleWorkoutSession(workoutType: "Bike"))
        try await manager.cacheWorkout(makeSampleWorkoutSession(workoutType: "Swim"))

        let swims = try await manager.fetchWorkouts(limit: 10, type: "Swim")
        #expect(swims.count == 2)
        for w in swims {
            #expect(w.workoutType == "Swim")
        }

        let bikes = try await manager.fetchWorkouts(limit: 10, type: "Bike")
        #expect(bikes.count == 1)
    }

    @Test("fetchWorkouts respects limit")
    func fetchWorkoutsLimit() async throws {
        let manager = try makeTestCacheManager()

        for i in 0..<5 {
            let date = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!
                .addingTimeInterval(Double(i) * 3600)
            try await manager.cacheWorkout(makeSampleWorkoutSession(startTime: date))
        }

        let results = try await manager.fetchWorkouts(limit: 3)
        #expect(results.count == 3)
    }

    @Test("cacheExercise inserts and upserts")
    func cacheExercise() async throws {
        let manager = try makeTestCacheManager()

        let exercise = makeSampleExercise(name: "Deadlift", category: .strength)
        try await manager.cacheExercise(exercise)

        let stats = try await manager.cacheStats()
        #expect(stats.exerciseCount == 1)

        // Upsert with updated category
        let updated = makeSampleExercise(name: "Deadlift", category: .strength, muscleGroup: "Back")
        try await manager.cacheExercise(updated)

        let stats2 = try await manager.cacheStats()
        #expect(stats2.exerciseCount == 1) // Still 1
    }

    @Test("fetchExercises returns all when no category filter")
    func fetchExercisesAll() async throws {
        let manager = try makeTestCacheManager()

        try await manager.cacheExercise(makeSampleExercise(name: "Bench Press", category: .strength))
        try await manager.cacheExercise(makeSampleExercise(name: "Running", category: .cardio))
        try await manager.cacheExercise(makeSampleExercise(name: "Yoga", category: .flexibility))

        let all = try await manager.fetchExercises()
        #expect(all.count == 3)
    }

    @Test("fetchExercises filters by category")
    func fetchExercisesFiltered() async throws {
        let manager = try makeTestCacheManager()

        try await manager.cacheExercise(makeSampleExercise(name: "Bench Press", category: .strength))
        try await manager.cacheExercise(makeSampleExercise(name: "Squat", category: .strength))
        try await manager.cacheExercise(makeSampleExercise(name: "Running", category: .cardio))

        let strength = try await manager.fetchExercises(category: .strength)
        #expect(strength.count == 2)
        for e in strength {
            #expect(e.category == "strength")
        }
    }

    @Test("fetchExercises returns results sorted by name")
    func fetchExercisesSorted() async throws {
        let manager = try makeTestCacheManager()

        try await manager.cacheExercise(makeSampleExercise(name: "Squat", category: .strength))
        try await manager.cacheExercise(makeSampleExercise(name: "Bench Press", category: .strength))
        try await manager.cacheExercise(makeSampleExercise(name: "Deadlift", category: .strength))

        let results = try await manager.fetchExercises()
        #expect(results[0].name == "Bench Press")
        #expect(results[1].name == "Deadlift")
        #expect(results[2].name == "Squat")
    }

    @Test("updateExercisePR updates existing exercise")
    func updateExercisePR() async throws {
        let manager = try makeTestCacheManager()

        try await manager.cacheExercise(makeSampleExercise(name: "Bench Press"))

        try await manager.updateExercisePR(name: "Bench Press", weight: 225, reps: 5, volume: 1125)

        let exercises = try await manager.fetchExercises()
        #expect(exercises.count == 1)
        #expect(exercises[0].prWeight == 225)
        #expect(exercises[0].prReps == 5)
        #expect(exercises[0].prVolume == 1125)
    }

    @Test("updateExercisePR does nothing for unknown exercise")
    func updateExercisePRUnknown() async throws {
        let manager = try makeTestCacheManager()

        // Should not throw, just silently return
        try await manager.updateExercisePR(
            name: "Nonexistent Exercise",
            weight: 100,
            reps: 10,
            volume: 1000
        )

        let stats = try await manager.cacheStats()
        #expect(stats.exerciseCount == 0)
    }

    @Test("rebuildCache clears and re-populates daily logs and metrics")
    func rebuildCache() async throws {
        let manager = try makeTestCacheManager()

        // Pre-populate some data
        let date = DateFormatting.dailyLogFormatter.date(from: "2026-02-15")!
        let oldLog = makeSampleDailyLog(date: date)
        try await manager.cacheDailyLog(oldLog, markdownContent: "old content")

        let oldMetric = makeSampleMetric(date: date, field: .weight, value: 170.0)
        try await manager.cacheMetrics([oldMetric])

        // Also add a workout (should survive rebuild)
        try await manager.cacheWorkout(makeSampleWorkoutSession())

        let statsBefore = try await manager.cacheStats()
        #expect(statsBefore.dailyLogCount == 1)
        #expect(statsBefore.metricCount == 1)
        #expect(statsBefore.workoutCount == 1)

        // Rebuild with new data
        let newDate1 = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!
        let newDate2 = DateFormatting.dailyLogFormatter.date(from: "2026-02-18")!
        let newLogs = [
            makeSampleDailyLog(date: newDate1),
            makeSampleDailyLog(date: newDate2),
        ]
        let markdownContents = [
            "2026-02-17": "new content 1",
            "2026-02-18": "new content 2",
        ]

        try await manager.rebuildCache(logs: newLogs, markdownContents: markdownContents)

        let statsAfter = try await manager.cacheStats()
        #expect(statsAfter.dailyLogCount == 2) // Old log cleared, 2 new ones
        #expect(statsAfter.metricCount == 0) // Metrics cleared by rebuild
        #expect(statsAfter.workoutCount == 1) // Workout survives rebuild
    }

    @Test("cacheStats returns correct counts")
    func cacheStatsCorrect() async throws {
        let manager = try makeTestCacheManager()

        // Empty cache
        let empty = try await manager.cacheStats()
        #expect(empty.dailyLogCount == 0)
        #expect(empty.metricCount == 0)
        #expect(empty.workoutCount == 0)
        #expect(empty.exerciseCount == 0)
        #expect(empty.oldestLogDate == nil)
        #expect(empty.newestLogDate == nil)

        // Add some data
        let date1 = DateFormatting.dailyLogFormatter.date(from: "2026-02-15")!
        let date2 = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!

        try await manager.cacheDailyLog(
            makeSampleDailyLog(date: date1),
            markdownContent: "content 1"
        )
        try await manager.cacheDailyLog(
            makeSampleDailyLog(date: date2),
            markdownContent: "content 2"
        )
        try await manager.cacheMetrics([
            makeSampleMetric(date: date1, field: .weight, value: 175),
            makeSampleMetric(date: date1, field: .sleep, value: 7.5),
            makeSampleMetric(date: date2, field: .weight, value: 176),
        ])
        try await manager.cacheWorkout(makeSampleWorkoutSession())
        try await manager.cacheExercise(makeSampleExercise(name: "Bench Press"))
        try await manager.cacheExercise(makeSampleExercise(name: "Squat"))

        let stats = try await manager.cacheStats()
        #expect(stats.dailyLogCount == 2)
        #expect(stats.metricCount == 3)
        #expect(stats.workoutCount == 1)
        #expect(stats.exerciseCount == 2)
        #expect(stats.oldestLogDate == date1)
        #expect(stats.newestLogDate == date2)
    }
}

// MARK: - PersistenceConfiguration Tests

@Suite("PersistenceConfiguration")
struct PersistenceConfigurationTests {

    @Test("createContainer succeeds with persistent storage")
    func createContainerPersistent() throws {
        let container = try PersistenceConfiguration.createContainer(inMemory: false)
        #expect(container.schema.entities.count == 4)
    }

    @Test("createContainer succeeds with in-memory storage")
    func createContainerInMemory() throws {
        let container = try PersistenceConfiguration.createContainer(inMemory: true)
        #expect(container.schema.entities.count == 4)
    }

    @Test("previewContainer creates in-memory store")
    func previewContainer() throws {
        let container = try PersistenceConfiguration.previewContainer()
        #expect(container.schema.entities.count == 4)

        // Verify we can insert and fetch (confirming it works)
        let context = ModelContext(container)
        let log = makeSampleDailyLog()
        let cached = CachedDailyLog(from: log, contentHash: "test")
        context.insert(cached)
        try context.save()

        let descriptor = FetchDescriptor<CachedDailyLog>()
        let results = try context.fetch(descriptor)
        #expect(results.count == 1)
    }

    @Test("modelTypes contains all four model types")
    func modelTypesComplete() {
        #expect(PersistenceConfiguration.modelTypes.count == 4)
    }
}

// MARK: - SHA256 Hash Tests

@Suite("CacheManager SHA256")
struct CacheManagerHashTests {

    @Test("SHA256 produces consistent output")
    func sha256Consistency() {
        let hash1 = CacheManager.sha256Hex("hello world")
        let hash2 = CacheManager.sha256Hex("hello world")
        #expect(hash1 == hash2)
    }

    @Test("SHA256 produces different output for different input")
    func sha256Different() {
        let hash1 = CacheManager.sha256Hex("hello world")
        let hash2 = CacheManager.sha256Hex("hello world!")
        #expect(hash1 != hash2)
    }

    @Test("SHA256 produces 64-character hex string")
    func sha256Length() {
        let hash = CacheManager.sha256Hex("test content")
        #expect(hash.count == 64)
        #expect(hash.allSatisfy { $0.isHexDigit })
    }
}
