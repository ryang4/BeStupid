import Foundation
import Observation

// MARK: - LogViewMode

enum LogViewMode: String, CaseIterable, Sendable {
    case list = "List"
    case calendar = "Calendar"
}

// MARK: - LogViewModel

@Observable
@MainActor
final class LogViewModel {

    // MARK: - State

    var logs: [DailyLog] = []
    var selectedLog: DailyLog?
    var isLoading: Bool = false
    var errorMessage: String?
    var searchText: String = ""
    var viewMode: LogViewMode = .list

    var currentProtocol: WeeklyProtocol?

    // Calendar state
    var selectedMonth: Date = Date()
    var daysWithLogs: Set<String> = []

    // Editing
    var isEditing: Bool = false
    var editingLog: DailyLog?

    // MARK: - Computed Properties

    /// Logs filtered by search text against title, tags, planned workout, and todo text.
    var filteredLogs: [DailyLog] {
        guard !searchText.isEmpty else { return logs }
        let query = searchText.lowercased()
        return logs.filter { log in
            log.title.lowercased().contains(query)
                || log.tags.contains { $0.lowercased().contains(query) }
                || (log.plannedWorkout?.lowercased().contains(query) ?? false)
                || log.todos.contains { $0.text.lowercased().contains(query) }
                || log.trainingActivities.contains { $0.type.lowercased().contains(query) }
                || log.strengthExercises.contains { $0.exerciseName.lowercased().contains(query) }
        }
    }

    /// Logs grouped by month label (e.g. "February 2026"), preserving chronological order.
    var logsByMonth: [String: [DailyLog]] {
        let formatter = DateFormatter()
        formatter.dateFormat = "MMMM yyyy"
        formatter.locale = Locale(identifier: "en_US_POSIX")

        var grouped: [String: [DailyLog]] = [:]
        for log in filteredLogs {
            let key = formatter.string(from: log.date)
            grouped[key, default: []].append(log)
        }
        return grouped
    }

    /// Month labels sorted newest-first for section ordering.
    var sortedMonthKeys: [String] {
        let formatter = DateFormatter()
        formatter.dateFormat = "MMMM yyyy"
        formatter.locale = Locale(identifier: "en_US_POSIX")

        let keysWithDates: [(String, Date)] = logsByMonth.keys.compactMap { key in
            guard let date = formatter.date(from: key) else { return nil }
            return (key, date)
        }
        return keysWithDates.sorted { $0.1 > $1.1 }.map(\.0)
    }

    /// Display string for the currently selected month in calendar view.
    var selectedMonthLabel: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "MMMM yyyy"
        return formatter.string(from: selectedMonth)
    }

    /// All calendar day cells for the selected month, including leading blanks for alignment.
    var calendarDays: [CalendarDay] {
        let calendar = Calendar.current
        let components = calendar.dateComponents([.year, .month], from: selectedMonth)
        guard let firstOfMonth = calendar.date(from: components),
              let range = calendar.range(of: .day, in: .month, for: firstOfMonth) else {
            return []
        }

        let firstWeekday = calendar.component(.weekday, from: firstOfMonth)
        // Sunday = 1, so leading blanks = firstWeekday - 1
        let leadingBlanks = firstWeekday - 1

        var days: [CalendarDay] = []

        // Leading blank cells
        for index in 0..<leadingBlanks {
            days.append(CalendarDay(id: "blank-\(index)", date: nil, dayNumber: 0, hasLog: false))
        }

        let dateFormatter = DateFormatting.dailyLogFormatter

        for day in range {
            var dayComponents = components
            dayComponents.day = day
            guard let date = calendar.date(from: dayComponents) else { continue }
            let dateString = dateFormatter.string(from: date)
            let hasLog = daysWithLogs.contains(dateString)
            days.append(CalendarDay(
                id: dateString,
                date: date,
                dayNumber: day,
                hasLog: hasLog
            ))
        }

        return days
    }

    // MARK: - Actions

    func loadLogs() async {
        isLoading = true
        errorMessage = nil

        // Simulate async loading. In production, this calls DataSyncCoordinator.
        try? await Task.sleep(for: .milliseconds(500))

        logs = Self.makeMockLogs()
        buildDaysWithLogs()

        isLoading = false
    }

    func selectLog(_ log: DailyLog) {
        selectedLog = log
    }

    func loadProtocol() async {
        try? await Task.sleep(for: .milliseconds(300))
        currentProtocol = Self.makeMockProtocol()
    }

    func startEditing(_ log: DailyLog) {
        editingLog = log
        isEditing = true
    }

    func saveEdit() async {
        guard let editingLog else { return }

        // In production: persist via DataSyncCoordinator, serialize to markdown.
        try? await Task.sleep(for: .milliseconds(300))

        if let index = logs.firstIndex(where: { $0.id == editingLog.id }) {
            logs[index] = editingLog
        }

        if selectedLog?.id == editingLog.id {
            selectedLog = editingLog
        }

        buildDaysWithLogs()
        isEditing = false
        self.editingLog = nil
    }

    func cancelEdit() {
        isEditing = false
        editingLog = nil
    }

    func selectDate(_ date: Date) async {
        let dateString = DateFormatting.dailyLogFormatter.string(from: date)
        if let log = logs.first(where: {
            DateFormatting.dailyLogFormatter.string(from: $0.date) == dateString
        }) {
            selectedLog = log
        } else {
            selectedLog = nil
        }
    }

    func changeMonth(by offset: Int) {
        let calendar = Calendar.current
        if let newMonth = calendar.date(byAdding: .month, value: offset, to: selectedMonth) {
            selectedMonth = newMonth
        }
    }

    // MARK: - Private Helpers

    private func buildDaysWithLogs() {
        daysWithLogs = Set(logs.map { DateFormatting.dailyLogFormatter.string(from: $0.date) })
    }

    // MARK: - Mock Data

    private static func makeMockLogs() -> [DailyLog] {
        let calendar = Calendar.current
        let today = Date()

        return (0..<30).compactMap { offset in
            guard let date = calendar.date(byAdding: .day, value: -offset, to: today) else {
                return nil
            }

            let workoutTypes = ["Swim", "Strength", "Bike", "Run", "Recovery", "Brick"]
            let workoutType = workoutTypes[offset % workoutTypes.count]

            var activities: [TrainingActivity] = []
            var strengthExercises: [StrengthEntry] = []

            switch workoutType {
            case "Swim":
                activities = [
                    TrainingActivity(
                        type: "Swim",
                        distance: Double.random(in: 1500...2500),
                        distanceUnit: .meters,
                        durationMinutes: Double.random(in: 35...55),
                        avgHeartRate: Int.random(in: 130...155)
                    )
                ]
            case "Bike":
                activities = [
                    TrainingActivity(
                        type: "Bike",
                        distance: Double.random(in: 20...40),
                        distanceUnit: .kilometers,
                        durationMinutes: Double.random(in: 45...90),
                        avgHeartRate: Int.random(in: 125...150)
                    )
                ]
            case "Run":
                activities = [
                    TrainingActivity(
                        type: "Run",
                        distance: Double.random(in: 5...10),
                        distanceUnit: .kilometers,
                        durationMinutes: Double.random(in: 25...55),
                        avgHeartRate: Int.random(in: 140...165)
                    )
                ]
            case "Strength":
                strengthExercises = [
                    StrengthEntry(exerciseName: "Bench Press", sets: 3, reps: 10, weightLbs: 155),
                    StrengthEntry(exerciseName: "Squat", sets: 3, reps: 8, weightLbs: 205),
                    StrengthEntry(exerciseName: "Pull-ups", sets: 3, reps: 10, weightLbs: 0),
                    StrengthEntry(exerciseName: "Overhead Press", sets: 3, reps: 10, weightLbs: 95),
                ]
            case "Brick":
                activities = [
                    TrainingActivity(
                        type: "Bike",
                        distance: 25,
                        distanceUnit: .kilometers,
                        durationMinutes: 45,
                        avgHeartRate: 138
                    ),
                    TrainingActivity(
                        type: "Run",
                        distance: 3,
                        distanceUnit: .kilometers,
                        durationMinutes: 15,
                        avgHeartRate: 155
                    ),
                ]
            default:
                break
            }

            let completedTodos = Int.random(in: 1...3)
            let totalTodos = Int.random(in: 3...5)
            let todos = (0..<totalTodos).map { idx in
                TodoItem(
                    text: ["Review sprint backlog", "Submit expense report", "Read training chapter", "Plan weekend route", "Update project docs"][idx % 5],
                    isCompleted: idx < completedTodos
                )
            }

            let habits = [
                HabitEntry(habitId: "h1", name: "Morning meditation", isCompleted: Bool.random()),
                HabitEntry(habitId: "h2", name: "Stretch 15 min", isCompleted: Bool.random()),
                HabitEntry(habitId: "h3", name: "Read 30 min", isCompleted: Bool.random()),
                HabitEntry(habitId: "h4", name: "Cold shower", isCompleted: Bool.random()),
            ]

            return DailyLog(
                date: date,
                tags: [workoutType.lowercased()],
                weight: Double.random(in: 183...188),
                sleep: Double.random(in: 5.5...8.5),
                sleepQuality: Double.random(in: 5...10),
                moodAM: Double.random(in: 5...10),
                moodPM: Double.random(in: 5...10),
                energy: Double.random(in: 4...10),
                focus: Double.random(in: 5...10),
                plannedWorkout: workoutType,
                trainingActivities: activities,
                strengthExercises: strengthExercises,
                todos: todos,
                habits: habits,
                caloriesSoFar: Int.random(in: 1600...2400),
                proteinSoFar: Int.random(in: 100...180),
                topThreeForTomorrow: [
                    "Continue base building cardio",
                    "Finish quarterly report",
                    "Meal prep for the week",
                ],
                dailyBriefing: offset == 0
                    ? "Base building phase continues. Focus on consistent Z2 cardio and maintaining strength."
                    : nil
            )
        }
    }

    private static func makeMockProtocol() -> WeeklyProtocol {
        WeeklyProtocol(
            date: DateFormatting.mondayOfWeek(for: Date()),
            title: "Base Building - Week 6",
            weekNumber: DateFormatting.weekNumber(for: Date()),
            phase: "Base Building",
            focus: "Aerobic base with maintenance strength",
            schedule: [
                ProtocolDay(dayOfWeek: "Monday", workoutType: "Swim", workout: "2000m continuous Z2 swim, bilateral breathing"),
                ProtocolDay(dayOfWeek: "Tuesday", workoutType: "Strength", workout: "Full body compound lifts, 3x10 moderate"),
                ProtocolDay(dayOfWeek: "Wednesday", workoutType: "Bike", workout: "60 min Z2 ride, cadence focus 85-90 rpm"),
                ProtocolDay(dayOfWeek: "Thursday", workoutType: "Run", workout: "40 min easy run, conversational pace"),
                ProtocolDay(dayOfWeek: "Friday", workoutType: "Swim", workout: "1500m drill-focused with pull buoy"),
                ProtocolDay(dayOfWeek: "Saturday", workoutType: "Brick", workout: "45 min bike + 15 min run transition"),
                ProtocolDay(dayOfWeek: "Sunday", workoutType: "Recovery", workout: "30 min easy walk or yoga"),
            ],
            trainingGoals: [
                "Build aerobic base to support peak phase",
                "Maintain current strength levels",
                "Improve swim bilateral breathing",
            ],
            cardioTargets: [
                "Swim": "2000-2500m per session, Z2 focus",
                "Bike": "60-90 min per session, Z2",
                "Run": "30-45 min easy pace",
            ],
            strengthTargets: [
                "Bench Press: 3x10 @ 155 lbs",
                "Squat: 3x8 @ 205 lbs",
                "Pull-ups: 3x10 bodyweight",
            ],
            aiRationale: "Week 6 of base building maintains the aerobic stimulus while keeping strength work at maintenance volume. Recovery is prioritized with one full rest day and one active recovery session. The brick workout on Saturday introduces short-duration multi-sport transitions to prepare for the upcoming build phase."
        )
    }
}

// MARK: - CalendarDay

struct CalendarDay: Identifiable, Sendable {
    let id: String
    let date: Date?
    let dayNumber: Int
    let hasLog: Bool
}
