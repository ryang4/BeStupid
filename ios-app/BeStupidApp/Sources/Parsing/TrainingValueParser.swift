import Foundation

// MARK: - ParsedTrainingValue

/// Result of parsing a training activity value string.
///
/// Training values can contain distance, duration, or both.
/// Example inputs: `750m/33:39`, `4.5/45`, `30:00`
struct ParsedTrainingValue: Sendable, Equatable {
    let distance: Double?
    let distanceUnit: DistanceUnit
    let durationMinutes: Double?

    init(
        distance: Double? = nil,
        distanceUnit: DistanceUnit = .meters,
        durationMinutes: Double? = nil
    ) {
        self.distance = distance
        self.distanceUnit = distanceUnit
        self.durationMinutes = durationMinutes
    }
}

// MARK: - TrainingValueParser

/// Parses training activity values from BeStupid daily log inline fields.
///
/// Handles these formats:
/// - `750m/33:39` -- distance with unit suffix, duration as MM:SS
/// - `4.5/45` -- distance (plain number), duration in minutes
/// - `1.2km/35:00` -- distance with km suffix, duration as MM:SS
/// - `3.1mi/28:30` -- distance with mi suffix, duration as MM:SS
/// - `30:00` -- duration only (MM:SS)
/// - `45` -- duration only (plain minutes)
/// - `750m` -- distance only
enum TrainingValueParser: Sendable {

    /// Regex for a distance value with optional unit suffix.
    /// Captures: (number)(optional unit: m, km, mi)
    private static let distancePattern = #/^(\d+(?:\.\d+)?)\s*(m|km|mi)?/#

    /// Regex for MM:SS time format.
    private static let timePattern = #/^(\d+):(\d{2})$/#

    // MARK: - Public API

    /// Parse a training value string into distance and/or duration.
    ///
    /// - Parameter value: The raw value string from an inline field.
    /// - Returns: A `ParsedTrainingValue` with whatever components could be parsed.
    static func parse(_ value: String) -> ParsedTrainingValue {
        let trimmed = value.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else {
            return ParsedTrainingValue()
        }

        // Check for distance/duration split (contains `/`)
        if trimmed.contains("/") {
            return parseDistanceSlashDuration(trimmed)
        }

        // Check for time-only format (MM:SS)
        if let duration = parseTimeString(trimmed) {
            return ParsedTrainingValue(durationMinutes: duration)
        }

        // Check for distance-only with unit suffix
        if let (dist, unit) = parseDistanceString(trimmed) {
            return ParsedTrainingValue(distance: dist, distanceUnit: unit)
        }

        // Check for plain number (interpreted as duration in minutes)
        if let minutes = Double(trimmed) {
            return ParsedTrainingValue(durationMinutes: minutes)
        }

        return ParsedTrainingValue()
    }

    /// Infer the default distance unit for an activity type.
    ///
    /// - Parameter activityType: The activity type string (e.g., "swim", "run", "bike").
    /// - Returns: The conventional distance unit for that activity.
    static func defaultUnit(for activityType: String) -> DistanceUnit {
        switch activityType.lowercased() {
        case "swim", "swimming":
            return .meters
        case "run", "running":
            return .miles
        case "bike", "biking", "cycling", "cycle":
            return .kilometers
        default:
            return .meters
        }
    }

    // MARK: - Internal Parsing

    /// Parse `distance/duration` format where `/` separates the two components.
    private static func parseDistanceSlashDuration(_ value: String) -> ParsedTrainingValue {
        let parts = value.split(separator: "/", maxSplits: 1)
        guard parts.count == 2 else {
            return ParsedTrainingValue()
        }

        let distancePart = String(parts[0]).trimmingCharacters(in: .whitespaces)
        let durationPart = String(parts[1]).trimmingCharacters(in: .whitespaces)

        // Parse distance component
        let (distance, unit) = parseDistanceString(distancePart) ?? (nil, .meters)

        // Parse duration component (could be MM:SS or plain minutes)
        let duration: Double?
        if let time = parseTimeString(durationPart) {
            duration = time
        } else if let minutes = Double(durationPart) {
            duration = minutes
        } else {
            duration = nil
        }

        return ParsedTrainingValue(
            distance: distance,
            distanceUnit: unit,
            durationMinutes: duration
        )
    }

    /// Parse a time string in `MM:SS` format to fractional minutes.
    ///
    /// - Parameter value: A string like "33:39".
    /// - Returns: Duration in minutes (e.g., 33.65), or `nil` if not valid.
    static func parseTimeString(_ value: String) -> Double? {
        guard let match = value.firstMatch(of: timePattern) else {
            return nil
        }
        guard let minutes = Double(String(match.1)),
              let seconds = Double(String(match.2))
        else {
            return nil
        }
        let total = minutes + (seconds / 60.0)
        // Round to 2 decimal places for clean representation
        return (total * 100).rounded() / 100
    }

    /// Parse a distance string with optional unit suffix.
    ///
    /// - Parameter value: A string like "750m", "4.5", "1.2km".
    /// - Returns: A tuple of (distance, unit), or `nil` if not a valid distance.
    static func parseDistanceString(_ value: String) -> (Double, DistanceUnit)? {
        guard let match = value.firstMatch(of: distancePattern) else {
            return nil
        }
        guard let distance = Double(String(match.1)) else {
            return nil
        }

        let unit: DistanceUnit
        if let unitStr = match.2 {
            switch String(unitStr).lowercased() {
            case "m": unit = .meters
            case "km": unit = .kilometers
            case "mi": unit = .miles
            default: unit = .meters
            }
        } else {
            // No unit suffix -- will be inferred from activity type later
            unit = .meters
        }

        return (distance, unit)
    }
}
