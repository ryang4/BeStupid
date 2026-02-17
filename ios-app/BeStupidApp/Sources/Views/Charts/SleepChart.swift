import SwiftUI
import Charts

// MARK: - SleepChart

/// Dual-axis chart showing sleep duration as colored bars and sleep quality as a line overlay.
/// Bars are colored green (7+ hrs), yellow (6-7 hrs), or red (<6 hrs).
/// A 7-day average line for sleep hours is also displayed.
struct SleepChart: View {
    let sleepData: [MetricDataPoint]
    let qualityData: [MetricDataPoint]

    @State private var selectedDate: Date?
    @State private var showQuality: Bool = true

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            qualityToggle
            chart
            legend
            selectedDetail
            averagesRow
        }
    }

    // MARK: - Toggle

    private var qualityToggle: some View {
        Toggle("Show Sleep Quality", isOn: $showQuality.animation(.easeInOut))
            .font(.caption)
            .foregroundStyle(.secondary)
            .toggleStyle(.switch)
            .controlSize(.mini)
    }

    // MARK: - Chart

    private var chart: some View {
        Chart {
            // Sleep duration bars with color coding.
            ForEach(sleepData) { point in
                BarMark(
                    x: .value("Date", point.date, unit: .day),
                    y: .value("Hours", point.value)
                )
                .foregroundStyle(sleepDurationColor(hours: point.value))
                .cornerRadius(2)
            }

            // 7-day average line for sleep duration.
            ForEach(sleepMovingAverage) { point in
                LineMark(
                    x: .value("Date", point.date, unit: .day),
                    y: .value("Hours", point.value),
                    series: .value("Series", "7-Day Avg")
                )
                .foregroundStyle(Color.blue)
                .lineStyle(StrokeStyle(lineWidth: 2))
                .interpolationMethod(.catmullRom)
            }

            // Sleep quality line overlay (scaled to match Y axis).
            if showQuality {
                ForEach(qualityData) { point in
                    LineMark(
                        x: .value("Date", point.date, unit: .day),
                        y: .value("Hours", qualityToHoursScale(point.value)),
                        series: .value("Series", "Quality")
                    )
                    .foregroundStyle(Color.purple)
                    .lineStyle(StrokeStyle(lineWidth: 1.5, dash: [5, 3]))
                    .interpolationMethod(.catmullRom)
                    .symbol {
                        Diamond()
                            .fill(Color.purple)
                            .frame(width: 6, height: 6)
                    }
                }
            }

            // 7-hour and 6-hour threshold lines.
            RuleMark(y: .value("Good", 7.0))
                .foregroundStyle(Color.green.opacity(0.3))
                .lineStyle(StrokeStyle(lineWidth: 0.8, dash: [6, 4]))

            RuleMark(y: .value("Minimum", 6.0))
                .foregroundStyle(Color.red.opacity(0.3))
                .lineStyle(StrokeStyle(lineWidth: 0.8, dash: [6, 4]))

            // Selection rule.
            if let date = selectedDate {
                RuleMark(x: .value("Date", date, unit: .day))
                    .foregroundStyle(.gray.opacity(0.3))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 3]))
            }
        }
        .chartYAxisLabel("Hours")
        .chartYScale(domain: yAxisDomain)
        .chartYAxis {
            AxisMarks(position: .leading, values: .stride(by: 1)) { value in
                AxisGridLine()
                AxisValueLabel {
                    if let doubleValue = value.as(Double.self) {
                        Text(String(format: "%.0f", doubleValue))
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
                                    selectedDate = closestSleepDate(to: date)
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
        .frame(height: 220)
    }

    // MARK: - Legend

    private var legend: some View {
        HStack(spacing: 12) {
            legendItem(color: .green, label: "7+ hrs")
            legendItem(color: .yellow, label: "6-7 hrs")
            legendItem(color: .red, label: "<6 hrs")

            Spacer()

            HStack(spacing: 4) {
                RoundedRectangle(cornerRadius: 1)
                    .fill(Color.blue)
                    .frame(width: 14, height: 2.5)
                Text("Avg")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            if showQuality {
                HStack(spacing: 4) {
                    Diamond()
                        .fill(Color.purple)
                        .frame(width: 6, height: 6)
                    Text("Quality")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .font(.caption2)
    }

    private func legendItem(color: Color, label: String) -> some View {
        HStack(spacing: 3) {
            RoundedRectangle(cornerRadius: 2)
                .fill(color)
                .frame(width: 10, height: 10)
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
    }

    // MARK: - Selected Detail

    @ViewBuilder
    private var selectedDetail: some View {
        if let date = selectedDate,
           let sleepPoint = sleepData.first(where: { Calendar.current.isDate($0.date, inSameDayAs: date) }) {
            let qualityPoint = qualityData.first(where: { Calendar.current.isDate($0.date, inSameDayAs: date) })

            HStack(spacing: 20) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(sleepPoint.date.formatted(date: .abbreviated, time: .omitted))
                        .font(.caption.bold())
                    Text(String(format: "%.1f hrs", sleepPoint.value))
                        .font(.subheadline.bold())
                        .foregroundStyle(sleepDurationColor(hours: sleepPoint.value))
                }

                if let quality = qualityPoint {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Quality")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                        Text(String(format: "%.0f/10", quality.value))
                            .font(.subheadline.bold())
                            .foregroundStyle(.purple)
                    }
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

    // MARK: - Averages

    private var averagesRow: some View {
        let sleepValues = sleepData.map(\.value)
        let qualityValues = qualityData.map(\.value)
        let avgSleep = sleepValues.isEmpty ? nil : sleepValues.reduce(0, +) / Double(sleepValues.count)
        let avgQuality = qualityValues.isEmpty ? nil : qualityValues.reduce(0, +) / Double(qualityValues.count)
        let nightsOver7 = sleepValues.filter { $0 >= 7.0 }.count
        let nightsUnder6 = sleepValues.filter { $0 < 6.0 }.count

        return HStack(spacing: 0) {
            avgStatItem(label: "Avg Sleep", value: avgSleep.map { String(format: "%.1f hrs", $0) } ?? "--")
            Divider().frame(height: 28)
            avgStatItem(label: "Avg Quality", value: avgQuality.map { String(format: "%.1f/10", $0) } ?? "--")
            Divider().frame(height: 28)
            avgStatItem(label: "Nights 7+", value: "\(nightsOver7)", color: .green)
            Divider().frame(height: 28)
            avgStatItem(label: "Nights <6", value: "\(nightsUnder6)", color: nightsUnder6 > 0 ? .red : .green)
        }
    }

    private func avgStatItem(label: String, value: String, color: Color = .primary) -> some View {
        VStack(spacing: 2) {
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.caption.bold())
                .foregroundStyle(color)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Helpers

    /// Compute a 7-day moving average for sleep duration.
    private var sleepMovingAverage: [MovingAveragePoint] {
        let sorted = sleepData.sorted { $0.date < $1.date }
        guard sorted.count >= 7 else { return [] }

        return (6..<sorted.count).map { index in
            let window = sorted[(index - 6)...index]
            let avg = window.reduce(0.0) { $0 + $1.value } / 7.0
            return MovingAveragePoint(date: sorted[index].date, value: avg)
        }
    }

    private func sleepDurationColor(hours: Double) -> Color {
        if hours >= 7.0 { return .green }
        if hours >= 6.0 { return .yellow }
        return .red
    }

    /// Scale quality (1-10) to the hours axis for overlay display.
    /// Maps 10 -> ~9 hrs, 5 -> ~4.5 hrs, 1 -> ~0.9 hrs.
    private func qualityToHoursScale(_ quality: Double) -> Double {
        quality * 0.9
    }

    private var yAxisDomain: ClosedRange<Double> {
        let maxSleep = sleepData.map(\.value).max() ?? 9.0
        return 0...(max(maxSleep + 1, 10))
    }

    private var xAxisStride: Int {
        let count = sleepData.count
        if count <= 14 { return 2 }
        if count <= 28 { return 4 }
        if count <= 56 { return 7 }
        return 14
    }

    private func closestSleepDate(to date: Date) -> Date? {
        sleepData
            .min(by: { abs($0.date.timeIntervalSince(date)) < abs($1.date.timeIntervalSince(date)) })?
            .date
    }
}

// MARK: - Diamond Shape

/// Small diamond shape used as a chart symbol for sleep quality points.
struct Diamond: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let midX = rect.midX
        let midY = rect.midY
        path.move(to: CGPoint(x: midX, y: rect.minY))
        path.addLine(to: CGPoint(x: rect.maxX, y: midY))
        path.addLine(to: CGPoint(x: midX, y: rect.maxY))
        path.addLine(to: CGPoint(x: rect.minX, y: midY))
        path.closeSubpath()
        return path
    }
}

// MARK: - Preview

#Preview("Sleep Chart - 4 Weeks") {
    let calendar = Calendar.current
    let today = calendar.startOfDay(for: Date())

    let sleepPoints: [MetricDataPoint] = (0..<28).map { dayOffset in
        let date = calendar.date(byAdding: .day, value: -(27 - dayOffset), to: today)!
        let isWeekend = calendar.isDateInWeekend(date)
        let hours = isWeekend
            ? Double.random(in: 7.0...8.5)
            : Double.random(in: 5.5...7.8)
        return MetricDataPoint(date: date, field: .sleep, value: round(hours * 10) / 10, source: .manual)
    }

    let qualityPoints: [MetricDataPoint] = (0..<28).map { dayOffset in
        let date = calendar.date(byAdding: .day, value: -(27 - dayOffset), to: today)!
        let quality = Double.random(in: 4...9)
        return MetricDataPoint(date: date, field: .sleepQuality, value: round(quality), source: .manual)
    }

    return SleepChart(sleepData: sleepPoints, qualityData: qualityPoints)
        .padding()
}

#Preview("Sleep Chart - Short Period") {
    let calendar = Calendar.current
    let today = calendar.startOfDay(for: Date())

    let sleepPoints: [MetricDataPoint] = (0..<7).map { dayOffset in
        let date = calendar.date(byAdding: .day, value: -(6 - dayOffset), to: today)!
        let hours = Double.random(in: 5.5...8.0)
        return MetricDataPoint(date: date, field: .sleep, value: round(hours * 10) / 10, source: .manual)
    }

    return SleepChart(sleepData: sleepPoints, qualityData: [])
        .padding()
}
