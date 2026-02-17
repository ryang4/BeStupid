import SwiftUI

/// Prominent card showing today's scheduled workout from the weekly protocol.
///
/// Displays the workout type with an SF Symbol icon, the full workout description,
/// the current training phase, and a button to start or resume the workout.
struct TodayCardView: View {
    let workoutType: String?
    let workoutDescription: String?
    let protocolPhase: String?
    let isWorkoutActive: Bool
    let onStartWorkout: () -> Void

    private var iconName: String {
        guard let type = workoutType?.lowercased() else { return "figure.mixed.cardio" }
        switch type {
        case "swim":
            return "figure.pool.swim"
        case "bike", "cycle", "cycling":
            return "figure.outdoor.cycle"
        case "run", "running":
            return "figure.run"
        case "strength", "weights", "gym":
            return "figure.strengthtraining.traditional"
        case "brick":
            return "figure.run.circle"
        case "recovery", "rest", "yoga":
            return "figure.mind.and.body"
        default:
            return "figure.mixed.cardio"
        }
    }

    private var accentColor: Color {
        guard let type = workoutType?.lowercased() else { return .gray }
        switch type {
        case "swim":
            return .cyan
        case "bike", "cycle", "cycling":
            return .orange
        case "run", "running":
            return .green
        case "strength", "weights", "gym":
            return .purple
        case "brick":
            return .red
        case "recovery", "rest", "yoga":
            return .mint
        default:
            return .blue
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header row: icon + workout type + phase badge
            HStack(alignment: .top) {
                Image(systemName: iconName)
                    .font(.system(size: 28))
                    .foregroundStyle(accentColor)
                    .frame(width: 40, height: 40)
                    .background(accentColor.opacity(0.12), in: RoundedRectangle(cornerRadius: 10))

                VStack(alignment: .leading, spacing: 2) {
                    Text(workoutType ?? "Rest Day")
                        .font(.title3)
                        .fontWeight(.bold)

                    if let protocolPhase {
                        Text(protocolPhase)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                Spacer()

                if isWorkoutActive {
                    livePulse
                }
            }

            // Workout description
            if let workoutDescription {
                Text(workoutDescription)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .lineLimit(3)
            }

            // Action button
            if workoutType != nil {
                Button(action: onStartWorkout) {
                    HStack(spacing: 6) {
                        Image(systemName: isWorkoutActive ? "play.fill" : "play.circle")
                            .font(.subheadline)

                        Text(isWorkoutActive ? "Resume Workout" : "Start Workout")
                            .fontWeight(.semibold)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                }
                .buttonStyle(.borderedProminent)
                .tint(accentColor)
                .controlSize(.regular)
            }
        }
        .padding(16)
        .background(.background, in: RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .strokeBorder(accentColor.opacity(0.2), lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.05), radius: 8, x: 0, y: 2)
    }

    // Pulsing live indicator for active workouts
    private var livePulse: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(.red)
                .frame(width: 8, height: 8)
                .shadow(color: .red.opacity(0.5), radius: 4)

            Text("LIVE")
                .font(.caption2)
                .fontWeight(.bold)
                .foregroundStyle(.red)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(.red.opacity(0.1), in: Capsule())
    }
}

// MARK: - No Workout Card

/// Displayed when there is no workout scheduled for today.
struct NoWorkoutCardView: View {
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "figure.mind.and.body")
                .font(.system(size: 32))
                .foregroundStyle(.mint)

            Text("Recovery Day")
                .font(.title3)
                .fontWeight(.semibold)

            Text("No workout scheduled. Rest, stretch, and recharge.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(20)
        .frame(maxWidth: .infinity)
        .background(.mint.opacity(0.06), in: RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .strokeBorder(.mint.opacity(0.15), lineWidth: 1)
        )
    }
}

// MARK: - Preview

#Preview("Swim Workout") {
    TodayCardView(
        workoutType: "Swim",
        workoutDescription: "2000m continuous Z2 swim, focus on bilateral breathing. Include 4x100m pull buoy sets.",
        protocolPhase: "Base Building - W06",
        isWorkoutActive: false,
        onStartWorkout: {}
    )
    .padding()
}

#Preview("Active Strength") {
    TodayCardView(
        workoutType: "Strength",
        workoutDescription: "Full body strength - compound lifts, 3x10 moderate weight",
        protocolPhase: "Base Building - W06",
        isWorkoutActive: true,
        onStartWorkout: {}
    )
    .padding()
}

#Preview("Brick Workout") {
    TodayCardView(
        workoutType: "Brick",
        workoutDescription: "45 min bike + 15 min run transition practice",
        protocolPhase: "Build Phase - W10",
        isWorkoutActive: false,
        onStartWorkout: {}
    )
    .padding()
}

#Preview("No Workout") {
    NoWorkoutCardView()
        .padding()
}
