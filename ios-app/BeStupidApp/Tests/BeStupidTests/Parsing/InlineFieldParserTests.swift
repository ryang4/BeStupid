import Testing
@testable import BeStupidApp

// MARK: - InlineFieldParserTests

@Suite("InlineFieldParser")
struct InlineFieldParserTests {

    // MARK: - Single Line Parsing

    @Test("Parses weight field")
    func parseWeight() {
        let result = InlineFieldParser.parseLine("Weight:: 244.5")
        #expect(result != nil)
        #expect(result?.name == "Weight")
        #expect(result?.rawValue == "244.5")
    }

    @Test("Parses sleep field with time format")
    func parseSleep() {
        let result = InlineFieldParser.parseLine("Sleep:: 6:35")
        #expect(result != nil)
        #expect(result?.name == "Sleep")
        #expect(result?.rawValue == "6:35")
    }

    @Test("Parses strength entry as inline field")
    func parseStrengthAsInlineField() {
        let result = InlineFieldParser.parseLine("Dumbbell bench press:: 3x10 @ 60 lbs")
        #expect(result != nil)
        #expect(result?.name == "Dumbbell bench press")
        #expect(result?.rawValue == "3x10 @ 60 lbs")
    }

    @Test("Parses field with underscores in name")
    func parseUnderscoreName() {
        let result = InlineFieldParser.parseLine("calories_so_far:: 2720")
        #expect(result != nil)
        #expect(result?.name == "calories_so_far")
        #expect(result?.rawValue == "2720")
    }

    @Test("Returns nil for non-field line")
    func nonFieldLine() {
        let result = InlineFieldParser.parseLine("Not a field line")
        #expect(result == nil)
    }

    @Test("Returns nil for empty line")
    func emptyLine() {
        let result = InlineFieldParser.parseLine("")
        #expect(result == nil)
    }

    @Test("Returns nil for whitespace-only line")
    func whitespaceOnlyLine() {
        let result = InlineFieldParser.parseLine("   ")
        #expect(result == nil)
    }

    @Test("Handles field with empty value")
    func emptyValue() {
        let result = InlineFieldParser.parseLine("Weight:: ")
        #expect(result != nil)
        #expect(result?.name == "Weight")
        #expect(result?.rawValue == "")
    }

    @Test("Returns nil for single colon separator")
    func singleColon() {
        // Single colon should NOT be treated as an inline field
        let result = InlineFieldParser.parseLine("Name: value")
        #expect(result == nil)
    }

    @Test("Parses field with numeric characters in name")
    func numericInName() {
        let result = InlineFieldParser.parseLine("Workout2:: 3x10 @ 50 lbs")
        #expect(result != nil)
        #expect(result?.name == "Workout2")
        #expect(result?.rawValue == "3x10 @ 50 lbs")
    }

    @Test("Trims whitespace from name and value")
    func trimming() {
        let result = InlineFieldParser.parseLine("  Weight ::   244.5  ")
        #expect(result != nil)
        #expect(result?.name == "Weight")
        #expect(result?.rawValue == "244.5")
    }

    @Test("Parses mood field")
    func parseMood() {
        let result = InlineFieldParser.parseLine("Mood_AM:: 6")
        #expect(result != nil)
        #expect(result?.name == "Mood_AM")
        #expect(result?.rawValue == "6")
    }

    // MARK: - Multi-Line Parsing

    @Test("Parses multiple fields from a block of text")
    func parseMultipleFields() {
        let text = """
        Weight:: 244.5
        Sleep:: 6:35
        Sleep_Quality:: 7.4
        Mood_AM:: 6
        Mood_PM:: 7
        Energy:: 7.2
        Focus:: 6.5
        """

        let results = InlineFieldParser.parseAll(from: text)
        #expect(results.count == 7)
        #expect(results[0].name == "Weight")
        #expect(results[0].rawValue == "244.5")
        #expect(results[1].name == "Sleep")
        #expect(results[1].rawValue == "6:35")
        #expect(results[6].name == "Focus")
        #expect(results[6].rawValue == "6.5")
    }

    @Test("Skips non-field lines in mixed content")
    func mixedContent() {
        let text = """
        Some description text
        Weight:: 244.5
        Another line
        Sleep:: 6:35
        """

        let results = InlineFieldParser.parseAll(from: text)
        #expect(results.count == 2)
        #expect(results[0].name == "Weight")
        #expect(results[1].name == "Sleep")
    }

    @Test("Returns empty array for text with no fields")
    func noFields() {
        let text = """
        Just some text
        No fields here
        """

        let results = InlineFieldParser.parseAll(from: text)
        #expect(results.isEmpty)
    }

    // MARK: - Dictionary Parsing

    @Test("Parses fields to dictionary")
    func parseToDictionary() {
        let text = """
        Weight:: 244.5
        Sleep:: 6:35
        """

        let dict = InlineFieldParser.parseToDictionary(from: text)
        #expect(dict["Weight"] == "244.5")
        #expect(dict["Sleep"] == "6:35")
        #expect(dict.count == 2)
    }

    @Test("Last value wins for duplicate field names")
    func duplicateFields() {
        let text = """
        Weight:: 244.5
        Weight:: 245.0
        """

        let dict = InlineFieldParser.parseToDictionary(from: text)
        #expect(dict["Weight"] == "245.0")
    }

    // MARK: - Find Field

    @Test("Finds field by name case-insensitively")
    func findFieldCaseInsensitive() {
        let text = """
        Weight:: 244.5
        Sleep_Quality:: 7.4
        """

        let weight = InlineFieldParser.findField(named: "weight", in: text)
        #expect(weight == "244.5")

        let sq = InlineFieldParser.findField(named: "SLEEP_QUALITY", in: text)
        #expect(sq == "7.4")
    }

    @Test("Returns nil when field not found")
    func findFieldNotFound() {
        let text = "Weight:: 244.5"
        let result = InlineFieldParser.findField(named: "Height", in: text)
        #expect(result == nil)
    }
}
