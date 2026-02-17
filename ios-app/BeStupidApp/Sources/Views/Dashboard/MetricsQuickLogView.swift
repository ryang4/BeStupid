import SwiftUI

/// A bottom sheet for quickly logging a single metric value.
///
/// Adapts its input interface based on the metric field:
/// - Weight: decimal number pad
/// - Sleep: decimal number pad with colon support
/// - Mood/Energy/Focus/Sleep Quality: 1-10 slider with emoji indicators
struct MetricsQuickLogView: View {
    let field: MetricField
    @Binding var value: String
    let onSave: (String) -> Void

    @Environment(\.dismiss) private var dismiss
    @FocusState private var isInputFocused: Bool
    @State private var sliderValue: Double = 5.0

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // Header with icon and field name
                fieldHeader

                // Input area varies by field type
                inputSection

                Spacer()

                // Save button
                Button {
                    let finalValue = isSliderField ? String(format: "%.0f", sliderValue) : value
                    onSave(finalValue)
                    dismiss()
                } label: {
                    Text("Save")
                        .fontWeight(.semibold)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                }
                .buttonStyle(.borderedProminent)
                .disabled(isSliderField ? false : value.trimmingCharacters(in: .whitespaces).isEmpty)
            }
            .padding(24)
            .navigationTitle("Log \(field.displayName)")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
            .onAppear {
                if isSliderField {
                    sliderValue = Double(value) ?? 5.0
                }
            }
        }
    }

    // MARK: - Field Header

    private var fieldHeader: some View {
        VStack(spacing: 8) {
            Image(systemName: iconForField)
                .font(.system(size: 36))
                .foregroundStyle(colorForField)
                .padding(12)
                .background(colorForField.opacity(0.1), in: Circle())

            Text(field.displayName)
                .font(.headline)

            Text(hintForField)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    // MARK: - Input Section

    @ViewBuilder
    private var inputSection: some View {
        if isSliderField {
            sliderInput
        } else {
            numericInput
        }
    }

    // Slider-based input for 1-10 scale metrics
    private var sliderInput: some View {
        VStack(spacing: 16) {
            // Current value display with emoji
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text(emojiForSliderValue)
                    .font(.system(size: 48))

                Text(String(format: "%.0f", sliderValue))
                    .font(.system(size: 56, weight: .bold, design: .rounded))

                Text("/10")
                    .font(.title3)
                    .foregroundStyle(.secondary)
            }

            // Slider
            VStack(spacing: 4) {
                Slider(value: $sliderValue, in: 1...10, step: 1) {
                    Text(field.displayName)
                } minimumValueLabel: {
                    Text("1")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                } maximumValueLabel: {
                    Text("10")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                .tint(colorForSliderValue)

                Text(labelForSliderValue)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .animation(.easeInOut(duration: 0.15), value: sliderValue)
            }
        }
    }

    // Numeric text input for weight and sleep
    private var numericInput: some View {
        VStack(spacing: 12) {
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                TextField(placeholderForField, text: $value)
                    .keyboardType(keyboardTypeForField)
                    .font(.system(size: 48, weight: .bold, design: .rounded))
                    .multilineTextAlignment(.center)
                    .focused($isInputFocused)

                Text(field.unitSuffix)
                    .font(.title3)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity)

            if field == .sleep {
                Text("Enter as decimal (7.5) or hours:minutes (7:30)")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }
        }
        .onAppear {
            isInputFocused = true
        }
    }

    // MARK: - Field Configuration

    private var isSliderField: Bool {
        switch field {
        case .moodAM, .moodPM, .energy, .focus, .sleepQuality:
            return true
        default:
            return false
        }
    }

    private var iconForField: String {
        switch field {
        case .weight: return "scalemass"
        case .sleep: return "bed.double"
        case .sleepQuality: return "moon.stars"
        case .moodAM: return "sun.horizon"
        case .moodPM: return "moon"
        case .energy: return "bolt.fill"
        case .focus: return "scope"
        default: return "pencil.line"
        }
    }

    private var colorForField: Color {
        switch field {
        case .weight: return .blue
        case .sleep: return .indigo
        case .sleepQuality: return .purple
        case .moodAM: return .orange
        case .moodPM: return .pink
        case .energy: return .green
        case .focus: return .teal
        default: return .blue
        }
    }

    private var hintForField: String {
        switch field {
        case .weight: return "Log your morning weight"
        case .sleep: return "How many hours did you sleep?"
        case .sleepQuality: return "Rate your sleep quality"
        case .moodAM: return "How are you feeling this morning?"
        case .moodPM: return "How was your afternoon/evening?"
        case .energy: return "Rate your energy level"
        case .focus: return "Rate your mental focus"
        default: return "Enter the value"
        }
    }

    private var placeholderForField: String {
        switch field {
        case .weight: return "185.0"
        case .sleep: return "7.5"
        default: return "0"
        }
    }

    private var keyboardTypeForField: UIKeyboardType {
        switch field {
        case .weight: return .decimalPad
        case .sleep: return .decimalPad
        default: return .numberPad
        }
    }

    // MARK: - Slider Value Helpers

    private var emojiForSliderValue: String {
        switch Int(sliderValue) {
        case 1...2: return "😫"
        case 3...4: return "😕"
        case 5...6: return "😐"
        case 7...8: return "😊"
        case 9...10: return "🤩"
        default: return "😐"
        }
    }

    private var labelForSliderValue: String {
        switch Int(sliderValue) {
        case 1...2: return "Very Low"
        case 3...4: return "Below Average"
        case 5...6: return "Average"
        case 7...8: return "Good"
        case 9...10: return "Excellent"
        default: return ""
        }
    }

    private var colorForSliderValue: Color {
        switch Int(sliderValue) {
        case 1...3: return .red
        case 4...5: return .orange
        case 6...7: return .yellow
        case 8...9: return .green
        case 10: return .mint
        default: return .blue
        }
    }
}

// MARK: - Preview

#Preview("Weight Input") {
    MetricsQuickLogView(
        field: .weight,
        value: .constant("185.4"),
        onSave: { _ in }
    )
}

#Preview("Sleep Input") {
    MetricsQuickLogView(
        field: .sleep,
        value: .constant("7.2"),
        onSave: { _ in }
    )
}

#Preview("Mood Slider") {
    MetricsQuickLogView(
        field: .moodAM,
        value: .constant("7"),
        onSave: { _ in }
    )
}

#Preview("Energy Slider") {
    MetricsQuickLogView(
        field: .energy,
        value: .constant("8"),
        onSave: { _ in }
    )
}
