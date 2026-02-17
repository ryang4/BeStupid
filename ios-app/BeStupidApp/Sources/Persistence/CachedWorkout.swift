import Foundation
import SwiftData

@Model
final class CachedWorkout {

    /// UUID string of the original `WorkoutSession.id`, used as the unique key.
    @Attribute(.unique) var workoutId: String

    /// Type of workout (e.g. "Swim", "Bike", "Strength").
    var workoutType: String

    /// When the workout began.
    var startTime: Date

    /// When the workout ended (nil if still in progress).
    var endTime: Date?

    /// Computed duration in minutes (denormalized for query efficiency).
    var durationMinutes: Double?

    /// Total distance covered, if applicable.
    var totalDistance: Double?

    /// Unit of the distance value (e.g. "m", "km", "mi").
    var distanceUnit: String?

    /// Free-form notes about the workout.
    var notes: String?

    /// Number of exercise sets in this session.
    var exerciseCount: Int

    /// Total volume (sum of weight * reps across all strength sets).
    var totalVolume: Double?

    /// JSON-encoded `WorkoutSession` for full detail display.
    var serializedSession: Data?

    // MARK: - Init

    init(from session: WorkoutSession) {
        self.workoutId = session.id.uuidString
        self.workoutType = session.workoutType
        self.startTime = session.startTime
        self.endTime = session.endTime
        self.durationMinutes = Self.computeDurationMinutes(session)
        self.totalDistance = session.totalDistance
        self.distanceUnit = session.distanceUnit?.rawValue
        self.notes = session.notes
        self.exerciseCount = session.exercises.count
        self.totalVolume = Self.computeTotalVolume(session)
        self.serializedSession = try? JSONEncoder().encode(session)
    }

    // MARK: - Conversion

    /// Deserializes back to the domain `WorkoutSession`.
    func toWorkoutSession() -> WorkoutSession? {
        guard let data = serializedSession else { return nil }
        return try? JSONDecoder().decode(WorkoutSession.self, from: data)
    }

    // MARK: - Private Helpers

    private static func computeDurationMinutes(_ session: WorkoutSession) -> Double? {
        guard let end = session.endTime else { return nil }
        let interval = end.timeIntervalSince(session.startTime)
        return interval / 60.0
    }

    private static func computeTotalVolume(_ session: WorkoutSession) -> Double? {
        let volumes = session.exercises.compactMap(\.volume)
        guard !volumes.isEmpty else { return nil }
        return volumes.reduce(0, +)
    }
}
