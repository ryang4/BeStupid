import Foundation

// MARK: - ProtocolParser

/// Parses a BeStupid weekly protocol markdown file into a `WeeklyProtocol` model.
///
/// Expected format includes:
/// - YAML frontmatter with title, date, week_number, phase, focus, target_compliance
/// - "Weekly Schedule" section with a markdown table
/// - "Training Goals" section with a bullet list
/// - "Weekly Targets" section with subsections for cardio and strength
/// - "AI Rationale" section with free text
enum ProtocolParser: Sendable {

    // MARK: - Public API

    /// Parse a complete weekly protocol markdown file.
    ///
    /// - Parameter markdown: The full markdown content of a protocol file.
    /// - Returns: A `WeeklyProtocol` populated with all parsed data.
    static func parse(_ markdown: String) -> WeeklyProtocol {
        let frontmatter = YAMLFrontmatterParser.parse(markdown)
        let sections = DailyLogParser.parseSections(markdown)

        let date = frontmatter.date ?? Date()
        let title = frontmatter.title ?? "Protocol"
        let weekNumber = frontmatter.weekNumber ?? ""
        let phase = frontmatter.phase ?? ""
        let focus = frontmatter.focus ?? ""
        let targetCompliance = frontmatter.targetCompliance ?? 0.8

        // Parse schedule table
        let schedule: [ProtocolDay]
        if let scheduleText = sections["Weekly Schedule"] {
            schedule = parseScheduleTable(scheduleText)
        } else {
            schedule = []
        }

        // Parse training goals (bullet list)
        let trainingGoals: [String]
        if let goalsText = sections["Training Goals"] {
            trainingGoals = parseBulletList(from: goalsText)
        } else {
            trainingGoals = []
        }

        // Parse weekly targets
        let (cardioTargets, strengthTargets) = parseWeeklyTargets(from: sections["Weekly Targets"])

        // AI Rationale (raw text)
        let aiRationale = sections["AI Rationale"]?.trimmingCharacters(in: .whitespacesAndNewlines)

        return WeeklyProtocol(
            date: date,
            title: title,
            weekNumber: weekNumber,
            phase: phase,
            focus: focus,
            targetCompliance: targetCompliance,
            schedule: schedule,
            trainingGoals: trainingGoals,
            cardioTargets: cardioTargets,
            strengthTargets: strengthTargets,
            aiRationale: aiRationale
        )
    }

    /// Parse a markdown table into an array of row arrays.
    ///
    /// Handles the standard markdown table format:
    /// ```
    /// | Header1 | Header2 |
    /// |---------|---------|
    /// | Cell1   | Cell2   |
    /// ```
    ///
    /// The separator row (containing `---`) is excluded from the result.
    /// Leading and trailing pipe characters are stripped.
    ///
    /// - Parameter text: The text containing a markdown table.
    /// - Returns: An array of rows, where each row is an array of cell strings.
    static func parseTable(_ text: String) -> [[String]] {
        let lines = text.components(separatedBy: "\n")
        var rows: [[String]] = []

        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)

            // Skip empty lines
            guard !trimmed.isEmpty else { continue }

            // Must contain pipes to be a table row
            guard trimmed.contains("|") else { continue }

            // Skip separator rows (e.g., |---|---|---|)
            let withoutPipesAndDashes = trimmed.replacingOccurrences(of: "|", with: "")
                .replacingOccurrences(of: "-", with: "")
                .replacingOccurrences(of: ":", with: "")
                .trimmingCharacters(in: .whitespaces)
            if withoutPipesAndDashes.isEmpty { continue }

            // Split by pipe and clean up cells
            let cells = trimmed.split(separator: "|", omittingEmptySubsequences: false)
                .map { String($0).trimmingCharacters(in: .whitespaces) }
                .filter { !$0.isEmpty || cells(in: trimmed) }

            // Re-parse: split by | but handle leading/trailing pipes
            let cleanCells = parseTableRow(trimmed)
            if !cleanCells.isEmpty {
                rows.append(cleanCells)
            }
        }

        return rows
    }

    // MARK: - Internal Parsing

    /// Parse a single table row by splitting on `|` and trimming.
    private static func parseTableRow(_ line: String) -> [String] {
        var row = line.trimmingCharacters(in: .whitespaces)

        // Remove leading pipe
        if row.hasPrefix("|") {
            row = String(row.dropFirst())
        }
        // Remove trailing pipe
        if row.hasSuffix("|") {
            row = String(row.dropLast())
        }

        return row.split(separator: "|")
            .map { String($0).trimmingCharacters(in: .whitespaces) }
    }

    /// Dummy helper used only in the filter closure above (never actually called at runtime).
    private static func cells(in _: String) -> Bool { false }

    /// Parse the schedule table into `ProtocolDay` values.
    ///
    /// Expects a 3-column table: Day | Type | Workout
    private static func parseScheduleTable(_ text: String) -> [ProtocolDay] {
        let allRows = parseTable(text)
        guard allRows.count > 1 else { return [] }

        // First row is the header -- skip it
        let dataRows = Array(allRows.dropFirst())

        return dataRows.compactMap { row in
            guard row.count >= 3 else { return nil }
            let dayOfWeek = row[0]
            let workoutType = row[1]
            let workout = row[2]

            guard !dayOfWeek.isEmpty else { return nil }

            return ProtocolDay(
                dayOfWeek: dayOfWeek,
                workoutType: workoutType,
                workout: workout
            )
        }
    }

    /// Parse a markdown bullet list into an array of strings.
    private static func parseBulletList(from text: String) -> [String] {
        let lines = text.components(separatedBy: "\n")
        var items: [String] = []

        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.hasPrefix("- ") {
                let item = String(trimmed.dropFirst(2)).trimmingCharacters(in: .whitespaces)
                if !item.isEmpty {
                    items.append(item)
                }
            } else if trimmed.hasPrefix("* ") {
                let item = String(trimmed.dropFirst(2)).trimmingCharacters(in: .whitespaces)
                if !item.isEmpty {
                    items.append(item)
                }
            }
        }

        return items
    }

    /// Parse the "Weekly Targets" section into cardio targets and strength targets.
    ///
    /// Expected format:
    /// ```
    /// **Cardio Volume:**
    /// - Swim: 700m
    /// - Bike: 45 minutes
    ///
    /// **Strength:**
    /// - Complete all planned strength workouts
    /// ```
    private static func parseWeeklyTargets(from text: String?) -> ([String: String], [String]) {
        guard let text else { return ([:], []) }

        var cardioTargets: [String: String] = [:]
        var strengthTargets: [String] = []

        // Split into subsections by bold headers (**Header:**)
        let lines = text.components(separatedBy: "\n")
        var currentSubsection: String?

        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)

            // Detect bold subsection headers
            if trimmed.hasPrefix("**") && trimmed.contains(":") {
                let headerContent = trimmed
                    .replacingOccurrences(of: "**", with: "")
                    .trimmingCharacters(in: .whitespaces)
                let headerName = headerContent.components(separatedBy: ":").first?
                    .trimmingCharacters(in: .whitespaces)
                    .lowercased() ?? ""

                if headerName.contains("cardio") {
                    currentSubsection = "cardio"
                } else if headerName.contains("strength") {
                    currentSubsection = "strength"
                } else {
                    currentSubsection = headerName
                }
                continue
            }

            // Parse bullet items within the current subsection
            guard trimmed.hasPrefix("- ") || trimmed.hasPrefix("* ") else { continue }
            let bulletContent = String(trimmed.dropFirst(2)).trimmingCharacters(in: .whitespaces)
            guard !bulletContent.isEmpty else { continue }

            switch currentSubsection {
            case "cardio":
                // Parse "Swim: 700m" format
                if let colonIndex = bulletContent.firstIndex(of: ":") {
                    let key = String(bulletContent[bulletContent.startIndex..<colonIndex])
                        .trimmingCharacters(in: .whitespaces)
                    let value = String(bulletContent[bulletContent.index(after: colonIndex)...])
                        .trimmingCharacters(in: .whitespaces)
                    cardioTargets[key] = value
                }
            case "strength":
                strengthTargets.append(bulletContent)
            default:
                break
            }
        }

        return (cardioTargets, strengthTargets)
    }
}
