import Foundation

// MARK: - MarkdownSerializer

/// Serializes BeStupid models back to markdown format.
///
/// The output matches the exact format produced by the BeStupid Telegram bot,
/// ensuring both the bot and the iOS app can read each other's files.
///
/// Output follows this section order:
/// 1. YAML frontmatter (---)
/// 2. Planned Workout
/// 3. Daily Briefing
/// 4. Today's Todos
/// 5. Daily Habits
/// 6. Quick Log
/// 7. Training Output
/// 8. Strength Log
/// 9. Fuel Log
/// 10. Top 3 for Tomorrow
enum MarkdownSerializer: Sendable {

    // MARK: - Date Formatter

    private static let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(identifier: "UTC")
        return formatter
    }()

    // MARK: - Full Document Serialization

    /// Serialize a `DailyLog` to a complete markdown file in BeStupid format.
    ///
    /// - Parameter log: The daily log to serialize.
    /// - Returns: A markdown string ready to be written to a file.
    static func serialize(_ log: DailyLog) -> String {
        var parts: [String] = []

        // Frontmatter
        parts.append(serializeFrontmatter(log))

        // Planned Workout
        if let workout = log.plannedWorkout, !workout.isEmpty {
            parts.append("## Planned Workout\n\(workout)")
        }

        // Daily Briefing
        if let briefing = log.dailyBriefing, !briefing.isEmpty {
            parts.append("## Daily Briefing\n\(briefing)")
        }

        // Today's Todos
        if !log.todos.isEmpty {
            parts.append("## Today's Todos\n\(serializeTodos(log.todos))")
        }

        // Daily Habits
        if !log.habits.isEmpty {
            parts.append("## Daily Habits\n\(serializeHabits(log.habits))")
        }

        // Quick Log
        let quickLog = serializeQuickLog(log)
        if !quickLog.isEmpty {
            parts.append("## Quick Log\n\(quickLog)")
        }

        // Training Output
        if !log.trainingActivities.isEmpty {
            parts.append("## Training Output\n\(serializeTrainingOutput(log.trainingActivities))")
        }

        // Strength Log
        if !log.strengthExercises.isEmpty {
            parts.append("## Strength Log\n\(serializeStrengthLog(log.strengthExercises))")
        }

        // Fuel Log
        if log.caloriesSoFar != nil || log.proteinSoFar != nil || !log.nutritionLineItems.isEmpty {
            parts.append("## Fuel Log\n\(serializeNutrition(calories: log.caloriesSoFar, protein: log.proteinSoFar, items: log.nutritionLineItems))")
        }

        // Top 3 for Tomorrow
        if !log.topThreeForTomorrow.isEmpty {
            parts.append("## Top 3 for Tomorrow\n\(serializeTopThree(log.topThreeForTomorrow))")
        }

        return parts.joined(separator: "\n\n") + "\n"
    }

    // MARK: - Frontmatter

    /// Serialize the YAML frontmatter block.
    private static func serializeFrontmatter(_ log: DailyLog) -> String {
        let dateStr = dateFormatter.string(from: log.date)
        var lines: [String] = ["---"]
        lines.append("title: \"\(log.title)\"")
        lines.append("date: \(dateStr)")
        if !log.tags.isEmpty {
            let tagsList = log.tags.map { "\"\($0)\"" }.joined(separator: ", ")
            lines.append("tags: [\(tagsList)]")
        }
        lines.append("---")
        return lines.joined(separator: "\n")
    }

    // MARK: - Section Serializers

    /// Serialize quick log metrics as inline fields.
    ///
    /// Only includes fields that have non-nil values.
    static func serializeQuickLog(_ log: DailyLog) -> String {
        var lines: [String] = []

        if let weight = log.weight {
            lines.append("Weight:: \(formatNumber(weight))")
        }
        if let sleep = log.sleep {
            lines.append("Sleep:: \(formatSleepValue(sleep))")
        }
        if let sq = log.sleepQuality {
            lines.append("Sleep_Quality:: \(formatNumber(sq))")
        }
        if let moodAM = log.moodAM {
            lines.append("Mood_AM:: \(formatNumber(moodAM))")
        }
        if let moodPM = log.moodPM {
            lines.append("Mood_PM:: \(formatNumber(moodPM))")
        }
        if let energy = log.energy {
            lines.append("Energy:: \(formatNumber(energy))")
        }
        if let focus = log.focus {
            lines.append("Focus:: \(formatNumber(focus))")
        }

        return lines.joined(separator: "\n")
    }

    /// Serialize strength exercises as inline fields.
    ///
    /// Format: `Exercise Name:: NxN @ N lbs`
    static func serializeStrengthLog(_ exercises: [StrengthEntry]) -> String {
        exercises.map { entry in
            let weight = formatNumber(entry.weightLbs)
            return "\(entry.exerciseName):: \(entry.sets)x\(entry.reps) @ \(weight) lbs"
        }.joined(separator: "\n")
    }

    /// Serialize training activities as inline fields.
    ///
    /// Format: `Type:: distance+unit/MM:SS` with optional `Avg_HR:: N`
    static func serializeTrainingOutput(_ activities: [TrainingActivity]) -> String {
        var lines: [String] = []
        var commonHR: Int?

        for activity in activities {
            let typeName = activity.type.capitalized
            var valueParts: [String] = []

            // Distance part
            if let distance = activity.distance {
                let distStr = formatNumber(distance)
                valueParts.append("\(distStr)\(activity.distanceUnit.rawValue)")
            }

            // Duration part
            if let duration = activity.durationMinutes {
                valueParts.append(formatDuration(duration))
            }

            let value = valueParts.joined(separator: "/")
            if !value.isEmpty {
                lines.append("\(typeName):: \(value)")
            }

            // Track HR
            if let hr = activity.avgHeartRate {
                commonHR = hr
            }
        }

        // Append Avg_HR if any activity had it
        if let hr = commonHR {
            lines.append("Avg_HR:: \(hr)")
        }

        return lines.joined(separator: "\n")
    }

    /// Serialize todos as a markdown checkbox list.
    static func serializeTodos(_ todos: [TodoItem]) -> String {
        todos.map { todo in
            let checkbox = todo.isCompleted ? "[x]" : "[ ]"
            return "- \(checkbox) \(todo.text)"
        }.joined(separator: "\n")
    }

    /// Serialize habits as a markdown checkbox list.
    static func serializeHabits(_ habits: [HabitEntry]) -> String {
        habits.map { habit in
            let checkbox = habit.isCompleted ? "[x]" : "[ ]"
            return "- \(checkbox) \(habit.name)"
        }.joined(separator: "\n")
    }

    /// Serialize the nutrition section.
    ///
    /// Includes calorie/protein totals as inline fields, followed by food line items.
    static func serializeNutrition(
        calories: Int?,
        protein: Int?,
        items: [NutritionEntry]
    ) -> String {
        var lines: [String] = []

        if let cal = calories {
            lines.append("calories_so_far:: \(cal)")
        }
        if let pro = protein {
            lines.append("protein_so_far:: \(pro)")
        }

        for item in items {
            if let time = item.time, !time.isEmpty {
                lines.append("\(time) - \(item.food)")
            } else {
                lines.append(item.food)
            }
        }

        return lines.joined(separator: "\n")
    }

    /// Serialize the top 3 for tomorrow as a numbered list.
    private static func serializeTopThree(_ items: [String]) -> String {
        items.enumerated().map { index, item in
            "\(index + 1). \(item)"
        }.joined(separator: "\n")
    }

    // MARK: - Formatting Helpers

    /// Format a Double, removing unnecessary trailing zeros.
    ///
    /// - 244.5 -> "244.5"
    /// - 244.0 -> "244"
    /// - 7.25 -> "7.25"
    private static func formatNumber(_ value: Double) -> String {
        if value == value.rounded() && value == Double(Int(value)) {
            return "\(Int(value))"
        }
        // Remove trailing zeros
        let formatted = String(format: "%g", value)
        return formatted
    }

    /// Format a sleep duration in decimal hours to H:MM display format.
    ///
    /// - 6.583 -> "6:35"
    /// - 7.0 -> "7:00"
    /// - 6.5 -> "6:30"
    private static func formatSleepValue(_ hours: Double) -> String {
        let h = Int(hours)
        let m = Int(((hours - Double(h)) * 60).rounded())
        return String(format: "%d:%02d", h, m)
    }

    /// Format a duration in fractional minutes to MM:SS display format.
    ///
    /// - 33.65 -> "33:39"
    /// - 30.0 -> "30:00"
    /// - 45.5 -> "45:30"
    private static func formatDuration(_ minutes: Double) -> String {
        let totalSeconds = Int((minutes * 60).rounded())
        let mins = totalSeconds / 60
        let secs = totalSeconds % 60
        return String(format: "%d:%02d", mins, secs)
    }
}
