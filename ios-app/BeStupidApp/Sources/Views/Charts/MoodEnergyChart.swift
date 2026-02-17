import SwiftUI
import Charts

// MARK: - MoodEnergyChart

/// Multi-line chart for mood (AM/PM), energy, and focus on a 1-10 scale.
/// Each metric line is independently toggleable. Weekend days are shaded.
struct MoodEnergyChart: View {
    let moodAMData: [MetricDataPoint]
    let moodPMData: [MetricDataPoint]
    let energyData: [MetricDataPoint]
    let focusData: [MetricDataPoint]

    @State private var showMoodAM: Bool = true
    @State private var showMoodPM: Bool = true
    @State private var showEnergy: Bool = true
    @State private var showFocus: Bool = true
    @State private var selectedDate: Date?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            metricToggles
            chart
            selectedDetail
            averagesGrid
        }
    }

    // MARK: - Metric Toggles

    private var metricToggles: some View {
        HStack(spacing: 12) {
            metricToggleButton(label: "Mood AM", color: MetricLineStyle.moodAM.color, isOn: $showMoodAM)
            metricToggleButton(label: "Mood PM", color: MetricLineStyle.moodPM.color, isOn: $showMoodPM)
            metricToggleButton(label: "Energy", color: MetricLineStyle.energy.color, isOn: $showEnergy)
            metricToggleButton(label: "Focus", color: MetricLineStyle.focus.color, isOn: $showFocus)
        }
    }

    private func metricToggleButton(label: String, color: Color, isOn: Binding<Bool>) -> some View {
        Button {
            withAnimation(.easeInOut(duration: 0.25)) {
                isOn.wrappedValue.toggle()
            }
        } label: {
            HStack(spacing: 4) {
                Circle()
                    .fill(isOn.wrappedValue ? color : color.opacity(0.2))
                    .frame(width: 8, height: 8)
                Text(label)
                    .font(.caption2.weight(.medium))
                    .foregroundStyle(isOn.wrappedValue ? .primary : .tertiary)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(
                Capsule()
                    .fill(isOn.wrappedValue ? color.opacity(0.1) : Color(.systemGray6))
            )
        }
        .buttonStyle(.plain)
    }

    // MARK: - Chart

    private var chart: some View {
        Chart {
            // Weekend shading.
            ForEach(weekendRanges, id: \.start) { range in
                RectangleMark(
                    xStart: .value("Start", range.start, unit: .day),
                    xEnd: .value("End", range.end, unit: .day),
                    yStart: .value("Bottom", 0),
                    yEnd: .value("Top", 10)
                )
                .foregroundStyle(Color.gray.opacity(0.06))
            }

            // Mood AM line.
            if showMoodAM {
                ForEach(moodAMData) { point in
                    LineMark(
                        x: .value("Date", point.date, unit: .day),
                        y: .value("Score", point.value),
                        series: .value("Metric", "Mood AM")
                    )
                    .foregroundStyle(MetricLineStyle.moodAM.color)
                    .lineStyle(StrokeStyle(lineWidth: 2))
                    .interpolationMethod(.catmullRom)
                    .symbol {
                        Circle()
                            .fill(MetricLineStyle.moodAM.color)
                            .frame(width: 5, height: 5)
                    }
                }
            }

            // Mood PM line.
            if showMoodPM {
                ForEach(moodPMData) { point in
                    LineMark(
                        x: .value("Date", point.date, unit: .day),
                        y: .value("Score", point.value),
                        series: .value("Metric", "Mood PM")
                    )
                    .foregroundStyle(MetricLineStyle.moodPM.color)
                    .lineStyle(StrokeStyle(lineWidth: 2, dash: [5, 3]))
                    .interpolationMethod(.catmullRom)
                    .symbol {
                        Circle()
                            .strokeBorder(MetricLineStyle.moodPM.color, lineWidth: 1.5)
                            .frame(width: 5, height: 5)
                    }
                }
            }

            // Energy line.
            if showEnergy {
                ForEach(energyData) { point in
                    LineMark(
                        x: .value("Date", point.date, unit: .day),
                        y: .value("Score", point.value),
                        series: .value("Metric", "Energy")
                    )
                    .foregroundStyle(MetricLineStyle.energy.color)
                    .lineStyle(StrokeStyle(lineWidth: 2))
                    .interpolationMethod(.catmullRom)
                    .symbol {
                        RoundedRectangle(cornerRadius: 1)
                            .fill(MetricLineStyle.energy.color)
                            .frame(width: 5, height: 5)
                    }
                }
            }

            // Focus line.
            if showFocus {
                ForEach(focusData) { point in
                    LineMark(
                        x: .value("Date", point.date, unit: .day),
                        y: .value("Score", point.value),
                        series: .value("Metric", "Focus")
                    )
                    .foregroundStyle(MetricLineStyle.focus.color)
                    .lineStyle(StrokeStyle(lineWidth: 2))
                    .interpolationMethod(.catmullRom)
                    .symbol {
                        Diamond()
                            .fill(MetricLineStyle.focus.color)
                            .frame(width: 6, height: 6)
                    }
                }
            }

            // Selection rule.
            if let date = selectedDate {
                RuleMark(x: .value("Date", date, unit: .day))
                    .foregroundStyle(.gray.opacity(0.3))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 3]))
            }
        }
        .chartYScale(domain: 0...10)
        .chartYAxisLabel("Score (1-10)")
        .chartYAxis {
            AxisMarks(position: .leading, values: .stride(by: 2)) { value in
                AxisGridLine()
                AxisValueLabel {
                    if let intValue = value.as(Int.self) {
                        Text("\(intValue)")
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
                                withAnimation(.easeInOut(duration: 0.15)) {
                                    selectedDate = closestDate(to: date)
                                }
                            }
                            .onEnded { _ in
                                withAnimation(.easeInOut(duration: 0.2)) {
                                    selectedDate = nil
                                }
                            }
                    )
            }
        }
        .frame(height: 250)
    }

    // MARK: - Selected Detail

    @ViewBuilder
    private var selectedDetail: some View {
        if let date = selectedDate {
            let calendar = Calendar.current
            let mAM = moodAMData.first(where: { calendar.isDate($0.date, inSameDayAs: date) })
            let mPM = moodPMData.first(where: { calendar.isDate($0.date, inSameDayAs: date) })
            let en = energyData.first(where: { calendar.isDate($0.date, inSameDayAs: date) })
            let fo = focusData.first(where: { calendar.isDate($0.date, inSameDayAs: date) })

            VStack(alignment: .leading, spacing: 4) {
                Text(date.formatted(date: .abbreviated, time: .omitted))
                    .font(.caption.bold())

                HStack(spacing: 16) {
                    if let mAM, showMoodAM {
                        detailChip(label: "Mood AM", value: String(format: "%.0f", mAM.value), color: MetricLineStyle.moodAM.color)
                    }
                    if let mPM, showMoodPM {
                        detailChip(label: "Mood PM", value: String(format: "%.0f", mPM.value), color: MetricLineStyle.moodPM.color)
                    }
                    if let en, showEnergy {
                        detailChip(label: "Energy", value: String(format: "%.0f", en.value), color: MetricLineStyle.energy.color)
                    }
                    if let fo, showFocus {
                        detailChip(label: "Focus", value: String(format: "%.0f", fo.value), color: MetricLineStyle.focus.color)
                    }
                }
            }
            .padding(8)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(Color(.systemGray6))
            )
            .transition(.opacity)
        }
    }

    private func detailChip(label: String, value: String, color: Color) -> some View {
        VStack(spacing: 1) {
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.caption.bold())
                .foregroundStyle(color)
        }
    }

    // MARK: - Averages Grid

    private var averagesGrid: some View {
        HStack(spacing: 0) {
            if showMoodAM {
                averageItem(label: "Mood AM", data: moodAMData, color: MetricLineStyle.moodAM.color)
            }
            if showMoodPM {
                if showMoodAM { Divider().frame(height: 28) }
                averageItem(label: "Mood PM", data: moodPMData, color: MetricLineStyle.moodPM.color)
            }
            if showEnergy {
                if showMoodAM || showMoodPM { Divider().frame(height: 28) }
                averageItem(label: "Energy", data: energyData, color: MetricLineStyle.energy.color)
            }
            if showFocus {
                if showMoodAM || showMoodPM || showEnergy { Divider().frame(height: 28) }
                averageItem(label: "Focus", data: focusData, color: MetricLineStyle.focus.color)
            }
        }
    }

    private func averageItem(label: String, data: [MetricDataPoint], color: Color) -> some View {
        let avg = data.isEmpty ? nil : data.reduce(0.0) { $0 + $1.value } / Double(data.count)
        return VStack(spacing: 2) {
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text(avg.map { String(format: "%.1f", $0) } ?? "--")
                .font(.caption.bold())
                .foregroundStyle(color)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Helpers

    private var xAxisStride: Int {
        let maxCount = [moodAMData.count, moodPMData.count, energyData.count, focusData.count].max() ?? 0
        if maxCount <= 14 { return 2 }
        if maxCount <= 28 { return 4 }
        if maxCount <= 56 { return 7 }
        return 14
    }

    /// Computes date ranges for weekend shading (Saturday-Sunday pairs).
    private var weekendRanges: [(start: Date, end: Date)] {
        let calendar = Calendar.current
        let allDates = Set(
            (moodAMData.map(\.date) + moodPMData.map(\.date) + energyData.map(\.date) + focusData.map(\.date))
                .map { calendar.startOfDay(for: $0) }
        )
        guard let earliest = allDates.min(), let latest = allDates.max() else { return [] }

        var ranges: [(start: Date, end: Date)] = []
        var currentDate = earliest

        while currentDate <= latest {
            let weekday = calendar.component(.weekday, from: currentDate)
            if weekday == 7 { // Saturday
                let sunday = calendar.date(byAdding: .day, value: 1, to: currentDate) ?? currentDate
                ranges.append((start: currentDate, end: sunday))
            }
            currentDate = calendar.date(byAdding: .day, value: 1, to: currentDate) ?? latest.addingTimeInterval(86400)
        }

        return ranges
    }

    private func closestDate(to date: Date) -> Date? {
        let allDates = moodAMData.map(\.date) + moodPMData.map(\.date) + energyData.map(\.date) + focusData.map(\.date)
        return allDates.min(by: { abs($0.timeIntervalSince(date)) < abs($1.timeIntervalSince(date)) })
    }
}

// MARK: - MetricLineStyle

/// Style configuration for each metric line in the mood/energy chart.
private enum MetricLineStyle {
    case moodAM
    case moodPM
    case energy
    case focus

    var color: Color {
        switch self {
        case .moodAM: return .orange
        case .moodPM: return .pink
        case .energy: return .green
        case .focus: return .blue
        }
    }
}

// MARK: - Preview

#Preview("Mood Energy Focus - 4 Weeks") {
    let calendar = Calendar.current
    let today = calendar.startOfDay(for: Date())

    func sampleData(field: MetricField, baseRange: ClosedRange<Double>) -> [MetricDataPoint] {
        (0..<28).map { dayOffset in
            let date = calendar.date(byAdding: .day, value: -(27 - dayOffset), to: today)!
            let value = Double.random(in: baseRange)
            return MetricDataPoint(date: date, field: field, value: round(value), source: .manual)
        }
    }

    return MoodEnergyChart(
        moodAMData: sampleData(field: .moodAM, baseRange: 5...9),
        moodPMData: sampleData(field: .moodPM, baseRange: 4...8),
        energyData: sampleData(field: .energy, baseRange: 4...9),
        focusData: sampleData(field: .focus, baseRange: 5...9)
    )
    .padding()
}

#Preview("Mood Energy Focus - Sparse Data") {
    let calendar = Calendar.current
    let today = calendar.startOfDay(for: Date())

    let moodAMPoints: [MetricDataPoint] = stride(from: 0, to: 14, by: 2).map { dayOffset in
        let date = calendar.date(byAdding: .day, value: -(13 - dayOffset), to: today)!
        return MetricDataPoint(date: date, field: .moodAM, value: Double.random(in: 5...8), source: .manual)
    }

    let energyPoints: [MetricDataPoint] = (0..<14).map { dayOffset in
        let date = calendar.date(byAdding: .day, value: -(13 - dayOffset), to: today)!
        return MetricDataPoint(date: date, field: .energy, value: Double.random(in: 4...9), source: .manual)
    }

    return MoodEnergyChart(
        moodAMData: moodAMPoints,
        moodPMData: [],
        energyData: energyPoints,
        focusData: []
    )
    .padding()
}
