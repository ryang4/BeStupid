import Foundation

struct StrengthEntry: Identifiable, Codable, Sendable, Equatable {
    let id: UUID
    var exerciseName: String
    var sets: Int
    var reps: Int
    var weightLbs: Double

    init(
        id: UUID = UUID(),
        exerciseName: String,
        sets: Int,
        reps: Int,
        weightLbs: Double
    ) {
        self.id = id
        self.exerciseName = exerciseName
        self.sets = sets
        self.reps = reps
        self.weightLbs = weightLbs
    }

    /// Total volume = sets x reps x weight.
    var totalVolume: Double {
        Double(sets * reps) * weightLbs
    }
}
