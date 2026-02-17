import SwiftUI
import Charts

// MARK: - TrainingVolumeChart

/// Stacked bar chart showing weekly training volume broken down by activity type.
/// Each bar represents one week, with segments for swim, bike, run, and strength minutes.
struct TrainingVolumeChart: View {
    let data: [WeeklyVolume]

    @State private var selectedWeek: WeeklyVolume?

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            chart
            selectedWeekDetail
        }
    }

    // MARK: - Chart

    private var chart: some View {
        Chart {
            ForEach(data) { week in
                BarMark(
                    x: .value("Week", week.weekLabel),
                    y: .value("Minutes", week.swimMinutes)
                )
                .foregroundStyle(by: .value("Type", "Swim"))

                BarMark(
                    x: .value("Week", week.weekLabel),
                    y: .value("Minutes", week.bikeMinutes)
                )
                .foregroundStyle(by: .value("Type", "Bike"))

                BarMark(
                    x: .value("Week", week.weekLabel),
                    y: .value("Minutes", week.runMinutes)
                )
                .foregroundStyle(by: .value("Type", "Run"))

                BarMark(
                    x: .value("Week", week.weekLabel),
                    y: .value("Minutes", week.strengthMinutes)
                )
                .foregroundStyle(by: .value("Type", "Strength"))
            }

            if let selected = selectedWeek {
                RuleMark(x: .value("Week", selected.weekLabel))
                    .foregroundStyle(.gray.opacity(0.3))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 4]))
                    .annotation(position: .top, alignment: .center) {
                        Text("\(Int(selected.totalMinutes)) min")
                            .font(.caption.bold())
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(Color(.systemBackground))
                                    .shadow(radius: 2)
                            )
                    }
            }
        }
        .chartForegroundStyleScale([
            "Swim": Color.blue,
            "Bike": Color.green,
            "Run": Color.orange,
            "Strength": Color.purple,
        ])
        .chartYAxisLabel("Minutes")
        .chartYAxis {
            AxisMarks(position: .leading) { value in
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
            AxisMarks { value in
                AxisValueLabel {
                    if let label = value.as(String.self) {
                        Text(label)
                            .font(.caption2)
                    }
                }
            }
        }
        .chartLegend(position: .bottom, alignment: .center, spacing: 12)
        .chartXSelection(value: $selectedWeek.animation(.easeInOut))
        .frame(height: 250)
    }

    // MARK: - Selection Detail

    @ViewBuilder
    private var selectedWeekDetail: some View {
        if let week = selectedWeek {
            HStack(spacing: 16) {
                volumeDetail(label: "Swim", minutes: week.swimMinutes, color: .blue)
                volumeDetail(label: "Bike", minutes: week.bikeMinutes, color: .green)
                volumeDetail(label: "Run", minutes: week.runMinutes, color: .orange)
                volumeDetail(label: "Str", minutes: week.strengthMinutes, color: .purple)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 4)
            .transition(.opacity.combined(with: .move(edge: .top)))
        }
    }

    private func volumeDetail(label: String, minutes: Double, color: Color) -> some View {
        VStack(spacing: 2) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text("\(Int(minutes))")
                .font(.caption.bold())
        }
    }
}

// MARK: - WeeklyVolume + Plottable for selection

extension WeeklyVolume: Plottable {
    var primitivePlottable: String { weekLabel }

    init?(primitivePlottable: String) {
        // Selection lookup is handled by the chart framework;
        // this initializer is required by protocol but not used for matching.
        return nil
    }
}

// MARK: - Preview

#Preview("Training Volume - 8 Weeks") {
    let calendar = Calendar.current
    let today = calendar.startOfDay(for: Date())

    let sampleData: [WeeklyVolume] = (0..<8).map { weekOffset in
        let weekStart = calendar.date(byAdding: .weekOfYear, value: -(7 - weekOffset), to: DateFormatting.mondayOfWeek(for: today))!
        let label = DateFormatting.weekNumber(for: weekStart)
        let progress = 1.0 + Double(weekOffset) * 0.05
        return WeeklyVolume(
            weekStart: weekStart,
            weekLabel: label,
            swimMinutes: round(40 * progress + Double.random(in: -5...5)),
            bikeMinutes: round(55 * progress + Double.random(in: -8...8)),
            runMinutes: round(35 * progress + Double.random(in: -5...5)),
            strengthMinutes: round(30 * progress + Double.random(in: -3...3))
        )
    }

    return TrainingVolumeChart(data: sampleData)
        .padding()
}
