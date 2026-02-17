import Foundation

// MARK: - DailyLogParser

/// Parses a complete BeStupid daily log markdown file into a `DailyLog` model.
///
/// The parser combines several sub-parsers:
/// - `YAMLFrontmatterParser` for title, date, and tags
/// - `InlineFieldParser` for `Key:: value` fields
/// - `StrengthLogParser` for strength exercise entries
/// - `TrainingValueParser` for training activity distance/duration values
///
/// Expected sections (all optional):
/// - "Planned Workout" -- raw text
/// - "Daily Briefing" -- raw text
/// - "Today's Todos" -- checkbox list
/// - "Daily Habits" -- checkbox list
/// - "Quick Log" -- inline fields (weight, sleep, mood, etc.)
/// - "Training Output" -- inline fields for activities + Avg_HR
/// - "Strength Log" -- strength exercise entries
/// - "Fuel Log" -- inline fields for calories/protein + line items
/// - "Top 3 for Tomorrow" -- numbered list
enum DailyLogParser: Sendable {

    // MARK: - Public API

    /// Parse a complete daily log markdown file into a `DailyLog`.
    ///
    /// - Parameter markdown: The full markdown content of a daily log file.
    /// - Returns: A `DailyLog` populated with all parsed data.
    static func parse(_ markdown: String) -> DailyLog {
        let frontmatter = YAMLFrontmatterParser.parse(markdown)
        let sections = parseSections(markdown)

        let date = frontmatter.date ?? Date()
        let title = frontmatter.title ?? DateFormatting.logFileName(for: date)

        // Parse each section
        let plannedWorkout = sections["Planned Workout"]?.trimmingCharacters(in: .whitespacesAndNewlines)
        let dailyBriefing = sections["Daily Briefing"]?.trimmingCharacters(in: .whitespacesAndNewlines)
        let todos = parseTodos(from: sections["Today's Todos"])
        let habits = parseHabits(from: sections["Daily Habits"])
        let quickLog = parseQuickLog(from: sections["Quick Log"])
        let (trainingActivities, avgHR) = parseTrainingOutput(from: sections["Training Output"])
        let strengthExercises = parseStrengthLog(from: sections["Strength Log"])
        let (caloriesSoFar, proteinSoFar, nutritionItems) = parseNutrition(from: sections["Fuel Log"])
        let topThree = parseNumberedList(from: sections["Top 3 for Tomorrow"])

        // Apply avg HR to training activities if present and they don't already have one
        let finalActivities: [TrainingActivity]
        if let hr = avgHR {
            finalActivities = trainingActivities.map { activity in
                if activity.avgHeartRate == nil {
                    return TrainingActivity(
                        id: activity.id,
                        type: activity.type,
                        distance: activity.distance,
                        distanceUnit: activity.distanceUnit,
                        durationMinutes: activity.durationMinutes,
                        avgHeartRate: hr,
                        avgWatts: activity.avgWatts
                    )
                }
                return activity
            }
        } else {
            finalActivities = trainingActivities
        }

        return DailyLog(
            date: date,
            title: title,
            tags: frontmatter.tags,
            weight: quickLog.weight,
            sleep: quickLog.sleep,
            sleepQuality: quickLog.sleepQuality,
            moodAM: quickLog.moodAM,
            moodPM: quickLog.moodPM,
            energy: quickLog.energy,
            focus: quickLog.focus,
            plannedWorkout: plannedWorkout,
            trainingActivities: finalActivities,
            strengthExercises: strengthExercises,
            todos: todos,
            habits: habits,
            caloriesSoFar: caloriesSoFar,
            proteinSoFar: proteinSoFar,
            nutritionLineItems: nutritionItems,
            topThreeForTomorrow: topThree,
            dailyBriefing: dailyBriefing
        )
    }

    /// Split a markdown document into sections by `## ` headers.
    ///
    /// Returns a dictionary mapping section header text to section body text.
    /// The frontmatter and any content before the first `## ` header are excluded.
    ///
    /// - Parameter markdown: The full markdown content.
    /// - Returns: A dictionary of `[headerName: bodyText]`.
    static func parseSections(_ markdown: String) -> [String: String] {
        let lines = markdown.components(separatedBy: "\n")
        var sections: [String: String] = [:]
        var currentHeader: String?
        var currentBody: [String] = []

        // Skip past frontmatter
        var inFrontmatter = false
        var pastFrontmatter = false

        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)

            // Handle frontmatter skip
            if !pastFrontmatter {
                if trimmed == "---" {
                    if inFrontmatter {
                        pastFrontmatter = true
                    } else {
                        inFrontmatter = true
                    }
                    continue
                }
                if inFrontmatter { continue }
                // If we never saw ---, everything is body
                pastFrontmatter = true
            }

            // Detect section headers
            if trimmed.hasPrefix("## ") {
                // Save previous section
                if let header = currentHeader {
                    sections[header] = currentBody.joined(separator: "\n")
                }
                currentHeader = String(trimmed.dropFirst(3)).trimmingCharacters(in: .whitespaces)
                currentBody = []
            } else {
                currentBody.append(line)
            }
        }

        // Save last section
        if let header = currentHeader {
            sections[header] = currentBody.joined(separator: "\n")
        }

        return sections
    }

    // MARK: - Section Parsers

    /// Parsed quick log metrics.
    private struct QuickLogValues {
        var weight: Double?
        var sleep: Double?
        var sleepQuality: Double?
        var moodAM: Double?
        var moodPM: Double?
        var energy: Double?
        var focus: Double?
    }

    /// Parse the "Quick Log" section containing inline fields for body metrics.
    private static func parseQuickLog(from text: String?) -> QuickLogValues {
        guard let text else { return QuickLogValues() }
        let fields = InlineFieldParser.parseToDictionary(from: text)
        var values = QuickLogValues()

        // Weight (plain number)
        if let weightStr = caseInsensitiveLookup("Weight", in: fields) {
            values.weight = Double(weightStr)
        }

        // Sleep (could be H:MM or decimal hours)
        if let sleepStr = caseInsensitiveLookup("Sleep", in: fields) {
            values.sleep = DateFormatting.normalizeSleep(sleepStr)
        }

        // Sleep Quality
        if let sqStr = caseInsensitiveLookup("Sleep_Quality", in: fields) {
            values.sleepQuality = Double(sqStr)
        }

        // Mood AM
        if let moodAMStr = caseInsensitiveLookup("Mood_AM", in: fields) {
            values.moodAM = Double(moodAMStr)
        }

        // Mood PM
        if let moodPMStr = caseInsensitiveLookup("Mood_PM", in: fields) {
            values.moodPM = Double(moodPMStr)
        }

        // Energy
        if let energyStr = caseInsensitiveLookup("Energy", in: fields) {
            values.energy = Double(energyStr)
        }

        // Focus
        if let focusStr = caseInsensitiveLookup("Focus", in: fields) {
            values.focus = Double(focusStr)
        }

        return values
    }

    /// Parse the "Training Output" section.
    ///
    /// Looks for inline fields like `Swim:: 750m/33:39` and `Avg_HR:: 117`.
    /// Known activity types: Swim, Bike, Run.
    private static func parseTrainingOutput(from text: String?) -> ([TrainingActivity], Int?) {
        guard let text else { return ([], nil) }
        let fields = InlineFieldParser.parseAll(from: text)
        var activities: [TrainingActivity] = []
        var avgHR: Int?

        let activityTypes = ["swim", "bike", "run"]

        for field in fields {
            let nameLower = field.name.lowercased().trimmingCharacters(in: .whitespaces)

            if nameLower == "avg_hr" || nameLower == "avghr" || nameLower == "avg hr" {
                avgHR = Int(field.rawValue)
                continue
            }

            // Check if this is a known activity type
            if activityTypes.contains(nameLower) {
                let parsed = TrainingValueParser.parse(field.rawValue)

                // Determine distance unit: use explicit suffix from value if present,
                // otherwise infer from activity type.
                let unit: DistanceUnit
                if parsed.distance != nil && hasExplicitUnitSuffix(field.rawValue) {
                    unit = parsed.distanceUnit
                } else if parsed.distance != nil {
                    unit = TrainingValueParser.defaultUnit(for: nameLower)
                } else {
                    unit = TrainingValueParser.defaultUnit(for: nameLower)
                }

                activities.append(TrainingActivity(
                    type: nameLower,
                    distance: parsed.distance,
                    distanceUnit: unit,
                    durationMinutes: parsed.durationMinutes
                ))
            }
        }

        return (activities, avgHR)
    }

    /// Parse the "Strength Log" section.
    private static func parseStrengthLog(from text: String?) -> [StrengthEntry] {
        guard let text else { return [] }
        return StrengthLogParser.parseAll(from: text)
    }

    /// Parse the "Today's Todos" section containing markdown checkboxes.
    ///
    /// Format: `- [x] Completed task` or `- [ ] Incomplete task`
    static func parseTodos(from text: String?) -> [TodoItem] {
        guard let text else { return [] }
        return parseCheckboxList(from: text).map { (isCompleted, label) in
            TodoItem(text: label, isCompleted: isCompleted)
        }
    }

    /// Parse the "Daily Habits" section containing markdown checkboxes.
    ///
    /// Format: `- [x] Habit name` or `- [ ] Habit name`
    /// The habit ID is derived from the name by lowercasing and replacing spaces with underscores.
    static func parseHabits(from text: String?) -> [HabitEntry] {
        guard let text else { return [] }
        return parseCheckboxList(from: text).map { (isCompleted, label) in
            let habitId = label.lowercased()
                .replacingOccurrences(of: " ", with: "_")
                .replacingOccurrences(of: "-", with: "_")
            return HabitEntry(habitId: habitId, name: label, isCompleted: isCompleted)
        }
    }

    /// Parse a markdown checkbox list into (isCompleted, text) tuples.
    private static func parseCheckboxList(from text: String) -> [(Bool, String)] {
        let lines = text.components(separatedBy: "\n")
        var results: [(Bool, String)] = []

        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)

            if trimmed.hasPrefix("- [x] ") || trimmed.hasPrefix("- [X] ") {
                let label = String(trimmed.dropFirst(6)).trimmingCharacters(in: .whitespaces)
                if !label.isEmpty {
                    results.append((true, label))
                }
            } else if trimmed.hasPrefix("- [ ] ") {
                let label = String(trimmed.dropFirst(6)).trimmingCharacters(in: .whitespaces)
                if !label.isEmpty {
                    results.append((false, label))
                }
            }
        }

        return results
    }

    /// Parse the "Fuel Log" section.
    ///
    /// Extracts:
    /// - `calories_so_far:: N` and `protein_so_far:: N` inline fields
    /// - Line items like `12pm - 4 eggs, toast, avocado`
    private static func parseNutrition(from text: String?) -> (Int?, Int?, [NutritionEntry]) {
        guard let text else { return (nil, nil, []) }
        let fields = InlineFieldParser.parseToDictionary(from: text)
        let lines = text.components(separatedBy: "\n")

        let caloriesSoFar: Int?
        if let calStr = caseInsensitiveLookup("calories_so_far", in: fields) {
            caloriesSoFar = Int(calStr)
        } else {
            caloriesSoFar = nil
        }

        let proteinSoFar: Int?
        if let proStr = caseInsensitiveLookup("protein_so_far", in: fields) {
            proteinSoFar = Int(proStr)
        } else {
            proteinSoFar = nil
        }

        // Parse food line items (lines that aren't inline fields and contain food descriptions)
        var items: [NutritionEntry] = []
        let nutritionLinePattern = #/^(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)?)\s*[-–]\s*(.+)$/#

        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard !trimmed.isEmpty else { continue }
            // Skip inline field lines
            if InlineFieldParser.parseLine(trimmed) != nil { continue }

            if let match = trimmed.firstMatch(of: nutritionLinePattern) {
                let time = String(match.1).trimmingCharacters(in: .whitespaces)
                let food = String(match.2).trimmingCharacters(in: .whitespaces)
                items.append(NutritionEntry(time: time, food: food))
            } else if !trimmed.hasPrefix("#") {
                // Non-field, non-header line might still be a food item without time
                // Only include if it looks like food (contains commas or common food words)
                // but don't include empty/whitespace-only lines
                let looksLikeFood = trimmed.contains(",") ||
                    trimmed.contains("egg") || trimmed.contains("protein") ||
                    trimmed.contains("chicken") || trimmed.contains("shake") ||
                    trimmed.contains("salad") || trimmed.contains("rice")
                if looksLikeFood {
                    items.append(NutritionEntry(food: trimmed))
                }
            }
        }

        return (caloriesSoFar, proteinSoFar, items)
    }

    /// Parse a numbered list (1. Item, 2. Item, ...).
    static func parseNumberedList(from text: String?) -> [String] {
        guard let text else { return [] }
        let lines = text.components(separatedBy: "\n")
        var items: [String] = []

        let numberedPattern = #/^\d+\.\s+(.+)$/#

        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if let match = trimmed.firstMatch(of: numberedPattern) {
                let item = String(match.1).trimmingCharacters(in: .whitespaces)
                if !item.isEmpty {
                    items.append(item)
                }
            }
        }

        return items
    }

    // MARK: - Helpers

    /// Case-insensitive lookup in a field dictionary.
    private static func caseInsensitiveLookup(_ key: String, in dict: [String: String]) -> String? {
        let lowered = key.lowercased()
        for (k, v) in dict {
            if k.lowercased() == lowered {
                return v
            }
        }
        return nil
    }
}
