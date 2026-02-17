import SwiftUI

// MARK: - ExerciseLogView

/// Input component for logging a single exercise set during a live workout.
/// Features autocomplete suggestions, quick-increment stepper buttons,
/// a reference to "last time" data, and a large LOG SET button for gym usability.
struct ExerciseLogView: View {
    @Binding var exerciseName: String
    @Binding var reps: String
    @Binding var weight: String
    let lastSessionData: (reps: Int, weight: Double)?
    let recentExercises: [String]
    let onLogSet: () -> Void
    let onQuickIncrement: (QuickIncrementField) -> Void

    @State private var isShowingSuggestions: Bool = false
    @FocusState private var focusedField: Field?

    private enum Field: Hashable {
        case exerciseName
        case reps
        case weight
    }

    var body: some View {
        VStack(spacing: 16) {
            exerciseNameField
            lastTimeReference
            repsAndWeightRow
            logSetButton
        }
        .padding(.horizontal)
    }

    // MARK: - Exercise Name

    private var exerciseNameField: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Exercise")
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundStyle(.secondary)

            ZStack(alignment: .topLeading) {
                TextField("e.g. Bench Press", text: $exerciseName)
                    .font(.title3)
                    .fontWeight(.semibold)
                    .textFieldStyle(.roundedBorder)
                    .textInputAutocapitalization(.words)
                    .autocorrectionDisabled()
                    .focused($focusedField, equals: .exerciseName)
                    .onChange(of: exerciseName) { _, newValue in
                        isShowingSuggestions = !newValue.isEmpty && focusedField == .exerciseName
                    }
                    .onSubmit {
                        focusedField = .reps
                    }

                if isShowingSuggestions {
                    suggestionsDropdown
                        .offset(y: 44)
                        .zIndex(10)
                }
            }
        }
    }

    private var suggestionsDropdown: some View {
        let query = exerciseName.lowercased().trimmingCharacters(in: .whitespaces)
        let allNames = recentExercises.uniqued()
        let filtered = query.isEmpty
            ? Array(allNames.prefix(6))
            : allNames.filter { $0.lowercased().contains(query) }.prefix(6).map { $0 }

        return Group {
            if !filtered.isEmpty {
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(filtered, id: \.self) { suggestion in
                        Button {
                            exerciseName = suggestion
                            isShowingSuggestions = false
                            focusedField = .reps
                        } label: {
                            Text(suggestion)
                                .font(.body)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 10)
                        }
                        .buttonStyle(.plain)

                        if suggestion != filtered.last {
                            Divider()
                                .padding(.leading, 12)
                        }
                    }
                }
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 10))
                .shadow(color: .black.opacity(0.15), radius: 8, y: 4)
            }
        }
    }

    // MARK: - Last Time Reference

    @ViewBuilder
    private var lastTimeReference: some View {
        if let data = lastSessionData {
            HStack(spacing: 4) {
                Image(systemName: "clock.arrow.circlepath")
                    .font(.caption)
                Text("Last time: \(data.reps) reps @ \(data.weight, specifier: "%.0f") lbs")
                    .font(.caption)
            }
            .foregroundStyle(.secondary)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 4)
        }
    }

    // MARK: - Reps & Weight Row

    private var repsAndWeightRow: some View {
        HStack(spacing: 16) {
            // Reps input
            VStack(alignment: .leading, spacing: 6) {
                Text("Reps")
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundStyle(.secondary)

                HStack(spacing: 8) {
                    Button {
                        onQuickIncrement(.reps(amount: -1))
                    } label: {
                        Image(systemName: "minus.circle.fill")
                            .font(.title2)
                            .foregroundStyle(.secondary)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Decrease reps by 1")

                    TextField("0", text: $reps)
                        .font(.system(size: 28, weight: .bold, design: .rounded))
                        .multilineTextAlignment(.center)
                        .keyboardType(.numberPad)
                        .frame(minWidth: 50)
                        .textFieldStyle(.roundedBorder)
                        .focused($focusedField, equals: .reps)

                    Button {
                        onQuickIncrement(.reps(amount: 1))
                    } label: {
                        Image(systemName: "plus.circle.fill")
                            .font(.title2)
                            .foregroundStyle(.accentColor)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Increase reps by 1")
                }
            }

            // Weight input
            VStack(alignment: .leading, spacing: 6) {
                Text("Weight (lbs)")
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundStyle(.secondary)

                HStack(spacing: 8) {
                    Button {
                        onQuickIncrement(.weight(amount: -5))
                    } label: {
                        Text("-5")
                            .font(.callout)
                            .fontWeight(.bold)
                            .foregroundStyle(.white)
                            .frame(width: 36, height: 36)
                            .background(Color.secondary.opacity(0.6), in: Circle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Decrease weight by 5 pounds")

                    TextField("0", text: $weight)
                        .font(.system(size: 28, weight: .bold, design: .rounded))
                        .multilineTextAlignment(.center)
                        .keyboardType(.decimalPad)
                        .frame(minWidth: 60)
                        .textFieldStyle(.roundedBorder)
                        .focused($focusedField, equals: .weight)

                    Button {
                        onQuickIncrement(.weight(amount: 5))
                    } label: {
                        Text("+5")
                            .font(.callout)
                            .fontWeight(.bold)
                            .foregroundStyle(.white)
                            .frame(width: 36, height: 36)
                            .background(Color.accentColor, in: Circle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Increase weight by 5 pounds")
                }
            }
        }
    }

    // MARK: - Log Set Button

    private var logSetButton: some View {
        let isValid = !exerciseName.trimmingCharacters(in: .whitespaces).isEmpty
            && (!reps.isEmpty || !weight.isEmpty)

        return Button {
            isShowingSuggestions = false
            focusedField = nil
            onLogSet()
        } label: {
            Text("LOG SET")
                .font(.title3)
                .fontWeight(.bold)
                .tracking(2)
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
                .background(
                    isValid ? Color.accentColor : Color.secondary.opacity(0.4),
                    in: RoundedRectangle(cornerRadius: 14)
                )
        }
        .buttonStyle(.plain)
        .sensoryFeedback(.success, trigger: exerciseName) // haptic on set logged
        .disabled(!isValid)
        .accessibilityLabel("Log set")
        .accessibilityHint(isValid ? "Double-tap to log this set" : "Enter an exercise name and reps or weight first")
    }
}

// MARK: - Array Extension

private extension Array where Element: Hashable {
    func uniqued() -> [Element] {
        var seen = Set<Element>()
        return filter { seen.insert($0).inserted }
    }
}

// MARK: - Previews

#Preview("Exercise Log - Empty") {
    ExerciseLogView(
        exerciseName: .constant(""),
        reps: .constant(""),
        weight: .constant(""),
        lastSessionData: nil,
        recentExercises: ["Bench Press", "Squat", "Deadlift", "Pull-ups", "Overhead Press"],
        onLogSet: {},
        onQuickIncrement: { _ in }
    )
}

#Preview("Exercise Log - Filled") {
    ExerciseLogView(
        exerciseName: .constant("Bench Press"),
        reps: .constant("10"),
        weight: .constant("155"),
        lastSessionData: (reps: 10, weight: 150.0),
        recentExercises: ["Bench Press", "Squat", "Deadlift"],
        onLogSet: {},
        onQuickIncrement: { _ in }
    )
}
