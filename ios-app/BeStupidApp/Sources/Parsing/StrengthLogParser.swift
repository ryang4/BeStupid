import Foundation

// MARK: - StrengthLogParser

/// Parses strength exercise entries from BeStupid daily log markdown.
///
/// Expected format: `Exercise Name:: NxN @ N lbs`
///
/// Examples:
/// - `Dumbbell bench press:: 3x10 @ 60 lbs`
/// - `Cable seated row:: 3x11 @ 120 lbs`
/// - `Assisted pull up:: 3x2 @ 50 lbs`
///
/// Handles variations in whitespace and optional "lbs" suffix:
/// - `3x10 @ 60 lbs`
/// - `3x10 @ 60`
/// - `3x10@60`
/// - `3 x 10 @ 60 lbs`
enum StrengthLogParser: Sendable {

    /// Regex for the sets x reps @ weight pattern.
    ///
    /// Captures:
    /// 1. Sets (integer or decimal)
    /// 2. Reps (integer or decimal)
    /// 3. Weight (integer or decimal)
    ///
    /// Allows optional spaces around `x` and `@`, optional `lbs` suffix.
    private static let setsRepsWeightPattern =
        #/(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\s*@\s*(\d+(?:\.\d+)?)\s*(?:lbs)?/#

    // MARK: - Public API

    /// Parse a single line in `Exercise Name:: NxN @ N lbs` format into a `StrengthEntry`.
    ///
    /// First extracts the inline field (name :: value), then parses the value
    /// as a strength notation. Returns `nil` if the line doesn't match.
    ///
    /// - Parameter line: A single line of text.
    /// - Returns: A `StrengthEntry` if successfully parsed, or `nil`.
    static func parse(_ line: String) -> StrengthEntry? {
        // First, parse as an inline field
        guard let field = InlineFieldParser.parseLine(line) else { return nil }
        return parseValue(exerciseName: field.name, value: field.rawValue)
    }

    /// Parse the value portion of a strength entry.
    ///
    /// - Parameters:
    ///   - exerciseName: The exercise name (already extracted from inline field).
    ///   - value: The raw value string like "3x10 @ 60 lbs".
    /// - Returns: A `StrengthEntry` if the value matches strength notation, or `nil`.
    static func parseValue(exerciseName: String, value: String) -> StrengthEntry? {
        let trimmed = value.trimmingCharacters(in: .whitespaces)
        guard let match = trimmed.firstMatch(of: setsRepsWeightPattern) else {
            return nil
        }

        guard let sets = Int(match.1),
              let reps = Int(match.2),
              let weight = Double(String(match.3))
        else {
            return nil
        }

        return StrengthEntry(
            exerciseName: exerciseName,
            sets: sets,
            reps: reps,
            weightLbs: weight
        )
    }

    /// Parse multiple lines of strength entries.
    ///
    /// Each line is attempted as a strength entry. Lines that don't match
    /// the expected pattern are silently skipped.
    ///
    /// - Parameter text: A multi-line string containing strength log entries.
    /// - Returns: An array of parsed `StrengthEntry` values in document order.
    static func parseAll(from text: String) -> [StrengthEntry] {
        text.components(separatedBy: "\n")
            .compactMap { parse($0) }
    }
}
