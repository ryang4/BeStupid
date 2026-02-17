import SwiftUI

struct LogEditorView: View {
    @Binding var log: DailyLog
    let onSave: () -> Void
    let onCancel: () -> Void

    // Local state for adding new items
    @State private var newTodoText: String = ""
    @State private var newFoodName: String = ""
    @State private var newFoodCalories: String = ""
    @State private var newFoodProtein: String = ""

    // Training activity editor state
    @State private var isAddingActivity: Bool = false
    @State private var newActivityType: String = "Swim"
    @State private var newActivityDistance: String = ""
    @State private var newActivityDistanceUnit: DistanceUnit = .meters
    @State private var newActivityDuration: String = ""
    @State private var newActivityHeartRate: String = ""

    // Strength exercise editor state
    @State private var isAddingExercise: Bool = false
    @State private var newExerciseName: String = ""
    @State private var newExerciseSets: String = "3"
    @State private var newExerciseReps: String = "10"
    @State private var newExerciseWeight: String = ""

    private let activityTypes = ["Swim", "Bike", "Run", "Walk", "Yoga", "Other"]

    var body: some View {
        NavigationStack {
            Form {
                metricsSection
                trainingSection
                strengthSection
                nutritionSection
                todosSection
                habitsSection
                notesSection
            }
            .navigationTitle("Edit Log")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel", action: onCancel)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save", action: onSave)
                        .fontWeight(.semibold)
                }
            }
        }
    }

    // MARK: - Metrics Section

    private var metricsSection: some View {
        Section("Metrics") {
            DecimalField(
                label: "Weight",
                value: Binding(
                    get: { log.weight },
                    set: { log.weight = $0 }
                ),
                unit: "lbs",
                icon: "scalemass"
            )

            DecimalField(
                label: "Sleep",
                value: Binding(
                    get: { log.sleep },
                    set: { log.sleep = $0 }
                ),
                unit: "hrs",
                icon: "moon.zzz"
            )

            SliderField(
                label: "Sleep Quality",
                value: Binding(
                    get: { log.sleepQuality ?? 5 },
                    set: { log.sleepQuality = $0 }
                ),
                range: 1...10,
                icon: "star"
            )

            SliderField(
                label: "Mood AM",
                value: Binding(
                    get: { log.moodAM ?? 5 },
                    set: { log.moodAM = $0 }
                ),
                range: 1...10,
                icon: "sun.max"
            )

            SliderField(
                label: "Mood PM",
                value: Binding(
                    get: { log.moodPM ?? 5 },
                    set: { log.moodPM = $0 }
                ),
                range: 1...10,
                icon: "moon"
            )

            SliderField(
                label: "Energy",
                value: Binding(
                    get: { log.energy ?? 5 },
                    set: { log.energy = $0 }
                ),
                range: 1...10,
                icon: "bolt"
            )

            SliderField(
                label: "Focus",
                value: Binding(
                    get: { log.focus ?? 5 },
                    set: { log.focus = $0 }
                ),
                range: 1...10,
                icon: "scope"
            )
        }
    }

    // MARK: - Training Section

    private var trainingSection: some View {
        Section("Training") {
            TextField("Planned Workout", text: Binding(
                get: { log.plannedWorkout ?? "" },
                set: { log.plannedWorkout = $0.isEmpty ? nil : $0 }
            ))

            ForEach(log.trainingActivities) { activity in
                TrainingActivityRow(activity: activity)
            }
            .onDelete { indexSet in
                log.trainingActivities.remove(atOffsets: indexSet)
            }

            if isAddingActivity {
                addActivityFields
            } else {
                Button {
                    isAddingActivity = true
                } label: {
                    Label("Add Training Activity", systemImage: "plus.circle")
                }
            }
        }
    }

    @ViewBuilder
    private var addActivityFields: some View {
        Picker("Type", selection: $newActivityType) {
            ForEach(activityTypes, id: \.self) { type in
                Text(type).tag(type)
            }
        }

        HStack {
            TextField("Distance", text: $newActivityDistance)
                .keyboardType(.decimalPad)
            Picker("Unit", selection: $newActivityDistanceUnit) {
                ForEach(DistanceUnit.allCases, id: \.self) { unit in
                    Text(unit.rawValue).tag(unit)
                }
            }
            .pickerStyle(.menu)
        }

        TextField("Duration (min)", text: $newActivityDuration)
            .keyboardType(.decimalPad)

        TextField("Avg Heart Rate (bpm)", text: $newActivityHeartRate)
            .keyboardType(.numberPad)

        HStack {
            Button("Cancel") {
                isAddingActivity = false
                clearActivityFields()
            }
            .foregroundStyle(.red)

            Spacer()

            Button("Add") {
                addTrainingActivity()
            }
            .disabled(newActivityType.isEmpty)
        }
    }

    // MARK: - Strength Section

    private var strengthSection: some View {
        Section("Strength") {
            ForEach(log.strengthExercises) { exercise in
                StrengthExerciseRow(exercise: exercise)
            }
            .onDelete { indexSet in
                log.strengthExercises.remove(atOffsets: indexSet)
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

    @ViewBuilder
    private var addExerciseFields: some View {
        TextField("Exercise Name", text: $newExerciseName)

        HStack(spacing: 16) {
            VStack(alignment: .leading) {
                Text("Sets").font(.caption).foregroundStyle(.secondary)
                TextField("Sets", text: $newExerciseSets)
                    .keyboardType(.numberPad)
                    .textFieldStyle(.roundedBorder)
            }
            VStack(alignment: .leading) {
                Text("Reps").font(.caption).foregroundStyle(.secondary)
                TextField("Reps", text: $newExerciseReps)
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
                clearExerciseFields()
            }
            .foregroundStyle(.red)

            Spacer()

            Button("Add") {
                addStrengthExercise()
            }
            .disabled(newExerciseName.isEmpty)
        }
    }

    // MARK: - Nutrition Section

    private var nutritionSection: some View {
        Section("Nutrition") {
            HStack {
                Label("Calories", systemImage: "flame")
                Spacer()
                TextField("kcal", value: Binding(
                    get: { log.caloriesSoFar },
                    set: { log.caloriesSoFar = $0 }
                ), format: .number)
                .keyboardType(.numberPad)
                .multilineTextAlignment(.trailing)
                .frame(width: 80)
            }

            HStack {
                Label("Protein", systemImage: "fork.knife")
                Spacer()
                TextField("g", value: Binding(
                    get: { log.proteinSoFar },
                    set: { log.proteinSoFar = $0 }
                ), format: .number)
                .keyboardType(.numberPad)
                .multilineTextAlignment(.trailing)
                .frame(width: 80)
            }

            ForEach(log.nutritionLineItems) { item in
                HStack {
                    VStack(alignment: .leading) {
                        Text(item.food).font(.subheadline)
                        if let cal = item.calories {
                            Text("\(cal) kcal").font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    Spacer()
                }
            }
            .onDelete { indexSet in
                log.nutritionLineItems.remove(atOffsets: indexSet)
            }

            HStack {
                TextField("Food item", text: $newFoodName)
                TextField("kcal", text: $newFoodCalories)
                    .keyboardType(.numberPad)
                    .frame(width: 60)
                TextField("P(g)", text: $newFoodProtein)
                    .keyboardType(.numberPad)
                    .frame(width: 50)
                Button {
                    addNutritionItem()
                } label: {
                    Image(systemName: "plus.circle.fill")
                        .foregroundStyle(.blue)
                }
                .disabled(newFoodName.isEmpty)
            }
        }
    }

    // MARK: - Todos Section

    private var todosSection: some View {
        Section("Todos") {
            ForEach($log.todos) { $todo in
                HStack {
                    Button {
                        todo.isCompleted.toggle()
                    } label: {
                        Image(systemName: todo.isCompleted ? "checkmark.circle.fill" : "circle")
                            .foregroundStyle(todo.isCompleted ? .green : .secondary)
                    }
                    .buttonStyle(.plain)

                    TextField("Todo", text: $todo.text)
                }
            }
            .onDelete { indexSet in
                log.todos.remove(atOffsets: indexSet)
            }

            HStack {
                Image(systemName: "plus.circle")
                    .foregroundStyle(.blue)
                TextField("Add todo...", text: $newTodoText)
                    .onSubmit {
                        addTodo()
                    }
            }
        }
    }

    // MARK: - Habits Section

    private var habitsSection: some View {
        Section("Habits") {
            ForEach($log.habits) { $habit in
                HStack {
                    Button {
                        habit.isCompleted.toggle()
                    } label: {
                        Image(systemName: habit.isCompleted ? "checkmark.diamond.fill" : "diamond")
                            .foregroundStyle(habit.isCompleted ? .purple : .secondary)
                    }
                    .buttonStyle(.plain)

                    Text(habit.name)
                        .foregroundStyle(habit.isCompleted ? .secondary : .primary)
                }
            }
        }
    }

    // MARK: - Notes Section

    private var notesSection: some View {
        Section("Notes") {
            TextField("Daily briefing...", text: Binding(
                get: { log.dailyBriefing ?? "" },
                set: { log.dailyBriefing = $0.isEmpty ? nil : $0 }
            ), axis: .vertical)
            .lineLimit(3...8)

            VStack(alignment: .leading, spacing: 8) {
                Text("Top 3 for Tomorrow")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(.secondary)

                ForEach(0..<3, id: \.self) { index in
                    HStack(spacing: 8) {
                        Text("\(index + 1).")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.blue)
                            .frame(width: 20, alignment: .trailing)

                        TextField("Priority \(index + 1)", text: Binding(
                            get: {
                                index < log.topThreeForTomorrow.count
                                    ? log.topThreeForTomorrow[index]
                                    : ""
                            },
                            set: { newValue in
                                ensureTopThreeCapacity(index)
                                log.topThreeForTomorrow[index] = newValue
                            }
                        ))
                    }
                }
            }
        }
    }

    // MARK: - Actions

    private func addTrainingActivity() {
        let activity = TrainingActivity(
            type: newActivityType,
            distance: Double(newActivityDistance),
            distanceUnit: newActivityDistanceUnit,
            durationMinutes: Double(newActivityDuration),
            avgHeartRate: Int(newActivityHeartRate)
        )
        log.trainingActivities.append(activity)
        isAddingActivity = false
        clearActivityFields()
    }

    private func addStrengthExercise() {
        guard !newExerciseName.isEmpty,
              let sets = Int(newExerciseSets),
              let reps = Int(newExerciseReps) else { return }

        let weight = Double(newExerciseWeight) ?? 0
        let exercise = StrengthEntry(
            exerciseName: newExerciseName,
            sets: sets,
            reps: reps,
            weightLbs: weight
        )
        log.strengthExercises.append(exercise)
        isAddingExercise = false
        clearExerciseFields()
    }

    private func addNutritionItem() {
        guard !newFoodName.isEmpty else { return }
        let item = NutritionEntry(
            food: newFoodName,
            calories: Int(newFoodCalories),
            proteinG: Int(newFoodProtein)
        )
        log.nutritionLineItems.append(item)
        newFoodName = ""
        newFoodCalories = ""
        newFoodProtein = ""
    }

    private func addTodo() {
        guard !newTodoText.isEmpty else { return }
        let todo = TodoItem(text: newTodoText)
        log.todos.append(todo)
        newTodoText = ""
    }

    private func ensureTopThreeCapacity(_ index: Int) {
        while log.topThreeForTomorrow.count <= index {
            log.topThreeForTomorrow.append("")
        }
    }

    private func clearActivityFields() {
        newActivityType = "Swim"
        newActivityDistance = ""
        newActivityDistanceUnit = .meters
        newActivityDuration = ""
        newActivityHeartRate = ""
    }

    private func clearExerciseFields() {
        newExerciseName = ""
        newExerciseSets = "3"
        newExerciseReps = "10"
        newExerciseWeight = ""
    }
}

// MARK: - DecimalField

private struct DecimalField: View {
    let label: String
    @Binding var value: Double?
    let unit: String
    let icon: String

    @State private var textValue: String = ""

    var body: some View {
        HStack {
            Label(label, systemImage: icon)
            Spacer()
            TextField(unit, text: $textValue)
                .keyboardType(.decimalPad)
                .multilineTextAlignment(.trailing)
                .frame(width: 80)
                .onChange(of: textValue) { _, newValue in
                    value = Double(newValue)
                }
            Text(unit)
                .font(.caption)
                .foregroundStyle(.secondary)
                .frame(width: 30, alignment: .leading)
        }
        .onAppear {
            if let value {
                textValue = String(format: "%.1f", value)
            }
        }
    }
}

// MARK: - SliderField

private struct SliderField: View {
    let label: String
    @Binding var value: Double
    let range: ClosedRange<Double>
    let icon: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Label(label, systemImage: icon)
                Spacer()
                Text(String(format: "%.0f/10", value))
                    .font(.subheadline.weight(.semibold).monospacedDigit())
                    .foregroundStyle(sliderColor)
            }

            Slider(value: $value, in: range, step: 1)
                .tint(sliderColor)
        }
    }

    private var sliderColor: Color {
        if value >= 8 { return .green }
        if value >= 6 { return .yellow }
        return .red
    }
}

// MARK: - TrainingActivityRow

private struct TrainingActivityRow: View {
    let activity: TrainingActivity

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(activity.type)
                .font(.subheadline.weight(.medium))

            HStack(spacing: 12) {
                if let distance = activity.distance {
                    Label(
                        formatDistance(distance, unit: activity.distanceUnit),
                        systemImage: "arrow.left.and.right"
                    )
                    .font(.caption)
                    .foregroundStyle(.secondary)
                }
                if let duration = activity.durationMinutes {
                    Label(
                        String(format: "%.0f min", duration),
                        systemImage: "clock"
                    )
                    .font(.caption)
                    .foregroundStyle(.secondary)
                }
                if let hr = activity.avgHeartRate {
                    Label("\(hr) bpm", systemImage: "heart")
                        .font(.caption)
                        .foregroundStyle(.red.opacity(0.8))
                }
            }
        }
    }

    private func formatDistance(_ distance: Double, unit: DistanceUnit) -> String {
        switch unit {
        case .meters: return String(format: "%.0fm", distance)
        case .kilometers: return String(format: "%.1f km", distance)
        case .miles: return String(format: "%.1f mi", distance)
        }
    }
}

// MARK: - StrengthExerciseRow

private struct StrengthExerciseRow: View {
    let exercise: StrengthEntry

    var body: some View {
        HStack {
            Text(exercise.exerciseName)
                .font(.subheadline)
            Spacer()
            Text("\(exercise.sets)x\(exercise.reps)")
                .font(.caption.monospacedDigit())
                .foregroundStyle(.secondary)
            Text(exercise.weightLbs > 0 ? String(format: "%.0f lbs", exercise.weightLbs) : "BW")
                .font(.caption.monospacedDigit())
                .foregroundStyle(.secondary)
                .frame(width: 60, alignment: .trailing)
        }
    }
}

// MARK: - Preview

#Preview("Log Editor") {
    @Previewable @State var log = DailyLog(
        date: Date(),
        title: "2026-02-17.md",
        tags: ["swim"],
        weight: 185.4,
        sleep: 7.2,
        sleepQuality: 8,
        moodAM: 7,
        energy: 8,
        focus: 7,
        plannedWorkout: "Swim + Strength",
        trainingActivities: [
            TrainingActivity(
                type: "Swim",
                distance: 2000,
                distanceUnit: .meters,
                durationMinutes: 45,
                avgHeartRate: 142
            )
        ],
        strengthExercises: [
            StrengthEntry(exerciseName: "Bench Press", sets: 3, reps: 10, weightLbs: 155),
            StrengthEntry(exerciseName: "Pull-ups", sets: 3, reps: 8, weightLbs: 0),
        ],
        todos: [
            TodoItem(text: "Review sprint backlog", isCompleted: true),
            TodoItem(text: "Submit expense report", isCompleted: false),
        ],
        habits: [
            HabitEntry(habitId: "h1", name: "Morning meditation", isCompleted: true),
            HabitEntry(habitId: "h2", name: "Stretch 15 min", isCompleted: false),
        ],
        caloriesSoFar: 1850,
        proteinSoFar: 125,
        topThreeForTomorrow: [
            "Long bike ride",
            "Finish quarterly review",
            "Meal prep",
        ],
        dailyBriefing: "Good progress this week."
    )

    LogEditorView(
        log: $log,
        onSave: {},
        onCancel: {}
    )
}

#Preview("Log Editor - Empty") {
    @Previewable @State var log = DailyLog(date: Date())
    LogEditorView(
        log: $log,
        onSave: {},
        onCancel: {}
    )
}
