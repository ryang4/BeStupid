import SwiftUI

/// A horizontal 7-day overview showing the training week at a glance.
///
/// Each day is displayed as a circle with:
/// - Day letter above ("M", "T", "W", etc.)
/// - Colored circle: green if workout completed, blue for today, gray if future
/// - Small workout type icon inside the circle
/// - Completion dot indicator below
struct WeekAtAGlanceView: View {
    let days: [DaySummary]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("This Week")
                .font(.headline)

            HStack(spacing: 0) {
                ForEach(days) { day in
                    DayCircleView(day: day, isToday: Calendar.current.isDateInToday(day.date))
                        .frame(maxWidth: .infinity)
                }
            }
        }
        .padding(16)
        .background(.background, in: RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .strokeBorder(Color.primary.opacity(0.08), lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.03), radius: 6, x: 0, y: 2)
    }
}

// MARK: - DayCircleView

/// Individual day circle within the week overview.
private struct DayCircleView: View {
    let day: DaySummary
    let isToday: Bool

    private var circleColor: Color {
        if isToday {
            return .blue
        } else if day.workoutCompleted {
            return .green
        } else if day.hasLog {
            return .orange.opacity(0.7)
        } else {
            return Color(.systemGray4)
        }
    }

    private var iconName: String {
        guard let type = day.workoutType?.lowercased() else { return "" }
        switch type {
        case "swim": return "figure.pool.swim"
        case "bike", "cycle": return "figure.outdoor.cycle"
        case "run": return "figure.run"
        case "strength": return "figure.strengthtraining.traditional"
        case "brick": return "figure.run.circle"
        case "recovery", "rest": return "figure.mind.and.body"
        default: return "figure.mixed.cardio"
        }
    }

    var body: some View {
        VStack(spacing: 6) {
            // Day letter
            Text(day.dayLetter)
                .font(.caption2)
                .fontWeight(isToday ? .bold : .medium)
                .foregroundStyle(isToday ? .primary : .secondary)

            // Circle with icon
            ZStack {
                Circle()
                    .fill(circleColor.opacity(isToday ? 1.0 : 0.8))
                    .frame(width: 36, height: 36)

                if isToday {
                    Circle()
                        .strokeBorder(.blue.opacity(0.3), lineWidth: 2)
                        .frame(width: 42, height: 42)
                }

                if !iconName.isEmpty {
                    Image(systemName: iconName)
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(.white)
                }
            }

            // Completion indicator
            completionDot
        }
    }

    @ViewBuilder
    private var completionDot: some View {
        if day.workoutCompleted {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 10))
                .foregroundStyle(.green)
        } else if isToday && day.hasLog {
            Circle()
                .fill(.blue)
                .frame(width: 6, height: 6)
        } else if day.hasLog {
            Circle()
                .fill(.orange.opacity(0.5))
                .frame(width: 6, height: 6)
        } else {
            Circle()
                .fill(Color.clear)
                .frame(width: 6, height: 6)
        }
    }
}

// MARK: - Preview

#Preview("Week Overview") {
    let calendar = Calendar.current
    let today = Date()
    let monday = DateFormatting.mondayOfWeek(for: today)
    let dayLetters = ["M", "T", "W", "T", "F", "S", "S"]
    let workoutTypes = ["Swim", "Strength", "Bike", "Run", "Swim", "Brick", "Recovery"]
    let todayIndex = (calendar.component(.weekday, from: today) + 5) % 7

    let days: [DaySummary] = (0..<7).map { offset in
        let date = calendar.date(byAdding: .day, value: offset, to: monday) ?? today
        return DaySummary(
            date: date,
            dayLetter: dayLetters[offset],
            workoutType: workoutTypes[offset],
            workoutCompleted: offset < todayIndex,
            todoCompletionRate: offset < todayIndex ? 0.8 : (offset == todayIndex ? 0.5 : 0.0),
            hasLog: offset <= todayIndex
        )
    }

    WeekAtAGlanceView(days: days)
        .padding()
}
