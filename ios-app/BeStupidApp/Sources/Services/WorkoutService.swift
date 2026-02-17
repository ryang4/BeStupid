import Foundation
import Observation

// MARK: - WorkoutService

/// Manages the lifecycle of workout sessions: start, log sets, rest timer, finish, and HealthKit sync.
/// Uses @Observable for SwiftUI integration and conforms to @unchecked Sendable because
/// all mutable state is accessed on MainActor or is internally synchronized.
@Observable
@MainActor
final class WorkoutService: @unchecked Sendable {
    private let healthKitProvider: any HealthDataProvider

    // MARK: - Published State

    /// The currently active workout session, if any.
    private(set) var activeWorkout: WorkoutSession?

    /// Whether a workout is currently in progress.
    var isWorkoutActive: Bool {
        activeWorkout?.isActive ?? false
    }

    /// Elapsed time in seconds since the workout started.
    var elapsedTime: TimeInterval {
        guard let workout = activeWorkout else { return 0 }
        if let endTime = workout.endTime {
            return endTime.timeIntervalSince(workout.startTime)
        }
        return Date().timeIntervalSince(workout.startTime)
    }

    /// Most recent heart rate reading during the active workout.
    private(set) var currentHeartRate: Int?

    /// Seconds remaining on the rest timer, or nil if not resting.
    private(set) var restTimeRemaining: Int?

    /// Whether a rest timer is currently counting down.
    var isResting: Bool {
        restTimeRemaining != nil
    }

    // MARK: - Internal State

    private var restTimer: Timer?
    private var heartRateTask: Task<Void, Never>?
    private var heartRateStream: AsyncStream<Int>?

    // MARK: - Init

    init(healthKitProvider: any HealthDataProvider) {
        self.healthKitProvider = healthKitProvider
    }

    // MARK: - Workout Lifecycle

    /// Starts a new workout session of the given type.
    /// - Parameter type: The workout type string (e.g. "swim", "run", "strength").
    /// - Returns: The newly created workout session.
    @discardableResult
    func startWorkout(type: String) -> WorkoutSession {
        // Cancel any existing workout state
        cancelRestTimer()
        stopHeartRateMonitoring()

        let session = WorkoutSession(
            workoutType: type,
            startTime: Date(),
            isActive: true
        )
        activeWorkout = session
        currentHeartRate = nil

        return session
    }

    /// Logs an exercise set to the current active workout.
    /// Automatically assigns the next set number for the given exercise name.
    /// - Parameters:
    ///   - exerciseName: The name of the exercise (e.g. "Bench Press").
    ///   - reps: Number of repetitions, if applicable.
    ///   - weightLbs: Weight in pounds, if applicable.
    ///   - duration: Duration in seconds, if applicable (for timed exercises).
    ///   - distance: Distance, if applicable.
    /// - Returns: The created ExerciseSet, or nil if no workout is active.
    @discardableResult
    func logSet(
        exerciseName: String,
        reps: Int? = nil,
        weightLbs: Double? = nil,
        duration: Double? = nil,
        distance: Double? = nil
    ) -> ExerciseSet? {
        guard var workout = activeWorkout, workout.isActive else {
            return nil
        }

        // Auto-increment set number per exercise
        let existingSetsForExercise = workout.exercises.filter { $0.exerciseName == exerciseName }
        let nextSetNumber = existingSetsForExercise.count + 1

        let exerciseSet = ExerciseSet(
            exerciseName: exerciseName,
            setNumber: nextSetNumber,
            reps: reps,
            weightLbs: weightLbs,
            durationSeconds: duration,
            distance: distance,
            completedAt: Date()
        )

        workout.addSet(exerciseSet)
        activeWorkout = workout

        return exerciseSet
    }

    /// Starts a rest timer that counts down from the given number of seconds.
    /// When the timer reaches zero, `restTimeRemaining` becomes nil.
    /// - Parameter seconds: Number of seconds to rest.
    func startRest(seconds: Int) {
        cancelRestTimer()
        restTimeRemaining = seconds

        restTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] timer in
            Task { @MainActor [weak self] in
                guard let self else {
                    timer.invalidate()
                    return
                }
                guard let remaining = self.restTimeRemaining, remaining > 0 else {
                    self.cancelRestTimer()
                    return
                }
                let newRemaining = remaining - 1
                if newRemaining <= 0 {
                    self.cancelRestTimer()
                } else {
                    self.restTimeRemaining = newRemaining
                }
            }
        }
    }

    /// Finishes the current workout, saves it to HealthKit, and returns the completed session.
    /// - Throws: HealthKitServiceError if saving fails.
    /// - Returns: The completed workout session, or nil if no workout was active.
    @discardableResult
    func finishWorkout() async throws -> WorkoutSession? {
        guard var workout = activeWorkout, workout.isActive else {
            return nil
        }

        // Stop ancillary processes
        cancelRestTimer()
        stopHeartRateMonitoring()

        // Finalize the workout
        workout.finish()
        activeWorkout = workout

        // Save to HealthKit
        try await healthKitProvider.saveWorkout(workout)

        // Clear active state
        let finished = workout
        activeWorkout = nil
        currentHeartRate = nil

        return finished
    }

    /// Discards the current workout without saving to HealthKit.
    func discardWorkout() {
        cancelRestTimer()
        stopHeartRateMonitoring()
        activeWorkout = nil
        currentHeartRate = nil
    }

    // MARK: - Conversion

    /// Converts a WorkoutSession's exercise sets into aggregated StrengthEntry values.
    /// Groups sets by exercise name and computes average reps and weight.
    /// Only includes exercises that have both reps and weight data.
    func toStrengthEntries(_ session: WorkoutSession) -> [StrengthEntry] {
        let grouped = Dictionary(grouping: session.exercises) { $0.exerciseName }
        var entries: [StrengthEntry] = []

        for exerciseName in session.uniqueExerciseNames {
            guard let sets = grouped[exerciseName] else { continue }
            let setsWithWeight = sets.filter { $0.reps != nil && $0.weightLbs != nil }
            guard !setsWithWeight.isEmpty else { continue }

            let totalReps = setsWithWeight.compactMap(\.reps).reduce(0, +)
            let avgReps = totalReps / setsWithWeight.count
            let avgWeight = setsWithWeight.compactMap(\.weightLbs).reduce(0.0, +) / Double(setsWithWeight.count)

            let entry = StrengthEntry(
                exerciseName: exerciseName,
                sets: setsWithWeight.count,
                reps: avgReps,
                weightLbs: avgWeight
            )
            entries.append(entry)
        }

        return entries
    }

    /// Converts a WorkoutSession into a TrainingActivity for the daily log.
    func toTrainingActivity(_ session: WorkoutSession) -> TrainingActivity {
        TrainingActivity(
            type: session.workoutType,
            distance: session.totalDistance,
            distanceUnit: session.distanceUnit ?? .meters,
            durationMinutes: session.durationMinutes,
            avgHeartRate: session.averageHeartRate
        )
    }

    // MARK: - Heart Rate Monitoring

    /// Begins streaming live heart rate data from HealthKit.
    /// Updates `currentHeartRate` as new samples arrive and appends to the active workout.
    func startHeartRateMonitoring() async {
        stopHeartRateMonitoring()

        let stream = await healthKitProvider.startLiveHeartRate()
        heartRateStream = stream

        heartRateTask = Task { [weak self] in
            for await bpm in stream {
                guard !Task.isCancelled else { break }
                await MainActor.run {
                    guard let self else { return }
                    self.currentHeartRate = bpm
                    self.activeWorkout?.recordHeartRate(bpm: bpm)
                }
            }
        }
    }

    /// Stops the live heart rate stream.
    func stopHeartRateMonitoring() {
        heartRateTask?.cancel()
        heartRateTask = nil

        Task {
            await healthKitProvider.stopLiveHeartRate()
        }

        heartRateStream = nil
    }

    // MARK: - Private Helpers

    private func cancelRestTimer() {
        restTimer?.invalidate()
        restTimer = nil
        restTimeRemaining = nil
    }
}
