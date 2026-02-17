import Foundation

// MARK: - ParsedField

/// A parsed inline field in `FieldName:: value` (Dataview-compatible) format.
struct ParsedField: Sendable, Equatable {
    let name: String
    let rawValue: String
}

// MARK: - InlineFieldParser

/// Parses Dataview-compatible inline fields from markdown text.
///
/// Inline fields follow the pattern: `FieldName:: value`
/// where the field name can contain letters, digits, underscores, and spaces,
/// and must start with a letter. The `::` delimiter separates name from value.
///
/// Examples:
/// - `Weight:: 244.5`
/// - `Sleep:: 6:35`
/// - `Dumbbell bench press:: 3x10 @ 60 lbs`
/// - `calories_so_far:: 2720`
enum InlineFieldParser: Sendable {

    /// Regex pattern for inline fields.
    /// Matches: `FieldName:: value` or `FieldName::` (empty value)
    /// - Field name: starts with a letter, followed by letters/digits/underscores/spaces
    /// - Separator: `::` followed by optional whitespace
    /// - Value: everything after the separator (may be empty)
    private static let fieldPattern = #/^([A-Za-z][A-Za-z0-9_ ]*)::[ \t]*(.*)$/#

    // MARK: - Public API

    /// Parse all inline fields from a block of text.
    ///
    /// Processes each line independently and returns all successfully parsed fields
    /// in the order they appear.
    ///
    /// - Parameter text: A multi-line string potentially containing inline fields.
    /// - Returns: An array of parsed fields in document order.
    static func parseAll(from text: String) -> [ParsedField] {
        text.components(separatedBy: "\n")
            .compactMap { parseLine($0) }
    }

    /// Parse a single line as an inline field.
    ///
    /// - Parameter line: A single line of text.
    /// - Returns: A `ParsedField` if the line matches the `Name:: value` pattern,
    ///   or `nil` if it does not.
    static func parseLine(_ line: String) -> ParsedField? {
        let trimmed = line.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return nil }

        guard let match = trimmed.firstMatch(of: fieldPattern) else {
            return nil
        }

        let name = String(match.1).trimmingCharacters(in: .whitespaces)
        let rawValue = String(match.2).trimmingCharacters(in: .whitespaces)

        // Require non-empty name
        guard !name.isEmpty else { return nil }

        return ParsedField(name: name, rawValue: rawValue)
    }

    // MARK: - Convenience

    /// Parse all inline fields from text and return as a dictionary.
    ///
    /// If the same field name appears multiple times, the last occurrence wins.
    /// Field names are stored as-is (case-sensitive).
    static func parseToDictionary(from text: String) -> [String: String] {
        let fields = parseAll(from: text)
        var dict: [String: String] = [:]
        for field in fields {
            dict[field.name] = field.rawValue
        }
        return dict
    }

    /// Look up a specific field by name from text (case-insensitive).
    ///
    /// Returns the raw value of the first matching field, or `nil` if not found.
    static func findField(named name: String, in text: String) -> String? {
        let lowered = name.lowercased()
        return parseAll(from: text)
            .first { $0.name.lowercased() == lowered }?
            .rawValue
    }
}
