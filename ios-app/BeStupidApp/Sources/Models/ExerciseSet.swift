import Foundation

// MARK: - ExerciseSet

struct ExerciseSet: Identifiable, Codable, Sendable, Equatable {
    let id: UUID
    var exerciseName: String
    var setNumber: Int
    var reps: Int?
    var weightLbs: Double?
    var durationSeconds: Double?
    var distance: Double?
    var restSeconds: Int?
    var completedAt: Date

    init(
        id: UUID = UUID(),
        exerciseName: String,
        setNumber: Int,
        reps: Int? = nil,
        weightLbs: Double? = nil,
        durationSeconds: Double? = nil,
        distance: Double? = nil,
        restSeconds: Int? = nil,
        completedAt: Date = Date()
    ) {
        self.id = id
        self.exerciseName = exerciseName
        self.setNumber = setNumber
        self.reps = reps
        self.weightLbs = weightLbs
        self.durationSeconds = durationSeconds
        self.distance = distance
        self.restSeconds = restSeconds
        self.completedAt = completedAt
    }

    /// Volume for this single set (reps x weight), if applicable.
    var volume: Double? {
        guard let reps, let weightLbs else { return nil }
        return Double(reps) * weightLbs
    }
}

// MARK: - HeartRateSample

struct HeartRateSample: Codable, Sendable, Equatable {
    var timestamp: Date
    var bpm: Int

    init(timestamp: Date = Date(), bpm: Int) {
        self.timestamp = timestamp
        self.bpm = bpm
    }
}
