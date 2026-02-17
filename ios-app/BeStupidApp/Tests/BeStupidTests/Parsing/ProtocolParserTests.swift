import Testing
import Foundation
@testable import BeStupidApp

// MARK: - ProtocolParserTests

@Suite("ProtocolParser")
struct ProtocolParserTests {

    // MARK: - Test Data

    /// A full example weekly protocol matching the BeStupid format.
    private static let fullProtocolMarkdown = """
    ---
    title: "Protocol 2026-W06: Base Building"
    date: 2026-02-04
    week_number: W06
    tags: ["protocol"]
    phase: "Base Building"
    focus: "Triathlon Training & Startup Building"
    target_compliance: 85%
    ---

    ## Weekly Schedule

    | Day | Type | Workout |
    |-----|------|---------|
    | Monday | Swim | 400m freestyle |
    | Tuesday | Strength | Workout A: bench, rows, pulls |
    | Wednesday | Bike | 45 min indoor trainer |
    | Thursday | Run | 4 miles easy |
    | Friday | Strength | Workout B: squats, deadlifts |
    | Saturday | Brick | 30 min bike + 20 min run |
    | Sunday | Active Recovery | Light swim or walk |

    ## Training Goals
    - Build aerobic base
    - Maintain strength
    - Practice transitions

    ## Weekly Targets

    **Cardio Volume:**
    - Swim: 700m
    - Bike: 45 minutes
    - Run: 4 miles

    **Strength:**
    - Complete all planned strength workouts

    ## AI Rationale
    This week focuses on building aerobic capacity while maintaining the strength foundation from previous weeks.
    """

    // MARK: - Frontmatter

    @Test("Parses protocol title")
    func title() {
        let protocol_ = ProtocolParser.parse(Self.fullProtocolMarkdown)
        #expect(protocol_.title == "Protocol 2026-W06: Base Building")
    }

    @Test("Parses protocol date")
    func date() {
        let protocol_ = ProtocolParser.parse(Self.fullProtocolMarkdown)
        let calendar = Calendar(identifier: .gregorian)
        var dateComponents = DateComponents()
        dateComponents.year = 2026
        dateComponents.month = 2
        dateComponents.day = 4
        dateComponents.timeZone = TimeZone(identifier: "UTC")
        let expectedDate = calendar.date(from: dateComponents)!
        #expect(calendar.isDate(protocol_.date, inSameDayAs: expectedDate))
    }

    @Test("Parses week number")
    func weekNumber() {
        let protocol_ = ProtocolParser.parse(Self.fullProtocolMarkdown)
        #expect(protocol_.weekNumber == "W06")
    }

    @Test("Parses phase")
    func phase() {
        let protocol_ = ProtocolParser.parse(Self.fullProtocolMarkdown)
        #expect(protocol_.phase == "Base Building")
    }

    @Test("Parses focus")
    func focus() {
        let protocol_ = ProtocolParser.parse(Self.fullProtocolMarkdown)
        #expect(protocol_.focus == "Triathlon Training & Startup Building")
    }

    @Test("Parses target compliance as decimal")
    func targetCompliance() {
        let protocol_ = ProtocolParser.parse(Self.fullProtocolMarkdown)
        #expect(protocol_.targetCompliance == 0.85)
    }

    @Test("Parses tags")
    func tags() {
        let frontmatter = YAMLFrontmatterParser.parse(Self.fullProtocolMarkdown)
        #expect(frontmatter.tags == ["protocol"])
    }

    // MARK: - Schedule Table

    @Test("Parses schedule table with all 7 days")
    func scheduleCount() {
        let protocol_ = ProtocolParser.parse(Self.fullProtocolMarkdown)
        #expect(protocol_.schedule.count == 7)
    }

    @Test("Parses Monday schedule entry")
    func monday() {
        let protocol_ = ProtocolParser.parse(Self.fullProtocolMarkdown)
        let monday = protocol_.schedule[0]
        #expect(monday.dayOfWeek == "Monday")
        #expect(monday.workoutType == "Swim")
        #expect(monday.workout == "400m freestyle")
    }

    @Test("Parses Tuesday schedule entry")
    func tuesday() {
        let protocol_ = ProtocolParser.parse(Self.fullProtocolMarkdown)
        let tuesday = protocol_.schedule[1]
        #expect(tuesday.dayOfWeek == "Tuesday")
        #expect(tuesday.workoutType == "Strength")
        #expect(tuesday.workout == "Workout A: bench, rows, pulls")
    }

    @Test("Parses Saturday brick day")
    func saturday() {
        let protocol_ = ProtocolParser.parse(Self.fullProtocolMarkdown)
        let saturday = protocol_.schedule[5]
        #expect(saturday.dayOfWeek == "Saturday")
        #expect(saturday.workoutType == "Brick")
        #expect(saturday.workout == "30 min bike + 20 min run")
    }

    @Test("Parses Sunday recovery day")
    func sunday() {
        let protocol_ = ProtocolParser.parse(Self.fullProtocolMarkdown)
        let sunday = protocol_.schedule[6]
        #expect(sunday.dayOfWeek == "Sunday")
        #expect(sunday.workoutType == "Active Recovery")
        #expect(sunday.workout == "Light swim or walk")
    }

    // MARK: - Training Goals

    @Test("Parses training goals")
    func trainingGoals() {
        let protocol_ = ProtocolParser.parse(Self.fullProtocolMarkdown)
        #expect(protocol_.trainingGoals.count == 3)
        #expect(protocol_.trainingGoals[0] == "Build aerobic base")
        #expect(protocol_.trainingGoals[1] == "Maintain strength")
        #expect(protocol_.trainingGoals[2] == "Practice transitions")
    }

    // MARK: - Weekly Targets

    @Test("Parses cardio targets")
    func cardioTargets() {
        let protocol_ = ProtocolParser.parse(Self.fullProtocolMarkdown)
        #expect(protocol_.cardioTargets["Swim"] == "700m")
        #expect(protocol_.cardioTargets["Bike"] == "45 minutes")
        #expect(protocol_.cardioTargets["Run"] == "4 miles")
    }

    @Test("Parses strength targets")
    func strengthTargets() {
        let protocol_ = ProtocolParser.parse(Self.fullProtocolMarkdown)
        #expect(protocol_.strengthTargets.count == 1)
        #expect(protocol_.strengthTargets[0] == "Complete all planned strength workouts")
    }

    // MARK: - AI Rationale

    @Test("Parses AI rationale")
    func aiRationale() {
        let protocol_ = ProtocolParser.parse(Self.fullProtocolMarkdown)
        #expect(protocol_.aiRationale != nil)
        #expect(protocol_.aiRationale!.contains("building aerobic capacity"))
    }

    // MARK: - Table Parsing

    @Test("parseTable handles standard markdown table")
    func parseTableStandard() {
        let table = """
        | A | B | C |
        |---|---|---|
        | 1 | 2 | 3 |
        | 4 | 5 | 6 |
        """
        let rows = ProtocolParser.parseTable(table)
        #expect(rows.count == 3) // header + 2 data rows
        #expect(rows[0] == ["A", "B", "C"])
        #expect(rows[1] == ["1", "2", "3"])
        #expect(rows[2] == ["4", "5", "6"])
    }

    @Test("parseTable skips separator row")
    func parseTableSkipsSeparator() {
        let table = """
        | H1 | H2 |
        |----|-----|
        | D1 | D2 |
        """
        let rows = ProtocolParser.parseTable(table)
        // Should have header row and 1 data row (separator skipped)
        #expect(rows.count == 2)
    }

    @Test("parseTable handles empty input")
    func parseTableEmpty() {
        let rows = ProtocolParser.parseTable("")
        #expect(rows.isEmpty)
    }

    @Test("parseTable handles cells with colons")
    func parseTableCellsWithColons() {
        let table = """
        | Day | Workout |
        |-----|---------|
        | Mon | Workout A: bench, rows |
        """
        let rows = ProtocolParser.parseTable(table)
        #expect(rows.count == 2)
        // The cell containing a colon should be preserved
        #expect(rows[1][1] == "Workout A: bench, rows")
    }

    // MARK: - Edge Cases

    @Test("Handles empty markdown")
    func emptyMarkdown() {
        let protocol_ = ProtocolParser.parse("")
        #expect(protocol_.schedule.isEmpty)
        #expect(protocol_.trainingGoals.isEmpty)
    }

    @Test("Handles protocol with only frontmatter")
    func frontmatterOnly() {
        let markdown = """
        ---
        title: "Test Protocol"
        date: 2026-02-01
        week_number: W05
        phase: "Testing"
        focus: "Test"
        target_compliance: 80%
        ---
        """
        let protocol_ = ProtocolParser.parse(markdown)
        #expect(protocol_.title == "Test Protocol")
        #expect(protocol_.weekNumber == "W05")
        #expect(protocol_.schedule.isEmpty)
    }

    @Test("Uses day lookup method")
    func dayLookup() {
        let protocol_ = ProtocolParser.parse(Self.fullProtocolMarkdown)
        let monday = protocol_.day(for: "Monday")
        #expect(monday != nil)
        #expect(monday?.workoutType == "Swim")

        let friday = protocol_.day(for: "friday")
        #expect(friday != nil)
        #expect(friday?.workoutType == "Strength")

        let missing = protocol_.day(for: "Holiday")
        #expect(missing == nil)
    }
}
