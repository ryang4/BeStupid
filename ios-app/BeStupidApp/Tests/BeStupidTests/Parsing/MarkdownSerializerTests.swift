import Testing
import Foundation
@testable import BeStupidApp

// MARK: - MarkdownSerializerTests

@Suite("MarkdownSerializer")
struct MarkdownSerializerTests {

    // MARK: - Helpers

    /// Create a date for testing (UTC).
    private static func makeDate(year: Int, month: Int, day: Int) -> Date {
        var components = DateComponents()
        components.year = year
        components.month = month
        components.day = day
        components.timeZone = TimeZone(identifier: "UTC")
        return Calendar(identifier: .gregorian).date(from: components)!
    }

    // MARK: - Todo Serialization

    @Test("Serializes todos with checkboxes")
    func serializeTodos() {
        let todos = [
            TodoItem(text: "Complete morning workout", isCompleted: true),
            TodoItem(text: "Review weekly protocol", isCompleted: false),
            TodoItem(text: "30 min coding", isCompleted: true),
        ]

        let result = MarkdownSerializer.serializeTodos(todos)
        let lines = result.components(separatedBy: "\n")
        #expect(lines.count == 3)
        #expect(lines[0] == "- [x] Complete morning workout")
        #expect(lines[1] == "- [ ] Review weekly protocol")
        #expect(lines[2] == "- [x] 30 min coding")
    }

    // MARK: - Habit Serialization

    @Test("Serializes habits with checkboxes")
    func serializeHabits() {
        let habits = [
            HabitEntry(habitId: "ai_automation", name: "Build and share one AI automation", isCompleted: true),
            HabitEntry(habitId: "yoga", name: "10 min yoga", isCompleted: false),
        ]

        let result = MarkdownSerializer.serializeHabits(habits)
        let lines = result.components(separatedBy: "\n")
        #expect(lines.count == 2)
        #expect(lines[0] == "- [x] Build and share one AI automation")
        #expect(lines[1] == "- [ ] 10 min yoga")
    }

    // MARK: - Strength Log Serialization

    @Test("Serializes strength exercises")
    func serializeStrengthLog() {
        let exercises = [
            StrengthEntry(exerciseName: "Dumbbell bench press", sets: 3, reps: 10, weightLbs: 60),
            StrengthEntry(exerciseName: "Cable seated row", sets: 3, reps: 11, weightLbs: 120),
        ]

        let result = MarkdownSerializer.serializeStrengthLog(exercises)
        let lines = result.components(separatedBy: "\n")
        #expect(lines.count == 2)
        #expect(lines[0] == "Dumbbell bench press:: 3x10 @ 60 lbs")
        #expect(lines[1] == "Cable seated row:: 3x11 @ 120 lbs")
    }

    @Test("Serializes strength with decimal weight")
    func serializeStrengthDecimalWeight() {
        let exercises = [
            StrengthEntry(exerciseName: "Dumbbell curl", sets: 3, reps: 12, weightLbs: 22.5),
        ]

        let result = MarkdownSerializer.serializeStrengthLog(exercises)
        #expect(result == "Dumbbell curl:: 3x12 @ 22.5 lbs")
    }

    // MARK: - Training Output Serialization

    @Test("Serializes training activities")
    func serializeTrainingOutput() {
        let activities = [
            TrainingActivity(type: "swim", distance: 750, distanceUnit: .meters, durationMinutes: 33.65, avgHeartRate: 117),
        ]

        let result = MarkdownSerializer.serializeTrainingOutput(activities)
        let lines = result.components(separatedBy: "\n")
        #expect(lines.count == 2)
        #expect(lines[0] == "Swim:: 750m/33:39")
        #expect(lines[1] == "Avg_HR:: 117")
    }

    @Test("Serializes multiple training activities")
    func serializeMultipleActivities() {
        let activities = [
            TrainingActivity(type: "bike", distance: 15, distanceUnit: .kilometers, durationMinutes: 45.0),
            TrainingActivity(type: "run", distance: 3.1, distanceUnit: .miles, durationMinutes: 28.5, avgHeartRate: 145),
        ]

        let result = MarkdownSerializer.serializeTrainingOutput(activities)
        let lines = result.components(separatedBy: "\n")
        #expect(lines[0] == "Bike:: 15km/45:00")
        #expect(lines[1] == "Run:: 3.1mi/28:30")
        #expect(lines[2] == "Avg_HR:: 145")
    }

    // MARK: - Nutrition Serialization

    @Test("Serializes nutrition with totals and items")
    func serializeNutrition() {
        let items = [
            NutritionEntry(time: "12pm", food: "4 eggs, toast, avocado"),
            NutritionEntry(time: "3pm", food: "protein shake, banana"),
        ]

        let result = MarkdownSerializer.serializeNutrition(
            calories: 2720,
            protein: 85,
            items: items
        )
        let lines = result.components(separatedBy: "\n")
        #expect(lines.count == 4)
        #expect(lines[0] == "calories_so_far:: 2720")
        #expect(lines[1] == "protein_so_far:: 85")
        #expect(lines[2] == "12pm - 4 eggs, toast, avocado")
        #expect(lines[3] == "3pm - protein shake, banana")
    }

    @Test("Serializes nutrition items without time")
    func serializeNutritionNoTime() {
        let items = [
            NutritionEntry(food: "Some snack"),
        ]

        let result = MarkdownSerializer.serializeNutrition(
            calories: nil,
            protein: nil,
            items: items
        )
        #expect(result == "Some snack")
    }

    // MARK: - Quick Log Serialization

    @Test("Serializes quick log fields")
    func serializeQuickLog() {
        let log = DailyLog(
            date: Self.makeDate(year: 2026, month: 1, day: 30),
            weight: 244.5,
            sleep: 6.583,
            sleepQuality: 7.4,
            moodAM: 6,
            moodPM: 7,
            energy: 7.2,
            focus: 6.5
        )

        let result = MarkdownSerializer.serializeQuickLog(log)
        let lines = result.components(separatedBy: "\n")
        #expect(lines.contains("Weight:: 244.5"))
        #expect(lines.contains("Sleep:: 6:35"))
        #expect(lines.contains("Sleep_Quality:: 7.4"))
        #expect(lines.contains("Mood_AM:: 6"))
        #expect(lines.contains("Mood_PM:: 7"))
        #expect(lines.contains("Energy:: 7.2"))
        #expect(lines.contains("Focus:: 6.5"))
    }

    @Test("Omits nil quick log fields")
    func serializeQuickLogPartial() {
        let log = DailyLog(
            date: Self.makeDate(year: 2026, month: 1, day: 30),
            weight: 244.5
        )

        let result = MarkdownSerializer.serializeQuickLog(log)
        #expect(result == "Weight:: 244.5")
    }

    // MARK: - Full Document Serialization

    @Test("Serializes complete daily log")
    func serializeFullLog() {
        let date = Self.makeDate(year: 2026, month: 1, day: 30)
        let log = DailyLog(
            date: date,
            title: "2026-01-30: Strength Day",
            tags: ["log"],
            weight: 244.5,
            sleep: 6.583,
            sleepQuality: 7.4,
            moodAM: 6,
            moodPM: 7,
            energy: 7.2,
            focus: 6.5,
            plannedWorkout: "400m freestyle swim",
            trainingActivities: [
                TrainingActivity(type: "swim", distance: 750, distanceUnit: .meters, durationMinutes: 33.65, avgHeartRate: 117)
            ],
            strengthExercises: [
                StrengthEntry(exerciseName: "Bench press", sets: 3, reps: 10, weightLbs: 60)
            ],
            todos: [
                TodoItem(text: "Complete morning workout", isCompleted: true),
                TodoItem(text: "Review protocol", isCompleted: false)
            ],
            habits: [
                HabitEntry(habitId: "yoga", name: "10 min yoga", isCompleted: true)
            ],
            caloriesSoFar: 2720,
            proteinSoFar: 85,
            nutritionLineItems: [
                NutritionEntry(time: "12pm", food: "4 eggs, toast")
            ],
            topThreeForTomorrow: ["Morning swim", "Ship feature X"],
            dailyBriefing: "Build momentum"
        )

        let result = MarkdownSerializer.serialize(log)

        // Verify frontmatter
        #expect(result.contains("---"))
        #expect(result.contains("title: \"2026-01-30: Strength Day\""))
        #expect(result.contains("date: 2026-01-30"))
        #expect(result.contains("tags: [\"log\"]"))

        // Verify sections exist
        #expect(result.contains("## Planned Workout"))
        #expect(result.contains("400m freestyle swim"))
        #expect(result.contains("## Daily Briefing"))
        #expect(result.contains("Build momentum"))
        #expect(result.contains("## Today's Todos"))
        #expect(result.contains("- [x] Complete morning workout"))
        #expect(result.contains("- [ ] Review protocol"))
        #expect(result.contains("## Daily Habits"))
        #expect(result.contains("- [x] 10 min yoga"))
        #expect(result.contains("## Quick Log"))
        #expect(result.contains("Weight:: 244.5"))
        #expect(result.contains("## Training Output"))
        #expect(result.contains("Swim:: 750m/33:39"))
        #expect(result.contains("## Strength Log"))
        #expect(result.contains("Bench press:: 3x10 @ 60 lbs"))
        #expect(result.contains("## Fuel Log"))
        #expect(result.contains("calories_so_far:: 2720"))
        #expect(result.contains("## Top 3 for Tomorrow"))
        #expect(result.contains("1. Morning swim"))
        #expect(result.contains("2. Ship feature X"))
    }

    @Test("Serialized output ends with newline")
    func endsWithNewline() {
        let log = DailyLog(
            date: Self.makeDate(year: 2026, month: 1, day: 30),
            title: "Test"
        )
        let result = MarkdownSerializer.serialize(log)
        #expect(result.hasSuffix("\n"))
    }

    // MARK: - Round-Trip

    @Test("Parse then serialize produces valid output")
    func roundTrip() {
        let original = """
        ---
        title: "2026-01-30: Strength Day"
        date: 2026-01-30
        tags: ["log"]
        ---

        ## Today's Todos
        - [x] Complete morning workout
        - [ ] Review weekly protocol

        ## Quick Log
        Weight:: 244.5
        Energy:: 7.2

        ## Strength Log
        Bench press:: 3x10 @ 60 lbs

        ## Top 3 for Tomorrow
        1. Morning swim
        2. Ship feature X
        """

        let parsed = DailyLogParser.parse(original)
        let serialized = MarkdownSerializer.serialize(parsed)

        // Re-parse the serialized output
        let reParsed = DailyLogParser.parse(serialized)

        // Verify key fields survived the round trip
        #expect(reParsed.title == parsed.title)
        #expect(reParsed.weight == parsed.weight)
        #expect(reParsed.energy == parsed.energy)
        #expect(reParsed.todos.count == parsed.todos.count)
        #expect(reParsed.todos[0].text == parsed.todos[0].text)
        #expect(reParsed.todos[0].isCompleted == parsed.todos[0].isCompleted)
        #expect(reParsed.strengthExercises.count == parsed.strengthExercises.count)
        #expect(reParsed.strengthExercises[0].exerciseName == parsed.strengthExercises[0].exerciseName)
        #expect(reParsed.topThreeForTomorrow == parsed.topThreeForTomorrow)
    }
}
