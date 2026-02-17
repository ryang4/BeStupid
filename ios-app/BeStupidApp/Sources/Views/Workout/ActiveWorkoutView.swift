import SwiftUI

// MARK: - ActiveWorkoutView

/// The real-time workout tracking screen.
/// Displays a timer header, exercise input area (strength or cardio),
/// rest timer overlay, logged sets list, and finish/discard controls.
/// Designed with large tap targets and readable numbers for gym use.
struct ActiveWorkoutView: View {
    @Bindable var viewModel: WorkoutViewModel

    @State private var isShowingDiscardAlert: Bool = false
    @State private var isShowingFinishConfirmation: Bool = false
    @State private var cardioDistance: String = ""
    @State private var cardioDistanceUnit: DistanceUnit = .miles

    @Environment(\.dismiss) private var dismiss

    private var isCardio: Bool {
        guard let workout = viewModel.activeWorkout else { return false }
        return WorkoutTypeInfo.isCardioType(workout.workoutType)
    }

    var body: some View {
        ZStack {
            mainContent
            if viewModel.isResting {
                RestTimerOverlay(
                    restTimeRemaining: viewModel.restTimeRemaining,
                    onSkip: { viewModel.skipRest() }
                )
                .transition(.opacity)
            }
        }
        .animation(.easeInOut(duration: 0.3), value: viewModel.isResting)
        .navigationBarBackButtonHidden(true)
        .toolbar {
            ToolbarItem(placement: .topBarLeading) {
                workoutTypeLabel
            }
            ToolbarItem(placement: .topBarTrailing) {
                heartRateIndicator
            }
        }
        .alert("Discard Workout?", isPresented: $isShowingDiscardAlert) {
            Button("Discard", role: .destructive) {
                viewModel.discardWorkout()
                dismiss()
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("All logged sets will be lost. This cannot be undone.")
        }
        .sheet(isPresented: $viewModel.isShowingSummary) {
            if let completed = viewModel.completedWorkout {
                WorkoutSummaryView(
                    workout: completed,
                    onSave: {
                        viewModel.confirmSave()
                        dismiss()
                    },
                    onDiscard: {
                        viewModel.discardWorkout()
                        dismiss()
                    }
                )
                .interactiveDismissDisabled()
            }
        }
    }

    // MARK: - Main Content

    private var mainContent: some View {
        VStack(spacing: 0) {
            // Timer header
            timerHeader
                .padding(.top, 8)

            Divider()
                .padding(.vertical, 8)

            // Input area (strength or cardio)
            ScrollView {
                VStack(spacing: 20) {
                    if isCardio {
                        cardioInputArea
                    } else {
                        strengthInputArea
                    }

                    loggedSetsList
                }
                .padding(.bottom, 100) // space for bottom bar
            }

            Spacer(minLength: 0)

            // Bottom bar
            bottomBar
        }
    }

    // MARK: - Timer Header

    private var timerHeader: some View {
        VStack(spacing: 4) {
            WorkoutTimerView(
                elapsedSeconds: viewModel.elapsedSeconds,
                isActive: viewModel.isWorkoutActive
            )

            if viewModel.totalSetsLogged > 0 {
                Text("\(viewModel.totalSetsLogged) sets logged")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
    }

    // MARK: - Workout Type Label

    private var workoutTypeLabel: some View {
        let typeInfo = viewModel.activeWorkout.map {
            WorkoutTypeInfo.info(for: $0.workoutType)
        }

        return HStack(spacing: 6) {
            if let info = typeInfo {
                Image(systemName: info.icon)
                    .foregroundStyle(info.color)
                Text(info.name)
                    .fontWeight(.semibold)
            }
        }
        .font(.headline)
    }

    // MARK: - Heart Rate Indicator

    @ViewBuilder
    private var heartRateIndicator: some View {
        if let bpm = viewModel.currentHeartRate {
            let zone = HeartRateZone(bpm: bpm)
            HStack(spacing: 4) {
                Image(systemName: "heart.fill")
                    .foregroundStyle(zone.color)
                    .symbolEffect(.pulse)
                Text("\(bpm)")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .monospacedDigit()
            }
        }
    }

    // MARK: - Strength Input

    private var strengthInputArea: some View {
        VStack(spacing: 16) {
            ExerciseLogView(
                exerciseName: $viewModel.currentExerciseName,
                reps: $viewModel.currentReps,
                weight: $viewModel.currentWeight,
                lastSessionData: viewModel.lastSessionData[viewModel.currentExerciseName],
                recentExercises: viewModel.recentExercises,
                onLogSet: {
                    viewModel.addSet()
                    viewModel.startRest()
                },
                onQuickIncrement: { field in
                    viewModel.quickIncrement(field: field)
                }
            )

            // Rest timer controls
            if !viewModel.isResting {
                restTimerControls
            }
        }
    }

    // MARK: - Cardio Input

    private var cardioInputArea: some View {
        CardioTrackingView(
            distance: $cardioDistance,
            distanceUnit: $cardioDistanceUnit,
            elapsedSeconds: viewModel.elapsedSeconds,
            currentHeartRate: viewModel.currentHeartRate
        )
    }

    // MARK: - Rest Timer Controls

    private var restTimerControls: some View {
        HStack(spacing: 16) {
            Text("Rest:")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            ForEach([60, 90, 120, 180], id: \.self) { seconds in
                Button {
                    viewModel.defaultRestSeconds = seconds
                } label: {
                    Text(formatRestOption(seconds))
                        .font(.caption)
                        .fontWeight(viewModel.defaultRestSeconds == seconds ? .bold : .regular)
                        .foregroundStyle(
                            viewModel.defaultRestSeconds == seconds ? .white : .primary
                        )
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(
                            viewModel.defaultRestSeconds == seconds
                                ? Color.accentColor
                                : Color.secondary.opacity(0.15),
                            in: Capsule()
                        )
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal)
    }

    // MARK: - Logged Sets List

    @ViewBuilder
    private var loggedSetsList: some View {
        if let workout = viewModel.activeWorkout, !workout.exercises.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Text("Logged Sets")
                    .font(.headline)
                    .padding(.horizontal)

                ForEach(workout.uniqueExerciseNames, id: \.self) { name in
                    let sets = workout.exercises.filter { $0.exerciseName == name }
                    LoggedExerciseGroup(exerciseName: name, sets: sets)
                }
            }
        }
    }

    // MARK: - Bottom Bar

    private var bottomBar: some View {
        HStack(spacing: 16) {
            Button {
                isShowingDiscardAlert = true
            } label: {
                Text("Discard")
                    .font(.headline)
                    .foregroundStyle(.red)
                    .padding(.vertical, 14)
                    .padding(.horizontal, 24)
                    .background(Color.red.opacity(0.1), in: RoundedRectangle(cornerRadius: 12))
            }
            .buttonStyle(.plain)

            Button {
                Task {
                    // Update cardio distance before finishing
                    if isCardio, let distance = Double(cardioDistance) {
                        viewModel.activeWorkout?.totalDistance = distance
                        viewModel.activeWorkout?.distanceUnit = cardioDistanceUnit
                    }
                    _ = await viewModel.finishWorkout()
                }
            } label: {
                Text("Finish Workout")
                    .font(.headline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .background(Color.green, in: RoundedRectangle(cornerRadius: 12))
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal)
        .padding(.vertical, 12)
        .background(.ultraThinMaterial)
    }

    // MARK: - Helpers

    private func formatRestOption(_ seconds: Int) -> String {
        if seconds >= 60 {
            let mins = seconds / 60
            let secs = seconds % 60
            return secs > 0 ? "\(mins):\(String(format: "%02d", secs))" : "\(mins)m"
        }
        return "\(seconds)s"
    }
}

// MARK: - LoggedExerciseGroup

/// Displays all logged sets for a single exercise in the active workout.
private struct LoggedExerciseGroup: View {
    let exerciseName: String
    let sets: [ExerciseSet]

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(exerciseName)
                .font(.subheadline)
                .fontWeight(.semibold)
                .padding(.horizontal)

            ForEach(sets) { exerciseSet in
                HStack {
                    Text("Set \(exerciseSet.setNumber)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .frame(width: 50, alignment: .leading)

                    if let reps = exerciseSet.reps {
                        Text("\(reps) reps")
                            .font(.caption)
                            .fontWeight(.medium)
                    }

                    if let weight = exerciseSet.weightLbs, weight > 0 {
                        Text("@ \(weight, specifier: "%.0f") lbs")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Spacer()

                    Text(exerciseSet.completedAt, style: .time)
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                }
                .padding(.horizontal)
                .padding(.vertical, 4)
            }
        }
        .padding(.vertical, 8)
        .background(Color.secondary.opacity(0.04), in: RoundedRectangle(cornerRadius: 10))
        .padding(.horizontal)
    }
}

// MARK: - Previews

#Preview("Active - Strength") {
    let viewModel = WorkoutViewModel()

    NavigationStack {
        ActiveWorkoutView(viewModel: viewModel)
    }
    .onAppear {
        viewModel.startWorkout(type: "Strength")
        viewModel.currentExerciseName = "Bench Press"
        viewModel.currentReps = "10"
        viewModel.currentWeight = "155"
        viewModel.recentExercises = ["Bench Press", "Squat", "Deadlift", "Pull-ups"]
        viewModel.lastSessionData = [
            "Bench Press": (reps: 10, weight: 150.0),
            "Squat": (reps: 8, weight: 225.0),
        ]
    }
}

#Preview("Active - Strength with Sets") {
    let viewModel = WorkoutViewModel()

    NavigationStack {
        ActiveWorkoutView(viewModel: viewModel)
    }
    .onAppear {
        viewModel.startWorkout(type: "Strength")
        // Simulate some logged sets
        viewModel.currentExerciseName = "Bench Press"
        viewModel.currentReps = "10"
        viewModel.currentWeight = "155"
        viewModel.addSet()
        viewModel.currentReps = "8"
        viewModel.currentWeight = "165"
        viewModel.addSet()
        viewModel.currentExerciseName = "Pull-ups"
        viewModel.currentReps = "10"
        viewModel.currentWeight = ""
        viewModel.addSet()
        // Set up for next entry
        viewModel.currentExerciseName = "Squat"
        viewModel.currentReps = ""
        viewModel.currentWeight = ""
    }
}

#Preview("Active - Cardio") {
    let viewModel = WorkoutViewModel()

    NavigationStack {
        ActiveWorkoutView(viewModel: viewModel)
    }
    .onAppear {
        viewModel.startWorkout(type: "Run")
        viewModel.currentHeartRate = 148
    }
}

#Preview("Active - Resting") {
    let viewModel = WorkoutViewModel()

    NavigationStack {
        ActiveWorkoutView(viewModel: viewModel)
    }
    .onAppear {
        viewModel.startWorkout(type: "Strength")
        viewModel.currentExerciseName = "Bench Press"
        viewModel.currentReps = "10"
        viewModel.currentWeight = "155"
        viewModel.addSet()
        viewModel.restTimeRemaining = 47
    }
}
