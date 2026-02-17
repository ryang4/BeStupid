import SwiftUI

struct ProtocolView: View {
    let trainingProtocol: WeeklyProtocol

    @State private var isRationaleExpanded: Bool = false

    private var todayDayOfWeek: String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "EEEE"
        return formatter.string(from: Date())
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                headerSection
                scheduleSection
                trainingGoalsSection
                cardioTargetsSection
                strengthTargetsSection
                rationaleSection
            }
            .padding()
        }
        .navigationTitle(trainingProtocol.title)
        .navigationBarTitleDisplayMode(.inline)
    }

    // MARK: - Header

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(trainingProtocol.phase)
                        .font(.title2.weight(.bold))
                    Text(trainingProtocol.weekNumber)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                complianceBadge
            }

            Text(trainingProtocol.focus)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.blue.opacity(0.06), in: RoundedRectangle(cornerRadius: 10))
        }
    }

    private var complianceBadge: some View {
        VStack(spacing: 2) {
            Text("\(Int(trainingProtocol.targetCompliance * 100))%")
                .font(.title3.weight(.bold).monospacedDigit())
                .foregroundStyle(.green)
            Text("Target")
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .padding(12)
        .background(Color.green.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
    }

    // MARK: - Schedule

    private var scheduleSection: some View {
        ProtocolSectionCard(title: "Weekly Schedule", icon: "calendar") {
            VStack(spacing: 0) {
                ForEach(Array(trainingProtocol.schedule.enumerated()), id: \.element.id) { index, day in
                    let isToday = day.dayOfWeek.lowercased() == todayDayOfWeek.lowercased()

                    HStack(spacing: 12) {
                        // Day indicator
                        VStack(spacing: 2) {
                            Text(String(day.dayOfWeek.prefix(3)))
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(isToday ? .white : .secondary)
                        }
                        .frame(width: 40, height: 40)
                        .background(
                            isToday ? Color.blue : Color(.tertiarySystemFill),
                            in: RoundedRectangle(cornerRadius: 8)
                        )

                        // Workout type icon
                        Image(systemName: workoutIconName(for: day.workoutType))
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundStyle(workoutColor(for: day.workoutType))
                            .frame(width: 28)

                        // Workout details
                        VStack(alignment: .leading, spacing: 2) {
                            HStack(spacing: 6) {
                                Text(day.workoutType)
                                    .font(.subheadline.weight(.semibold))
                                if isToday {
                                    Text("TODAY")
                                        .font(.caption2.weight(.bold))
                                        .foregroundStyle(.blue)
                                        .padding(.horizontal, 6)
                                        .padding(.vertical, 2)
                                        .background(.blue.opacity(0.12), in: Capsule())
                                }
                            }

                            Text(day.workout)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .lineLimit(2)
                        }

                        Spacer(minLength: 0)
                    }
                    .padding(.vertical, 10)
                    .padding(.horizontal, 12)
                    .background(
                        isToday ? Color.blue.opacity(0.04) : Color.clear,
                        in: RoundedRectangle(cornerRadius: 8)
                    )

                    if index < trainingProtocol.schedule.count - 1 {
                        Divider()
                            .padding(.leading, 52)
                    }
                }
            }
        }
    }

    // MARK: - Training Goals

    @ViewBuilder
    private var trainingGoalsSection: some View {
        if !trainingProtocol.trainingGoals.isEmpty {
            ProtocolSectionCard(title: "Training Goals", icon: "target") {
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(Array(trainingProtocol.trainingGoals.enumerated()), id: \.offset) { index, goal in
                        HStack(alignment: .top, spacing: 10) {
                            Image(systemName: "\(index + 1).circle.fill")
                                .font(.subheadline)
                                .foregroundStyle(.blue)
                            Text(goal)
                                .font(.subheadline)
                        }
                    }
                }
            }
        }
    }

    // MARK: - Cardio Targets

    @ViewBuilder
    private var cardioTargetsSection: some View {
        if !trainingProtocol.cardioTargets.isEmpty {
            ProtocolSectionCard(title: "Cardio Targets", icon: "heart.circle") {
                VStack(spacing: 10) {
                    ForEach(trainingProtocol.cardioTargets.sorted(by: { $0.key < $1.key }), id: \.key) { sport, target in
                        HStack(spacing: 12) {
                            Image(systemName: workoutIconName(for: sport))
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(workoutColor(for: sport))
                                .frame(width: 28, height: 28)
                                .background(workoutColor(for: sport).opacity(0.12), in: Circle())

                            VStack(alignment: .leading, spacing: 2) {
                                Text(sport)
                                    .font(.subheadline.weight(.semibold))
                                Text(target)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }

                            Spacer()
                        }
                        .padding(10)
                        .background(Color(.tertiarySystemFill), in: RoundedRectangle(cornerRadius: 8))
                    }
                }
            }
        }
    }

    // MARK: - Strength Targets

    @ViewBuilder
    private var strengthTargetsSection: some View {
        if !trainingProtocol.strengthTargets.isEmpty {
            ProtocolSectionCard(title: "Strength Targets", icon: "dumbbell") {
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(trainingProtocol.strengthTargets, id: \.self) { target in
                        HStack(spacing: 10) {
                            Image(systemName: "checkmark.circle")
                                .font(.subheadline)
                                .foregroundStyle(.purple)
                            Text(target)
                                .font(.subheadline)
                        }
                    }
                }
            }
        }
    }

    // MARK: - AI Rationale

    @ViewBuilder
    private var rationaleSection: some View {
        if let rationale = trainingProtocol.aiRationale, !rationale.isEmpty {
            ProtocolSectionCard(title: "AI Rationale", icon: "brain.head.profile") {
                VStack(alignment: .leading, spacing: 8) {
                    Button {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            isRationaleExpanded.toggle()
                        }
                    } label: {
                        HStack {
                            Text(isRationaleExpanded ? "Hide reasoning" : "Show reasoning")
                                .font(.subheadline)
                                .foregroundStyle(.blue)
                            Spacer()
                            Image(systemName: isRationaleExpanded ? "chevron.up" : "chevron.down")
                                .font(.caption)
                                .foregroundStyle(.blue)
                        }
                    }
                    .buttonStyle(.plain)

                    if isRationaleExpanded {
                        Text(rationale)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                            .transition(.opacity.combined(with: .move(edge: .top)))
                    }
                }
            }
        }
    }

    // MARK: - Helpers

    private func workoutIconName(for type: String) -> String {
        switch type.lowercased() {
        case "swim", "swimming": return "figure.pool.swim"
        case "bike", "cycling": return "figure.outdoor.cycle"
        case "run", "running": return "figure.run"
        case "strength", "weights": return "dumbbell"
        case "brick", "mixed": return "figure.mixed.cardio"
        case "recovery", "rest": return "figure.cooldown"
        default: return "figure.walk"
        }
    }

    private func workoutColor(for type: String) -> Color {
        switch type.lowercased() {
        case "swim", "swimming": return .cyan
        case "bike", "cycling": return .green
        case "run", "running": return .orange
        case "strength", "weights": return .purple
        case "brick", "mixed": return .red
        case "recovery", "rest": return .mint
        default: return .gray
        }
    }
}

// MARK: - ProtocolSectionCard

private struct ProtocolSectionCard<Content: View>: View {
    let title: String
    let icon: String
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label(title, systemImage: icon)
                .font(.headline)

            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Preview

#Preview("Protocol View - Full") {
    NavigationStack {
        ProtocolView(
            trainingProtocol: WeeklyProtocol(
                date: DateFormatting.mondayOfWeek(for: Date()),
                title: "Base Building - Week 6",
                weekNumber: DateFormatting.weekNumber(for: Date()),
                phase: "Base Building",
                focus: "Aerobic base with maintenance strength",
                targetCompliance: 0.85,
                schedule: [
                    ProtocolDay(dayOfWeek: "Monday", workoutType: "Swim", workout: "2000m continuous Z2 swim, bilateral breathing focus"),
                    ProtocolDay(dayOfWeek: "Tuesday", workoutType: "Strength", workout: "Full body compound lifts, 3x10 moderate weight"),
                    ProtocolDay(dayOfWeek: "Wednesday", workoutType: "Bike", workout: "60 min Z2 ride, flat terrain, cadence focus 85-90 rpm"),
                    ProtocolDay(dayOfWeek: "Thursday", workoutType: "Run", workout: "40 min easy run, conversational pace, focus on form"),
                    ProtocolDay(dayOfWeek: "Friday", workoutType: "Swim", workout: "1500m drill-focused swim with pull buoy work"),
                    ProtocolDay(dayOfWeek: "Saturday", workoutType: "Brick", workout: "45 min bike + 15 min run transition practice"),
                    ProtocolDay(dayOfWeek: "Sunday", workoutType: "Recovery", workout: "30 min easy walk or yoga, full body stretching"),
                ],
                trainingGoals: [
                    "Build aerobic base to support peak phase",
                    "Maintain current strength levels",
                    "Improve swim bilateral breathing",
                ],
                cardioTargets: [
                    "Swim": "2000-2500m per session, Z2 focus",
                    "Bike": "60-90 min per session, Z2",
                    "Run": "30-45 min easy pace",
                ],
                strengthTargets: [
                    "Bench Press: 3x10 @ 155 lbs",
                    "Squat: 3x8 @ 205 lbs",
                    "Pull-ups: 3x10 bodyweight",
                ],
                aiRationale: "Week 6 of base building maintains the aerobic stimulus while keeping strength work at maintenance volume. Recovery is prioritized with one full rest day and one active recovery session. The brick workout on Saturday introduces short-duration multi-sport transitions to prepare for the upcoming build phase."
            )
        )
    }
}

#Preview("Protocol View - Minimal") {
    NavigationStack {
        ProtocolView(
            trainingProtocol: WeeklyProtocol(
                date: Date(),
                title: "Recovery Week",
                weekNumber: "W08",
                phase: "Recovery",
                focus: "Active recovery and mental reset",
                schedule: [
                    ProtocolDay(dayOfWeek: "Monday", workoutType: "Recovery", workout: "Light yoga"),
                    ProtocolDay(dayOfWeek: "Wednesday", workoutType: "Swim", workout: "Easy 1000m swim"),
                    ProtocolDay(dayOfWeek: "Friday", workoutType: "Walk", workout: "30 min walk"),
                ]
            )
        )
    }
}
