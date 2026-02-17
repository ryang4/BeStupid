import SwiftUI

// MARK: - WorkoutSummaryView

/// Post-workout summary screen displayed after finishing a workout.
/// Shows duration, volume, heart rate stats, exercise breakdown, and a notes field.
/// The user can save or discard the completed workout.
struct WorkoutSummaryView: View {
    let workout: WorkoutSession
    let onSave: () -> Void
    let onDiscard: () -> Void

    @State private var notes: String = ""
    @State private var isShowingDiscardConfirmation: Bool = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    headerSection
                    statsGrid
                    heartRateSection
                    exerciseBreakdownSection
                    notesSection
                    actionButtons
                }
                .padding()
            }
            .navigationTitle("Workout Complete")
            .navigationBarTitleDisplayMode(.large)
            .confirmationDialog(
                "Discard Workout?",
                isPresented: $isShowingDiscardConfirmation,
                titleVisibility: .visible
            ) {
                Button("Discard", role: .destructive, action: onDiscard)
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("This workout will not be saved. This action cannot be undone.")
            }
            .onAppear {
                notes = workout.notes ?? ""
            }
        }
    }

    // MARK: - Header

    private var headerSection: some View {
        let typeInfo = WorkoutTypeInfo.info(for: workout.workoutType)

        return VStack(spacing: 12) {
            Image(systemName: typeInfo.icon)
                .font(.system(size: 48))
                .foregroundStyle(typeInfo.color)

            Text(workout.workoutType)
                .font(.title)
                .fontWeight(.bold)

            if let durationMinutes = workout.durationMinutes {
                Text(formatDuration(minutes: durationMinutes))
                    .font(.title2)
                    .foregroundStyle(.secondary)
            }

            Text(workout.startTime, style: .date)
                .font(.subheadline)
                .foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
    }

    // MARK: - Stats Grid

    private var statsGrid: some View {
        let stats = buildStatItems()

        return LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 16) {
            ForEach(stats) { stat in
                StatCard(stat: stat)
            }
        }
    }

    // MARK: - Heart Rate Section

    @ViewBuilder
    private var heartRateSection: some View {
        if !workout.heartRateSamples.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Label("Heart Rate", systemImage: "heart.fill")
                    .font(.headline)
                    .foregroundStyle(.red)

                HStack(spacing: 24) {
                    if let avg = workout.averageHeartRate {
                        VStack(spacing: 4) {
                            Text("\(avg)")
                                .font(.system(size: 28, weight: .bold, design: .rounded))
                            Text("Avg BPM")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }

                    if let max = workout.maxHeartRate {
                        VStack(spacing: 4) {
                            Text("\(max)")
                                .font(.system(size: 28, weight: .bold, design: .rounded))
                                .foregroundStyle(.red)
                            Text("Max BPM")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }

                    VStack(spacing: 4) {
                        Text("\(workout.heartRateSamples.count)")
                            .font(.system(size: 28, weight: .bold, design: .rounded))
                            .foregroundStyle(.secondary)
                        Text("Samples")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                .frame(maxWidth: .infinity)
            }
            .padding()
            .background(Color.red.opacity(0.06), in: RoundedRectangle(cornerRadius: 16))
        }
    }

    // MARK: - Exercise Breakdown

    @ViewBuilder
    private var exerciseBreakdownSection: some View {
        if !workout.exercises.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Label("Exercises", systemImage: "list.bullet")
                    .font(.headline)

                ForEach(workout.uniqueExerciseNames, id: \.self) { name in
                    let sets = workout.exercises.filter { $0.exerciseName == name }
                    ExerciseBreakdownRow(exerciseName: name, sets: sets)
                }
            }
            .padding()
            .background(Color.secondary.opacity(0.06), in: RoundedRectangle(cornerRadius: 16))
        }
    }

    // MARK: - Notes

    private var notesSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Notes", systemImage: "note.text")
                .font(.headline)

            TextField("How did it feel? Any PRs?", text: $notes, axis: .vertical)
                .lineLimit(3...6)
                .textFieldStyle(.roundedBorder)
        }
    }

    // MARK: - Action Buttons

    private var actionButtons: some View {
        VStack(spacing: 12) {
            Button {
                onSave()
            } label: {
                Label("Save to Log", systemImage: "checkmark.circle.fill")
                    .font(.headline)
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
                    .background(Color.accentColor, in: RoundedRectangle(cornerRadius: 14))
            }
            .buttonStyle(.plain)
            .sensoryFeedback(.success, trigger: false)

            Button {
                isShowingDiscardConfirmation = true
            } label: {
                Text("Discard")
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundStyle(.red)
            }
            .buttonStyle(.plain)
            .padding(.vertical, 8)
        }
    }

    // MARK: - Helpers

    private func buildStatItems() -> [StatItem] {
        var items: [StatItem] = []

        // Duration
        if let minutes = workout.durationMinutes {
            items.append(StatItem(
                title: "Duration",
                value: formatDuration(minutes: minutes),
                icon: "clock",
                color: .accentColor
            ))
        }

        // Total Sets
        if !workout.exercises.isEmpty {
            items.append(StatItem(
                title: "Total Sets",
                value: "\(workout.exercises.count)",
                icon: "number",
                color: .purple
            ))
        }

        // Total Volume
        let volume = workout.exercises.compactMap(\.volume).reduce(0, +)
        if volume > 0 {
            items.append(StatItem(
                title: "Volume",
                value: formatVolume(volume),
                icon: "scalemass",
                color: .orange
            ))
        }

        // Distance
        if let distance = workout.totalDistance, let unit = workout.distanceUnit {
            items.append(StatItem(
                title: "Distance",
                value: String(format: "%.1f %@", distance, unit.rawValue),
                icon: "point.topleft.down.to.point.bottomright.curvepath",
                color: .green
            ))
        }

        // Exercises count
        let uniqueCount = workout.uniqueExerciseNames.count
        if uniqueCount > 0 {
            items.append(StatItem(
                title: "Exercises",
                value: "\(uniqueCount)",
                icon: "figure.strengthtraining.traditional",
                color: .teal
            ))
        }

        return items
    }

    private func formatDuration(minutes: Double) -> String {
        let hours = Int(minutes) / 60
        let mins = Int(minutes) % 60
        if hours > 0 {
            return "\(hours)h \(mins)m"
        }
        return "\(mins) min"
    }

    private func formatVolume(_ volume: Double) -> String {
        if volume >= 1000 {
            return String(format: "%.1fk lbs", volume / 1000.0)
        }
        return String(format: "%.0f lbs", volume)
    }
}

// MARK: - StatItem

private struct StatItem: Identifiable {
    let id = UUID()
    let title: String
    let value: String
    let icon: String
    let color: Color
}

// MARK: - StatCard

private struct StatCard: View {
    let stat: StatItem

    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: stat.icon)
                .font(.title3)
                .foregroundStyle(stat.color)

            Text(stat.value)
                .font(.title3)
                .fontWeight(.bold)

            Text(stat.title)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 16)
        .background(stat.color.opacity(0.08), in: RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - ExerciseBreakdownRow

private struct ExerciseBreakdownRow: View {
    let exerciseName: String
    let sets: [ExerciseSet]

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(exerciseName)
                .font(.subheadline)
                .fontWeight(.semibold)

            HStack(spacing: 12) {
                ForEach(sets) { exerciseSet in
                    setLabel(for: exerciseSet)
                }
            }
        }
        .padding(.vertical, 4)
    }

    @ViewBuilder
    private func setLabel(for exerciseSet: ExerciseSet) -> some View {
        if let reps = exerciseSet.reps, let weight = exerciseSet.weightLbs {
            Text("\(reps) x \(weight, specifier: "%.0f")")
                .font(.caption)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color.secondary.opacity(0.1), in: Capsule())
        } else if let reps = exerciseSet.reps {
            Text("\(reps) reps")
                .font(.caption)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color.secondary.opacity(0.1), in: Capsule())
        } else if let duration = exerciseSet.durationSeconds {
            Text("\(Int(duration))s")
                .font(.caption)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color.secondary.opacity(0.1), in: Capsule())
        }
    }
}

// MARK: - Previews

#Preview("Summary - Strength") {
    let workout = WorkoutSession(
        workoutType: "Strength",
        startTime: Date().addingTimeInterval(-3600),
        endTime: Date(),
        isActive: false,
        exercises: [
            ExerciseSet(exerciseName: "Bench Press", setNumber: 1, reps: 10, weightLbs: 155),
            ExerciseSet(exerciseName: "Bench Press", setNumber: 2, reps: 8, weightLbs: 165),
            ExerciseSet(exerciseName: "Bench Press", setNumber: 3, reps: 6, weightLbs: 175),
            ExerciseSet(exerciseName: "Pull-ups", setNumber: 1, reps: 10, weightLbs: 0),
            ExerciseSet(exerciseName: "Pull-ups", setNumber: 2, reps: 8, weightLbs: 0),
            ExerciseSet(exerciseName: "Pull-ups", setNumber: 3, reps: 6, weightLbs: 0),
            ExerciseSet(exerciseName: "Squat", setNumber: 1, reps: 8, weightLbs: 225),
            ExerciseSet(exerciseName: "Squat", setNumber: 2, reps: 8, weightLbs: 225),
            ExerciseSet(exerciseName: "Squat", setNumber: 3, reps: 6, weightLbs: 245),
        ],
        heartRateSamples: [
            HeartRateSample(bpm: 85),
            HeartRateSample(bpm: 130),
            HeartRateSample(bpm: 145),
            HeartRateSample(bpm: 120),
            HeartRateSample(bpm: 155),
        ]
    )

    WorkoutSummaryView(
        workout: workout,
        onSave: {},
        onDiscard: {}
    )
}

#Preview("Summary - Cardio") {
    let workout = WorkoutSession(
        workoutType: "Run",
        startTime: Date().addingTimeInterval(-2400),
        endTime: Date(),
        isActive: false,
        totalDistance: 5.2,
        distanceUnit: .kilometers,
        heartRateSamples: [
            HeartRateSample(bpm: 135),
            HeartRateSample(bpm: 148),
            HeartRateSample(bpm: 152),
            HeartRateSample(bpm: 156),
            HeartRateSample(bpm: 142),
        ]
    )

    WorkoutSummaryView(
        workout: workout,
        onSave: {},
        onDiscard: {}
    )
}

#Preview("Summary - Minimal") {
    let workout = WorkoutSession(
        workoutType: "Recovery",
        startTime: Date().addingTimeInterval(-1800),
        endTime: Date(),
        isActive: false
    )

    WorkoutSummaryView(
        workout: workout,
        onSave: {},
        onDiscard: {}
    )
}
