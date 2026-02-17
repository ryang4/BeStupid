import Testing
@testable import BeStupidApp

// MARK: - StrengthLogParserTests

@Suite("StrengthLogParser")
struct StrengthLogParserTests {

    // MARK: - Single Entry Parsing

    @Test("Parses standard strength entry")
    func standardEntry() {
        let result = StrengthLogParser.parse("Dumbbell bench press:: 3x10 @ 60 lbs")
        #expect(result != nil)
        #expect(result?.exerciseName == "Dumbbell bench press")
        #expect(result?.sets == 3)
        #expect(result?.reps == 10)
        #expect(result?.weightLbs == 60.0)
    }

    @Test("Parses cable seated row")
    func cableSeatedRow() {
        let result = StrengthLogParser.parse("Cable seated row:: 3x11 @ 120 lbs")
        #expect(result != nil)
        #expect(result?.exerciseName == "Cable seated row")
        #expect(result?.sets == 3)
        #expect(result?.reps == 11)
        #expect(result?.weightLbs == 120.0)
    }

    @Test("Parses assisted pull up")
    func assistedPullUp() {
        let result = StrengthLogParser.parse("Assisted pull up:: 3x2 @ 50 lbs")
        #expect(result != nil)
        #expect(result?.exerciseName == "Assisted pull up")
        #expect(result?.sets == 3)
        #expect(result?.reps == 2)
        #expect(result?.weightLbs == 50.0)
    }

    @Test("Parses without spaces around x and @")
    func noSpaces() {
        let result = StrengthLogParser.parse("Bench press:: 3x10@60")
        #expect(result != nil)
        #expect(result?.exerciseName == "Bench press")
        #expect(result?.sets == 3)
        #expect(result?.reps == 10)
        #expect(result?.weightLbs == 60.0)
    }

    @Test("Parses with extra spaces around x and @")
    func extraSpaces() {
        let result = StrengthLogParser.parse("Bench press:: 3 x 10 @ 60 lbs")
        #expect(result != nil)
        #expect(result?.sets == 3)
        #expect(result?.reps == 10)
        #expect(result?.weightLbs == 60.0)
    }

    @Test("Parses without lbs suffix")
    func noLbsSuffix() {
        let result = StrengthLogParser.parse("Bench press:: 3x10 @ 60")
        #expect(result != nil)
        #expect(result?.weightLbs == 60.0)
    }

    @Test("Parses decimal weight")
    func decimalWeight() {
        let result = StrengthLogParser.parse("Dumbbell curl:: 3x12 @ 22.5 lbs")
        #expect(result != nil)
        #expect(result?.weightLbs == 22.5)
    }

    @Test("Returns nil for non-strength entry")
    func nonStrengthEntry() {
        let result = StrengthLogParser.parse("Not a strength entry:: some text")
        #expect(result == nil)
    }

    @Test("Returns nil for plain text line")
    func plainTextLine() {
        let result = StrengthLogParser.parse("Just some regular text")
        #expect(result == nil)
    }

    @Test("Returns nil for empty line")
    func emptyLine() {
        let result = StrengthLogParser.parse("")
        #expect(result == nil)
    }

    @Test("Returns nil for inline field with non-strength value")
    func nonStrengthValue() {
        let result = StrengthLogParser.parse("Weight:: 244.5")
        #expect(result == nil)
    }

    // MARK: - Multi-Line Parsing

    @Test("Parses multiple strength entries")
    func parseMultiple() {
        let text = """
        Dumbbell bench press:: 3x10 @ 60 lbs
        Cable seated row:: 3x11 @ 120 lbs
        Assisted pull up:: 3x2 @ 50 lbs
        """

        let results = StrengthLogParser.parseAll(from: text)
        #expect(results.count == 3)
        #expect(results[0].exerciseName == "Dumbbell bench press")
        #expect(results[1].exerciseName == "Cable seated row")
        #expect(results[2].exerciseName == "Assisted pull up")
    }

    @Test("Skips non-strength lines in mixed content")
    func mixedContent() {
        let text = """
        Some description text
        Dumbbell bench press:: 3x10 @ 60 lbs

        Another line
        Cable seated row:: 3x11 @ 120 lbs
        """

        let results = StrengthLogParser.parseAll(from: text)
        #expect(results.count == 2)
    }

    @Test("Returns empty array for no strength entries")
    func noEntries() {
        let text = """
        Just some text
        Weight:: 244.5
        Sleep:: 6:35
        """

        let results = StrengthLogParser.parseAll(from: text)
        #expect(results.isEmpty)
    }

    // MARK: - Value Parsing

    @Test("parseValue with standard format")
    func parseValueStandard() {
        let result = StrengthLogParser.parseValue(exerciseName: "Squat", value: "5x5 @ 225 lbs")
        #expect(result != nil)
        #expect(result?.exerciseName == "Squat")
        #expect(result?.sets == 5)
        #expect(result?.reps == 5)
        #expect(result?.weightLbs == 225.0)
    }

    @Test("parseValue returns nil for non-strength value")
    func parseValueNonStrength() {
        let result = StrengthLogParser.parseValue(exerciseName: "Something", value: "hello world")
        #expect(result == nil)
    }

    // MARK: - Total Volume

    @Test("Parsed entry has correct total volume")
    func totalVolume() {
        let result = StrengthLogParser.parse("Bench press:: 3x10 @ 60 lbs")
        #expect(result != nil)
        #expect(result?.totalVolume == 1800.0) // 3 * 10 * 60
    }
}
