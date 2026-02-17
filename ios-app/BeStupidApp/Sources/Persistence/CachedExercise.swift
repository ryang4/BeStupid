import Foundation
import SwiftData

@Model
final class CachedExercise {

    /// Exercise name, used as the unique key (exercises are identified by name).
    @Attribute(.unique) var name: String

    /// Category raw value (e.g. "strength", "cardio").
    var category: String

    /// Optional muscle group (e.g. "Chest", "Back", "Legs").
    var muscleGroup: String?

    /// Optional equipment (e.g. "Barbell", "Dumbbell", "Bodyweight").
    var equipment: String?

    /// Whether this is a user-created custom exercise.
    var isCustom: Bool

    // MARK: - Personal Records

    /// Heaviest weight ever used for this exercise (in lbs).
    var prWeight: Double?

    /// Most reps completed at any weight in a single set.
    var prReps: Int?

    /// Highest single-session volume (sum of weight * reps across all sets).
    var prVolume: Double?

    /// Date this exercise was last performed.
    var lastUsedDate: Date?

    // MARK: - Init

    init(from exercise: Exercise) {
        self.name = exercise.name
        self.category = exercise.category.rawValue
        self.muscleGroup = exercise.muscleGroup
        self.equipment = exercise.equipment
        self.isCustom = exercise.isCustom
        self.prWeight = nil
        self.prReps = nil
        self.prVolume = nil
        self.lastUsedDate = nil
    }

    // MARK: - Conversion

    /// Converts back to the domain `Exercise` model.
    func toExercise() -> Exercise {
        Exercise(
            name: name,
            category: ExerciseCategory(rawValue: category) ?? .strength,
            muscleGroup: muscleGroup,
            equipment: equipment,
            isCustom: isCustom
        )
    }

    // MARK: - PR Updates

    /// Updates personal records only when the new value exceeds the current PR.
    /// Also updates `lastUsedDate` unconditionally since any call means the exercise was used.
    ///
    /// - Parameters:
    ///   - weight: The heaviest single-set weight from the session (nil to skip comparison).
    ///   - reps: The highest single-set rep count from the session (nil to skip comparison).
    ///   - volume: The total session volume for this exercise (nil to skip comparison).
    ///   - date: The date the exercise was performed.
    func updatePR(weight: Double?, reps: Int?, volume: Double?, date: Date) {
        // Always update last used date
        if let existing = lastUsedDate {
            if date > existing {
                lastUsedDate = date
            }
        } else {
            lastUsedDate = date
        }

        // Update weight PR if new value exceeds current
        if let newWeight = weight {
            if let currentPR = prWeight {
                if newWeight > currentPR {
                    prWeight = newWeight
                }
            } else {
                prWeight = newWeight
            }
        }

        // Update reps PR if new value exceeds current
        if let newReps = reps {
            if let currentPR = prReps {
                if newReps > currentPR {
                    prReps = newReps
                }
            } else {
                prReps = newReps
            }
        }

        // Update volume PR if new value exceeds current
        if let newVolume = volume {
            if let currentPR = prVolume {
                if newVolume > currentPR {
                    prVolume = newVolume
                }
            } else {
                prVolume = newVolume
            }
        }
    }
}
