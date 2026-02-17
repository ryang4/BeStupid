import Testing
import Foundation
@testable import BeStupidApp

// MARK: - YAMLFrontmatterParserTests

@Suite("YAMLFrontmatterParser")
struct YAMLFrontmatterParserTests {

    // MARK: - Raw Frontmatter Extraction

    @Test("Extracts raw frontmatter between delimiters")
    func extractRaw() {
        let markdown = """
        ---
        title: "Test"
        date: 2026-01-30
        ---
        Some body content
        """
        let raw = YAMLFrontmatterParser.extractRawFrontmatter(from: markdown)
        #expect(raw != nil)
        #expect(raw!.contains("title: \"Test\""))
        #expect(raw!.contains("date: 2026-01-30"))
    }

    @Test("Returns nil when no frontmatter")
    func noFrontmatter() {
        let markdown = "Just some text\nNo frontmatter here"
        let raw = YAMLFrontmatterParser.extractRawFrontmatter(from: markdown)
        #expect(raw == nil)
    }

    @Test("Returns nil when only opening delimiter")
    func onlyOpening() {
        let markdown = "---\ntitle: Test\nNo closing"
        let raw = YAMLFrontmatterParser.extractRawFrontmatter(from: markdown)
        #expect(raw == nil)
    }

    @Test("Returns nil for empty frontmatter")
    func emptyFrontmatter() {
        let markdown = "---\n---\nBody"
        let raw = YAMLFrontmatterParser.extractRawFrontmatter(from: markdown)
        #expect(raw == nil)
    }

    // MARK: - Full Parsing

    @Test("Parses daily log frontmatter")
    func dailyLogFrontmatter() {
        let markdown = """
        ---
        title: "2026-01-30: Strength Day"
        date: 2026-01-30
        tags: ["log"]
        ---
        Body text
        """

        let result = YAMLFrontmatterParser.parse(markdown)
        #expect(result.title == "2026-01-30: Strength Day")
        #expect(result.tags == ["log"])
        #expect(result.date != nil)

        let calendar = Calendar(identifier: .gregorian)
        var components = DateComponents()
        components.year = 2026
        components.month = 1
        components.day = 30
        components.timeZone = TimeZone(identifier: "UTC")
        let expected = calendar.date(from: components)!
        #expect(calendar.isDate(result.date!, inSameDayAs: expected))
    }

    @Test("Parses protocol frontmatter")
    func protocolFrontmatter() {
        let markdown = """
        ---
        title: "Protocol 2026-W06: Base Building"
        date: 2026-02-04
        week_number: W06
        tags: ["protocol"]
        phase: "Base Building"
        focus: "Triathlon Training & Startup Building"
        target_compliance: 85%
        ---
        Body
        """

        let result = YAMLFrontmatterParser.parse(markdown)
        #expect(result.title == "Protocol 2026-W06: Base Building")
        #expect(result.weekNumber == "W06")
        #expect(result.phase == "Base Building")
        #expect(result.focus == "Triathlon Training & Startup Building")
        #expect(result.targetCompliance == 0.85)
        #expect(result.tags == ["protocol"])
    }

    @Test("Returns defaults for no frontmatter")
    func defaults() {
        let result = YAMLFrontmatterParser.parse("No frontmatter here")
        #expect(result.title == nil)
        #expect(result.date == nil)
        #expect(result.tags.isEmpty)
        #expect(result.weekNumber == nil)
    }

    // MARK: - Value Parsing

    @Test("Unquotes double-quoted strings")
    func unquoteDouble() {
        #expect(YAMLFrontmatterParser.unquote("\"hello world\"") == "hello world")
    }

    @Test("Unquotes single-quoted strings")
    func unquoteSingle() {
        #expect(YAMLFrontmatterParser.unquote("'hello world'") == "hello world")
    }

    @Test("Passes through unquoted strings")
    func unquotePassthrough() {
        #expect(YAMLFrontmatterParser.unquote("hello") == "hello")
    }

    @Test("Handles empty quoted string")
    func unquoteEmpty() {
        #expect(YAMLFrontmatterParser.unquote("\"\"") == "")
    }

    @Test("Parses inline array with quoted strings")
    func parseInlineArray() {
        let result = YAMLFrontmatterParser.parseInlineArray("[\"log\", \"protocol\"]")
        #expect(result == ["log", "protocol"])
    }

    @Test("Parses inline array with single element")
    func parseInlineArraySingle() {
        let result = YAMLFrontmatterParser.parseInlineArray("[\"log\"]")
        #expect(result == ["log"])
    }

    @Test("Parses empty inline array")
    func parseInlineArrayEmpty() {
        let result = YAMLFrontmatterParser.parseInlineArray("[]")
        #expect(result.isEmpty)
    }

    @Test("Handles single unquoted value as array")
    func singleUnquotedValue() {
        let result = YAMLFrontmatterParser.parseInlineArray("log")
        #expect(result == ["log"])
    }

    @Test("Parses percentage to decimal")
    func parsePercentage() {
        let result = YAMLFrontmatterParser.parsePercentageOrDouble("85%")
        #expect(result == 0.85)
    }

    @Test("Parses decimal directly")
    func parseDecimal() {
        let result = YAMLFrontmatterParser.parsePercentageOrDouble("0.85")
        #expect(result == 0.85)
    }

    @Test("Parses percentage without % sign")
    func parsePercentageNoSign() {
        // Numbers > 1.0 are assumed to be percentages
        let result = YAMLFrontmatterParser.parsePercentageOrDouble("85")
        #expect(result == 0.85)
    }

    @Test("Returns nil for invalid number")
    func parseInvalidNumber() {
        let result = YAMLFrontmatterParser.parsePercentageOrDouble("abc")
        #expect(result == nil)
    }

    @Test("Parses date in yyyy-MM-dd format")
    func parseDate() {
        let result = YAMLFrontmatterParser.parseDate("2026-02-04")
        #expect(result != nil)
        let calendar = Calendar(identifier: .gregorian)
        let components = calendar.dateComponents(in: TimeZone(identifier: "UTC")!, from: result!)
        #expect(components.year == 2026)
        #expect(components.month == 2)
        #expect(components.day == 4)
    }

    @Test("Returns nil for invalid date")
    func parseInvalidDate() {
        let result = YAMLFrontmatterParser.parseDate("not-a-date")
        #expect(result == nil)
    }

    // MARK: - Key-Value Pair Parsing

    @Test("Parses key-value pairs from block")
    func parseKeyValuePairs() {
        let block = """
        title: "Test"
        date: 2026-01-30
        tags: ["log"]
        """
        let pairs = YAMLFrontmatterParser.parseKeyValuePairs(block)
        #expect(pairs.count == 3)
        #expect(pairs[0].key == "title")
        #expect(pairs[0].value == "\"Test\"")
        #expect(pairs[1].key == "date")
        #expect(pairs[1].value == "2026-01-30")
    }

    @Test("Skips empty lines")
    func skipEmptyLines() {
        let block = """
        title: "Test"

        date: 2026-01-30
        """
        let pairs = YAMLFrontmatterParser.parseKeyValuePairs(block)
        #expect(pairs.count == 2)
    }

    @Test("Handles colons in value")
    func colonsInValue() {
        let block = "title: \"Protocol 2026-W06: Base Building\""
        let pairs = YAMLFrontmatterParser.parseKeyValuePairs(block)
        #expect(pairs.count == 1)
        #expect(pairs[0].key == "title")
        // The value includes everything after the first colon
        #expect(pairs[0].value == "\"Protocol 2026-W06: Base Building\"")
    }
}
