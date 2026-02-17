import Foundation
import Observation
import SwiftUI

// MARK: - QuickIncrementField

enum QuickIncrementField: Sendable {
    case weight(amount: Double)
    case reps(amount: Int)
}

// MARK: - WorkoutViewModel

@Observable
@MainActor
final class WorkoutViewModel {

    // MARK: - Active Workout State

    var activeWorkout: WorkoutSession?

    var isWorkoutActive: Bool {
        activeWorkout?.isActive ?? false
    }

    var elapsedSeconds: Int = 0
    var currentHeartRate: Int?
    var currentExerciseName: String = ""
    var currentReps: String = ""
    var currentWeight: String = ""

    // MARK: - Rest Timer

    var restTimeRemaining: Int = 0

    var isResting: Bool {
        restTimeRemaining > 0
    }

    var defaultRestSeconds: Int = 90

    // MARK: - Exercise Library

    var exercises: [Exercise] = []
    var recentExercises: [String] = []
    var lastSessionData: [String: (reps: Int, weight: Double)] = [:]

    // MARK: - Workout History

    var recentWorkouts: [WorkoutSession] = []

    // MARK: - After-the-Fact Entry

    var isShowingManualEntry: Bool = false
    var manualEntryType: String = ""
    var manualEntryDate: Date = Date()
    var manualEntryDuration: String = ""
    var manualEntryDistance: String = ""
    var manualEntryDistanceUnit: DistanceUnit = .miles
    var manualEntryHeartRate: String = ""
    var manualEntryExercises: [StrengthEntry] = []
    var manualEntryNotes: String = ""

    // MARK: - Navigation State

    var isShowingSummary: Bool = false
    var completedWorkout: WorkoutSession?
    var workoutNotes: String = ""

    // MARK: - Validation

    var canLogSet: Bool {
        !currentExerciseName.trimmingCharacters(in: .whitespaces).isEmpty
            && (!currentReps.isEmpty || !currentWeight.isEmpty)
    }

    var canSubmitManualEntry: Bool {
        !manualEntryType.trimmingCharacters(in: .whitespaces).isEmpty
            && (!manualEntryDuration.isEmpty || !manualEntryDistance.isEmpty || !manualEntryExercises.isEmpty)
    }

    // MARK: - Filtered Exercise Suggestions

    var exerciseSuggestions: [String] {
        let query = currentExerciseName.lowercased().trimmingCharacters(in: .whitespaces)
        guard !query.isEmpty else { return recentExercises }

        let libraryNames = exercises.map(\.name)
        let allNames = (recentExercises + libraryNames).uniqued()
        return allNames.filter { $0.lowercased().contains(query) }
    }

    // MARK: - Computed Workout Stats

    var totalSetsLogged: Int {
        activeWorkout?.exercises.count ?? 0
    }

    var totalVolume: Double {
        activeWorkout?.exercises.compactMap(\.volume).reduce(0, +) ?? 0
    }

    var uniqueExercisesInSession: [String] {
        activeWorkout?.uniqueExerciseNames ?? []
    }

    // MARK: - Timer Infrastructure

    private var workoutTimer: Timer?
    private var restTimer: Timer?

    // MARK: - Workout Lifecycle

    /// Creates a new workout session and starts the elapsed-time timer.
    func startWorkout(type: String) {
        let session = WorkoutSession(
            workoutType: type,
            startTime: Date(),
            isActive: true
        )
        activeWorkout = session
        elapsedSeconds = 0
        currentHeartRate = nil
        currentExerciseName = ""
        currentReps = ""
        currentWeight = ""
        workoutNotes = ""

        loadLastSessionData(for: type)
        startTimer()
    }

    /// Logs the current exercise/reps/weight as a set on the active workout.
    func addSet() {
        guard var workout = activeWorkout, workout.isActive else { return }

        let name = currentExerciseName.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }

        let reps = Int(currentReps)
        let weight = Double(currentWeight)

        let existingSets = workout.exercises.filter { $0.exerciseName == name }
        let nextSetNumber = existingSets.count + 1

        let exerciseSet = ExerciseSet(
            exerciseName: name,
            setNumber: nextSetNumber,
            reps: reps,
            weightLbs: weight,
            completedAt: Date()
        )

        workout.addSet(exerciseSet)
        activeWorkout = workout

        // Update recent exercises
        if !recentExercises.contains(name) {
            recentExercises.insert(name, at: 0)
            if recentExercises.count > 20 {
                recentExercises.removeLast()
            }
        }

        // Update last session data for this exercise
        if let r = reps, let w = weight {
            lastSessionData[name] = (reps: r, weight: w)
        }

        // Clear reps/weight but keep exercise name for quick multi-set logging
        currentReps = ""
        currentWeight = ""
    }

    /// Starts the rest timer counting down from `defaultRestSeconds`.
    func startRest() {
        cancelRestTimer()
        restTimeRemaining = defaultRestSeconds

        restTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] timer in
            Task { @MainActor [weak self] in
                guard let self else {
                    timer.invalidate()
                    return
                }
                if self.restTimeRemaining > 1 {
                    self.restTimeRemaining -= 1
                } else {
                    self.cancelRestTimer()
                }
            }
        }
    }

    /// Cancels the rest timer immediately.
    func skipRest() {
        cancelRestTimer()
    }

    /// Ends the active workout, saves it, and returns the completed session.
    func finishWorkout() async -> WorkoutSession? {
        stopTimer()
        cancelRestTimer()

        guard var workout = activeWorkout, workout.isActive else { return nil }

        workout.finish()
        if !workoutNotes.trimmingCharacters(in: .whitespaces).isEmpty {
            workout.notes = workoutNotes
        }

        activeWorkout = workout

        // Store in recent history
        recentWorkouts.insert(workout, at: 0)
        if recentWorkouts.count > 50 {
            recentWorkouts.removeLast()
        }

        completedWorkout = workout
        isShowingSummary = true

        return workout
    }

    /// Discards the current workout without saving.
    func discardWorkout() {
        stopTimer()
        cancelRestTimer()
        activeWorkout = nil
        currentHeartRate = nil
        elapsedSeconds = 0
        completedWorkout = nil
        isShowingSummary = false
    }

    /// Called after the user reviews the summary and confirms save.
    func confirmSave() {
        activeWorkout = nil
        currentHeartRate = nil
        elapsedSeconds = 0
        isShowingSummary = false
        completedWorkout = nil
    }

    // MARK: - After-the-Fact Entry

    /// Creates a workout session from the manual entry fields and saves it.
    func submitManualEntry() async {
        let type = manualEntryType.trimmingCharacters(in: .whitespaces)
        guard !type.isEmpty else { return }

        let durationMinutes = Double(manualEntryDuration)
        let distance = Double(manualEntryDistance)
        let heartRate = Int(manualEntryHeartRate)

        // Compute a synthetic duration for start/end times
        let durationSeconds = (durationMinutes ?? 0) * 60.0
        let startTime = manualEntryDate.addingTimeInterval(-durationSeconds)

        var session = WorkoutSession(
            workoutType: type,
            startTime: startTime,
            endTime: manualEntryDate,
            isActive: false,
            notes: manualEntryNotes.isEmpty ? nil : manualEntryNotes,
            totalDistance: distance,
            distanceUnit: distance != nil ? manualEntryDistanceUnit : nil
        )

        // Add strength exercises as sets
        for entry in manualEntryExercises {
            for setNum in 1...entry.sets {
                let exerciseSet = ExerciseSet(
                    exerciseName: entry.exerciseName,
                    setNumber: setNum,
                    reps: entry.reps,
                    weightLbs: entry.weightLbs,
                    completedAt: manualEntryDate
                )
                session.addSet(exerciseSet)
            }
        }

        // Record heart rate if provided
        if let hr = heartRate {
            session.recordHeartRate(bpm: hr, at: manualEntryDate)
        }

        // Store in recent history
        recentWorkouts.insert(session, at: 0)
        if recentWorkouts.count > 50 {
            recentWorkouts.removeLast()
        }

        resetManualEntryFields()
    }

    /// Adds an exercise to the manual entry exercise list.
    func addManualExercise(name: String, sets: Int, reps: Int, weight: Double) {
        let entry = StrengthEntry(
            exerciseName: name,
            sets: sets,
            reps: reps,
            weightLbs: weight
        )
        manualEntryExercises.append(entry)
    }

    /// Removes an exercise from the manual entry list at the given index.
    func removeManualExercise(at index: Int) {
        guard manualEntryExercises.indices.contains(index) else { return }
        manualEntryExercises.remove(at: index)
    }

    // MARK: - Exercise Library

    /// Loads the built-in and custom exercise library.
    func loadExercises() async {
        guard exercises.isEmpty else { return }

        exercises = Self.defaultExercises()
    }

    /// Adds a custom exercise to the library.
    func addExercise(_ exercise: Exercise) async {
        guard !exercises.contains(where: { $0.name.lowercased() == exercise.name.lowercased() }) else { return }
        exercises.append(exercise)
    }

    /// Applies a quick increment to the current reps or weight field.
    func quickIncrement(field: QuickIncrementField) {
        switch field {
        case .weight(let amount):
            let current = Double(currentWeight) ?? 0
            let newValue = max(0, current + amount)
            currentWeight = newValue.truncatingRemainder(dividingBy: 1) == 0
                ? String(format: "%.0f", newValue)
                : String(format: "%.1f", newValue)

        case .reps(let amount):
            let current = Int(currentReps) ?? 0
            let newValue = max(0, current + amount)
            currentReps = "\(newValue)"
        }
    }

    // MARK: - Timer Management

    func startTimer() {
        stopTimer()
        workoutTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] timer in
            Task { @MainActor [weak self] in
                guard let self, self.isWorkoutActive else {
                    timer.invalidate()
                    return
                }
                self.elapsedSeconds += 1
            }
        }
    }

    func stopTimer() {
        workoutTimer?.invalidate()
        workoutTimer = nil
    }

    // MARK: - Private Helpers

    private func cancelRestTimer() {
        restTimer?.invalidate()
        restTimer = nil
        restTimeRemaining = 0
    }

    private func resetManualEntryFields() {
        isShowingManualEntry = false
        manualEntryType = ""
        manualEntryDate = Date()
        manualEntryDuration = ""
        manualEntryDistance = ""
        manualEntryDistanceUnit = .miles
        manualEntryHeartRate = ""
        manualEntryExercises = []
        manualEntryNotes = ""
    }

    private func loadLastSessionData(for workoutType: String) {
        // Find the most recent session of this type and extract per-exercise data
        guard let lastSession = recentWorkouts.first(where: { $0.workoutType == workoutType }) else {
            return
        }

        var data: [String: (reps: Int, weight: Double)] = [:]
        for name in lastSession.uniqueExerciseNames {
            let sets = lastSession.exercises.filter { $0.exerciseName == name }
            if let lastSet = sets.last, let reps = lastSet.reps, let weight = lastSet.weightLbs {
                data[name] = (reps: reps, weight: weight)
            }
        }
        lastSessionData = data
    }

    // MARK: - Default Exercise Library

    private static func defaultExercises() -> [Exercise] {
        [
            // Strength - Chest
            Exercise(name: "Bench Press", category: .strength, muscleGroup: "Chest", equipment: "Barbell", isCustom: false),
            Exercise(name: "Incline Dumbbell Press", category: .strength, muscleGroup: "Chest", equipment: "Dumbbells", isCustom: false),
            Exercise(name: "Push-ups", category: .strength, muscleGroup: "Chest", equipment: "Bodyweight", isCustom: false),
            Exercise(name: "Cable Flyes", category: .strength, muscleGroup: "Chest", equipment: "Cable", isCustom: false),

            // Strength - Back
            Exercise(name: "Pull-ups", category: .strength, muscleGroup: "Back", equipment: "Bodyweight", isCustom: false),
            Exercise(name: "Barbell Row", category: .strength, muscleGroup: "Back", equipment: "Barbell", isCustom: false),
            Exercise(name: "Lat Pulldown", category: .strength, muscleGroup: "Back", equipment: "Cable", isCustom: false),
            Exercise(name: "Dumbbell Row", category: .strength, muscleGroup: "Back", equipment: "Dumbbells", isCustom: false),
            Exercise(name: "Deadlift", category: .strength, muscleGroup: "Back", equipment: "Barbell", isCustom: false),

            // Strength - Shoulders
            Exercise(name: "Overhead Press", category: .strength, muscleGroup: "Shoulders", equipment: "Barbell", isCustom: false),
            Exercise(name: "Lateral Raises", category: .strength, muscleGroup: "Shoulders", equipment: "Dumbbells", isCustom: false),
            Exercise(name: "Face Pulls", category: .strength, muscleGroup: "Shoulders", equipment: "Cable", isCustom: false),

            // Strength - Legs
            Exercise(name: "Squat", category: .strength, muscleGroup: "Legs", equipment: "Barbell", isCustom: false),
            Exercise(name: "Leg Press", category: .strength, muscleGroup: "Legs", equipment: "Machine", isCustom: false),
            Exercise(name: "Romanian Deadlift", category: .strength, muscleGroup: "Legs", equipment: "Barbell", isCustom: false),
            Exercise(name: "Lunges", category: .strength, muscleGroup: "Legs", equipment: "Dumbbells", isCustom: false),
            Exercise(name: "Calf Raises", category: .strength, muscleGroup: "Legs", equipment: "Machine", isCustom: false),

            // Strength - Arms
            Exercise(name: "Bicep Curls", category: .strength, muscleGroup: "Arms", equipment: "Dumbbells", isCustom: false),
            Exercise(name: "Tricep Pushdown", category: .strength, muscleGroup: "Arms", equipment: "Cable", isCustom: false),
            Exercise(name: "Hammer Curls", category: .strength, muscleGroup: "Arms", equipment: "Dumbbells", isCustom: false),

            // Strength - Core
            Exercise(name: "Plank", category: .strength, muscleGroup: "Core", equipment: "Bodyweight", isCustom: false),
            Exercise(name: "Hanging Leg Raises", category: .strength, muscleGroup: "Core", equipment: "Bodyweight", isCustom: false),
            Exercise(name: "Cable Woodchops", category: .strength, muscleGroup: "Core", equipment: "Cable", isCustom: false),

            // Cardio
            Exercise(name: "Treadmill Run", category: .cardio, muscleGroup: nil, equipment: "Treadmill", isCustom: false),
            Exercise(name: "Stationary Bike", category: .cardio, muscleGroup: nil, equipment: "Bike", isCustom: false),
            Exercise(name: "Rowing Machine", category: .cardio, muscleGroup: nil, equipment: "Rower", isCustom: false),

            // Flexibility
            Exercise(name: "Yoga Flow", category: .flexibility, muscleGroup: nil, equipment: "Mat", isCustom: false),
            Exercise(name: "Foam Rolling", category: .flexibility, muscleGroup: nil, equipment: "Foam Roller", isCustom: false),
            Exercise(name: "Static Stretching", category: .flexibility, muscleGroup: nil, equipment: "None", isCustom: false),
        ]
    }
}

// MARK: - Array Extension

private extension Array where Element: Hashable {
    /// Returns the array with duplicates removed, preserving order.
    func uniqued() -> [Element] {
        var seen = Set<Element>()
        return filter { seen.insert($0).inserted }
    }
}
