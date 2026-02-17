import Testing
import Foundation
@testable import BeStupidApp

// MARK: - Mock HealthDataProvider

/// A mock implementation of HealthDataProvider for testing WorkoutService
/// without requiring HealthKit availability.
actor MockHealthDataProvider: HealthDataProvider {
    var authorizationRequested = false
    var savedWorkouts: [WorkoutSession] = []
    var shouldThrowOnSave = false
    var saveError: Error?

    var mockHeartRateSamples: [HeartRateSample] = []
    var mockSleepData: SleepData = SleepData(
        totalHours: 7.5,
        inBedHours: 8.0,
        deepSleepHours: 1.5,
        remSleepHours: 2.0,
        lightSleepHours: 4.0,
        awakeHours: 0.5,
        startTime: nil,
        endTime: nil
    )
    var mockWeightSamples: [WeightSample] = []
    var mockSteps: Int = 8500
    var mockRestingHeartRate: Int? = 55

    private var liveHeartRateContinuation: AsyncStream<Int>.Continuation?
    private(set) var liveHeartRateStopped = false
    private(set) var liveHeartRateStarted = false

    // MARK: - Authorization

    func requestAuthorization() async throws {
        authorizationRequested = true
    }

    var isAuthorized: Bool {
        authorizationRequested
    }

    // MARK: - Write

    func saveWorkout(_ session: WorkoutSession) async throws {
        if shouldThrowOnSave, let error = saveError {
            throw error
        }
        if shouldThrowOnSave {
            throw HealthKitServiceError.queryFailed("Mock save failure")
        }
        savedWorkouts.append(session)
    }

    // MARK: - Read

    func fetchHeartRate(from startDate: Date, to endDate: Date) async throws -> [HeartRateSample] {
        mockHeartRateSamples.filter { $0.timestamp >= startDate && $0.timestamp <= endDate }
    }

    func fetchSleepAnalysis(for date: Date) async throws -> SleepData {
        mockSleepData
    }

    func fetchWeight(from startDate: Date, to endDate: Date) async throws -> [WeightSample] {
        mockWeightSamples.filter { $0.date >= startDate && $0.date <= endDate }
    }

    func fetchSteps(for date: Date) async throws -> Int {
        mockSteps
    }

    func fetchRestingHeartRate(for date: Date) async throws -> Int? {
        mockRestingHeartRate
    }

    // MARK: - Live Heart Rate

    func startLiveHeartRate() -> AsyncStream<Int> {
        liveHeartRateStarted = true
        liveHeartRateStopped = false
        let (stream, continuation) = AsyncStream<Int>.makeStream()
        self.liveHeartRateContinuation = continuation
        return stream
    }

    func stopLiveHeartRate() {
        liveHeartRateStopped = true
        liveHeartRateContinuation?.finish()
        liveHeartRateContinuation = nil
    }

    /// Simulate a heart rate sample arriving on the live stream.
    func emitHeartRate(_ bpm: Int) {
        liveHeartRateContinuation?.yield(bpm)
    }

    // MARK: - Test Helpers

    func getSavedWorkoutCount() -> Int {
        savedWorkouts.count
    }

    func getLastSavedWorkout() -> WorkoutSession? {
        savedWorkouts.last
    }
}

// MARK: - WorkoutService Tests

@Suite("WorkoutService Tests")
struct WorkoutServiceTests {

    // MARK: - Helpers

    @MainActor
    private func makeSUT() -> (WorkoutService, MockHealthDataProvider) {
        let mock = MockHealthDataProvider()
        let service = WorkoutService(healthKitProvider: mock)
        return (service, mock)
    }

    // MARK: - Start Workout

    @Test("startWorkout creates a session with correct type")
    @MainActor
    func startWorkoutCreatesSessionWithCorrectType() {
        let (service, _) = makeSUT()

        let session = service.startWorkout(type: "strength")

        #expect(session.workoutType == "strength")
        #expect(session.isActive == true)
        #expect(session.exercises.isEmpty)
        #expect(session.heartRateSamples.isEmpty)
        #expect(session.endTime == nil)
    }

    @Test("startWorkout sets the start time to approximately now")
    @MainActor
    func startWorkoutSetsStartTime() {
        let (service, _) = makeSUT()
        let before = Date()

        let session = service.startWorkout(type: "run")

        let after = Date()
        #expect(session.startTime >= before)
        #expect(session.startTime <= after)
    }

    @Test("startWorkout sets activeWorkout property")
    @MainActor
    func startWorkoutSetsActiveWorkout() {
        let (service, _) = makeSUT()

        #expect(service.activeWorkout == nil)
        #expect(service.isWorkoutActive == false)

        service.startWorkout(type: "swim")

        #expect(service.activeWorkout != nil)
        #expect(service.isWorkoutActive == true)
    }

    @Test("startWorkout replaces previous active workout")
    @MainActor
    func startWorkoutReplacePrevious() {
        let (service, _) = makeSUT()

        let first = service.startWorkout(type: "run")
        let second = service.startWorkout(type: "bike")

        #expect(service.activeWorkout?.id == second.id)
        #expect(service.activeWorkout?.id != first.id)
        #expect(service.activeWorkout?.workoutType == "bike")
    }

    // MARK: - Log Set

    @Test("logSet adds exercise set with correct set number starting at 1")
    @MainActor
    func logSetAddsExerciseWithCorrectSetNumber() {
        let (service, _) = makeSUT()
        service.startWorkout(type: "strength")

        let set = service.logSet(exerciseName: "Bench Press", reps: 10, weightLbs: 135)

        #expect(set != nil)
        #expect(set?.exerciseName == "Bench Press")
        #expect(set?.setNumber == 1)
        #expect(set?.reps == 10)
        #expect(set?.weightLbs == 135)
        #expect(service.activeWorkout?.exercises.count == 1)
    }

    @Test("logSet auto-increments set number per exercise")
    @MainActor
    func logSetAutoIncrementsSetNumber() {
        let (service, _) = makeSUT()
        service.startWorkout(type: "strength")

        let set1 = service.logSet(exerciseName: "Squat", reps: 5, weightLbs: 225)
        let set2 = service.logSet(exerciseName: "Squat", reps: 5, weightLbs: 225)
        let set3 = service.logSet(exerciseName: "Squat", reps: 5, weightLbs: 225)

        #expect(set1?.setNumber == 1)
        #expect(set2?.setNumber == 2)
        #expect(set3?.setNumber == 3)
        #expect(service.activeWorkout?.exercises.count == 3)
    }

    @Test("logSet tracks different exercises independently")
    @MainActor
    func logSetTracksDifferentExercisesIndependently() {
        let (service, _) = makeSUT()
        service.startWorkout(type: "strength")

        let benchSet1 = service.logSet(exerciseName: "Bench Press", reps: 10, weightLbs: 135)
        let squatSet1 = service.logSet(exerciseName: "Squat", reps: 5, weightLbs: 225)
        let benchSet2 = service.logSet(exerciseName: "Bench Press", reps: 8, weightLbs: 155)

        #expect(benchSet1?.setNumber == 1)
        #expect(squatSet1?.setNumber == 1)
        #expect(benchSet2?.setNumber == 2)
        #expect(service.activeWorkout?.exercises.count == 3)
    }

    @Test("logSet returns nil when no workout is active")
    @MainActor
    func logSetReturnsNilWithNoWorkout() {
        let (service, _) = makeSUT()

        let result = service.logSet(exerciseName: "Deadlift", reps: 5, weightLbs: 315)

        #expect(result == nil)
    }

    @Test("logSet records completedAt timestamp")
    @MainActor
    func logSetRecordsTimestamp() {
        let (service, _) = makeSUT()
        service.startWorkout(type: "strength")
        let before = Date()

        let set = service.logSet(exerciseName: "Pull-ups", reps: 12)

        let after = Date()
        #expect(set != nil)
        #expect(set!.completedAt >= before)
        #expect(set!.completedAt <= after)
    }

    @Test("logSet supports duration-based exercises")
    @MainActor
    func logSetSupportsDuration() {
        let (service, _) = makeSUT()
        service.startWorkout(type: "strength")

        let set = service.logSet(exerciseName: "Plank", duration: 60.0)

        #expect(set?.durationSeconds == 60.0)
        #expect(set?.reps == nil)
        #expect(set?.weightLbs == nil)
    }

    // MARK: - Finish Workout

    @Test("finishWorkout sets endTime and isActive to false")
    @MainActor
    func finishWorkoutSetsEndTimeAndInactive() async throws {
        let (service, _) = makeSUT()
        service.startWorkout(type: "run")

        let finished = try await service.finishWorkout()

        #expect(finished != nil)
        #expect(finished?.isActive == false)
        #expect(finished?.endTime != nil)
    }

    @Test("finishWorkout calls healthKit.saveWorkout")
    @MainActor
    func finishWorkoutSavesToHealthKit() async throws {
        let (service, mock) = makeSUT()
        service.startWorkout(type: "run")

        let finished = try await service.finishWorkout()

        let savedCount = await mock.getSavedWorkoutCount()
        #expect(savedCount == 1)

        let savedWorkout = await mock.getLastSavedWorkout()
        #expect(savedWorkout?.id == finished?.id)
    }

    @Test("finishWorkout clears activeWorkout")
    @MainActor
    func finishWorkoutClearsActive() async throws {
        let (service, _) = makeSUT()
        service.startWorkout(type: "bike")

        _ = try await service.finishWorkout()

        #expect(service.activeWorkout == nil)
        #expect(service.isWorkoutActive == false)
    }

    @Test("finishWorkout returns nil when no workout is active")
    @MainActor
    func finishWorkoutReturnsNilWhenInactive() async throws {
        let (service, _) = makeSUT()

        let result = try await service.finishWorkout()

        #expect(result == nil)
    }

    @Test("finishWorkout preserves logged sets in the saved workout")
    @MainActor
    func finishWorkoutPreservesSets() async throws {
        let (service, mock) = makeSUT()
        service.startWorkout(type: "strength")
        service.logSet(exerciseName: "Bench Press", reps: 10, weightLbs: 135)
        service.logSet(exerciseName: "Bench Press", reps: 8, weightLbs: 155)

        _ = try await service.finishWorkout()

        let saved = await mock.getLastSavedWorkout()
        #expect(saved?.exercises.count == 2)
        #expect(saved?.exercises[0].exerciseName == "Bench Press")
        #expect(saved?.exercises[1].weightLbs == 155)
    }

    // MARK: - Discard Workout

    @Test("discardWorkout does not save to HealthKit")
    @MainActor
    func discardWorkoutDoesNotSave() async {
        let (service, mock) = makeSUT()
        service.startWorkout(type: "run")
        service.logSet(exerciseName: "Mile 1", duration: 480)

        service.discardWorkout()

        let savedCount = await mock.getSavedWorkoutCount()
        #expect(savedCount == 0)
    }

    @Test("discardWorkout clears activeWorkout")
    @MainActor
    func discardWorkoutClearsActive() {
        let (service, _) = makeSUT()
        service.startWorkout(type: "swim")

        service.discardWorkout()

        #expect(service.activeWorkout == nil)
        #expect(service.isWorkoutActive == false)
    }

    @Test("discardWorkout clears currentHeartRate")
    @MainActor
    func discardWorkoutClearsHeartRate() {
        let (service, _) = makeSUT()
        service.startWorkout(type: "run")

        service.discardWorkout()

        #expect(service.currentHeartRate == nil)
    }

    // MARK: - Rest Timer

    @Test("startRest sets restTimeRemaining")
    @MainActor
    func startRestSetsTime() {
        let (service, _) = makeSUT()

        service.startRest(seconds: 90)

        #expect(service.restTimeRemaining == 90)
        #expect(service.isResting == true)
    }

    @Test("startRest replaces existing rest timer")
    @MainActor
    func startRestReplacesExisting() {
        let (service, _) = makeSUT()
        service.startRest(seconds: 60)
        service.startRest(seconds: 120)

        #expect(service.restTimeRemaining == 120)
    }

    @Test("isResting is false when no rest timer active")
    @MainActor
    func isRestingFalseByDefault() {
        let (service, _) = makeSUT()

        #expect(service.isResting == false)
        #expect(service.restTimeRemaining == nil)
    }

    @Test("discardWorkout cancels rest timer")
    @MainActor
    func discardWorkoutCancelsRest() {
        let (service, _) = makeSUT()
        service.startWorkout(type: "strength")
        service.startRest(seconds: 60)

        service.discardWorkout()

        #expect(service.isResting == false)
        #expect(service.restTimeRemaining == nil)
    }

    // MARK: - Elapsed Time

    @Test("elapsedTime returns 0 when no workout is active")
    @MainActor
    func elapsedTimeZeroWhenInactive() {
        let (service, _) = makeSUT()

        #expect(service.elapsedTime == 0)
    }

    @Test("elapsedTime is positive during active workout")
    @MainActor
    func elapsedTimePositiveDuringWorkout() async throws {
        let (service, _) = makeSUT()
        service.startWorkout(type: "run")

        // Give a tiny bit of time to pass
        try await Task.sleep(for: .milliseconds(50))

        #expect(service.elapsedTime > 0)
    }

    // MARK: - toStrengthEntries Conversion

    @Test("toStrengthEntries aggregates sets into entries")
    @MainActor
    func toStrengthEntriesAggregatesSets() {
        let (service, _) = makeSUT()

        let session = WorkoutSession(
            workoutType: "strength",
            startTime: Date().addingTimeInterval(-3600),
            endTime: Date(),
            isActive: false,
            exercises: [
                ExerciseSet(exerciseName: "Bench Press", setNumber: 1, reps: 10, weightLbs: 135),
                ExerciseSet(exerciseName: "Bench Press", setNumber: 2, reps: 8, weightLbs: 155),
                ExerciseSet(exerciseName: "Bench Press", setNumber: 3, reps: 6, weightLbs: 175),
                ExerciseSet(exerciseName: "Squat", setNumber: 1, reps: 5, weightLbs: 225),
                ExerciseSet(exerciseName: "Squat", setNumber: 2, reps: 5, weightLbs: 225),
            ]
        )

        let entries = service.toStrengthEntries(session)

        #expect(entries.count == 2)

        let bench = entries.first { $0.exerciseName == "Bench Press" }
        #expect(bench != nil)
        #expect(bench?.sets == 3)
        // Average reps: (10 + 8 + 6) / 3 = 8
        #expect(bench?.reps == 8)
        // Average weight: (135 + 155 + 175) / 3 = 155
        #expect(bench?.weightLbs == 155.0)

        let squat = entries.first { $0.exerciseName == "Squat" }
        #expect(squat != nil)
        #expect(squat?.sets == 2)
        #expect(squat?.reps == 5)
        #expect(squat?.weightLbs == 225.0)
    }

    @Test("toStrengthEntries excludes exercises without reps and weight")
    @MainActor
    func toStrengthEntriesExcludesDurationOnly() {
        let (service, _) = makeSUT()

        let session = WorkoutSession(
            workoutType: "strength",
            startTime: Date().addingTimeInterval(-3600),
            endTime: Date(),
            isActive: false,
            exercises: [
                ExerciseSet(exerciseName: "Bench Press", setNumber: 1, reps: 10, weightLbs: 135),
                ExerciseSet(exerciseName: "Plank", setNumber: 1, durationSeconds: 60),
            ]
        )

        let entries = service.toStrengthEntries(session)

        #expect(entries.count == 1)
        #expect(entries[0].exerciseName == "Bench Press")
    }

    @Test("toStrengthEntries preserves exercise order")
    @MainActor
    func toStrengthEntriesPreservesOrder() {
        let (service, _) = makeSUT()

        let session = WorkoutSession(
            workoutType: "strength",
            startTime: Date().addingTimeInterval(-3600),
            endTime: Date(),
            isActive: false,
            exercises: [
                ExerciseSet(exerciseName: "Deadlift", setNumber: 1, reps: 3, weightLbs: 315),
                ExerciseSet(exerciseName: "Bench Press", setNumber: 1, reps: 10, weightLbs: 135),
                ExerciseSet(exerciseName: "Squat", setNumber: 1, reps: 5, weightLbs: 225),
            ]
        )

        let entries = service.toStrengthEntries(session)

        #expect(entries.count == 3)
        #expect(entries[0].exerciseName == "Deadlift")
        #expect(entries[1].exerciseName == "Bench Press")
        #expect(entries[2].exerciseName == "Squat")
    }

    @Test("toStrengthEntries returns empty for empty workout")
    @MainActor
    func toStrengthEntriesEmptyWorkout() {
        let (service, _) = makeSUT()

        let session = WorkoutSession(
            workoutType: "strength",
            startTime: Date(),
            endTime: Date(),
            isActive: false
        )

        let entries = service.toStrengthEntries(session)

        #expect(entries.isEmpty)
    }

    // MARK: - toTrainingActivity Conversion

    @Test("toTrainingActivity creates correct activity from session")
    @MainActor
    func toTrainingActivityCreatesCorrectActivity() {
        let (service, _) = makeSUT()

        let startTime = Date().addingTimeInterval(-1800)
        let endTime = Date()

        let session = WorkoutSession(
            workoutType: "run",
            startTime: startTime,
            endTime: endTime,
            isActive: false,
            totalDistance: 5.0,
            distanceUnit: .kilometers,
            heartRateSamples: [
                HeartRateSample(bpm: 140),
                HeartRateSample(bpm: 150),
                HeartRateSample(bpm: 160),
            ]
        )

        let activity = service.toTrainingActivity(session)

        #expect(activity.type == "run")
        #expect(activity.distance == 5.0)
        #expect(activity.distanceUnit == .kilometers)
        #expect(activity.avgHeartRate == 150) // (140 + 150 + 160) / 3
        #expect(activity.durationMinutes != nil)
    }

    @Test("toTrainingActivity uses meters as default distance unit")
    @MainActor
    func toTrainingActivityDefaultsToMeters() {
        let (service, _) = makeSUT()

        let session = WorkoutSession(
            workoutType: "swim",
            startTime: Date().addingTimeInterval(-1800),
            endTime: Date(),
            isActive: false,
            totalDistance: 1500
        )

        let activity = service.toTrainingActivity(session)

        #expect(activity.distanceUnit == .meters)
        #expect(activity.distance == 1500)
    }

    @Test("toTrainingActivity handles session with no distance")
    @MainActor
    func toTrainingActivityNoDistance() {
        let (service, _) = makeSUT()

        let session = WorkoutSession(
            workoutType: "strength",
            startTime: Date().addingTimeInterval(-3600),
            endTime: Date(),
            isActive: false
        )

        let activity = service.toTrainingActivity(session)

        #expect(activity.type == "strength")
        #expect(activity.distance == nil)
        #expect(activity.avgHeartRate == nil)
    }
}

// MARK: - Workout Type Mapping Tests

@Suite("WorkoutTypeMapping Tests")
struct WorkoutTypeMappingTests {

    @Test("swim maps to swimming")
    func swimMapping() {
        let result = WorkoutTypeMapping.activityType(for: "swim")
        #expect(result == .swimming)
    }

    @Test("bike maps to cycling")
    func bikeMapping() {
        let result = WorkoutTypeMapping.activityType(for: "bike")
        #expect(result == .cycling)
    }

    @Test("run maps to running")
    func runMapping() {
        let result = WorkoutTypeMapping.activityType(for: "run")
        #expect(result == .running)
    }

    @Test("strength maps to traditionalStrengthTraining")
    func strengthMapping() {
        let result = WorkoutTypeMapping.activityType(for: "strength")
        #expect(result == .traditionalStrengthTraining)
    }

    @Test("brick maps to mixedCardio")
    func brickMapping() {
        let result = WorkoutTypeMapping.activityType(for: "brick")
        #expect(result == .mixedCardio)
    }

    @Test("recovery maps to flexibility")
    func recoveryMapping() {
        let result = WorkoutTypeMapping.activityType(for: "recovery")
        #expect(result == .flexibility)
    }

    @Test("yoga maps to yoga")
    func yogaMapping() {
        let result = WorkoutTypeMapping.activityType(for: "yoga")
        #expect(result == .yoga)
    }

    @Test("walk maps to walking")
    func walkMapping() {
        let result = WorkoutTypeMapping.activityType(for: "walk")
        #expect(result == .walking)
    }

    @Test("unknown type maps to other")
    func unknownMapping() {
        let result = WorkoutTypeMapping.activityType(for: "unicycling")
        #expect(result == .other)
    }

    @Test("mapping is case-insensitive")
    func caseInsensitive() {
        #expect(WorkoutTypeMapping.activityType(for: "SWIM") == .swimming)
        #expect(WorkoutTypeMapping.activityType(for: "Run") == .running)
        #expect(WorkoutTypeMapping.activityType(for: "Bike") == .cycling)
        #expect(WorkoutTypeMapping.activityType(for: "STRENGTH") == .traditionalStrengthTraining)
    }
}

// MARK: - MockHealthDataProvider Tests

@Suite("MockHealthDataProvider Tests")
struct MockHealthDataProviderTests {

    @Test("requestAuthorization sets authorizationRequested")
    func authorizationTracking() async throws {
        let mock = MockHealthDataProvider()

        let beforeAuth = await mock.isAuthorized
        #expect(beforeAuth == false)

        try await mock.requestAuthorization()

        let afterAuth = await mock.isAuthorized
        #expect(afterAuth == true)
    }

    @Test("saveWorkout stores the workout")
    func saveWorkoutStores() async throws {
        let mock = MockHealthDataProvider()
        let session = WorkoutSession(
            workoutType: "run",
            startTime: Date().addingTimeInterval(-1800),
            endTime: Date(),
            isActive: false
        )

        try await mock.saveWorkout(session)

        let count = await mock.getSavedWorkoutCount()
        #expect(count == 1)
    }

    @Test("fetchSteps returns mock value")
    func fetchStepsReturnsMock() async throws {
        let mock = MockHealthDataProvider()
        let steps = try await mock.fetchSteps(for: Date())
        #expect(steps == 8500)
    }

    @Test("fetchRestingHeartRate returns mock value")
    func fetchRestingHRReturnsMock() async throws {
        let mock = MockHealthDataProvider()
        let hr = try await mock.fetchRestingHeartRate(for: Date())
        #expect(hr == 55)
    }

    @Test("fetchSleepAnalysis returns mock sleep data")
    func fetchSleepReturnsMock() async throws {
        let mock = MockHealthDataProvider()
        let sleep = try await mock.fetchSleepAnalysis(for: Date())
        #expect(sleep.totalHours == 7.5)
        #expect(sleep.deepSleepHours == 1.5)
    }

    @Test("fetchHeartRate filters by date range")
    func fetchHeartRateFilters() async throws {
        let mock = MockHealthDataProvider()
        let now = Date()
        let hourAgo = now.addingTimeInterval(-3600)
        let twoHoursAgo = now.addingTimeInterval(-7200)

        await mock.setMockHeartRateSamples([
            HeartRateSample(timestamp: twoHoursAgo, bpm: 60),
            HeartRateSample(timestamp: hourAgo, bpm: 75),
            HeartRateSample(timestamp: now, bpm: 80),
        ])

        let results = try await mock.fetchHeartRate(from: hourAgo, to: now)

        #expect(results.count == 2)
        #expect(results[0].bpm == 75)
        #expect(results[1].bpm == 80)
    }

    @Test("fetchWeight filters by date range")
    func fetchWeightFilters() async throws {
        let mock = MockHealthDataProvider()
        let now = Date()
        let yesterday = now.addingTimeInterval(-86400)
        let twoDaysAgo = now.addingTimeInterval(-172800)

        await mock.setMockWeightSamples([
            WeightSample(id: UUID(), date: twoDaysAgo, weightLbs: 180, source: "Withings"),
            WeightSample(id: UUID(), date: yesterday, weightLbs: 179, source: "Withings"),
            WeightSample(id: UUID(), date: now, weightLbs: 178, source: "Manual"),
        ])

        let results = try await mock.fetchWeight(from: yesterday, to: now)

        #expect(results.count == 2)
    }
}

// MARK: - SleepData Tests

@Suite("SleepData Tests")
struct SleepDataTests {

    @Test("empty SleepData has zero hours")
    func emptySleepData() {
        let empty = SleepData.empty
        #expect(empty.totalHours == 0)
        #expect(empty.inBedHours == 0)
        #expect(empty.deepSleepHours == nil)
        #expect(empty.remSleepHours == nil)
        #expect(empty.lightSleepHours == nil)
        #expect(empty.awakeHours == nil)
        #expect(empty.startTime == nil)
        #expect(empty.endTime == nil)
    }

    @Test("SleepData supports equatable comparison")
    func sleepDataEquatable() {
        let a = SleepData(
            totalHours: 7.0,
            inBedHours: 8.0,
            deepSleepHours: 1.5,
            remSleepHours: 2.0,
            lightSleepHours: 3.5,
            awakeHours: 1.0,
            startTime: nil,
            endTime: nil
        )
        let b = SleepData(
            totalHours: 7.0,
            inBedHours: 8.0,
            deepSleepHours: 1.5,
            remSleepHours: 2.0,
            lightSleepHours: 3.5,
            awakeHours: 1.0,
            startTime: nil,
            endTime: nil
        )
        #expect(a == b)
    }
}

// MARK: - WeightSample Tests

@Suite("WeightSample Tests")
struct WeightSampleTests {

    @Test("WeightSample stores correct properties")
    func weightSampleProperties() {
        let now = Date()
        let sample = WeightSample(id: UUID(), date: now, weightLbs: 180.5, source: "Withings")

        #expect(sample.weightLbs == 180.5)
        #expect(sample.source == "Withings")
        #expect(sample.date == now)
    }

    @Test("WeightSample supports equatable comparison")
    func weightSampleEquatable() {
        let id = UUID()
        let now = Date()
        let a = WeightSample(id: id, date: now, weightLbs: 175.0, source: "Manual")
        let b = WeightSample(id: id, date: now, weightLbs: 175.0, source: "Manual")
        #expect(a == b)
    }
}

// MARK: - HealthKitServiceError Tests

@Suite("HealthKitServiceError Tests")
struct HealthKitServiceErrorTests {

    @Test("healthKitNotAvailable has descriptive message")
    func notAvailableDescription() {
        let error = HealthKitServiceError.healthKitNotAvailable
        #expect(error.errorDescription?.contains("not available") == true)
    }

    @Test("workoutNotFinished has descriptive message")
    func notFinishedDescription() {
        let error = HealthKitServiceError.workoutNotFinished
        #expect(error.errorDescription?.contains("active") == true)
    }

    @Test("duplicateWorkout has descriptive message")
    func duplicateDescription() {
        let error = HealthKitServiceError.duplicateWorkout
        #expect(error.errorDescription?.contains("already exists") == true)
    }

    @Test("invalidWorkoutType includes the type name")
    func invalidTypeDescription() {
        let error = HealthKitServiceError.invalidWorkoutType("zorbing")
        #expect(error.errorDescription?.contains("zorbing") == true)
    }

    @Test("queryFailed includes the reason")
    func queryFailedDescription() {
        let error = HealthKitServiceError.queryFailed("timeout")
        #expect(error.errorDescription?.contains("timeout") == true)
    }
}

// MARK: - Mock Helpers

extension MockHealthDataProvider {
    func setMockHeartRateSamples(_ samples: [HeartRateSample]) {
        mockHeartRateSamples = samples
    }

    func setMockWeightSamples(_ samples: [WeightSample]) {
        mockWeightSamples = samples
    }
}
