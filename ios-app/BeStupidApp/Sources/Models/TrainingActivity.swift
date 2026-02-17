import Foundation

// MARK: - DistanceUnit

enum DistanceUnit: String, Codable, Sendable, CaseIterable, Equatable {
    case meters = "m"
    case kilometers = "km"
    case miles = "mi"

    var displayName: String {
        switch self {
        case .meters: return "meters"
        case .kilometers: return "kilometers"
        case .miles: return "miles"
        }
    }

    /// Converts a distance in this unit to meters.
    func toMeters(_ distance: Double) -> Double {
        switch self {
        case .meters: return distance
        case .kilometers: return distance * 1_000
        case .miles: return distance * 1_609.344
        }
    }
}

// MARK: - TrainingActivity

struct TrainingActivity: Identifiable, Codable, Sendable, Equatable {
    let id: UUID
    var type: String
    var distance: Double?
    var distanceUnit: DistanceUnit
    var durationMinutes: Double?
    var avgHeartRate: Int?
    var avgWatts: Int?

    init(
        id: UUID = UUID(),
        type: String,
        distance: Double? = nil,
        distanceUnit: DistanceUnit = .meters,
        durationMinutes: Double? = nil,
        avgHeartRate: Int? = nil,
        avgWatts: Int? = nil
    ) {
        self.id = id
        self.type = type
        self.distance = distance
        self.distanceUnit = distanceUnit
        self.durationMinutes = durationMinutes
        self.avgHeartRate = avgHeartRate
        self.avgWatts = avgWatts
    }

    /// Distance converted to meters, if distance is present.
    var distanceInMeters: Double? {
        guard let distance else { return nil }
        return distanceUnit.toMeters(distance)
    }

    /// Pace in minutes per kilometer, if both distance and duration are present.
    var paceMinPerKm: Double? {
        guard let distance, distance > 0, let durationMinutes else { return nil }
        let km = distanceUnit.toMeters(distance) / 1_000
        return durationMinutes / km
    }
}
