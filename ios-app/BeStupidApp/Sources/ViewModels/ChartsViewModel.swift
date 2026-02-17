import Foundation
import Observation

// MARK: - TimeRange

enum TimeRange: String, CaseIterable, Sendable {
    case oneWeek = "1W"
    case twoWeeks = "2W"
    case fourWeeks = "4W"
    case eightWeeks = "8W"
    case twelveWeeks = "12W"
    case all = "All"

    /// Number of days this range covers. Returns nil for `.all`.
    var days: Int? {
        switch self {
        case .oneWeek: return 7
        case .twoWeeks: return 14
        case .fourWeeks: return 28
        case .eightWeeks: return 56
        case .twelveWeeks: return 84
        case .all: return nil
        }
    }

    /// Computes the start date for this time range relative to today.
    var startDate: Date {
        let calendar = Calendar.current
        guard let dayCount = days else {
            // For "All", return a date far in the past.
            return calendar.date(byAdding: .year, value: -5, to: Date()) ?? Date.distantPast
        }
        return calendar.date(byAdding: .day, value: -dayCount, to: calendar.startOfDay(for: Date())) ?? Date.distantPast
    }
}

// MARK: - ChartTab

enum ChartTab: String, CaseIterable, Sendable {
    case training = "Training"
    case body = "Body"
    case compliance = "Compliance"
}

// MARK: - WeeklyVolume

struct WeeklyVolume: Identifiable, Sendable {
    let id: UUID
    let weekStart: Date
    let weekLabel: String
    let swimMinutes: Double
    let bikeMinutes: Double
    let runMinutes: Double
    let strengthMinutes: Double
    let totalMinutes: Double

    init(
        id: UUID = UUID(),
        weekStart: Date,
        weekLabel: String,
        swimMinutes: Double,
        bikeMinutes: Double,
        runMinutes: Double,
        strengthMinutes: Double
    ) {
        self.id = id
        self.weekStart = weekStart
        self.weekLabel = weekLabel
        self.swimMinutes = swimMinutes
        self.bikeMinutes = bikeMinutes
        self.runMinutes = runMinutes
        self.strengthMinutes = strengthMinutes
        self.totalMinutes = swimMinutes + bikeMinutes + runMinutes + strengthMinutes
    }
}

// MARK: - StrengthProgress

struct StrengthProgress: Identifiable, Sendable {
    let id: UUID
    let date: Date
    let exerciseName: String
    let maxWeight: Double
    let totalVolume: Double
    let estimatedOneRepMax: Double

    init(
        id: UUID = UUID(),
        date: Date,
        exerciseName: String,
        maxWeight: Double,
        totalVolume: Double,
        repsAtMaxWeight: Int
    ) {
        self.id = id
        self.date = date
        self.exerciseName = exerciseName
        self.maxWeight = maxWeight
        self.totalVolume = totalVolume
        // Epley formula: 1RM = weight * (1 + reps / 30)
        self.estimatedOneRepMax = maxWeight * (1.0 + Double(repsAtMaxWeight) / 30.0)
    }
}

// MARK: - MovingAveragePoint

struct MovingAveragePoint: Identifiable, Sendable {
    let id: UUID
    let date: Date
    let value: Double

    init(id: UUID = UUID(), date: Date, value: Double) {
        self.id = id
        self.date = date
        self.value = value
    }
}

// MARK: - DayActivity

struct DayActivity: Identifiable, Sendable {
    let id: UUID
    let date: Date
    let workoutType: String?
    let durationMinutes: Double
    let intensity: Double

    init(
        id: UUID = UUID(),
        date: Date,
        workoutType: String? = nil,
        durationMinutes: Double = 0,
        intensity: Double = 0
    ) {
        self.id = id
        self.date = date
        self.workoutType = workoutType
        self.durationMinutes = durationMinutes
        self.intensity = min(max(intensity, 0), 1)
    }
}

// MARK: - ComplianceDay

struct ComplianceDay: Identifiable, Sendable {
    let id: UUID
    let date: Date
    let dayLabel: String
    let todoCompletionRate: Double
    let habitCompletionRate: Double
    let workoutCompleted: Bool

    init(
        id: UUID = UUID(),
        date: Date,
        dayLabel: String,
        todoCompletionRate: Double = 0,
        habitCompletionRate: Double = 0,
        workoutCompleted: Bool = false
    ) {
        self.id = id
        self.date = date
        self.dayLabel = dayLabel
        self.todoCompletionRate = todoCompletionRate
        self.habitCompletionRate = habitCompletionRate
        self.workoutCompleted = workoutCompleted
    }
}

// MARK: - ChartsViewModel

@Observable
@MainActor
final class ChartsViewModel {

    // MARK: - State

    var selectedTimeRange: TimeRange = .fourWeeks
    var selectedChartTab: ChartTab = .training
    var isLoading: Bool = false

    // Training data
    var weeklyTrainingVolume: [WeeklyVolume] = []
    var strengthProgress: [StrengthProgress] = []
    var selectedExercise: String?
    var availableExercises: [String] = []
    var workoutFrequency: [DayActivity] = []

    // Body metrics data
    var weightData: [MetricDataPoint] = []
    var sleepData: [MetricDataPoint] = []
    var sleepQualityData: [MetricDataPoint] = []
    var moodAMData: [MetricDataPoint] = []
    var moodPMData: [MetricDataPoint] = []
    var energyData: [MetricDataPoint] = []
    var focusData: [MetricDataPoint] = []

    // Compliance data
    var complianceDays: [ComplianceDay] = []

    // MARK: - Computed Properties

    /// 7-day moving average for weight data within the selected time range.
    var weightMovingAverage: [MovingAveragePoint] {
        computeMovingAverage(for: filteredWeightData, windowSize: 7)
    }

    /// Average sleep hours across the filtered data.
    var sleepAverage: Double? {
        let filtered = filteredSleepData
        guard !filtered.isEmpty else { return nil }
        let total = filtered.reduce(0.0) { $0 + $1.value }
        return total / Double(filtered.count)
    }

    /// Strength data filtered to the currently selected exercise.
    var filteredStrengthProgress: [StrengthProgress] {
        guard let exercise = selectedExercise else { return [] }
        let cutoff = selectedTimeRange.startDate
        return strengthProgress
            .filter { $0.exerciseName == exercise && $0.date >= cutoff }
            .sorted { $0.date < $1.date }
    }

    /// Weight data filtered to the selected time range.
    var filteredWeightData: [MetricDataPoint] {
        filterByTimeRange(weightData)
    }

    /// Sleep data filtered to the selected time range.
    var filteredSleepData: [MetricDataPoint] {
        filterByTimeRange(sleepData)
    }

    /// Sleep quality data filtered to the selected time range.
    var filteredSleepQualityData: [MetricDataPoint] {
        filterByTimeRange(sleepQualityData)
    }

    /// Mood (AM) data filtered to the selected time range.
    var filteredMoodAMData: [MetricDataPoint] {
        filterByTimeRange(moodAMData)
    }

    /// Mood (PM) data filtered to the selected time range.
    var filteredMoodPMData: [MetricDataPoint] {
        filterByTimeRange(moodPMData)
    }

    /// Energy data filtered to the selected time range.
    var filteredEnergyData: [MetricDataPoint] {
        filterByTimeRange(energyData)
    }

    /// Focus data filtered to the selected time range.
    var filteredFocusData: [MetricDataPoint] {
        filterByTimeRange(focusData)
    }

    /// Weekly volume data filtered to the selected time range.
    var filteredWeeklyVolume: [WeeklyVolume] {
        let cutoff = selectedTimeRange.startDate
        return weeklyTrainingVolume
            .filter { $0.weekStart >= cutoff }
            .sorted { $0.weekStart < $1.weekStart }
    }

    /// Workout frequency data filtered to the selected time range.
    var filteredWorkoutFrequency: [DayActivity] {
        let cutoff = selectedTimeRange.startDate
        return workoutFrequency
            .filter { $0.date >= cutoff }
            .sorted { $0.date < $1.date }
    }

    /// Compliance data filtered to the selected time range.
    var filteredComplianceDays: [ComplianceDay] {
        let cutoff = selectedTimeRange.startDate
        return complianceDays
            .filter { $0.date >= cutoff }
            .sorted { $0.date < $1.date }
    }

    // MARK: - Actions

    func loadChartData() async {
        isLoading = true

        // Simulate network/disk latency for demo.
        try? await Task.sleep(for: .milliseconds(400))

        let calendar = Calendar.current
        let today = calendar.startOfDay(for: Date())

        generateWeeklyTrainingVolume(calendar: calendar, today: today)
        generateStrengthProgress(calendar: calendar, today: today)
        generateWorkoutFrequency(calendar: calendar, today: today)
        generateBodyMetrics(calendar: calendar, today: today)
        generateComplianceData(calendar: calendar, today: today)

        if selectedExercise == nil, let first = availableExercises.first {
            selectedExercise = first
        }

        isLoading = false
    }

    func selectTimeRange(_ range: TimeRange) async {
        selectedTimeRange = range
        // In production, this might trigger a reload from persistent storage
        // for larger date ranges. For now the data is already in memory.
    }

    func selectExercise(_ name: String) async {
        selectedExercise = name
    }

    // MARK: - Private Helpers

    private func filterByTimeRange(_ points: [MetricDataPoint]) -> [MetricDataPoint] {
        let cutoff = selectedTimeRange.startDate
        return points
            .filter { $0.date >= cutoff }
            .sorted { $0.date < $1.date }
    }

    private func computeMovingAverage(for points: [MetricDataPoint], windowSize: Int) -> [MovingAveragePoint] {
        let sorted = points.sorted { $0.date < $1.date }
        guard sorted.count >= windowSize else { return [] }

        var result: [MovingAveragePoint] = []
        for index in (windowSize - 1)..<sorted.count {
            let windowStart = index - windowSize + 1
            let windowSlice = sorted[windowStart...index]
            let avg = windowSlice.reduce(0.0) { $0 + $1.value } / Double(windowSize)
            result.append(MovingAveragePoint(date: sorted[index].date, value: avg))
        }
        return result
    }

    // MARK: - Sample Data Generation

    private func generateWeeklyTrainingVolume(calendar: Calendar, today: Date) {
        var volumes: [WeeklyVolume] = []

        // Generate 12 weeks of data for the broadest range.
        for weekOffset in stride(from: -11, through: 0, by: 1) {
            guard let weekStart = calendar.date(byAdding: .weekOfYear, value: weekOffset, to: DateFormatting.mondayOfWeek(for: today)) else {
                continue
            }
            let weekLabel = DateFormatting.weekNumber(for: weekStart)

            // Simulate a progressive half-ironman base build:
            // Volume ramps up gradually with some variation.
            let progressFactor = 1.0 + Double(weekOffset + 11) * 0.04
            let variation = Double.random(in: 0.85...1.15)

            let swimMin = (40.0 + Double(weekOffset + 11) * 2.5) * variation
            let bikeMin = (50.0 + Double(weekOffset + 11) * 5.0) * variation
            let runMin = (30.0 + Double(weekOffset + 11) * 2.0) * variation
            let strengthMin = max(30.0 * progressFactor * Double.random(in: 0.8...1.1), 20.0)

            volumes.append(WeeklyVolume(
                weekStart: weekStart,
                weekLabel: weekLabel,
                swimMinutes: round(swimMin),
                bikeMinutes: round(bikeMin),
                runMinutes: round(runMin),
                strengthMinutes: round(strengthMin)
            ))
        }

        weeklyTrainingVolume = volumes
    }

    private func generateStrengthProgress(calendar: Calendar, today: Date) {
        let exercises = ["Bench Press", "Squat", "Deadlift", "Overhead Press", "Pull-ups"]
        availableExercises = exercises

        struct ExerciseProfile {
            let baseWeight: Double
            let weeklyGain: Double
            let baseReps: Int
            let baseSets: Int
        }

        let profiles: [String: ExerciseProfile] = [
            "Bench Press": ExerciseProfile(baseWeight: 135, weeklyGain: 1.5, baseReps: 10, baseSets: 3),
            "Squat": ExerciseProfile(baseWeight: 185, weeklyGain: 2.5, baseReps: 8, baseSets: 4),
            "Deadlift": ExerciseProfile(baseWeight: 225, weeklyGain: 2.5, baseReps: 5, baseSets: 3),
            "Overhead Press": ExerciseProfile(baseWeight: 95, weeklyGain: 1.0, baseReps: 10, baseSets: 3),
            "Pull-ups": ExerciseProfile(baseWeight: 0, weeklyGain: 0, baseReps: 8, baseSets: 3)
        ]

        var allProgress: [StrengthProgress] = []

        for exercise in exercises {
            guard let profile = profiles[exercise] else { continue }

            // Two sessions per week for each exercise over 12 weeks.
            for weekOffset in stride(from: -11, through: 0, by: 1) {
                for sessionInWeek in [1, 4] { // Tuesday and Friday roughly
                    guard let sessionDate = calendar.date(byAdding: .day, value: weekOffset * 7 + sessionInWeek, to: DateFormatting.mondayOfWeek(for: today)) else {
                        continue
                    }

                    // Skip future dates.
                    guard sessionDate <= today else { continue }

                    let weeksIn = Double(weekOffset + 11)
                    let variation = Double.random(in: 0.95...1.05)
                    let maxWeight: Double
                    let reps: Int

                    if exercise == "Pull-ups" {
                        // Bodyweight exercise; track reps progression.
                        maxWeight = 0
                        reps = profile.baseReps + Int(weeksIn * 0.3)
                    } else {
                        maxWeight = round((profile.baseWeight + weeksIn * profile.weeklyGain) * variation / 2.5) * 2.5
                        reps = profile.baseReps + (Int(weeksIn) % 3 == 0 ? 1 : 0)
                    }

                    let totalVol = maxWeight * Double(reps) * Double(profile.baseSets)

                    allProgress.append(StrengthProgress(
                        date: sessionDate,
                        exerciseName: exercise,
                        maxWeight: maxWeight,
                        totalVolume: totalVol,
                        repsAtMaxWeight: reps
                    ))
                }
            }
        }

        strengthProgress = allProgress.sorted { $0.date < $1.date }
    }

    private func generateWorkoutFrequency(calendar: Calendar, today: Date) {
        var activities: [DayActivity] = []
        let workoutTypes = ["Swim", "Strength", "Bike", "Run", "Swim", "Brick", "Recovery"]

        for dayOffset in stride(from: -83, through: 0, by: 1) {
            guard let date = calendar.date(byAdding: .day, value: dayOffset, to: today) else {
                continue
            }

            let weekdayIndex = (calendar.component(.weekday, from: date) + 5) % 7
            let workoutType = workoutTypes[weekdayIndex]

            // 85% chance of actually doing the workout on any given day.
            let didWorkout = Double.random(in: 0...1) < 0.85

            if didWorkout {
                let baseDuration: Double
                switch workoutType {
                case "Swim": baseDuration = Double.random(in: 35...55)
                case "Bike": baseDuration = Double.random(in: 45...90)
                case "Run": baseDuration = Double.random(in: 30...55)
                case "Strength": baseDuration = Double.random(in: 40...60)
                case "Brick": baseDuration = Double.random(in: 50...75)
                case "Recovery": baseDuration = Double.random(in: 20...40)
                default: baseDuration = 30
                }

                let intensity = min(baseDuration / 90.0 + Double.random(in: -0.1...0.1), 1.0)

                activities.append(DayActivity(
                    date: date,
                    workoutType: workoutType,
                    durationMinutes: round(baseDuration),
                    intensity: intensity
                ))
            } else {
                activities.append(DayActivity(
                    date: date,
                    workoutType: nil,
                    durationMinutes: 0,
                    intensity: 0
                ))
            }
        }

        workoutFrequency = activities
    }

    private func generateBodyMetrics(calendar: Calendar, today: Date) {
        var weight: [MetricDataPoint] = []
        var sleep: [MetricDataPoint] = []
        var sleepQuality: [MetricDataPoint] = []
        var moodAM: [MetricDataPoint] = []
        var moodPM: [MetricDataPoint] = []
        var energy: [MetricDataPoint] = []
        var focus: [MetricDataPoint] = []

        // Weight: gradual decline from ~190 to ~184 over 12 weeks with daily noise.
        var currentWeight = 190.0

        for dayOffset in stride(from: -83, through: 0, by: 1) {
            guard let date = calendar.date(byAdding: .day, value: dayOffset, to: today) else {
                continue
            }

            // Weight: gentle downward trend with daily fluctuation.
            let dailyChange = Double.random(in: -0.4...0.25)
            currentWeight += dailyChange
            currentWeight = max(currentWeight, 183.0)
            currentWeight = min(currentWeight, 192.0)
            // Apply gentle downward pull toward target.
            currentWeight -= 0.05
            weight.append(MetricDataPoint(date: date, field: .weight, value: round(currentWeight * 10) / 10, source: .manual))

            // Sleep: 6-8.5 hours with weekend bonus.
            let isWeekend = calendar.isDateInWeekend(date)
            let baseSleep = isWeekend ? Double.random(in: 7.0...8.5) : Double.random(in: 6.0...7.8)
            sleep.append(MetricDataPoint(date: date, field: .sleep, value: round(baseSleep * 10) / 10, source: .manual))

            // Sleep quality: loosely correlated with duration.
            let qualityBase = (baseSleep - 5.0) * 1.8 + Double.random(in: -1.5...1.5)
            let qualityValue = min(max(round(qualityBase * 10) / 10, 1), 10)
            sleepQuality.append(MetricDataPoint(date: date, field: .sleepQuality, value: qualityValue, source: .manual))

            // Mood AM: 5-9, slightly correlated with sleep.
            let moodAMBase = (baseSleep - 5.0) * 0.8 + 3.0 + Double.random(in: -1.0...1.5)
            let moodAMValue = min(max(round(moodAMBase), 1), 10)
            moodAM.append(MetricDataPoint(date: date, field: .moodAM, value: moodAMValue, source: .manual))

            // Mood PM: similar but independent variation.
            let moodPMBase = moodAMValue + Double.random(in: -2.0...2.0)
            let moodPMValue = min(max(round(moodPMBase), 1), 10)
            moodPM.append(MetricDataPoint(date: date, field: .moodPM, value: moodPMValue, source: .manual))

            // Energy: 4-9, inversely affected by heavy workout days.
            let weekdayIndex = (calendar.component(.weekday, from: date) + 5) % 7
            let isHeavyDay = weekdayIndex == 2 || weekdayIndex == 5 // Bike or Brick days
            let energyBase = isHeavyDay
                ? Double.random(in: 4.0...7.0)
                : Double.random(in: 5.5...9.0)
            energy.append(MetricDataPoint(date: date, field: .energy, value: round(energyBase), source: .manual))

            // Focus: 5-9, slight weekly pattern (lower Friday).
            let isFriday = weekdayIndex == 4
            let focusBase = isFriday
                ? Double.random(in: 4.5...7.0)
                : Double.random(in: 5.5...9.0)
            focus.append(MetricDataPoint(date: date, field: .focus, value: round(focusBase), source: .manual))
        }

        weightData = weight
        sleepData = sleep
        sleepQualityData = sleepQuality
        moodAMData = moodAM
        moodPMData = moodPM
        energyData = energy
        focusData = focus
    }

    private func generateComplianceData(calendar: Calendar, today: Date) {
        var days: [ComplianceDay] = []
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "E"
        dateFormatter.locale = Locale(identifier: "en_US_POSIX")

        for dayOffset in stride(from: -83, through: 0, by: 1) {
            guard let date = calendar.date(byAdding: .day, value: dayOffset, to: today) else {
                continue
            }

            let dayLabel = dateFormatter.string(from: date)

            // Simulate gradually improving compliance over 12 weeks.
            let weekFactor = Double(dayOffset + 83) / 83.0
            let baseTodoRate = 0.55 + weekFactor * 0.2 + Double.random(in: -0.15...0.15)
            let baseHabitRate = 0.50 + weekFactor * 0.25 + Double.random(in: -0.15...0.15)
            let workoutDone = Double.random(in: 0...1) < (0.75 + weekFactor * 0.1)

            days.append(ComplianceDay(
                date: date,
                dayLabel: dayLabel,
                todoCompletionRate: min(max(baseTodoRate, 0), 1),
                habitCompletionRate: min(max(baseHabitRate, 0), 1),
                workoutCompleted: workoutDone
            ))
        }

        complianceDays = days
    }
}
