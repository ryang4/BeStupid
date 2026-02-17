import Foundation
import Testing

@testable import BeStupidApp

// MARK: - DailyLog Tests

@Suite("DailyLog")
struct DailyLogTests {

    @Test("Default initialization creates empty log for today")
    func defaultInit() {
        let log = DailyLog()

        #expect(log.tags.isEmpty)
        #expect(log.weight == nil)
        #expect(log.sleep == nil)
        #expect(log.sleepQuality == nil)
        #expect(log.moodAM == nil)
        #expect(log.moodPM == nil)
        #expect(log.energy == nil)
        #expect(log.focus == nil)
        #expect(log.plannedWorkout == nil)
        #expect(log.trainingActivities.isEmpty)
        #expect(log.strengthExercises.isEmpty)
        #expect(log.todos.isEmpty)
        #expect(log.habits.isEmpty)
        #expect(log.caloriesSoFar == nil)
        #expect(log.proteinSoFar == nil)
        #expect(log.nutritionLineItems.isEmpty)
        #expect(log.topThreeForTomorrow.isEmpty)
        #expect(log.dailyBriefing == nil)
    }

    @Test("Title defaults to log file name when not provided")
    func defaultTitle() {
        let date = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!
        let log = DailyLog(date: date)

        #expect(log.title == "2026-02-17.md")
    }

    @Test("Custom title overrides default")
    func customTitle() {
        let log = DailyLog(title: "My Custom Title")

        #expect(log.title == "My Custom Title")
    }

    @Test("Todo completion rate is nil when no todos")
    func todoCompletionRateEmpty() {
        let log = DailyLog()
        #expect(log.todoCompletionRate == nil)
    }

    @Test("Todo completion rate computes correctly")
    func todoCompletionRate() {
        let log = DailyLog(todos: [
            TodoItem(text: "Done", isCompleted: true),
            TodoItem(text: "Not done", isCompleted: false),
            TodoItem(text: "Also done", isCompleted: true),
            TodoItem(text: "Still pending", isCompleted: false),
        ])

        #expect(log.todoCompletionRate == 0.5)
    }

    @Test("Habit completion rate computes correctly")
    func habitCompletionRate() {
        let log = DailyLog(habits: [
            HabitEntry(habitId: "h1", name: "Meditate", isCompleted: true),
            HabitEntry(habitId: "h2", name: "Read", isCompleted: false),
            HabitEntry(habitId: "h3", name: "Journal", isCompleted: true),
        ])

        let rate = try #require(log.habitCompletionRate)
        #expect(abs(rate - 2.0 / 3.0) < 0.001)
    }

    @Test("Total calories and protein from nutrition items")
    func nutritionTotals() {
        let log = DailyLog(nutritionLineItems: [
            NutritionEntry(food: "Eggs", calories: 200, proteinG: 14),
            NutritionEntry(food: "Oatmeal", calories: 350, proteinG: 10),
            NutritionEntry(food: "Coffee", calories: nil, proteinG: nil),
        ])

        #expect(log.totalCaloriesFromItems == 550)
        #expect(log.totalProteinFromItems == 24)
    }

    @Test("Total strength volume sums all exercises")
    func totalStrengthVolume() {
        let log = DailyLog(strengthExercises: [
            StrengthEntry(exerciseName: "Squat", sets: 3, reps: 5, weightLbs: 225),
            StrengthEntry(exerciseName: "Bench", sets: 3, reps: 8, weightLbs: 185),
        ])

        let expected = (3.0 * 5.0 * 225.0) + (3.0 * 8.0 * 185.0)
        #expect(log.totalStrengthVolume == expected)
    }

    @Test("Codable roundtrip preserves all fields")
    func codableRoundtrip() throws {
        let date = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!
        let fixedID = UUID(uuidString: "12345678-1234-1234-1234-123456789ABC")!

        let original = DailyLog(
            id: fixedID,
            date: date,
            title: "Test Log",
            tags: ["training", "nutrition"],
            weight: 183.5,
            sleep: 7.5,
            sleepQuality: 8.0,
            moodAM: 7.0,
            moodPM: 8.0,
            energy: 6.5,
            focus: 7.0,
            plannedWorkout: "Swim 700m",
            trainingActivities: [
                TrainingActivity(
                    id: fixedID,
                    type: "swim",
                    distance: 700,
                    distanceUnit: .meters,
                    durationMinutes: 25.0,
                    avgHeartRate: 145
                )
            ],
            strengthExercises: [
                StrengthEntry(
                    id: fixedID,
                    exerciseName: "Squat",
                    sets: 3,
                    reps: 5,
                    weightLbs: 225
                )
            ],
            todos: [
                TodoItem(id: fixedID, text: "Ship feature", isCompleted: true)
            ],
            habits: [
                HabitEntry(id: fixedID, habitId: "meditate", name: "Meditate", isCompleted: true)
            ],
            caloriesSoFar: 1200,
            proteinSoFar: 90,
            nutritionLineItems: [
                NutritionEntry(
                    id: fixedID,
                    time: "08:00",
                    food: "Eggs",
                    calories: 200,
                    proteinG: 14,
                    carbsG: 2,
                    fatG: 15
                )
            ],
            topThreeForTomorrow: ["Task A", "Task B", "Task C"],
            dailyBriefing: "Big day ahead"
        )

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(original)

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let decoded = try decoder.decode(DailyLog.self, from: data)

        #expect(decoded == original)
        #expect(decoded.id == fixedID)
        #expect(decoded.title == "Test Log")
        #expect(decoded.tags == ["training", "nutrition"])
        #expect(decoded.weight == 183.5)
        #expect(decoded.sleep == 7.5)
        #expect(decoded.sleepQuality == 8.0)
        #expect(decoded.moodAM == 7.0)
        #expect(decoded.moodPM == 8.0)
        #expect(decoded.energy == 6.5)
        #expect(decoded.focus == 7.0)
        #expect(decoded.plannedWorkout == "Swim 700m")
        #expect(decoded.trainingActivities.count == 1)
        #expect(decoded.trainingActivities[0].type == "swim")
        #expect(decoded.strengthExercises.count == 1)
        #expect(decoded.strengthExercises[0].exerciseName == "Squat")
        #expect(decoded.todos.count == 1)
        #expect(decoded.todos[0].isCompleted == true)
        #expect(decoded.habits.count == 1)
        #expect(decoded.habits[0].name == "Meditate")
        #expect(decoded.caloriesSoFar == 1200)
        #expect(decoded.proteinSoFar == 90)
        #expect(decoded.nutritionLineItems.count == 1)
        #expect(decoded.nutritionLineItems[0].food == "Eggs")
        #expect(decoded.topThreeForTomorrow == ["Task A", "Task B", "Task C"])
        #expect(decoded.dailyBriefing == "Big day ahead")
    }
}

// MARK: - WorkoutSession Tests

@Suite("WorkoutSession")
struct WorkoutSessionTests {

    @Test("Duration computation for active session returns positive value")
    func durationActiveSession() {
        let startTime = Date().addingTimeInterval(-300) // 5 minutes ago
        let session = WorkoutSession(workoutType: "Strength", startTime: startTime)

        let duration = try #require(session.duration)
        #expect(duration >= 299 && duration <= 301)
    }

    @Test("Duration computation for finished session uses endTime")
    func durationFinishedSession() {
        let start = Date(timeIntervalSince1970: 1000)
        let end = Date(timeIntervalSince1970: 1600) // 600 seconds = 10 minutes
        let session = WorkoutSession(
            workoutType: "Run",
            startTime: start,
            endTime: end,
            isActive: false
        )

        #expect(session.duration == 600)
        #expect(session.durationMinutes == 10.0)
    }

    @Test("Duration is nil for inactive session without endTime")
    func durationInactiveNoEnd() {
        let session = WorkoutSession(
            workoutType: "Swim",
            startTime: Date(),
            endTime: nil,
            isActive: false
        )

        #expect(session.duration == nil)
        #expect(session.durationMinutes == nil)
    }

    @Test("finish() sets endTime and clears isActive")
    func finishSession() {
        var session = WorkoutSession(workoutType: "Bike")

        #expect(session.isActive == true)
        #expect(session.endTime == nil)

        session.finish()

        #expect(session.isActive == false)
        #expect(session.endTime != nil)
    }

    @Test("Average and max heart rate from samples")
    func heartRateStats() {
        var session = WorkoutSession(workoutType: "Run")
        session.recordHeartRate(bpm: 120)
        session.recordHeartRate(bpm: 140)
        session.recordHeartRate(bpm: 160)

        #expect(session.averageHeartRate == 140)
        #expect(session.maxHeartRate == 160)
    }

    @Test("Heart rate stats are nil when no samples")
    func heartRateStatsEmpty() {
        let session = WorkoutSession(workoutType: "Walk")

        #expect(session.averageHeartRate == nil)
        #expect(session.maxHeartRate == nil)
    }

    @Test("Unique exercise names preserves order and deduplicates")
    func uniqueExerciseNames() {
        let session = WorkoutSession(
            workoutType: "Strength",
            exercises: [
                ExerciseSet(exerciseName: "Squat", setNumber: 1),
                ExerciseSet(exerciseName: "Bench", setNumber: 1),
                ExerciseSet(exerciseName: "Squat", setNumber: 2),
                ExerciseSet(exerciseName: "Row", setNumber: 1),
                ExerciseSet(exerciseName: "Bench", setNumber: 2),
            ]
        )

        #expect(session.uniqueExerciseNames == ["Squat", "Bench", "Row"])
    }

    @Test("addSet appends to exercises list")
    func addSet() {
        var session = WorkoutSession(workoutType: "Strength")
        let exerciseSet = ExerciseSet(exerciseName: "Deadlift", setNumber: 1, reps: 5, weightLbs: 315)
        session.addSet(exerciseSet)

        #expect(session.exercises.count == 1)
        #expect(session.exercises[0].exerciseName == "Deadlift")
    }
}

// MARK: - StrengthEntry Tests

@Suite("StrengthEntry")
struct StrengthEntryTests {

    @Test("totalVolume computes sets * reps * weight")
    func totalVolume() {
        let entry = StrengthEntry(exerciseName: "Bench Press", sets: 3, reps: 10, weightLbs: 185)
        #expect(entry.totalVolume == 3 * 10 * 185.0)
    }

    @Test("totalVolume is zero when weight is zero")
    func totalVolumeZeroWeight() {
        let entry = StrengthEntry(exerciseName: "Pushup", sets: 3, reps: 20, weightLbs: 0)
        #expect(entry.totalVolume == 0)
    }
}

// MARK: - TrainingActivity Tests

@Suite("TrainingActivity")
struct TrainingActivityTests {

    @Test("Distance in meters conversion from km")
    func distanceInMetersFromKm() {
        let activity = TrainingActivity(type: "bike", distance: 40, distanceUnit: .kilometers)
        #expect(activity.distanceInMeters == 40_000)
    }

    @Test("Distance in meters conversion from miles")
    func distanceInMetersFromMiles() {
        let activity = TrainingActivity(type: "run", distance: 1, distanceUnit: .miles)
        let meters = try #require(activity.distanceInMeters)
        #expect(abs(meters - 1609.344) < 0.01)
    }

    @Test("Distance in meters returns nil when no distance")
    func distanceInMetersNil() {
        let activity = TrainingActivity(type: "swim")
        #expect(activity.distanceInMeters == nil)
    }

    @Test("Pace computation")
    func pace() {
        let activity = TrainingActivity(type: "run", distance: 5, distanceUnit: .kilometers, durationMinutes: 25)
        let pace = try #require(activity.paceMinPerKm)
        #expect(abs(pace - 5.0) < 0.001)
    }
}

// MARK: - DateFormatting Tests

@Suite("DateFormatting")
struct DateFormattingTests {

    @Test("normalizeSleep converts H:MM format")
    func normalizeSleepColonFormat() {
        let result = DateFormatting.normalizeSleep("6:35")
        let expected = 6.0 + 35.0 / 60.0 // 6.583...
        let value = try #require(result)
        #expect(abs(value - expected) < 0.001)
    }

    @Test("normalizeSleep passes through decimal")
    func normalizeSleepDecimal() {
        #expect(DateFormatting.normalizeSleep("6.5") == 6.5)
    }

    @Test("normalizeSleep returns nil for zero")
    func normalizeSleepZero() {
        #expect(DateFormatting.normalizeSleep("0") == nil)
    }

    @Test("normalizeSleep passes through integer")
    func normalizeSleepInteger() {
        #expect(DateFormatting.normalizeSleep("7") == 7.0)
    }

    @Test("normalizeSleep returns nil for empty string")
    func normalizeSleepEmpty() {
        #expect(DateFormatting.normalizeSleep("") == nil)
    }

    @Test("normalizeSleep returns nil for invalid input")
    func normalizeSleepInvalid() {
        #expect(DateFormatting.normalizeSleep("abc") == nil)
    }

    @Test("normalizeQualityScore divides values over 10")
    func normalizeQualityScoreOver10() {
        #expect(DateFormatting.normalizeQualityScore("80") == 8.0)
    }

    @Test("normalizeQualityScore passes through values <= 10")
    func normalizeQualityScoreNormal() {
        #expect(DateFormatting.normalizeQualityScore("7.5") == 7.5)
    }

    @Test("normalizeQualityScore passes through 10 exactly")
    func normalizeQualityScore10() {
        #expect(DateFormatting.normalizeQualityScore("10") == 10.0)
    }

    @Test("normalizeQualityScore returns nil for empty string")
    func normalizeQualityScoreEmpty() {
        #expect(DateFormatting.normalizeQualityScore("") == nil)
    }

    @Test("logFileName produces correct format")
    func logFileNameFormat() {
        let date = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!
        let fileName = DateFormatting.logFileName(for: date)
        #expect(fileName == "2026-02-17.md")
    }

    @Test("logFileName for different date")
    func logFileNameDifferentDate() {
        let date = DateFormatting.dailyLogFormatter.date(from: "2025-12-31")!
        let fileName = DateFormatting.logFileName(for: date)
        #expect(fileName == "2025-12-31.md")
    }

    @Test("protocolFileName uses Monday of the week")
    func protocolFileName() {
        // 2026-02-17 is a Tuesday, so Monday is 2026-02-16
        let date = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!
        let fileName = DateFormatting.protocolFileName(for: date)
        #expect(fileName == "protocol_2026-02-16.md")
    }

    @Test("weekNumber returns correct ISO week string")
    func weekNumberFormat() {
        // 2026-02-17 is in ISO week 8
        let date = DateFormatting.dailyLogFormatter.date(from: "2026-02-17")!
        let weekNum = DateFormatting.weekNumber(for: date)
        #expect(weekNum == "W08")
    }

    @Test("weekNumber for January 1 edge case")
    func weekNumberJan1() {
        // 2026-01-01 is a Thursday => ISO week 1
        let date = DateFormatting.dailyLogFormatter.date(from: "2026-01-01")!
        let weekNum = DateFormatting.weekNumber(for: date)
        #expect(weekNum == "W01")
    }
}

// MARK: - Enum Raw Value Tests

@Suite("Enum Raw Values")
struct EnumRawValueTests {

    @Test("DistanceUnit raw values")
    func distanceUnitRawValues() {
        #expect(DistanceUnit.meters.rawValue == "m")
        #expect(DistanceUnit.kilometers.rawValue == "km")
        #expect(DistanceUnit.miles.rawValue == "mi")
    }

    @Test("DistanceUnit CaseIterable has 3 cases")
    func distanceUnitCaseCount() {
        #expect(DistanceUnit.allCases.count == 3)
    }

    @Test("ExerciseCategory raw values")
    func exerciseCategoryRawValues() {
        #expect(ExerciseCategory.strength.rawValue == "strength")
        #expect(ExerciseCategory.cardio.rawValue == "cardio")
        #expect(ExerciseCategory.flexibility.rawValue == "flexibility")
        #expect(ExerciseCategory.balance.rawValue == "balance")
    }

    @Test("ExerciseCategory CaseIterable has 4 cases")
    func exerciseCategoryCaseCount() {
        #expect(ExerciseCategory.allCases.count == 4)
    }

    @Test("MetricField raw values")
    func metricFieldRawValues() {
        #expect(MetricField.weight.rawValue == "weight")
        #expect(MetricField.sleep.rawValue == "sleep")
        #expect(MetricField.sleepQuality.rawValue == "sleepQuality")
        #expect(MetricField.moodAM.rawValue == "moodAM")
        #expect(MetricField.moodPM.rawValue == "moodPM")
        #expect(MetricField.energy.rawValue == "energy")
        #expect(MetricField.focus.rawValue == "focus")
        #expect(MetricField.swimDistance.rawValue == "swimDistance")
        #expect(MetricField.bikeDistance.rawValue == "bikeDistance")
        #expect(MetricField.runDistance.rawValue == "runDistance")
        #expect(MetricField.swimDuration.rawValue == "swimDuration")
        #expect(MetricField.bikeDuration.rawValue == "bikeDuration")
        #expect(MetricField.runDuration.rawValue == "runDuration")
        #expect(MetricField.calories.rawValue == "calories")
        #expect(MetricField.protein.rawValue == "protein")
        #expect(MetricField.todoCompletion.rawValue == "todoCompletion")
        #expect(MetricField.habitCompletion.rawValue == "habitCompletion")
    }

    @Test("MetricField CaseIterable has 17 cases")
    func metricFieldCaseCount() {
        #expect(MetricField.allCases.count == 17)
    }

    @Test("MetricSource raw values")
    func metricSourceRawValues() {
        #expect(MetricSource.manual.rawValue == "manual")
        #expect(MetricSource.garmin.rawValue == "garmin")
        #expect(MetricSource.healthkit.rawValue == "healthkit")
        #expect(MetricSource.parsed.rawValue == "parsed")
    }

    @Test("MemoryCategory raw values")
    func memoryCategoryRawValues() {
        #expect(MemoryCategory.people.rawValue == "people")
        #expect(MemoryCategory.projects.rawValue == "projects")
        #expect(MemoryCategory.decisions.rawValue == "decisions")
        #expect(MemoryCategory.commitments.rawValue == "commitments")
    }

    @Test("MemoryCategory CaseIterable has 4 cases")
    func memoryCategoryCaseCount() {
        #expect(MemoryCategory.allCases.count == 4)
    }

    @Test("AppTab raw values")
    func appTabRawValues() {
        #expect(AppTab.dashboard.rawValue == "dashboard")
        #expect(AppTab.workout.rawValue == "workout")
        #expect(AppTab.logs.rawValue == "logs")
        #expect(AppTab.charts.rawValue == "charts")
        #expect(AppTab.settings.rawValue == "settings")
    }

    @Test("AppTab CaseIterable has 5 cases")
    func appTabCaseCount() {
        #expect(AppTab.allCases.count == 5)
    }
}

// MARK: - ExerciseSet Tests

@Suite("ExerciseSet")
struct ExerciseSetTests {

    @Test("Volume computes reps * weight when both present")
    func volume() {
        let set = ExerciseSet(exerciseName: "Bench", setNumber: 1, reps: 10, weightLbs: 185)
        #expect(set.volume == 1850)
    }

    @Test("Volume is nil when reps is nil")
    func volumeNilReps() {
        let set = ExerciseSet(exerciseName: "Plank", setNumber: 1, durationSeconds: 60)
        #expect(set.volume == nil)
    }

    @Test("Volume is nil when weight is nil")
    func volumeNilWeight() {
        let set = ExerciseSet(exerciseName: "Pull-up", setNumber: 1, reps: 10)
        #expect(set.volume == nil)
    }
}

// MARK: - NutritionEntry Tests

@Suite("NutritionEntry")
struct NutritionEntryTests {

    @Test("totalMacrosG sums all macros")
    func totalMacros() {
        let entry = NutritionEntry(food: "Chicken", proteinG: 30, carbsG: 5, fatG: 10)
        #expect(entry.totalMacrosG == 45)
    }

    @Test("totalMacrosG handles nil values as zero")
    func totalMacrosNil() {
        let entry = NutritionEntry(food: "Water")
        #expect(entry.totalMacrosG == 0)
    }
}

// MARK: - Exercise Tests

@Suite("Exercise")
struct ExerciseTests {

    @Test("Default isCustom is true")
    func defaultIsCustom() {
        let exercise = Exercise(name: "My Exercise", category: .strength)
        #expect(exercise.isCustom == true)
    }

    @Test("Exercise conforms to Hashable")
    func hashable() {
        let id = UUID()
        let a = Exercise(id: id, name: "Squat", category: .strength)
        let b = Exercise(id: id, name: "Squat", category: .strength)
        #expect(a.hashValue == b.hashValue)
    }
}

// MARK: - MemoryItem Tests

@Suite("MemoryItem")
struct MemoryItemTests {

    @Test("addInteraction appends and updates timestamp")
    func addInteraction() {
        var item = MemoryItem(
            category: .people,
            slug: "john-doe",
            name: "John Doe"
        )
        let initialUpdated = item.updated

        let interactionDate = Date().addingTimeInterval(100)
        item.addInteraction(note: "Met for coffee", date: interactionDate)

        #expect(item.interactions.count == 1)
        #expect(item.interactions[0].note == "Met for coffee")
        #expect(item.updated == interactionDate)
        #expect(item.updated != initialUpdated)
    }

    @Test("latestInteraction returns most recent")
    func latestInteraction() {
        var item = MemoryItem(category: .projects, slug: "be-stupid", name: "BeStupid")
        let early = Date(timeIntervalSince1970: 1000)
        let late = Date(timeIntervalSince1970: 2000)

        item.addInteraction(note: "Started project", date: early)
        item.addInteraction(note: "Shipped v1", date: late)

        let latest = try #require(item.latestInteraction)
        #expect(latest.note == "Shipped v1")
    }
}

// MARK: - GarminData Tests

@Suite("GarminData")
struct GarminDataTests {

    @Test("Body battery drain computes start - end")
    func bodyBatteryDrain() {
        let data = GarminDayData(
            date: Date(),
            bodyBatteryStart: 80,
            bodyBatteryEnd: 30
        )
        #expect(data.bodyBatteryDrain == 50)
    }

    @Test("Body battery drain is nil when values missing")
    func bodyBatteryDrainNil() {
        let data = GarminDayData(date: Date())
        #expect(data.bodyBatteryDrain == nil)
    }

    @Test("Total activity calories sums all activities")
    func totalActivityCalories() {
        let data = GarminDayData(
            date: Date(),
            activities: [
                GarminActivity(type: "running", name: "Morning Run", startTime: Date(), durationMinutes: 30, calories: 300),
                GarminActivity(type: "cycling", name: "Evening Ride", startTime: Date(), durationMinutes: 45, calories: 400),
            ]
        )
        #expect(data.totalActivityCalories == 700)
    }

    @Test("Total activity minutes sums all activities")
    func totalActivityMinutes() {
        let data = GarminDayData(
            date: Date(),
            activities: [
                GarminActivity(type: "running", name: "Run", startTime: Date(), durationMinutes: 30),
                GarminActivity(type: "swimming", name: "Swim", startTime: Date(), durationMinutes: 25),
            ]
        )
        #expect(data.totalActivityMinutes == 55)
    }

    @Test("GarminActivity distance in miles conversion")
    func garminActivityDistanceMiles() {
        let activity = GarminActivity(type: "running", name: "Run", startTime: Date(), durationMinutes: 30, distanceKm: 5.0)
        let miles = try #require(activity.distanceMiles)
        #expect(abs(miles - 3.10686) < 0.01)
    }
}

// MARK: - WeeklyProtocol Tests

@Suite("WeeklyProtocol")
struct WeeklyProtocolTests {

    @Test("Day lookup by dayOfWeek is case-insensitive")
    func dayLookup() {
        let proto = WeeklyProtocol(
            date: Date(),
            title: "Week 7",
            weekNumber: "W07",
            phase: "Base Building",
            focus: "Aerobic base",
            schedule: [
                ProtocolDay(dayOfWeek: "Monday", workoutType: "Swim", workout: "700m easy"),
                ProtocolDay(dayOfWeek: "Tuesday", workoutType: "Strength", workout: "Full body"),
            ]
        )

        let monday = proto.day(for: "monday")
        #expect(monday?.workoutType == "Swim")

        let tuesday = proto.day(for: "TUESDAY")
        #expect(tuesday?.workoutType == "Strength")

        let sunday = proto.day(for: "Sunday")
        #expect(sunday == nil)
    }

    @Test("Total workout days counts schedule entries")
    func totalWorkoutDays() {
        let proto = WeeklyProtocol(
            date: Date(),
            title: "Week 7",
            weekNumber: "W07",
            phase: "Base",
            focus: "Volume",
            schedule: [
                ProtocolDay(dayOfWeek: "Monday", workoutType: "Swim", workout: "700m"),
                ProtocolDay(dayOfWeek: "Wednesday", workoutType: "Run", workout: "5k"),
                ProtocolDay(dayOfWeek: "Friday", workoutType: "Bike", workout: "30 min"),
            ]
        )
        #expect(proto.totalWorkoutDays == 3)
    }
}

// MARK: - SyncStatus Tests

@Suite("SyncStatus")
struct SyncStatusTests {

    @Test("SyncStatus convenience properties")
    func syncStatusProperties() {
        #expect(SyncStatus.idle.isIdle == true)
        #expect(SyncStatus.idle.isSyncing == false)
        #expect(SyncStatus.idle.isError == false)
        #expect(SyncStatus.idle.errorMessage == nil)

        #expect(SyncStatus.syncing.isIdle == false)
        #expect(SyncStatus.syncing.isSyncing == true)

        let error = SyncStatus.error("Network timeout")
        #expect(error.isError == true)
        #expect(error.errorMessage == "Network timeout")
        #expect(error.isIdle == false)

        let success = SyncStatus.success(Date())
        #expect(success.isIdle == false)
        #expect(success.isError == false)
    }
}

// MARK: - Codable Roundtrip Tests for Supporting Types

@Suite("Codable Roundtrips")
struct CodableRoundtripTests {

    @Test("TrainingActivity Codable roundtrip")
    func trainingActivityRoundtrip() throws {
        let original = TrainingActivity(
            type: "swim",
            distance: 700,
            distanceUnit: .meters,
            durationMinutes: 25,
            avgHeartRate: 145,
            avgWatts: 120
        )
        let data = try JSONEncoder().encode(original)
        let decoded = try JSONDecoder().decode(TrainingActivity.self, from: data)
        #expect(decoded == original)
    }

    @Test("WorkoutSession Codable roundtrip")
    func workoutSessionRoundtrip() throws {
        let start = Date(timeIntervalSince1970: 1_000_000)
        let end = Date(timeIntervalSince1970: 1_003_600)
        let original = WorkoutSession(
            workoutType: "Strength",
            startTime: start,
            endTime: end,
            isActive: false,
            exercises: [
                ExerciseSet(exerciseName: "Squat", setNumber: 1, reps: 5, weightLbs: 225, completedAt: start)
            ],
            notes: "Good session",
            heartRateSamples: [
                HeartRateSample(timestamp: start, bpm: 130)
            ]
        )

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(original)

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let decoded = try decoder.decode(WorkoutSession.self, from: data)

        #expect(decoded == original)
    }

    @Test("MemoryItem Codable roundtrip")
    func memoryItemRoundtrip() throws {
        let date = Date(timeIntervalSince1970: 1_700_000_000)
        let original = MemoryItem(
            category: .people,
            slug: "jane-doe",
            name: "Jane Doe",
            status: "active",
            created: date,
            updated: date,
            fields: ["role": "Engineer", "company": "Acme"],
            interactions: [
                Interaction(date: date, note: "Initial meeting")
            ]
        )

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(original)

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let decoded = try decoder.decode(MemoryItem.self, from: data)

        #expect(decoded == original)
    }

    @Test("MetricDataPoint Codable roundtrip")
    func metricDataPointRoundtrip() throws {
        let date = Date(timeIntervalSince1970: 1_700_000_000)
        let original = MetricDataPoint(
            date: date,
            field: .weight,
            value: 183.5,
            source: .garmin
        )

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(original)

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let decoded = try decoder.decode(MetricDataPoint.self, from: data)

        #expect(decoded == original)
    }

    @Test("GarminDayData Codable roundtrip")
    func garminDayDataRoundtrip() throws {
        let date = Date(timeIntervalSince1970: 1_700_000_000)
        let original = GarminDayData(
            date: date,
            syncedAt: date,
            sleepScore: 85,
            sleepHours: 7.5,
            hrvOvernight: 55,
            bodyBatteryStart: 80,
            bodyBatteryEnd: 30,
            trainingReadiness: 70,
            recoveryScore: 0.75,
            recoveryStatus: "good",
            activities: [
                GarminActivity(type: "running", name: "Morning Run", startTime: date, durationMinutes: 30, distanceKm: 5.0, calories: 300, avgHR: 155)
            ]
        )

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(original)

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let decoded = try decoder.decode(GarminDayData.self, from: data)

        #expect(decoded == original)
    }

    @Test("WeeklyProtocol Codable roundtrip")
    func weeklyProtocolRoundtrip() throws {
        let date = Date(timeIntervalSince1970: 1_700_000_000)
        let original = WeeklyProtocol(
            date: date,
            title: "Week 7 Protocol",
            weekNumber: "W07",
            phase: "Base Building",
            focus: "Aerobic volume",
            targetCompliance: 0.85,
            schedule: [
                ProtocolDay(dayOfWeek: "Monday", workoutType: "Swim", workout: "700m easy")
            ],
            trainingGoals: ["Build aerobic base", "Increase swim distance"],
            cardioTargets: ["Swim": "700m", "Run": "5k"],
            strengthTargets: ["3x5 Squat @ 225"],
            aiRationale: "Building aerobic capacity before intensity phase"
        )

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(original)

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let decoded = try decoder.decode(WeeklyProtocol.self, from: data)

        #expect(decoded == original)
    }
}
