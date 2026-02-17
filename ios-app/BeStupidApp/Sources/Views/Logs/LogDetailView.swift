import SwiftUI

struct LogDetailView: View {
    let log: DailyLog
    let onEdit: () -> Void

    private var dateLabel: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEEE, MMMM d, yyyy"
        return formatter.string(from: log.date)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                headerSection
                metricsSection
                workoutSection
                trainingSection
                strengthSection
                todosSection
                habitsSection
                nutritionSection
                briefingSection
                topThreeSection
            }
            .padding()
        }
        .navigationTitle(log.title)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button("Edit", action: onEdit)
            }
        }
    }

    // MARK: - Header

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(dateLabel)
                .font(.title2.weight(.semibold))

            if !log.tags.isEmpty {
                HStack(spacing: 6) {
                    ForEach(log.tags, id: \.self) { tag in
                        Text(tag)
                            .font(.caption.weight(.medium))
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(.blue.opacity(0.12), in: Capsule())
                            .foregroundStyle(.blue)
                    }
                }
            }
        }
    }

    // MARK: - Metrics Summary Cards

    @ViewBuilder
    private var metricsSection: some View {
        let hasAnyMetric = log.weight != nil || log.sleep != nil || log.moodAM != nil || log.energy != nil || log.focus != nil
        if hasAnyMetric {
            DetailSectionCard(title: "Metrics") {
                LazyVGrid(columns: [
                    GridItem(.flexible()),
                    GridItem(.flexible()),
                    GridItem(.flexible()),
                ], spacing: 12) {
                    if let weight = log.weight {
                        MetricPill(
                            label: "Weight",
                            value: String(format: "%.1f", weight),
                            unit: "lbs",
                            icon: "scalemass",
                            color: .blue
                        )
                    }
                    if let sleep = log.sleep {
                        MetricPill(
                            label: "Sleep",
                            value: String(format: "%.1f", sleep),
                            unit: "hrs",
                            icon: "moon.zzz",
                            color: sleepColor(sleep)
                        )
                    }
                    if let sq = log.sleepQuality {
                        MetricPill(
                            label: "Sleep Q",
                            value: String(format: "%.0f", sq),
                            unit: "/10",
                            icon: "star",
                            color: ratingColor(sq)
                        )
                    }
                    if let moodAM = log.moodAM {
                        MetricPill(
                            label: "Mood AM",
                            value: String(format: "%.0f", moodAM),
                            unit: "/10",
                            icon: "sun.max",
                            color: ratingColor(moodAM)
                        )
                    }
                    if let moodPM = log.moodPM {
                        MetricPill(
                            label: "Mood PM",
                            value: String(format: "%.0f", moodPM),
                            unit: "/10",
                            icon: "moon",
                            color: ratingColor(moodPM)
                        )
                    }
                    if let energy = log.energy {
                        MetricPill(
                            label: "Energy",
                            value: String(format: "%.0f", energy),
                            unit: "/10",
                            icon: "bolt",
                            color: ratingColor(energy)
                        )
                    }
                    if let focus = log.focus {
                        MetricPill(
                            label: "Focus",
                            value: String(format: "%.0f", focus),
                            unit: "/10",
                            icon: "scope",
                            color: ratingColor(focus)
                        )
                    }
                }
            }
        }
    }

    // MARK: - Planned Workout

    @ViewBuilder
    private var workoutSection: some View {
        if let workout = log.plannedWorkout {
            DetailSectionCard(title: "Planned Workout") {
                HStack(spacing: 10) {
                    Image(systemName: workoutIconName(for: workout))
                        .font(.title2)
                        .foregroundStyle(workoutTintColor(for: workout))
                        .frame(width: 40, height: 40)
                        .background(workoutTintColor(for: workout).opacity(0.12), in: RoundedRectangle(cornerRadius: 8))

                    Text(workout)
                        .font(.body.weight(.medium))
                }
            }
        }
    }

    // MARK: - Training Activities

    @ViewBuilder
    private var trainingSection: some View {
        if !log.trainingActivities.isEmpty {
            DetailSectionCard(title: "Training Output") {
                VStack(spacing: 12) {
                    ForEach(log.trainingActivities) { activity in
                        HStack(spacing: 0) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(activity.type)
                                    .font(.subheadline.weight(.semibold))

                                HStack(spacing: 16) {
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
                                        Label(
                                            "\(hr) bpm",
                                            systemImage: "heart"
                                        )
                                        .font(.caption)
                                        .foregroundStyle(.red.opacity(0.8))
                                    }

                                    if let pace = activity.paceMinPerKm {
                                        Label(
                                            String(format: "%.1f min/km", pace),
                                            systemImage: "speedometer"
                                        )
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                    }
                                }
                            }
                            Spacer(minLength: 0)
                        }
                        .padding(12)
                        .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 8))
                    }
                }
            }
        }
    }

    // MARK: - Strength Log

    @ViewBuilder
    private var strengthSection: some View {
        if !log.strengthExercises.isEmpty {
            DetailSectionCard(title: "Strength Log") {
                VStack(spacing: 0) {
                    // Table header
                    HStack {
                        Text("Exercise")
                            .frame(maxWidth: .infinity, alignment: .leading)
                        Text("Sets")
                            .frame(width: 40)
                        Text("Reps")
                            .frame(width: 40)
                        Text("Weight")
                            .frame(width: 60)
                        Text("Volume")
                            .frame(width: 65, alignment: .trailing)
                    }
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 8)
                    .padding(.bottom, 8)

                    Divider()

                    // Table rows
                    ForEach(log.strengthExercises) { exercise in
                        HStack {
                            Text(exercise.exerciseName)
                                .font(.subheadline)
                                .frame(maxWidth: .infinity, alignment: .leading)
                            Text("\(exercise.sets)")
                                .font(.subheadline.monospacedDigit())
                                .frame(width: 40)
                            Text("\(exercise.reps)")
                                .font(.subheadline.monospacedDigit())
                                .frame(width: 40)
                            Text(exercise.weightLbs > 0 ? String(format: "%.0f", exercise.weightLbs) : "BW")
                                .font(.subheadline.monospacedDigit())
                                .frame(width: 60)
                            Text(String(format: "%.0f", exercise.totalVolume))
                                .font(.subheadline.monospacedDigit())
                                .frame(width: 65, alignment: .trailing)
                        }
                        .padding(.horizontal, 8)
                        .padding(.vertical, 6)

                        if exercise.id != log.strengthExercises.last?.id {
                            Divider().padding(.horizontal, 8)
                        }
                    }

                    Divider()
                        .padding(.horizontal, 8)
                        .padding(.top, 4)

                    // Total row
                    HStack {
                        Text("Total Volume")
                            .font(.subheadline.weight(.semibold))
                            .frame(maxWidth: .infinity, alignment: .leading)
                        Text(String(format: "%.0f lbs", log.totalStrengthVolume))
                            .font(.subheadline.weight(.semibold).monospacedDigit())
                    }
                    .padding(.horizontal, 8)
                    .padding(.top, 8)
                }
            }
        }
    }

    // MARK: - Todos

    @ViewBuilder
    private var todosSection: some View {
        if !log.todos.isEmpty {
            DetailSectionCard(title: "Todos") {
                VStack(spacing: 0) {
                    if let rate = log.todoCompletionRate {
                        HStack {
                            ProgressView(value: rate)
                                .tint(completionColor(rate))
                            Text("\(Int(rate * 100))%")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(completionColor(rate))
                        }
                        .padding(.bottom, 12)
                    }

                    ForEach(log.todos) { todo in
                        HStack(spacing: 10) {
                            Image(systemName: todo.isCompleted ? "checkmark.circle.fill" : "circle")
                                .foregroundStyle(todo.isCompleted ? .green : .secondary)
                                .font(.body)

                            Text(todo.text)
                                .font(.subheadline)
                                .strikethrough(todo.isCompleted, color: .secondary)
                                .foregroundStyle(todo.isCompleted ? .secondary : .primary)

                            Spacer()
                        }
                        .padding(.vertical, 4)
                    }
                }
            }
        }
    }

    // MARK: - Habits

    @ViewBuilder
    private var habitsSection: some View {
        if !log.habits.isEmpty {
            DetailSectionCard(title: "Habits") {
                VStack(spacing: 0) {
                    if let rate = log.habitCompletionRate {
                        HStack {
                            ProgressView(value: rate)
                                .tint(completionColor(rate))
                            Text("\(Int(rate * 100))%")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(completionColor(rate))
                        }
                        .padding(.bottom, 12)
                    }

                    ForEach(log.habits) { habit in
                        HStack(spacing: 10) {
                            Image(systemName: habit.isCompleted ? "checkmark.diamond.fill" : "diamond")
                                .foregroundStyle(habit.isCompleted ? .purple : .secondary)
                                .font(.body)

                            Text(habit.name)
                                .font(.subheadline)
                                .strikethrough(habit.isCompleted, color: .secondary)
                                .foregroundStyle(habit.isCompleted ? .secondary : .primary)

                            Spacer()
                        }
                        .padding(.vertical, 4)
                    }
                }
            }
        }
    }

    // MARK: - Nutrition

    @ViewBuilder
    private var nutritionSection: some View {
        let hasNutrition = log.caloriesSoFar != nil || log.proteinSoFar != nil || !log.nutritionLineItems.isEmpty
        if hasNutrition {
            DetailSectionCard(title: "Nutrition") {
                VStack(alignment: .leading, spacing: 12) {
                    HStack(spacing: 20) {
                        if let cal = log.caloriesSoFar {
                            VStack(spacing: 2) {
                                Text("\(cal)")
                                    .font(.title3.weight(.semibold).monospacedDigit())
                                Text("kcal")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        if let protein = log.proteinSoFar {
                            VStack(spacing: 2) {
                                Text("\(protein)g")
                                    .font(.title3.weight(.semibold).monospacedDigit())
                                Text("protein")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }

                    if !log.nutritionLineItems.isEmpty {
                        Divider()

                        ForEach(log.nutritionLineItems) { item in
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(item.food)
                                        .font(.subheadline)
                                    if let time = item.time {
                                        Text(time)
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                }

                                Spacer()

                                VStack(alignment: .trailing, spacing: 2) {
                                    if let cal = item.calories {
                                        Text("\(cal) kcal")
                                            .font(.caption.monospacedDigit())
                                    }
                                    HStack(spacing: 8) {
                                        if let p = item.proteinG {
                                            Text("P:\(p)g")
                                                .font(.caption2.monospacedDigit())
                                                .foregroundStyle(.secondary)
                                        }
                                        if let c = item.carbsG {
                                            Text("C:\(c)g")
                                                .font(.caption2.monospacedDigit())
                                                .foregroundStyle(.secondary)
                                        }
                                        if let f = item.fatG {
                                            Text("F:\(f)g")
                                                .font(.caption2.monospacedDigit())
                                                .foregroundStyle(.secondary)
                                        }
                                    }
                                }
                            }
                            .padding(.vertical, 2)
                        }
                    }
                }
            }
        }
    }

    // MARK: - Briefing

    @ViewBuilder
    private var briefingSection: some View {
        if let briefing = log.dailyBriefing, !briefing.isEmpty {
            DetailSectionCard(title: "Daily Briefing") {
                Text(briefing)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
    }

    // MARK: - Top Three for Tomorrow

    @ViewBuilder
    private var topThreeSection: some View {
        if !log.topThreeForTomorrow.isEmpty {
            DetailSectionCard(title: "Top 3 for Tomorrow") {
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(Array(log.topThreeForTomorrow.enumerated()), id: \.offset) { index, item in
                        HStack(alignment: .top, spacing: 10) {
                            Text("\(index + 1).")
                                .font(.subheadline.weight(.semibold))
                                .foregroundStyle(.blue)
                                .frame(width: 20, alignment: .trailing)
                            Text(item)
                                .font(.subheadline)
                        }
                    }
                }
            }
        }
    }

    // MARK: - Color Helpers

    private func sleepColor(_ hours: Double) -> Color {
        if hours >= 7.5 { return .green }
        if hours >= 6.5 { return .yellow }
        return .red
    }

    private func ratingColor(_ score: Double) -> Color {
        if score >= 8 { return .green }
        if score >= 6 { return .yellow }
        return .red
    }

    private func completionColor(_ rate: Double) -> Color {
        if rate >= 0.8 { return .green }
        if rate >= 0.5 { return .yellow }
        return .red
    }

    private func formatDistance(_ distance: Double, unit: DistanceUnit) -> String {
        switch unit {
        case .meters:
            return String(format: "%.0fm", distance)
        case .kilometers:
            return String(format: "%.1f km", distance)
        case .miles:
            return String(format: "%.1f mi", distance)
        }
    }

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

    private func workoutTintColor(for type: String) -> Color {
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

// MARK: - MetricPill

private struct MetricPill: View {
    let label: String
    let value: String
    let unit: String
    let icon: String
    let color: Color

    var body: some View {
        VStack(spacing: 4) {
            Image(systemName: icon)
                .font(.caption)
                .foregroundStyle(color)

            HStack(alignment: .firstTextBaseline, spacing: 1) {
                Text(value)
                    .font(.subheadline.weight(.semibold).monospacedDigit())
                Text(unit)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background(color.opacity(0.06), in: RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - DetailSectionCard

private struct DetailSectionCard<Content: View>: View {
    let title: String
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title)
                .font(.headline)

            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Preview

#Preview("Log Detail - Full") {
    NavigationStack {
        LogDetailView(
            log: DailyLog(
                date: Date(),
                title: "2026-02-17.md",
                tags: ["swim", "strength"],
                weight: 185.4,
                sleep: 7.2,
                sleepQuality: 8,
                moodAM: 7,
                moodPM: 8,
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
                    StrengthEntry(exerciseName: "Squat", sets: 3, reps: 8, weightLbs: 205),
                ],
                todos: [
                    TodoItem(text: "Review sprint backlog", isCompleted: true),
                    TodoItem(text: "Submit expense report", isCompleted: false),
                    TodoItem(text: "Plan weekend long ride route", isCompleted: false),
                    TodoItem(text: "Read training chapter", isCompleted: true),
                ],
                habits: [
                    HabitEntry(habitId: "h1", name: "Morning meditation", isCompleted: true),
                    HabitEntry(habitId: "h2", name: "Stretch 15 min", isCompleted: false),
                    HabitEntry(habitId: "h3", name: "Read 30 min", isCompleted: true),
                    HabitEntry(habitId: "h4", name: "Cold shower", isCompleted: false),
                    HabitEntry(habitId: "h5", name: "Journal", isCompleted: true),
                ],
                caloriesSoFar: 1850,
                proteinSoFar: 125,
                nutritionLineItems: [
                    NutritionEntry(time: "7:30 AM", food: "Oatmeal with berries", calories: 350, proteinG: 12, carbsG: 55, fatG: 8),
                    NutritionEntry(time: "12:00 PM", food: "Chicken salad", calories: 550, proteinG: 45, carbsG: 20, fatG: 25),
                    NutritionEntry(time: "3:00 PM", food: "Protein shake", calories: 250, proteinG: 30, carbsG: 15, fatG: 5),
                ],
                topThreeForTomorrow: [
                    "Long bike ride - 60 min Z2",
                    "Finish quarterly review",
                    "Meal prep for the week",
                ],
                dailyBriefing: "Base building phase continues. Focus on consistent Z2 cardio and maintaining strength. Sleep trending well this week."
            ),
            onEdit: {}
        )
    }
}

#Preview("Log Detail - Minimal") {
    NavigationStack {
        LogDetailView(
            log: DailyLog(
                date: Date(),
                weight: 186.0,
                sleep: 6.5,
                energy: 6,
                plannedWorkout: "Recovery"
            ),
            onEdit: {}
        )
    }
}
