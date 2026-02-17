import Foundation

struct WorkoutSession: Identifiable, Codable, Sendable, Equatable {
    let id: UUID
    var workoutType: String
    var startTime: Date
    var endTime: Date?
    var isActive: Bool
    var exercises: [ExerciseSet]
    var notes: String?
    var totalDistance: Double?
    var distanceUnit: DistanceUnit?
    var heartRateSamples: [HeartRateSample]

    init(
        id: UUID = UUID(),
        workoutType: String,
        startTime: Date = Date(),
        endTime: Date? = nil,
        isActive: Bool = true,
        exercises: [ExerciseSet] = [],
        notes: String? = nil,
        totalDistance: Double? = nil,
        distanceUnit: DistanceUnit? = nil,
        heartRateSamples: [HeartRateSample] = []
    ) {
        self.id = id
        self.workoutType = workoutType
        self.startTime = startTime
        self.endTime = endTime
        self.isActive = isActive
        self.exercises = exercises
        self.notes = notes
        self.totalDistance = totalDistance
        self.distanceUnit = distanceUnit
        self.heartRateSamples = heartRateSamples
    }

    /// Elapsed duration in seconds.
    /// Returns time between start and end if finished, time since start if active, or nil if
    /// neither active nor finished (should not happen in practice).
    var duration: TimeInterval? {
        if let end = endTime {
            return end.timeIntervalSince(startTime)
        }
        return isActive ? Date().timeIntervalSince(startTime) : nil
    }

    /// Elapsed duration in minutes.
    var durationMinutes: Double? {
        duration.map { $0 / 60.0 }
    }

    /// Average heart rate across all samples, if any samples are recorded.
    var averageHeartRate: Int? {
        guard !heartRateSamples.isEmpty else { return nil }
        let total = heartRateSamples.reduce(0) { $0 + $1.bpm }
        return total / heartRateSamples.count
    }

    /// Max heart rate across all samples, if any samples are recorded.
    var maxHeartRate: Int? {
        heartRateSamples.map(\.bpm).max()
    }

    /// Distinct exercise names in this session.
    var uniqueExerciseNames: [String] {
        var seen = Set<String>()
        var result: [String] = []
        for exercise in exercises {
            if seen.insert(exercise.exerciseName).inserted {
                result.append(exercise.exerciseName)
            }
        }
        return result
    }

    /// Marks the session as finished with the current timestamp.
    mutating func finish() {
        endTime = Date()
        isActive = false
    }

    /// Adds a new exercise set to the session.
    mutating func addSet(_ set: ExerciseSet) {
        exercises.append(set)
    }

    /// Records a heart rate sample.
    mutating func recordHeartRate(bpm: Int, at timestamp: Date = Date()) {
        heartRateSamples.append(HeartRateSample(timestamp: timestamp, bpm: bpm))
    }
}
