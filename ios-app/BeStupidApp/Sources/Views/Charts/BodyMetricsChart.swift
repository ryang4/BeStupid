import SwiftUI
import Charts

// MARK: - BodyMetricsChart

/// Weight trend chart with daily data points (scatter), a 7-day moving average line,
/// and an optional horizontal target weight rule.
struct BodyMetricsChart: View {
    let weightData: [MetricDataPoint]
    let movingAverage: [MovingAveragePoint]
    let targetWeight: Double?

    @State private var selectedPoint: MetricDataPoint?

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            chart
            legend
            selectedPointDetail
            summaryStats
        }
    }

    // MARK: - Chart

    private var chart: some View {
        Chart {
            // Target weight horizontal rule.
            if let target = targetWeight {
                RuleMark(y: .value("Target", target))
                    .foregroundStyle(Color.mint.opacity(0.6))
                    .lineStyle(StrokeStyle(lineWidth: 1.5, dash: [8, 4]))
                    .annotation(position: .trailing, alignment: .trailing) {
                        Text("Goal")
                            .font(.caption2)
                            .foregroundStyle(.mint)
                            .padding(.leading, 4)
                    }
            }

            // Daily weight scatter points.
            ForEach(weightData) { point in
                PointMark(
                    x: .value("Date", point.date, unit: .day),
                    y: .value("Weight", point.value)
                )
                .foregroundStyle(pointColor(for: point))
                .symbolSize(30)
                .symbol(.circle)
            }

            // 7-day moving average line.
            ForEach(movingAverage) { point in
                LineMark(
                    x: .value("Date", point.date, unit: .day),
                    y: .value("Weight", point.value)
                )
                .foregroundStyle(Color.blue)
                .lineStyle(StrokeStyle(lineWidth: 2.5))
                .interpolationMethod(.catmullRom)
            }

            // Selection vertical rule.
            if let selected = selectedPoint {
                RuleMark(x: .value("Date", selected.date, unit: .day))
                    .foregroundStyle(.gray.opacity(0.3))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 3]))
                    .annotation(position: .top, alignment: .center) {
                        VStack(spacing: 1) {
                            Text(String(format: "%.1f", selected.value))
                                .font(.caption.bold())
                            Text(selected.date.formatted(date: .abbreviated, time: .omitted))
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(
                            RoundedRectangle(cornerRadius: 6)
                                .fill(Color(.systemBackground))
                                .shadow(color: .black.opacity(0.1), radius: 4, y: 2)
                        )
                    }
            }
        }
        .chartYAxisLabel("lbs")
        .chartYScale(domain: yAxisDomain)
        .chartYAxis {
            AxisMarks(position: .leading) { value in
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
                                    selectedPoint = closestPoint(to: date)
                                }
                            }
                            .onEnded { _ in
                                withAnimation(.easeInOut(duration: 0.2)) {
                                    selectedPoint = nil
                                }
                            }
                    )
            }
        }
        .frame(height: 250)
    }

    // MARK: - Legend

    private var legend: some View {
        HStack(spacing: 16) {
            legendItem(color: .gray.opacity(0.6), label: "Daily", style: .circle)
            legendItem(color: .blue, label: "7-Day Avg", style: .line)
            if targetWeight != nil {
                legendItem(color: .mint, label: "Target", style: .dashed)
            }
        }
        .font(.caption2)
    }

    private enum LegendStyle {
        case circle, line, dashed
    }

    private func legendItem(color: Color, label: String, style: LegendStyle) -> some View {
        HStack(spacing: 4) {
            switch style {
            case .circle:
                Circle()
                    .fill(color)
                    .frame(width: 8, height: 8)
            case .line:
                RoundedRectangle(cornerRadius: 1)
                    .fill(color)
                    .frame(width: 16, height: 3)
            case .dashed:
                HStack(spacing: 2) {
                    ForEach(0..<3, id: \.self) { _ in
                        RoundedRectangle(cornerRadius: 1)
                            .fill(color)
                            .frame(width: 4, height: 2)
                    }
                }
            }
            Text(label)
                .foregroundStyle(.secondary)
        }
    }

    // MARK: - Selected Detail

    @ViewBuilder
    private var selectedPointDetail: some View {
        if let point = selectedPoint {
            let maValue = closestMovingAverage(to: point.date)
            HStack(spacing: 20) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Weigh-in")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Text(String(format: "%.1f lbs", point.value))
                        .font(.subheadline.bold())
                }
                if let ma = maValue {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("7-Day Avg")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                        Text(String(format: "%.1f lbs", ma))
                            .font(.subheadline.bold())
                            .foregroundStyle(.blue)
                    }
                }
                if let target = targetWeight {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("To Goal")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                        let diff = point.value - target
                        Text(String(format: "%+.1f lbs", diff))
                            .font(.subheadline.bold())
                            .foregroundStyle(diff <= 0 ? .green : .orange)
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

    // MARK: - Summary Stats

    private var summaryStats: some View {
        let sorted = weightData.sorted { $0.date < $1.date }
        let current = sorted.last?.value
        let starting = sorted.first?.value
        let change: Double? = {
            guard let c = current, let s = starting else { return nil }
            return c - s
        }()
        let minWeight = weightData.map(\.value).min()
        let maxWeight = weightData.map(\.value).max()

        return HStack(spacing: 0) {
            statItem(label: "Current", value: current.map { String(format: "%.1f", $0) } ?? "--")
            Divider().frame(height: 30)
            statItem(
                label: "Change",
                value: change.map { String(format: "%+.1f", $0) } ?? "--",
                color: (change ?? 0) <= 0 ? .green : .red
            )
            Divider().frame(height: 30)
            statItem(label: "Low", value: minWeight.map { String(format: "%.1f", $0) } ?? "--")
            Divider().frame(height: 30)
            statItem(label: "High", value: maxWeight.map { String(format: "%.1f", $0) } ?? "--")
        }
    }

    private func statItem(label: String, value: String, color: Color = .primary) -> some View {
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

    private var yAxisDomain: ClosedRange<Double> {
        let values = weightData.map(\.value)
        let maValues = movingAverage.map(\.value)
        var allValues = values + maValues
        if let target = targetWeight {
            allValues.append(target)
        }
        guard let minVal = allValues.min(), let maxVal = allValues.max() else {
            return 170...200
        }
        let padding = max((maxVal - minVal) * 0.15, 1.0)
        return (minVal - padding)...(maxVal + padding)
    }

    private var xAxisStride: Int {
        let dayCount = weightData.count
        if dayCount <= 14 { return 2 }
        if dayCount <= 28 { return 4 }
        if dayCount <= 56 { return 7 }
        return 14
    }

    private func closestPoint(to date: Date) -> MetricDataPoint? {
        weightData.min(by: { abs($0.date.timeIntervalSince(date)) < abs($1.date.timeIntervalSince(date)) })
    }

    private func closestMovingAverage(to date: Date) -> Double? {
        movingAverage
            .min(by: { abs($0.date.timeIntervalSince(date)) < abs($1.date.timeIntervalSince(date)) })?
            .value
    }

    private func pointColor(for point: MetricDataPoint) -> Color {
        if let target = targetWeight {
            return point.value <= target ? .green.opacity(0.6) : .gray.opacity(0.5)
        }
        return .gray.opacity(0.5)
    }
}

// MARK: - Preview

#Preview("Body Metrics - Weight Trend") {
    let calendar = Calendar.current
    let today = calendar.startOfDay(for: Date())

    var currentWeight = 189.0
    let weightPoints: [MetricDataPoint] = (0..<28).map { dayOffset in
        let date = calendar.date(byAdding: .day, value: -(27 - dayOffset), to: today)!
        currentWeight += Double.random(in: -0.5...0.3) - 0.08
        return MetricDataPoint(date: date, field: .weight, value: round(currentWeight * 10) / 10, source: .manual)
    }

    // Compute moving average.
    let sorted = weightPoints.sorted { $0.date < $1.date }
    let maPoints: [MovingAveragePoint] = (6..<sorted.count).map { index in
        let window = sorted[(index - 6)...index]
        let avg = window.reduce(0.0) { $0 + $1.value } / 7.0
        return MovingAveragePoint(date: sorted[index].date, value: avg)
    }

    return BodyMetricsChart(
        weightData: weightPoints,
        movingAverage: maPoints,
        targetWeight: 180.0
    )
    .padding()
}

#Preview("Body Metrics - No Target") {
    let calendar = Calendar.current
    let today = calendar.startOfDay(for: Date())

    var currentWeight = 186.0
    let weightPoints: [MetricDataPoint] = (0..<14).map { dayOffset in
        let date = calendar.date(byAdding: .day, value: -(13 - dayOffset), to: today)!
        currentWeight += Double.random(in: -0.4...0.3) - 0.05
        return MetricDataPoint(date: date, field: .weight, value: round(currentWeight * 10) / 10, source: .manual)
    }

    let sorted = weightPoints.sorted { $0.date < $1.date }
    let maPoints: [MovingAveragePoint] = (6..<sorted.count).map { index in
        let window = sorted[(index - 6)...index]
        let avg = window.reduce(0.0) { $0 + $1.value } / 7.0
        return MovingAveragePoint(date: sorted[index].date, value: avg)
    }

    return BodyMetricsChart(
        weightData: weightPoints,
        movingAverage: maPoints,
        targetWeight: nil
    )
    .padding()
}
