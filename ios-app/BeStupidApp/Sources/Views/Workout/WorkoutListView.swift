import SwiftUI

// MARK: - WorkoutListView

/// Main workout tab view. Displays an active workout banner, a workout type picker grid,
/// recent workout history, and a manual entry option for logging past workouts.
struct WorkoutListView: View {
    @Environment(AppState.self) private var appState
    @State private var viewModel = WorkoutViewModel()
    @State private var isShowingActiveWorkout: Bool = false
    @State private var isShowingManualEntry: Bool = false
    @State private var selectedWorkoutType: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    activeWorkoutBanner
                    workoutTypePicker
                    logPastWorkoutButton
                    recentWorkoutsList
                }
                .padding(.vertical)
            }
            .navigationTitle("Workout")
            .navigationDestination(isPresented: $isShowingActiveWorkout) {
                ActiveWorkoutView(viewModel: viewModel)
            }
            .sheet(isPresented: $isShowingManualEntry) {
                ManualEntrySheet(viewModel: viewModel)
            }
            .task {
                await viewModel.loadExercises()
            }
        }
    }

    // MARK: - Active Workout Banner

    @ViewBuilder
    private var activeWorkoutBanner: some View {
        if viewModel.isWorkoutActive, let workout = viewModel.activeWorkout {
            let typeInfo = WorkoutTypeInfo.info(for: workout.workoutType)

            Button {
                isShowingActiveWorkout = true
            } label: {
                HStack(spacing: 16) {
                    Image(systemName: typeInfo.icon)
                        .font(.title2)
                        .foregroundStyle(typeInfo.color)

                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(workout.workoutType) in Progress")
                            .font(.headline)
                            .foregroundStyle(.primary)

                        Text(formattedElapsed(viewModel.elapsedSeconds))
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                            .monospacedDigit()
                    }

                    Spacer()

                    Image(systemName: "chevron.right")
                        .font(.body)
                        .foregroundStyle(.secondary)
                }
                .padding()
                .background(activeWorkoutBackground(typeInfo.color))
                .padding(.horizontal)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Continue \(workout.workoutType) workout, \(formattedElapsed(viewModel.elapsedSeconds)) elapsed")
            .accessibilityAddTraits(.isButton)
        }
    }

    private func activeWorkoutBackground(_ color: Color) -> some View {
        RoundedRectangle(cornerRadius: 16)
            .fill(color.opacity(0.12))
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .strokeBorder(color.opacity(0.3), lineWidth: 1.5)
            )
    }

    // MARK: - Workout Type Picker

    private var workoutTypePicker: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Start Workout")
                .font(.title3)
                .fontWeight(.bold)
                .padding(.horizontal)

            WorkoutTypePickerView { type in
                guard !viewModel.isWorkoutActive else { return }
                viewModel.startWorkout(type: type)
                isShowingActiveWorkout = true
            }
        }
    }

    // MARK: - Log Past Workout Button

    private var logPastWorkoutButton: some View {
        Button {
            isShowingManualEntry = true
        } label: {
            HStack(spacing: 10) {
                Image(systemName: "square.and.pencil")
                    .font(.body)
                Text("Log Past Workout")
                    .font(.headline)
            }
            .foregroundStyle(.accentColor)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(Color.accentColor.opacity(0.1), in: RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(.plain)
        .padding(.horizontal)
    }

    // MARK: - Recent Workouts List

    @ViewBuilder
    private var recentWorkoutsList: some View {
        if !viewModel.recentWorkouts.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Text("Recent Workouts")
                    .font(.title3)
                    .fontWeight(.bold)
                    .padding(.horizontal)

                ForEach(viewModel.recentWorkouts) { workout in
                    RecentWorkoutRow(workout: workout)
                }
            }
        } else {
            emptyState
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: 16) {
            Image(systemName: "figure.run.circle")
                .font(.system(size: 48))
                .foregroundStyle(.secondary)

            Text("No Recent Workouts")
                .font(.headline)
                .foregroundStyle(.secondary)

            Text("Start a workout above or log a past session")
                .font(.subheadline)
                .foregroundStyle(.tertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
    }

    // MARK: - Helpers

    private func formattedElapsed(_ seconds: Int) -> String {
        let hours = seconds / 3600
        let minutes = (seconds % 3600) / 60
        let secs = seconds % 60

        if hours > 0 {
            return String(format: "%d:%02d:%02d", hours, minutes, secs)
        }
        return String(format: "%02d:%02d", minutes, secs)
    }
}

// MARK: - RecentWorkoutRow

/// A row displaying a completed workout in the recent history list.
private struct RecentWorkoutRow: View {
    let workout: WorkoutSession

    var body: some View {
        let typeInfo = WorkoutTypeInfo.info(for: workout.workoutType)

        HStack(spacing: 14) {
            // Type icon
            Image(systemName: typeInfo.icon)
                .font(.title3)
                .foregroundStyle(typeInfo.color)
                .frame(width: 40, height: 40)
                .background(typeInfo.color.opacity(0.12), in: Circle())

            // Details
            VStack(alignment: .leading, spacing: 2) {
                Text(workout.workoutType)
                    .font(.headline)

                HStack(spacing: 8) {
                    if let minutes = workout.durationMinutes {
                        Label(formatDuration(minutes), systemImage: "clock")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    if let distance = workout.totalDistance, let unit = workout.distanceUnit {
                        Label(
                            String(format: "%.1f %@", distance, unit.rawValue),
                            systemImage: "point.topleft.down.to.point.bottomright.curvepath"
                        )
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    }

                    if !workout.exercises.isEmpty {
                        Label(
                            "\(workout.exercises.count) sets",
                            systemImage: "number"
                        )
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    }
                }
            }

            Spacer()

            // Date
            VStack(alignment: .trailing, spacing: 2) {
                Text(workout.startTime, style: .date)
                    .font(.caption2)
                    .foregroundStyle(.tertiary)

                Text(workout.startTime, style: .time)
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
    }

    private func formatDuration(_ minutes: Double) -> String {
        let hours = Int(minutes) / 60
        let mins = Int(minutes) % 60
        if hours > 0 {
            return "\(hours)h \(mins)m"
        }
        return "\(mins)m"
    }
}

// MARK: - ManualEntrySheet

/// Sheet for logging a workout after the fact (from Garmin, gym log, etc.).
private struct ManualEntrySheet: View {
    @Bindable var viewModel: WorkoutViewModel
    @Environment(\.dismiss) private var dismiss

    // Local state for adding exercises
    @State private var newExerciseName: String = ""
    @State private var newExerciseSets: String = "3"
    @State private var newExerciseReps: String = "10"
    @State private var newExerciseWeight: String = ""
    @State private var isAddingExercise: Bool = false

    var body: some View {
        NavigationStack {
            Form {
                workoutTypeSection
                dateAndTimeSection
                cardioDetailsSection
                strengthSection
                notesSection
            }
            .navigationTitle("Log Past Workout")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        Task {
                            await viewModel.submitManualEntry()
                            dismiss()
                        }
                    }
                    .disabled(!viewModel.canSubmitManualEntry)
                    .fontWeight(.bold)
                }
            }
        }
        .onAppear {
            viewModel.manualEntryDate = Date()
        }
    }

    // MARK: - Workout Type Section

    private var workoutTypeSection: some View {
        Section("Workout Type") {
            LazyVGrid(
                columns: [GridItem(.adaptive(minimum: 80), spacing: 8)],
                spacing: 8
            ) {
                ForEach(WorkoutTypeInfo.builtInTypes) { typeInfo in
                    Button {
                        viewModel.manualEntryType = typeInfo.name
                    } label: {
                        VStack(spacing: 4) {
                            Image(systemName: typeInfo.icon)
                                .font(.title3)
                            Text(typeInfo.name)
                                .font(.caption)
                        }
                        .foregroundStyle(
                            viewModel.manualEntryType == typeInfo.name ? .white : typeInfo.color
                        )
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                        .background(
                            viewModel.manualEntryType == typeInfo.name
                                ? typeInfo.color
                                : typeInfo.color.opacity(0.1),
                            in: RoundedRectangle(cornerRadius: 10)
                        )
                    }
                    .buttonStyle(.plain)
                }
            }

            if viewModel.manualEntryType.isEmpty
                || !WorkoutTypeInfo.builtInTypes.contains(where: { $0.name == viewModel.manualEntryType }) {
                TextField("Or enter custom type...", text: $viewModel.manualEntryType)
                    .textInputAutocapitalization(.words)
            }
        }
    }

    // MARK: - Date & Time Section

    private var dateAndTimeSection: some View {
        Section("Date & Duration") {
            DatePicker(
                "Date",
                selection: $viewModel.manualEntryDate,
                in: ...Date(),
                displayedComponents: [.date, .hourAndMinute]
            )

            HStack {
                Text("Duration (min)")
                Spacer()
                TextField("45", text: $viewModel.manualEntryDuration)
                    .keyboardType(.numberPad)
                    .multilineTextAlignment(.trailing)
                    .frame(width: 80)
            }
        }
    }

    // MARK: - Cardio Details Section

    private var cardioDetailsSection: some View {
        Section("Cardio Details") {
            HStack {
                Text("Distance")
                Spacer()
                TextField("0.0", text: $viewModel.manualEntryDistance)
                    .keyboardType(.decimalPad)
                    .multilineTextAlignment(.trailing)
                    .frame(width: 80)

                Picker("Unit", selection: $viewModel.manualEntryDistanceUnit) {
                    ForEach(DistanceUnit.allCases, id: \.self) { unit in
                        Text(unit.rawValue).tag(unit)
                    }
                }
                .pickerStyle(.segmented)
                .frame(width: 120)
            }

            HStack {
                Text("Avg Heart Rate")
                Spacer()
                TextField("140", text: $viewModel.manualEntryHeartRate)
                    .keyboardType(.numberPad)
                    .multilineTextAlignment(.trailing)
                    .frame(width: 80)
                Text("bpm")
                    .foregroundStyle(.secondary)
            }
        }
    }

    // MARK: - Strength Section

    private var strengthSection: some View {
        Section("Strength Exercises") {
            ForEach(Array(viewModel.manualEntryExercises.enumerated()), id: \.element.id) { index, entry in
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(entry.exerciseName)
                            .font(.subheadline)
                            .fontWeight(.medium)
                        Text("\(entry.sets)x\(entry.reps) @ \(entry.weightLbs, specifier: "%.0f") lbs")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Spacer()

                    Button {
                        viewModel.removeManualExercise(at: index)
                    } label: {
                        Image(systemName: "minus.circle.fill")
                            .foregroundStyle(.red)
                    }
                    .buttonStyle(.plain)
                }
            }

            if isAddingExercise {
                addExerciseFields
            } else {
                Button {
                    isAddingExercise = true
                } label: {
                    Label("Add Exercise", systemImage: "plus.circle")
                }
            }
        }
    }

    private var addExerciseFields: some View {
        VStack(spacing: 8) {
            TextField("Exercise name", text: $newExerciseName)
                .textInputAutocapitalization(.words)

            HStack(spacing: 12) {
                VStack(alignment: .leading) {
                    Text("Sets").font(.caption).foregroundStyle(.secondary)
                    TextField("3", text: $newExerciseSets)
                        .keyboardType(.numberPad)
                        .textFieldStyle(.roundedBorder)
                }

                VStack(alignment: .leading) {
                    Text("Reps").font(.caption).foregroundStyle(.secondary)
                    TextField("10", text: $newExerciseReps)
                        .keyboardType(.numberPad)
                        .textFieldStyle(.roundedBorder)
                }

                VStack(alignment: .leading) {
                    Text("Weight").font(.caption).foregroundStyle(.secondary)
                    TextField("lbs", text: $newExerciseWeight)
                        .keyboardType(.decimalPad)
                        .textFieldStyle(.roundedBorder)
                }
            }

            HStack {
                Button("Cancel") {
                    isAddingExercise = false
                    resetNewExerciseFields()
                }
                .foregroundStyle(.secondary)

                Spacer()

                Button("Add") {
                    submitNewExercise()
                }
                .disabled(newExerciseName.trimmingCharacters(in: .whitespaces).isEmpty)
                .fontWeight(.semibold)
            }
            .padding(.top, 4)
        }
    }

    // MARK: - Notes Section

    private var notesSection: some View {
        Section("Notes") {
            TextField("How did it go?", text: $viewModel.manualEntryNotes, axis: .vertical)
                .lineLimit(3...6)
        }
    }

    // MARK: - Helpers

    private func submitNewExercise() {
        let name = newExerciseName.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }

        let sets = Int(newExerciseSets) ?? 3
        let reps = Int(newExerciseReps) ?? 10
        let weight = Double(newExerciseWeight) ?? 0

        viewModel.addManualExercise(name: name, sets: sets, reps: reps, weight: weight)
        resetNewExerciseFields()
        isAddingExercise = false
    }

    private func resetNewExerciseFields() {
        newExerciseName = ""
        newExerciseSets = "3"
        newExerciseReps = "10"
        newExerciseWeight = ""
    }
}

// MARK: - Previews

#Preview("Workout List - Empty") {
    WorkoutListView()
        .environment(AppState())
}

#Preview("Workout List - With History") {
    let appState = AppState()
    let viewModel = WorkoutViewModel()

    // Pre-populate with mock recent workouts
    let strengthWorkout = WorkoutSession(
        workoutType: "Strength",
        startTime: Date().addingTimeInterval(-86400),
        endTime: Date().addingTimeInterval(-86400 + 3600),
        isActive: false,
        exercises: [
            ExerciseSet(exerciseName: "Bench Press", setNumber: 1, reps: 10, weightLbs: 155),
            ExerciseSet(exerciseName: "Bench Press", setNumber: 2, reps: 8, weightLbs: 165),
            ExerciseSet(exerciseName: "Bench Press", setNumber: 3, reps: 6, weightLbs: 175),
        ]
    )
    let runWorkout = WorkoutSession(
        workoutType: "Run",
        startTime: Date().addingTimeInterval(-172800),
        endTime: Date().addingTimeInterval(-172800 + 2400),
        isActive: false,
        totalDistance: 5.0,
        distanceUnit: .kilometers,
        heartRateSamples: [HeartRateSample(bpm: 148)]
    )
    let swimWorkout = WorkoutSession(
        workoutType: "Swim",
        startTime: Date().addingTimeInterval(-259200),
        endTime: Date().addingTimeInterval(-259200 + 2700),
        isActive: false,
        totalDistance: 2000,
        distanceUnit: .meters
    )

    return WorkoutListView()
        .environment(appState)
        .onAppear {
            // Note: In a real app, recent workouts would be injected or loaded.
            // This preview demonstrates the layout structure.
        }
}

#Preview("Workout List - Active Workout") {
    let appState = AppState()

    return WorkoutListView()
        .environment(appState)
}

#Preview("Manual Entry Sheet") {
    ManualEntrySheet(viewModel: WorkoutViewModel())
}
