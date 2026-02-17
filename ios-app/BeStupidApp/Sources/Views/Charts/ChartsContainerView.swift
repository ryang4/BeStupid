import SwiftUI
import Charts

// MARK: - ChartsContainerView

struct ChartsContainerView: View {
    @State private var viewModel = ChartsViewModel()

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                chartTabPicker
                timeRangeSelector
                Divider()

                if viewModel.isLoading {
                    loadingView
                } else {
                    ScrollView {
                        LazyVStack(spacing: 24) {
                            switch viewModel.selectedChartTab {
                            case .training:
                                trainingCharts
                            case .body:
                                bodyCharts
                            case .compliance:
                                complianceCharts
                            }
                        }
                        .padding(.horizontal)
                        .padding(.top, 16)
                        .padding(.bottom, 32)
                    }
                }
            }
            .navigationTitle("Charts")
            .task {
                await viewModel.loadChartData()
            }
        }
    }

    // MARK: - Tab Picker

    private var chartTabPicker: some View {
        Picker("Chart Type", selection: $viewModel.selectedChartTab) {
            ForEach(ChartTab.allCases, id: \.self) { tab in
                Text(tab.rawValue).tag(tab)
            }
        }
        .pickerStyle(.segmented)
        .padding(.horizontal)
        .padding(.top, 8)
    }

    // MARK: - Time Range Selector

    private var timeRangeSelector: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(TimeRange.allCases, id: \.self) { range in
                    Button {
                        withAnimation(.easeInOut(duration: 0.3)) {
                            Task {
                                await viewModel.selectTimeRange(range)
                            }
                        }
                    } label: {
                        Text(range.rawValue)
                            .font(.subheadline.weight(.medium))
                            .padding(.horizontal, 14)
                            .padding(.vertical, 6)
                            .background(
                                Capsule()
                                    .fill(viewModel.selectedTimeRange == range
                                          ? Color.accentColor
                                          : Color(.systemGray5))
                            )
                            .foregroundStyle(viewModel.selectedTimeRange == range
                                             ? .white
                                             : .primary)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal)
            .padding(.vertical, 10)
        }
    }

    // MARK: - Loading

    private var loadingView: some View {
        VStack(spacing: 16) {
            Spacer()
            ProgressView()
                .controlSize(.large)
            Text("Loading chart data...")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Training Charts

    @ViewBuilder
    private var trainingCharts: some View {
        ChartSectionCard(title: "Weekly Training Volume", subtitle: "Minutes per activity type") {
            if viewModel.filteredWeeklyVolume.isEmpty {
                emptyState(message: "No training data for this period.")
            } else {
                TrainingVolumeChart(data: viewModel.filteredWeeklyVolume)
            }
        }

        ChartSectionCard(title: "Strength Progress", subtitle: selectedExerciseSubtitle) {
            if viewModel.availableExercises.isEmpty {
                emptyState(message: "No strength data recorded yet.")
            } else {
                StrengthProgressChart(
                    data: viewModel.filteredStrengthProgress,
                    selectedExercise: viewModel.selectedExercise,
                    availableExercises: viewModel.availableExercises,
                    onSelectExercise: { exercise in
                        Task { await viewModel.selectExercise(exercise) }
                    }
                )
            }
        }

        ChartSectionCard(title: "Workout Frequency", subtitle: "Daily activity heat map") {
            if viewModel.filteredWorkoutFrequency.isEmpty {
                emptyState(message: "No workout data for this period.")
            } else {
                workoutFrequencyGrid
            }
        }
    }

    private var selectedExerciseSubtitle: String {
        if let exercise = viewModel.selectedExercise {
            return "Tracking \(exercise)"
        }
        return "Select an exercise"
    }

    private var workoutFrequencyGrid: some View {
        let data = viewModel.filteredWorkoutFrequency
        return LazyVGrid(
            columns: Array(repeating: GridItem(.flexible(), spacing: 4), count: 7),
            spacing: 4
        ) {
            ForEach(data) { day in
                RoundedRectangle(cornerRadius: 3)
                    .fill(heatMapColor(for: day))
                    .frame(height: 28)
                    .overlay {
                        if day.workoutType != nil {
                            Text(workoutEmoji(for: day.workoutType))
                                .font(.caption2)
                        }
                    }
                    .help(heatMapTooltip(for: day))
            }
        }
        .padding(.vertical, 4)
    }

    private func heatMapColor(for day: DayActivity) -> Color {
        guard day.workoutType != nil else {
            return Color(.systemGray6)
        }
        let intensity = day.intensity
        if intensity < 0.3 {
            return Color.green.opacity(0.3)
        } else if intensity < 0.6 {
            return Color.green.opacity(0.55)
        } else {
            return Color.green.opacity(0.85)
        }
    }

    private func workoutEmoji(for type: String?) -> String {
        guard let type else { return "" }
        switch type {
        case "Swim": return "S"
        case "Bike": return "B"
        case "Run": return "R"
        case "Strength": return "W"
        case "Brick": return "Bk"
        case "Recovery": return "Rc"
        default: return "?"
        }
    }

    private func heatMapTooltip(for day: DayActivity) -> String {
        let dateStr = day.date.formatted(date: .abbreviated, time: .omitted)
        guard let type = day.workoutType else {
            return "\(dateStr): Rest day"
        }
        return "\(dateStr): \(type) - \(Int(day.durationMinutes)) min"
    }

    // MARK: - Body Charts

    @ViewBuilder
    private var bodyCharts: some View {
        ChartSectionCard(title: "Weight Trend", subtitle: "Daily weigh-ins with 7-day average") {
            if viewModel.filteredWeightData.isEmpty {
                emptyState(message: "No weight data for this period.")
            } else {
                BodyMetricsChart(
                    weightData: viewModel.filteredWeightData,
                    movingAverage: viewModel.weightMovingAverage,
                    targetWeight: 180.0
                )
            }
        }

        ChartSectionCard(title: "Sleep", subtitle: sleepSubtitle) {
            if viewModel.filteredSleepData.isEmpty {
                emptyState(message: "No sleep data for this period.")
            } else {
                SleepChart(
                    sleepData: viewModel.filteredSleepData,
                    qualityData: viewModel.filteredSleepQualityData
                )
            }
        }

        ChartSectionCard(title: "Mood, Energy & Focus", subtitle: "Daily subjective metrics (1-10)") {
            let hasData = !viewModel.filteredMoodAMData.isEmpty
                || !viewModel.filteredEnergyData.isEmpty
                || !viewModel.filteredFocusData.isEmpty
            if !hasData {
                emptyState(message: "No mood/energy data for this period.")
            } else {
                MoodEnergyChart(
                    moodAMData: viewModel.filteredMoodAMData,
                    moodPMData: viewModel.filteredMoodPMData,
                    energyData: viewModel.filteredEnergyData,
                    focusData: viewModel.filteredFocusData
                )
            }
        }
    }

    private var sleepSubtitle: String {
        if let avg = viewModel.sleepAverage {
            return String(format: "Average: %.1f hrs", avg)
        }
        return "Hours & quality"
    }

    // MARK: - Compliance Charts

    @ViewBuilder
    private var complianceCharts: some View {
        ChartSectionCard(title: "Todo Completion", subtitle: "Daily completion rate") {
            if viewModel.filteredComplianceDays.isEmpty {
                emptyState(message: "No compliance data for this period.")
            } else {
                complianceTodoChart
            }
        }

        ChartSectionCard(title: "Habit Completion", subtitle: "Daily habit streak") {
            if viewModel.filteredComplianceDays.isEmpty {
                emptyState(message: "No habit data for this period.")
            } else {
                complianceHabitChart
            }
        }

        ChartSectionCard(title: "Workout Compliance", subtitle: "Did you show up?") {
            if viewModel.filteredComplianceDays.isEmpty {
                emptyState(message: "No workout compliance data for this period.")
            } else {
                complianceWorkoutChart
            }
        }
    }

    private var complianceTodoChart: some View {
        let data = viewModel.filteredComplianceDays
        return Chart(data) { day in
            BarMark(
                x: .value("Date", day.date, unit: .day),
                y: .value("Completion", day.todoCompletionRate * 100)
            )
            .foregroundStyle(
                day.todoCompletionRate >= 0.8
                    ? Color.green
                    : day.todoCompletionRate >= 0.5
                        ? Color.yellow
                        : Color.red
            )
            .cornerRadius(2)
        }
        .chartYAxis {
            AxisMarks(values: [0, 25, 50, 75, 100]) { value in
                AxisGridLine()
                AxisValueLabel {
                    if let intValue = value.as(Int.self) {
                        Text("\(intValue)%")
                            .font(.caption2)
                    }
                }
            }
        }
        .chartXAxis {
            AxisMarks(values: .stride(by: .day, count: xAxisStride)) { _ in
                AxisGridLine()
                AxisValueLabel(format: .dateTime.month(.abbreviated).day(), centered: true)
            }
        }
        .chartYScale(domain: 0...100)
        .frame(height: 200)
    }

    private var complianceHabitChart: some View {
        let data = viewModel.filteredComplianceDays
        return Chart(data) { day in
            BarMark(
                x: .value("Date", day.date, unit: .day),
                y: .value("Completion", day.habitCompletionRate * 100)
            )
            .foregroundStyle(
                day.habitCompletionRate >= 0.8
                    ? Color.blue
                    : day.habitCompletionRate >= 0.5
                        ? Color.cyan
                        : Color.gray
            )
            .cornerRadius(2)
        }
        .chartYAxis {
            AxisMarks(values: [0, 25, 50, 75, 100]) { value in
                AxisGridLine()
                AxisValueLabel {
                    if let intValue = value.as(Int.self) {
                        Text("\(intValue)%")
                            .font(.caption2)
                    }
                }
            }
        }
        .chartXAxis {
            AxisMarks(values: .stride(by: .day, count: xAxisStride)) { _ in
                AxisGridLine()
                AxisValueLabel(format: .dateTime.month(.abbreviated).day(), centered: true)
            }
        }
        .chartYScale(domain: 0...100)
        .frame(height: 200)
    }

    private var complianceWorkoutChart: some View {
        let data = viewModel.filteredComplianceDays
        return Chart(data) { day in
            PointMark(
                x: .value("Date", day.date, unit: .day),
                y: .value("Done", day.workoutCompleted ? 1 : 0)
            )
            .foregroundStyle(day.workoutCompleted ? Color.green : Color.red.opacity(0.5))
            .symbolSize(day.workoutCompleted ? 80 : 40)
            .symbol(day.workoutCompleted ? .circle : .cross)
        }
        .chartYAxis {
            AxisMarks(values: [0, 1]) { value in
                AxisGridLine()
                AxisValueLabel {
                    if let intValue = value.as(Int.self) {
                        Text(intValue == 1 ? "Yes" : "No")
                            .font(.caption2)
                    }
                }
            }
        }
        .chartXAxis {
            AxisMarks(values: .stride(by: .day, count: xAxisStride)) { _ in
                AxisGridLine()
                AxisValueLabel(format: .dateTime.month(.abbreviated).day(), centered: true)
            }
        }
        .chartYScale(domain: -0.2...1.2)
        .frame(height: 120)
    }

    /// Stride for x-axis date labels based on the selected time range.
    private var xAxisStride: Int {
        switch viewModel.selectedTimeRange {
        case .oneWeek: return 1
        case .twoWeeks: return 2
        case .fourWeeks: return 4
        case .eightWeeks: return 7
        case .twelveWeeks: return 14
        case .all: return 14
        }
    }

    // MARK: - Empty State

    private func emptyState(message: String) -> some View {
        VStack(spacing: 8) {
            Image(systemName: "chart.bar.xaxis.ascending")
                .font(.title)
                .foregroundStyle(.tertiary)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(height: 150)
        .frame(maxWidth: .infinity)
    }
}

// MARK: - ChartSectionCard

/// Reusable card wrapper for chart sections with title and subtitle.
struct ChartSectionCard<Content: View>: View {
    let title: String
    let subtitle: String
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.headline)
                Text(subtitle)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            content()
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color(.systemBackground))
                .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
        )
    }
}

// MARK: - Preview

#Preview {
    ChartsContainerView()
}
