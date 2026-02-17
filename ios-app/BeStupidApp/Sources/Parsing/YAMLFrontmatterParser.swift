import Foundation

// MARK: - YAMLFrontmatter

/// Structured representation of YAML frontmatter extracted from a markdown file.
/// Supports the fields used by BeStupid daily logs and weekly protocols.
struct YAMLFrontmatter: Sendable, Equatable {
    var title: String?
    var date: Date?
    var tags: [String]
    var weekNumber: String?
    var phase: String?
    var focus: String?
    var targetCompliance: Double?

    init(
        title: String? = nil,
        date: Date? = nil,
        tags: [String] = [],
        weekNumber: String? = nil,
        phase: String? = nil,
        focus: String? = nil,
        targetCompliance: Double? = nil
    ) {
        self.title = title
        self.date = date
        self.tags = tags
        self.weekNumber = weekNumber
        self.phase = phase
        self.focus = focus
        self.targetCompliance = targetCompliance
    }
}

// MARK: - YAMLFrontmatterParser

/// Lightweight YAML frontmatter parser for BeStupid markdown files.
///
/// Handles the subset of YAML used in daily logs and weekly protocols:
/// - `key: "quoted string"` or `key: unquoted string`
/// - `key: 2026-01-30` (dates in yyyy-MM-dd format)
/// - `key: ["tag1", "tag2"]` (inline arrays)
/// - `key: 85%` (percentages converted to 0.0-1.0 Double)
///
/// This is intentionally NOT a full YAML parser. It covers exactly the patterns
/// produced by the BeStupid Telegram bot.
enum YAMLFrontmatterParser: Sendable {

    // MARK: - Date Formatter

    private static let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(identifier: "UTC")
        return formatter
    }()

    // MARK: - Public API

    /// Extract the raw frontmatter string from between `---` delimiters.
    ///
    /// Returns `nil` if the markdown does not start with a `---` line
    /// or if there is no closing `---`.
    static func extractRawFrontmatter(from markdown: String) -> String? {
        let lines = markdown.components(separatedBy: "\n")

        // First line must be ---
        guard let firstLine = lines.first,
              firstLine.trimmingCharacters(in: .whitespaces) == "---"
        else {
            return nil
        }

        // Find the closing ---
        var closingIndex: Int?
        for i in 1..<lines.count {
            if lines[i].trimmingCharacters(in: .whitespaces) == "---" {
                closingIndex = i
                break
            }
        }

        guard let endIndex = closingIndex, endIndex > 1 else {
            return nil
        }

        let frontmatterLines = lines[1..<endIndex]
        return frontmatterLines.joined(separator: "\n")
    }

    /// Parse a complete markdown document and return structured frontmatter.
    ///
    /// If the document has no frontmatter, returns a default `YAMLFrontmatter`
    /// with all fields nil/empty.
    static func parse(_ markdown: String) -> YAMLFrontmatter {
        guard let raw = extractRawFrontmatter(from: markdown) else {
            return YAMLFrontmatter()
        }
        return parseFrontmatterBlock(raw)
    }

    // MARK: - Internal Parsing

    /// Parse a raw frontmatter block (without `---` delimiters) into structured data.
    static func parseFrontmatterBlock(_ block: String) -> YAMLFrontmatter {
        let fields = parseKeyValuePairs(block)
        var frontmatter = YAMLFrontmatter()

        for (key, value) in fields {
            switch key {
            case "title":
                frontmatter.title = unquote(value)
            case "date":
                frontmatter.date = parseDate(value)
            case "tags":
                frontmatter.tags = parseInlineArray(value)
            case "week_number":
                frontmatter.weekNumber = unquote(value)
            case "phase":
                frontmatter.phase = unquote(value)
            case "focus":
                frontmatter.focus = unquote(value)
            case "target_compliance":
                frontmatter.targetCompliance = parsePercentageOrDouble(value)
            default:
                break
            }
        }

        return frontmatter
    }

    /// Parse `key: value` lines into an ordered list of (key, rawValue) pairs.
    static func parseKeyValuePairs(_ block: String) -> [(key: String, value: String)] {
        var result: [(key: String, value: String)] = []
        let lines = block.components(separatedBy: "\n")

        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard !trimmed.isEmpty else { continue }

            // Find the first colon that separates key from value
            guard let colonIndex = trimmed.firstIndex(of: ":") else { continue }

            let key = String(trimmed[trimmed.startIndex..<colonIndex])
                .trimmingCharacters(in: .whitespaces)
            let value = String(trimmed[trimmed.index(after: colonIndex)...])
                .trimmingCharacters(in: .whitespaces)

            guard !key.isEmpty else { continue }
            result.append((key: key, value: value))
        }

        return result
    }

    // MARK: - Value Parsers

    /// Remove surrounding quotes from a string value.
    /// Handles both `"quoted"` and `'quoted'` styles.
    static func unquote(_ value: String) -> String {
        let trimmed = value.trimmingCharacters(in: .whitespaces)
        if (trimmed.hasPrefix("\"") && trimmed.hasSuffix("\"")) ||
           (trimmed.hasPrefix("'") && trimmed.hasSuffix("'")) {
            let start = trimmed.index(after: trimmed.startIndex)
            let end = trimmed.index(before: trimmed.endIndex)
            guard start < end else { return "" }
            return String(trimmed[start..<end])
        }
        return trimmed
    }

    /// Parse a date string in `yyyy-MM-dd` format.
    static func parseDate(_ value: String) -> Date? {
        let trimmed = unquote(value).trimmingCharacters(in: .whitespaces)
        return dateFormatter.date(from: trimmed)
    }

    /// Parse an inline YAML array like `["tag1", "tag2"]`.
    static func parseInlineArray(_ value: String) -> [String] {
        let trimmed = value.trimmingCharacters(in: .whitespaces)

        // Must be wrapped in brackets
        guard trimmed.hasPrefix("[") && trimmed.hasSuffix("]") else {
            // Single unquoted value
            let single = unquote(trimmed)
            return single.isEmpty ? [] : [single]
        }

        // Remove brackets
        let inner = String(trimmed.dropFirst().dropLast())
            .trimmingCharacters(in: .whitespaces)
        guard !inner.isEmpty else { return [] }

        // Split by commas and unquote each element
        return inner.components(separatedBy: ",")
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .map { unquote($0) }
            .filter { !$0.isEmpty }
    }

    /// Parse a percentage string (e.g., "85%") or plain double (e.g., "0.85").
    /// Returns value in 0.0-1.0 range.
    static func parsePercentageOrDouble(_ value: String) -> Double? {
        let trimmed = unquote(value).trimmingCharacters(in: .whitespaces)

        if trimmed.hasSuffix("%") {
            let numberString = String(trimmed.dropLast())
                .trimmingCharacters(in: .whitespaces)
            guard let number = Double(numberString) else { return nil }
            return number / 100.0
        }

        guard let number = Double(trimmed) else { return nil }
        // If the number is > 1, assume it's a percentage
        return number > 1.0 ? number / 100.0 : number
    }
}
