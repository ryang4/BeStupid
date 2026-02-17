import SwiftUI
import Charts

// MARK: - StrengthProgressChart

/// Line chart showing weight and estimated 1RM progression for a selected exercise,
/// with a volume trend area chart layered behind.
struct StrengthProgressChart: View {
    let data: [StrengthProgress]
    let selectedExercise: String?
    let availableExercises: [String]
    let onSelectExercise: (String) -> Void

    @State private var selectedDataPoint: StrengthProgress?
    @State private var showVolume: Bool = true

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            exercisePicker
            chartToggle

            if data.isEmpty {
                emptyExerciseState
            } else {
                chart
                selectedPointDetail
                summaryRow
            }
        }
    }

    // MARK: - Exercise Picker

    private var exercisePicker: some View {
        Menu {
            ForEach(availableExercises, id: \.self) { exercise in
                Button {
                    onSelectExercise(exercise)
                    selectedDataPoint = nil
                } label: {
                    HStack {
                        Text(exercise)
                        if exercise == selectedExercise {
                            Image(systemName: "checkmark")
                        }
                    }
                }
            }
        } label: {
            HStack(spacing: 6) {
                Text(selectedExercise ?? "Select Exercise")
                    .font(.subheadline.weight(.medium))
                Image(systemName: "chevron.up.chevron.down")
                    .font(.caption)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(Color(.systemGray6))
            )
        }
        .buttonStyle(.plain)
    }

    // MARK: - Toggle

    private var chartToggle: some View {
        Toggle("Show Volume", isOn: $showVolume.animation(.easeInOut))
            .font(.caption)
            .foregroundStyle(.secondary)
            .toggleStyle(.switch)
            .controlSize(.mini)
    }

    // MARK: - Chart

    private var chart: some View {
        Chart {
            // Volume area (background layer).
            if showVolume {
                ForEach(data) { point in
                    AreaMark(
                        x: .value("Date", point.date, unit: .day),
                        y: .value("Volume", point.totalVolume)
                    )
                    .foregroundStyle(
                        LinearGradient(
                            colors: [Color.purple.opacity(0.2), Color.purple.opacity(0.05)],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )
                    .interpolationMethod(.catmullRom)
                }
            }

            // Max weight line.
            if isWeightedExercise {
                ForEach(data) { point in
                    LineMark(
                        x: .value("Date", point.date, unit: .day),
                        y: .value("Weight", point.maxWeight),
                        series: .value("Metric", "Max Weight")
                    )
                    .foregroundStyle(Color.blue)
                    .lineStyle(StrokeStyle(lineWidth: 2))
                    .interpolationMethod(.catmullRom)
                    .symbol {
                        Circle()
                            .fill(Color.blue)
                            .frame(width: 6, height: 6)
                    }
                }

                // Estimated 1RM line.
                ForEach(data) { point in
                    LineMark(
                        x: .value("Date", point.date, unit: .day),
                        y: .value("Weight", point.estimatedOneRepMax),
                        series: .value("Metric", "Est. 1RM")
                    )
                    .foregroundStyle(Color.red)
                    .lineStyle(StrokeStyle(lineWidth: 2, dash: [6, 3]))
                    .interpolationMethod(.catmullRom)
                }
            } else {
                // For bodyweight exercises, show total volume as the main line.
                ForEach(data) { point in
                    LineMark(
                        x: .value("Date", point.date, unit: .day),
                        y: .value("Volume", point.totalVolume),
                        series: .value("Metric", "Volume")
                    )
                    .foregroundStyle(Color.blue)
                    .lineStyle(StrokeStyle(lineWidth: 2))
                    .interpolationMethod(.catmullRom)
                    .symbol {
                        Circle()
                            .fill(Color.blue)
                            .frame(width: 6, height: 6)
                    }
                }
            }

            // Selection indicator.
            if let selected = selectedDataPoint {
                RuleMark(x: .value("Date", selected.date, unit: .day))
                    .foregroundStyle(.gray.opacity(0.4))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 3]))
            }
        }
        .chartYAxisLabel(isWeightedExercise ? "lbs" : "Volume")
        .chartYAxis {
            AxisMarks(position: .leading) { value in
                AxisGridLine()
                AxisValueLabel {
                    if let doubleValue = value.as(Double.self) {
                        Text("\(Int(doubleValue))")
                            .font(.caption2)
                    }
                }
            }
        }
        .chartXAxis {
            AxisMarks(values: .stride(by: .day, count: xAxisStrideForData)) { _ in
                AxisGridLine()
                AxisValueLabel(format: .dateTime.month(.abbreviated).day(), centered: true)
            }
        }
        .chartLegend(position: .bottom, alignment: .center, spacing: 8)
        .chartOverlay { proxy in
            GeometryReader { geometry in
                Rectangle()
                    .fill(.clear)
                    .contentShape(Rectangle())
                    .gesture(
                        DragGesture(minimumDistance: 0)
                            .onChanged { dragValue in
                                let origin = geometry[proxy.plotFrame!].origin
                                let locationX = dragValue.location.x - origin.x
                                guard let date: Date = proxy.value(atX: locationX) else { return }
                                selectedDataPoint = closestDataPoint(to: date)
                            }
                            .onEnded { _ in
                                selectedDataPoint = nil
                            }
                    )
            }
        }
        .frame(height: 250)
    }

    // MARK: - Selection Detail

    @ViewBuilder
    private var selectedPointDetail: some View {
        if let point = selectedDataPoint {
            HStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(point.date.formatted(date: .abbreviated, time: .omitted))
                        .font(.caption.bold())
                    if isWeightedExercise {
                        Text("Max: \(Int(point.maxWeight)) lbs")
                            .font(.caption)
                            .foregroundStyle(.blue)
                        Text("Est. 1RM: \(Int(point.estimatedOneRepMax)) lbs")
                            .font(.caption)
                            .foregroundStyle(.red)
                    }
                    Text("Volume: \(formatVolume(point.totalVolume))")
                        .font(.caption)
                        .foregroundStyle(.purple)
                }
                Spacer()
            }
            .padding(8)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(Color(.systemGray6))
            )
            .transition(.opacity)
        }
    }

    // MARK: - Summary

    @ViewBuilder
    private var summaryRow: some View {
        if let first = data.first, let last = data.last, isWeightedExercise {
            let weightChange = last.maxWeight - first.maxWeight
            let oneRMChange = last.estimatedOneRepMax - first.estimatedOneRepMax
            HStack(spacing: 16) {
                summaryItem(
                    label: "Weight",
                    value: "\(signPrefix(weightChange))\(Int(abs(weightChange))) lbs",
                    isPositive: weightChange >= 0
                )
                summaryItem(
                    label: "Est. 1RM",
                    value: "\(signPrefix(oneRMChange))\(Int(abs(oneRMChange))) lbs",
                    isPositive: oneRMChange >= 0
                )
                summaryItem(
                    label: "Sessions",
                    value: "\(data.count)",
                    isPositive: true
                )
            }
            .frame(maxWidth: .infinity)
        }
    }

    private func summaryItem(label: String, value: String, isPositive: Bool) -> some View {
        VStack(spacing: 2) {
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.caption.bold())
                .foregroundStyle(isPositive ? .green : .red)
        }
    }

    // MARK: - Empty State

    private var emptyExerciseState: some View {
        VStack(spacing: 8) {
            Image(systemName: "dumbbell")
                .font(.title2)
                .foregroundStyle(.tertiary)
            Text("No data for this exercise in the selected period.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(height: 200)
        .frame(maxWidth: .infinity)
    }

    // MARK: - Helpers

    private var isWeightedExercise: Bool {
        guard let point = data.first else { return true }
        return point.maxWeight > 0
    }

    private var xAxisStrideForData: Int {
        let daySpan = data.isEmpty ? 28 : max(1, Calendar.current.dateComponents([.day], from: data.first!.date, to: data.last!.date).day ?? 28)
        if daySpan <= 14 { return 2 }
        if daySpan <= 28 { return 4 }
        if daySpan <= 56 { return 7 }
        return 14
    }

    private func closestDataPoint(to date: Date) -> StrengthProgress? {
        data.min(by: { abs($0.date.timeIntervalSince(date)) < abs($1.date.timeIntervalSince(date)) })
    }

    private func formatVolume(_ volume: Double) -> String {
        if volume >= 10_000 {
            return String(format: "%.1fk", volume / 1_000)
        }
        return "\(Int(volume))"
    }

    private func signPrefix(_ value: Double) -> String {
        value >= 0 ? "+" : ""
    }
}

// MARK: - Preview

#Preview("Strength Progress - Bench Press") {
    let calendar = Calendar.current
    let today = calendar.startOfDay(for: Date())

    let sampleData: [StrengthProgress] = (0..<20).map { sessionIndex in
        let dayOffset = -(20 - sessionIndex) * 3
        let date = calendar.date(byAdding: .day, value: dayOffset, to: today)!
        let weekNum = Double(sessionIndex) / 2.0
        let weight = 135.0 + weekNum * 1.5 + Double.random(in: -2.5...2.5)
        let reps = 10 + (sessionIndex % 4 == 0 ? 1 : 0)
        return StrengthProgress(
            date: date,
            exerciseName: "Bench Press",
            maxWeight: round(weight / 2.5) * 2.5,
            totalVolume: weight * Double(reps) * 3,
            repsAtMaxWeight: reps
        )
    }

    return StrengthProgressChart(
        data: sampleData,
        selectedExercise: "Bench Press",
        availableExercises: ["Bench Press", "Squat", "Deadlift", "Overhead Press", "Pull-ups"],
        onSelectExercise: { _ in }
    )
    .padding()
}

#Preview("Strength Progress - Pull-ups (Bodyweight)") {
    let calendar = Calendar.current
    let today = calendar.startOfDay(for: Date())

    let sampleData: [StrengthProgress] = (0..<16).map { sessionIndex in
        let dayOffset = -(16 - sessionIndex) * 4
        let date = calendar.date(byAdding: .day, value: dayOffset, to: today)!
        return StrengthProgress(
            date: date,
            exerciseName: "Pull-ups",
            maxWeight: 0,
            totalVolume: Double(8 + sessionIndex / 3) * 3.0,
            repsAtMaxWeight: 8 + sessionIndex / 3
        )
    }

    return StrengthProgressChart(
        data: sampleData,
        selectedExercise: "Pull-ups",
        availableExercises: ["Bench Press", "Squat", "Deadlift", "Overhead Press", "Pull-ups"],
        onSelectExercise: { _ in }
    )
    .padding()
}
