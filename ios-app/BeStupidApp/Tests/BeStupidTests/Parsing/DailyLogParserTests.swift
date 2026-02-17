import Testing
import Foundation
@testable import BeStupidApp

// MARK: - DailyLogParserTests

@Suite("DailyLogParser")
struct DailyLogParserTests {

    // MARK: - Test Data

    /// A full example daily log matching the BeStupid format.
    private static let fullLogMarkdown = """
    ---
    title: "2026-01-30: Strength Day"
    date: 2026-01-30
    tags: ["log"]
    ---

    ## Planned Workout
    400m freestyle swim

    ## Daily Briefing
    **Today's Focus:** Build momentum

    ## Today's Todos
    - [x] Complete morning workout
    - [ ] Review weekly protocol
    - [x] 30 min coding

    ## Daily Habits
    - [x] Build and share one AI automation
    - [ ] 10 min yoga

    ## Quick Log
    Weight:: 244.5
    Sleep:: 6:35
    Sleep_Quality:: 7.4
    Mood_AM:: 6
    Mood_PM:: 7
    Energy:: 7.2
    Focus:: 6.5

    ## Training Output
    Swim:: 750m/33:39
    Avg_HR:: 117

    ## Strength Log
    Dumbbell bench press:: 3x10 @ 60 lbs
    Cable seated row:: 3x11 @ 120 lbs
    Assisted pull up:: 3x2 @ 50 lbs

    ## Fuel Log
    calories_so_far:: 2720
    protein_so_far:: 85
    12pm - 4 eggs, toast, avocado
    3pm - protein shake, banana

    ## Top 3 for Tomorrow
    1. Morning swim
    2. Ship feature X
    3. Review protocol
    """

    // MARK: - Full Document Parsing

    @Test("Parses frontmatter correctly")
    func frontmatter() {
        let log = DailyLogParser.parse(Self.fullLogMarkdown)
        #expect(log.title == "2026-01-30: Strength Day")
        #expect(log.tags == ["log"])

        let calendar = Calendar(identifier: .gregorian)
        var dateComponents = DateComponents()
        dateComponents.year = 2026
        dateComponents.month = 1
        dateComponents.day = 30
        dateComponents.timeZone = TimeZone(identifier: "UTC")
        let expectedDate = calendar.date(from: dateComponents)!

        #expect(calendar.isDate(log.date, inSameDayAs: expectedDate))
    }

    @Test("Parses planned workout")
    func plannedWorkout() {
        let log = DailyLogParser.parse(Self.fullLogMarkdown)
        #expect(log.plannedWorkout == "400m freestyle swim")
    }

    @Test("Parses daily briefing")
    func dailyBriefing() {
        let log = DailyLogParser.parse(Self.fullLogMarkdown)
        #expect(log.dailyBriefing != nil)
        #expect(log.dailyBriefing!.contains("Build momentum"))
    }

    @Test("Parses todos with correct completion state")
    func todos() {
        let log = DailyLogParser.parse(Self.fullLogMarkdown)
        #expect(log.todos.count == 3)

        #expect(log.todos[0].text == "Complete morning workout")
        #expect(log.todos[0].isCompleted == true)

        #expect(log.todos[1].text == "Review weekly protocol")
        #expect(log.todos[1].isCompleted == false)

        #expect(log.todos[2].text == "30 min coding")
        #expect(log.todos[2].isCompleted == true)
    }

    @Test("Parses habits with correct completion state")
    func habits() {
        let log = DailyLogParser.parse(Self.fullLogMarkdown)
        #expect(log.habits.count == 2)

        #expect(log.habits[0].name == "Build and share one AI automation")
        #expect(log.habits[0].isCompleted == true)

        #expect(log.habits[1].name == "10 min yoga")
        #expect(log.habits[1].isCompleted == false)
    }

    @Test("Parses habit IDs from names")
    func habitIds() {
        let log = DailyLogParser.parse(Self.fullLogMarkdown)
        #expect(log.habits[0].habitId == "build_and_share_one_ai_automation")
        #expect(log.habits[1].habitId == "10_min_yoga")
    }

    @Test("Parses quick log weight")
    func quickLogWeight() {
        let log = DailyLogParser.parse(Self.fullLogMarkdown)
        #expect(log.weight == 244.5)
    }

    @Test("Parses quick log sleep as decimal hours")
    func quickLogSleep() {
        let log = DailyLogParser.parse(Self.fullLogMarkdown)
        // 6:35 = 6 + 35/60 = 6.583...
        #expect(log.sleep != nil)
        #expect(log.sleep! >= 6.58)
        #expect(log.sleep! <= 6.59)
    }

    @Test("Parses quick log sleep quality")
    func quickLogSleepQuality() {
        let log = DailyLogParser.parse(Self.fullLogMarkdown)
        #expect(log.sleepQuality == 7.4)
    }

    @Test("Parses quick log mood values")
    func quickLogMood() {
        let log = DailyLogParser.parse(Self.fullLogMarkdown)
        #expect(log.moodAM == 6.0)
        #expect(log.moodPM == 7.0)
    }

    @Test("Parses quick log energy and focus")
    func quickLogEnergyFocus() {
        let log = DailyLogParser.parse(Self.fullLogMarkdown)
        #expect(log.energy == 7.2)
        #expect(log.focus == 6.5)
    }

    @Test("Parses training activities with correct units")
    func trainingActivities() {
        let log = DailyLogParser.parse(Self.fullLogMarkdown)
        #expect(log.trainingActivities.count == 1)

        let swim = log.trainingActivities[0]
        #expect(swim.type == "swim")
        #expect(swim.distance == 750.0)
        #expect(swim.distanceUnit == .meters)
        // 33:39 = 33 + 39/60 = 33.65
        #expect(swim.durationMinutes != nil)
        #expect(swim.durationMinutes! >= 33.64)
        #expect(swim.durationMinutes! <= 33.66)
    }

    @Test("Applies avg HR to training activities")
    func trainingAvgHR() {
        let log = DailyLogParser.parse(Self.fullLogMarkdown)
        #expect(log.trainingActivities.count == 1)
        #expect(log.trainingActivities[0].avgHeartRate == 117)
    }

    @Test("Parses strength exercises")
    func strengthExercises() {
        let log = DailyLogParser.parse(Self.fullLogMarkdown)
        #expect(log.strengthExercises.count == 3)

        #expect(log.strengthExercises[0].exerciseName == "Dumbbell bench press")
        #expect(log.strengthExercises[0].sets == 3)
        #expect(log.strengthExercises[0].reps == 10)
        #expect(log.strengthExercises[0].weightLbs == 60.0)

        #expect(log.strengthExercises[1].exerciseName == "Cable seated row")
        #expect(log.strengthExercises[1].sets == 3)
        #expect(log.strengthExercises[1].reps == 11)
        #expect(log.strengthExercises[1].weightLbs == 120.0)

        #expect(log.strengthExercises[2].exerciseName == "Assisted pull up")
        #expect(log.strengthExercises[2].sets == 3)
        #expect(log.strengthExercises[2].reps == 2)
        #expect(log.strengthExercises[2].weightLbs == 50.0)
    }

    @Test("Parses nutrition calories and protein totals")
    func nutritionTotals() {
        let log = DailyLogParser.parse(Self.fullLogMarkdown)
        #expect(log.caloriesSoFar == 2720)
        #expect(log.proteinSoFar == 85)
    }

    @Test("Parses nutrition line items")
    func nutritionItems() {
        let log = DailyLogParser.parse(Self.fullLogMarkdown)
        #expect(log.nutritionLineItems.count == 2)

        #expect(log.nutritionLineItems[0].time == "12pm")
        #expect(log.nutritionLineItems[0].food == "4 eggs, toast, avocado")

        #expect(log.nutritionLineItems[1].time == "3pm")
        #expect(log.nutritionLineItems[1].food == "protein shake, banana")
    }

    @Test("Parses top 3 for tomorrow")
    func topThreeForTomorrow() {
        let log = DailyLogParser.parse(Self.fullLogMarkdown)
        #expect(log.topThreeForTomorrow.count == 3)
        #expect(log.topThreeForTomorrow[0] == "Morning swim")
        #expect(log.topThreeForTomorrow[1] == "Ship feature X")
        #expect(log.topThreeForTomorrow[2] == "Review protocol")
    }

    // MARK: - Section Parsing

    @Test("parseSections extracts all sections")
    func parseSections() {
        let sections = DailyLogParser.parseSections(Self.fullLogMarkdown)
        #expect(sections.keys.contains("Planned Workout"))
        #expect(sections.keys.contains("Daily Briefing"))
        #expect(sections.keys.contains("Today's Todos"))
        #expect(sections.keys.contains("Daily Habits"))
        #expect(sections.keys.contains("Quick Log"))
        #expect(sections.keys.contains("Training Output"))
        #expect(sections.keys.contains("Strength Log"))
        #expect(sections.keys.contains("Fuel Log"))
        #expect(sections.keys.contains("Top 3 for Tomorrow"))
    }

    // MARK: - Edge Cases

    @Test("Handles empty markdown")
    func emptyMarkdown() {
        let log = DailyLogParser.parse("")
        #expect(log.todos.isEmpty)
        #expect(log.habits.isEmpty)
        #expect(log.trainingActivities.isEmpty)
        #expect(log.strengthExercises.isEmpty)
        #expect(log.nutritionLineItems.isEmpty)
        #expect(log.topThreeForTomorrow.isEmpty)
    }

    @Test("Handles markdown with only frontmatter")
    func frontmatterOnly() {
        let markdown = """
        ---
        title: "2026-02-01: Test"
        date: 2026-02-01
        tags: ["log"]
        ---
        """

        let log = DailyLogParser.parse(markdown)
        #expect(log.title == "2026-02-01: Test")
        #expect(log.todos.isEmpty)
    }

    @Test("Handles markdown without frontmatter")
    func noFrontmatter() {
        let markdown = """
        ## Quick Log
        Weight:: 200.0
        """

        let log = DailyLogParser.parse(markdown)
        #expect(log.weight == 200.0)
    }

    @Test("Handles minimal log with single section")
    func minimalLog() {
        let markdown = """
        ---
        title: "2026-02-01: Minimal"
        date: 2026-02-01
        tags: ["log"]
        ---

        ## Quick Log
        Weight:: 200.0
        Energy:: 8
        """

        let log = DailyLogParser.parse(markdown)
        #expect(log.weight == 200.0)
        #expect(log.energy == 8.0)
        #expect(log.todos.isEmpty)
        #expect(log.strengthExercises.isEmpty)
    }

    @Test("Parses multiple training activities")
    func multipleTrainingActivities() {
        let markdown = """
        ---
        title: "2026-02-01: Brick Day"
        date: 2026-02-01
        tags: ["log"]
        ---

        ## Training Output
        Bike:: 15km/45:00
        Run:: 3.1mi/28:30
        Avg_HR:: 145
        """

        let log = DailyLogParser.parse(markdown)
        #expect(log.trainingActivities.count == 2)

        let bike = log.trainingActivities[0]
        #expect(bike.type == "bike")
        #expect(bike.distance == 15.0)
        #expect(bike.distanceUnit == .kilometers)
        #expect(bike.durationMinutes == 45.0)
        #expect(bike.avgHeartRate == 145)

        let run = log.trainingActivities[1]
        #expect(run.type == "run")
        #expect(run.distance == 3.1)
        #expect(run.distanceUnit == .miles)
        #expect(run.durationMinutes == 28.5)
        #expect(run.avgHeartRate == 145)
    }

    // MARK: - Todo/Habit Parsing Details

    @Test("parseTodos handles empty input")
    func parseTodosEmpty() {
        let todos = DailyLogParser.parseTodos(from: nil)
        #expect(todos.isEmpty)
    }

    @Test("parseTodos handles mixed checkbox formats")
    func parseTodosMixed() {
        let text = """
        - [x] Done task
        - [X] Also done (uppercase X)
        - [ ] Not done
        Some non-checkbox line
        """
        let todos = DailyLogParser.parseTodos(from: text)
        #expect(todos.count == 3)
        #expect(todos[0].isCompleted == true)
        #expect(todos[1].isCompleted == true)
        #expect(todos[2].isCompleted == false)
    }

    @Test("parseHabits derives habit IDs correctly")
    func parseHabitIds() {
        let text = """
        - [x] Build and share one AI automation
        - [ ] 10 min yoga
        - [x] Morning stretching routine
        """
        let habits = DailyLogParser.parseHabits(from: text)
        #expect(habits.count == 3)
        #expect(habits[0].habitId == "build_and_share_one_ai_automation")
        #expect(habits[1].habitId == "10_min_yoga")
        #expect(habits[2].habitId == "morning_stretching_routine")
    }

    // MARK: - Numbered List Parsing

    @Test("parseNumberedList handles standard format")
    func parseNumberedList() {
        let text = """
        1. First item
        2. Second item
        3. Third item
        """
        let items = DailyLogParser.parseNumberedList(from: text)
        #expect(items.count == 3)
        #expect(items[0] == "First item")
        #expect(items[1] == "Second item")
        #expect(items[2] == "Third item")
    }

    @Test("parseNumberedList skips non-numbered lines")
    func parseNumberedListSkips() {
        let text = """
        Some intro text
        1. First item
        Not numbered
        2. Second item
        """
        let items = DailyLogParser.parseNumberedList(from: text)
        #expect(items.count == 2)
    }

    @Test("parseNumberedList returns empty for nil")
    func parseNumberedListNil() {
        let items = DailyLogParser.parseNumberedList(from: nil)
        #expect(items.isEmpty)
    }

    // MARK: - Computed Properties

    @Test("Todo completion rate calculated correctly")
    func todoCompletionRate() {
        let log = DailyLogParser.parse(Self.fullLogMarkdown)
        // 2 of 3 completed = 0.666...
        #expect(log.todoCompletionRate != nil)
        #expect(log.todoCompletionRate! >= 0.66)
        #expect(log.todoCompletionRate! <= 0.67)
    }

    @Test("Habit completion rate calculated correctly")
    func habitCompletionRate() {
        let log = DailyLogParser.parse(Self.fullLogMarkdown)
        // 1 of 2 completed = 0.5
        #expect(log.habitCompletionRate == 0.5)
    }
}
