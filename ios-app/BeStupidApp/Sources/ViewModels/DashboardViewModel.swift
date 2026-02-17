import Foundation
import Observation
import SwiftUI

// MARK: - DaySummary

struct DaySummary: Identifiable, Sendable {
    let id: UUID
    let date: Date
    let dayLetter: String
    let workoutType: String?
    let workoutCompleted: Bool
    let todoCompletionRate: Double
    let hasLog: Bool

    init(
        id: UUID = UUID(),
        date: Date,
        dayLetter: String,
        workoutType: String? = nil,
        workoutCompleted: Bool = false,
        todoCompletionRate: Double = 0.0,
        hasLog: Bool = false
    ) {
        self.id = id
        self.date = date
        self.dayLetter = dayLetter
        self.workoutType = workoutType
        self.workoutCompleted = workoutCompleted
        self.todoCompletionRate = todoCompletionRate
        self.hasLog = hasLog
    }
}

// MARK: - TrendDirection

enum TrendDirection: Sendable {
    case up
    case down
    case stable
    case insufficient

    var systemImage: String {
        switch self {
        case .up: return "arrow.up.right"
        case .down: return "arrow.down.right"
        case .stable: return "arrow.right"
        case .insufficient: return "minus"
        }
    }

    /// Returns the color for this trend direction in the context of a given metric.
    /// For weight, down is positive (green). For sleep, mood, energy, up is positive.
    func color(for field: MetricField) -> Color {
        switch self {
        case .insufficient, .stable:
            return .secondary
        case .up:
            switch field {
            case .weight:
                return .red
            default:
                return .green
            }
        case .down:
            switch field {
            case .weight:
                return .green
            default:
                return .red
            }
        }
    }

    /// Default color when metric context is not available.
    var color: Color {
        switch self {
        case .up: return .green
        case .down: return .red
        case .stable, .insufficient: return .secondary
        }
    }
}

// MARK: - DashboardViewModel

@Observable
@MainActor
final class DashboardViewModel {

    // MARK: - State

    var todayLog: DailyLog?
    var currentProtocol: WeeklyProtocol?
    var recentMetrics: [MetricField: [MetricDataPoint]] = [:]
    var weekSummary: [DaySummary] = []
    var isLoading: Bool = true
    var errorMessage: String?

    // Quick log editing
    var isEditingMetric: Bool = false
    var editingField: MetricField?
    var editingValue: String = ""

    // MARK: - Computed Properties

    var todayWorkoutType: String? {
        guard let proto = currentProtocol else { return nil }
        let dayName = todayDayOfWeekName
        return proto.day(for: dayName)?.workoutType
    }

    var todayWorkoutDescription: String? {
        guard let proto = currentProtocol else { return nil }
        let dayName = todayDayOfWeekName
        return proto.day(for: dayName)?.workout
    }

    var weightTrend: TrendDirection {
        computeTrend(for: .weight)
    }

    var sleepAverage: Double? {
        guard let points = recentMetrics[.sleep], !points.isEmpty else { return nil }
        let sum = points.reduce(0.0) { $0 + $1.value }
        return sum / Double(points.count)
    }

    var moodTrend: TrendDirection {
        computeTrend(for: .moodAM)
    }

    var hasActiveWorkout: Bool {
        // This will be checked against AppState in the view layer.
        // The ViewModel provides protocol-based workout info; active state
        // comes from AppState.currentWorkout.
        false
    }

    // MARK: - Actions

    func loadDashboard() async {
        isLoading = true
        errorMessage = nil

        // Simulate async loading with mock data.
        // In production, this will call DataSyncCoordinator.
        try? await Task.sleep(for: .milliseconds(600))

        todayLog = Self.makeMockTodayLog()
        currentProtocol = Self.makeMockProtocol()
        recentMetrics = Self.makeMockRecentMetrics()
        weekSummary = Self.makeMockWeekSummary()

        isLoading = false
    }

    func toggleTodo(at index: Int) async {
        guard var log = todayLog, index >= 0, index < log.todos.count else { return }
        log.todos[index] = TodoItem(
            id: log.todos[index].id,
            text: log.todos[index].text,
            isCompleted: !log.todos[index].isCompleted
        )
        todayLog = log
        // In production: persist change via DataSyncCoordinator
    }

    func toggleHabit(at index: Int) async {
        guard var log = todayLog, index >= 0, index < log.habits.count else { return }
        log.habits[index] = HabitEntry(
            id: log.habits[index].id,
            habitId: log.habits[index].habitId,
            name: log.habits[index].name,
            isCompleted: !log.habits[index].isCompleted
        )
        todayLog = log
        // In production: persist change via DataSyncCoordinator
    }

    func updateMetric(field: MetricField, value: String) async {
        guard var log = todayLog else { return }

        switch field {
        case .weight:
            log.weight = Double(value)
        case .sleep:
            log.sleep = DateFormatting.normalizeSleep(value)
        case .sleepQuality:
            log.sleepQuality = DateFormatting.normalizeQualityScore(value)
        case .moodAM:
            log.moodAM = DateFormatting.normalizeQualityScore(value)
        case .moodPM:
            log.moodPM = DateFormatting.normalizeQualityScore(value)
        case .energy:
            log.energy = DateFormatting.normalizeQualityScore(value)
        case .focus:
            log.focus = DateFormatting.normalizeQualityScore(value)
        default:
            break
        }

        todayLog = log
        dismissQuickLog()
        // In production: persist change via DataSyncCoordinator
    }

    func startQuickLog(field: MetricField) {
        editingField = field
        editingValue = currentValueString(for: field)
        isEditingMetric = true
    }

    func dismissQuickLog() {
        isEditingMetric = false
        editingField = nil
        editingValue = ""
    }

    func refresh() async {
        await loadDashboard()
    }

    // MARK: - Private Helpers

    private var todayDayOfWeekName: String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "EEEE"
        return formatter.string(from: Date())
    }

    private func currentValueString(for field: MetricField) -> String {
        guard let log = todayLog else { return "" }
        switch field {
        case .weight:
            return log.weight.map { String(format: "%.1f", $0) } ?? ""
        case .sleep:
            return log.sleep.map { String(format: "%.1f", $0) } ?? ""
        case .sleepQuality:
            return log.sleepQuality.map { String(format: "%.0f", $0) } ?? ""
        case .moodAM:
            return log.moodAM.map { String(format: "%.0f", $0) } ?? ""
        case .moodPM:
            return log.moodPM.map { String(format: "%.0f", $0) } ?? ""
        case .energy:
            return log.energy.map { String(format: "%.0f", $0) } ?? ""
        case .focus:
            return log.focus.map { String(format: "%.0f", $0) } ?? ""
        default:
            return ""
        }
    }

    private func computeTrend(for field: MetricField) -> TrendDirection {
        guard let points = recentMetrics[field], points.count >= 3 else {
            return .insufficient
        }

        let sorted = points.sorted { $0.date < $1.date }
        let recentHalf = Array(sorted.suffix(sorted.count / 2))
        let olderHalf = Array(sorted.prefix(sorted.count / 2))

        guard !recentHalf.isEmpty, !olderHalf.isEmpty else { return .insufficient }

        let recentAvg = recentHalf.reduce(0.0) { $0 + $1.value } / Double(recentHalf.count)
        let olderAvg = olderHalf.reduce(0.0) { $0 + $1.value } / Double(olderHalf.count)

        let percentChange = abs(recentAvg - olderAvg) / max(olderAvg, 0.01)

        if percentChange < 0.02 {
            return .stable
        } else if recentAvg > olderAvg {
            return .up
        } else {
            return .down
        }
    }

    // MARK: - Mock Data Factories

    private static func makeMockTodayLog() -> DailyLog {
        DailyLog(
            date: Date(),
            title: DateFormatting.logFileName(for: Date()),
            weight: 185.4,
            sleep: 7.2,
            sleepQuality: 8,
            moodAM: 7,
            moodPM: nil,
            energy: 8,
            focus: 7,
            plannedWorkout: "Swim + Strength",
            trainingActivities: [
                TrainingActivity(
                    type: "Swim",
                    distance: 2000,
                    distanceUnit: .meters,
                    durationMinutes: 45,
                    avgHeartRate: 142
                )
            ],
            strengthExercises: [
                StrengthEntry(exerciseName: "Bench Press", sets: 3, reps: 10, weightLbs: 155),
                StrengthEntry(exerciseName: "Pull-ups", sets: 3, reps: 8, weightLbs: 0)
            ],
            todos: [
                TodoItem(text: "Review sprint backlog", isCompleted: true),
                TodoItem(text: "Submit expense report", isCompleted: false),
                TodoItem(text: "Plan weekend long ride route", isCompleted: false),
                TodoItem(text: "Read training chapter", isCompleted: true)
            ],
            habits: [
                HabitEntry(habitId: "h1", name: "Morning meditation", isCompleted: true),
                HabitEntry(habitId: "h2", name: "Stretch 15 min", isCompleted: false),
                HabitEntry(habitId: "h3", name: "Read 30 min", isCompleted: true),
                HabitEntry(habitId: "h4", name: "Cold shower", isCompleted: false),
                HabitEntry(habitId: "h5", name: "Journal", isCompleted: true)
            ],
            caloriesSoFar: 1850,
            proteinSoFar: 125,
            topThreeForTomorrow: [
                "Long bike ride - 60 min Z2",
                "Finish quarterly review",
                "Meal prep for the week"
            ],
            dailyBriefing: "Base building phase continues. Focus on consistent Z2 cardio and maintaining strength."
        )
    }

    private static func makeMockProtocol() -> WeeklyProtocol {
        WeeklyProtocol(
            date: DateFormatting.mondayOfWeek(for: Date()),
            title: "Base Building - Week 6",
            weekNumber: DateFormatting.weekNumber(for: Date()),
            phase: "Base Building",
            focus: "Aerobic base with maintenance strength",
            schedule: [
                ProtocolDay(dayOfWeek: "Monday", workoutType: "Swim", workout: "2000m continuous Z2 swim, focus on bilateral breathing"),
                ProtocolDay(dayOfWeek: "Tuesday", workoutType: "Strength", workout: "Full body strength - compound lifts, 3x10 moderate weight"),
                ProtocolDay(dayOfWeek: "Wednesday", workoutType: "Bike", workout: "60 min Z2 ride, flat terrain, cadence focus 85-90 rpm"),
                ProtocolDay(dayOfWeek: "Thursday", workoutType: "Run", workout: "40 min easy run, conversational pace, focus on form"),
                ProtocolDay(dayOfWeek: "Friday", workoutType: "Swim", workout: "1500m drill-focused swim with pull buoy work"),
                ProtocolDay(dayOfWeek: "Saturday", workoutType: "Brick", workout: "45 min bike + 15 min run transition practice"),
                ProtocolDay(dayOfWeek: "Sunday", workoutType: "Recovery", workout: "30 min easy walk or yoga, full body stretching")
            ],
            trainingGoals: [
                "Build aerobic base to support peak phase",
                "Maintain current strength levels",
                "Improve swim bilateral breathing"
            ]
        )
    }

    private static func makeMockRecentMetrics() -> [MetricField: [MetricDataPoint]] {
        let calendar = Calendar.current
        let today = Date()

        func points(for field: MetricField, values: [Double]) -> [MetricDataPoint] {
            values.enumerated().map { offset, value in
                let date = calendar.date(byAdding: .day, value: -(6 - offset), to: today) ?? today
                return MetricDataPoint(date: date, field: field, value: value, source: .manual)
            }
        }

        return [
            .weight: points(for: .weight, values: [186.2, 185.8, 186.0, 185.6, 185.5, 185.2, 185.4]),
            .sleep: points(for: .sleep, values: [6.8, 7.5, 7.0, 6.5, 7.8, 7.2, 7.2]),
            .moodAM: points(for: .moodAM, values: [6, 7, 6, 7, 8, 7, 7]),
            .energy: points(for: .energy, values: [7, 6, 7, 8, 7, 8, 8])
        ]
    }

    private static func makeMockWeekSummary() -> [DaySummary] {
        let calendar = Calendar.current
        let today = Date()
        let monday = DateFormatting.mondayOfWeek(for: today)
        let dayLetters = ["M", "T", "W", "T", "F", "S", "S"]
        let workoutTypes = ["Swim", "Strength", "Bike", "Run", "Swim", "Brick", "Recovery"]

        let todayWeekday = calendar.component(.weekday, from: today)
        // ISO weekday: Monday = 1. Calendar weekday: Sunday = 1, Monday = 2, ...
        let todayIndex = (todayWeekday + 5) % 7 // Convert to 0-based Mon index

        return (0..<7).map { offset in
            let date = calendar.date(byAdding: .day, value: offset, to: monday) ?? today
            let isPast = offset < todayIndex
            let isToday = offset == todayIndex
            return DaySummary(
                date: date,
                dayLetter: dayLetters[offset],
                workoutType: workoutTypes[offset],
                workoutCompleted: isPast,
                todoCompletionRate: isPast ? Double.random(in: 0.6...1.0) : (isToday ? 0.5 : 0.0),
                hasLog: isPast || isToday
            )
        }
    }
}
