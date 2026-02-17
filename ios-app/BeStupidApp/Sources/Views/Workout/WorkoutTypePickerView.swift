import SwiftUI

// MARK: - WorkoutTypeInfo

/// Describes a built-in workout type with its display metadata.
struct WorkoutTypeInfo: Identifiable, Sendable {
    let id: String
    let name: String
    let icon: String
    let color: Color
    let isBuiltIn: Bool

    init(name: String, icon: String, color: Color, isBuiltIn: Bool = true) {
        self.id = name
        self.name = name
        self.icon = icon
        self.color = color
        self.isBuiltIn = isBuiltIn
    }

    /// The built-in workout types for triathlon training.
    static let builtInTypes: [WorkoutTypeInfo] = [
        WorkoutTypeInfo(name: "Swim", icon: "figure.pool.swim", color: .blue),
        WorkoutTypeInfo(name: "Bike", icon: "figure.outdoor.cycle", color: .green),
        WorkoutTypeInfo(name: "Run", icon: "figure.run", color: .orange),
        WorkoutTypeInfo(name: "Strength", icon: "figure.strengthtraining.traditional", color: .purple),
        WorkoutTypeInfo(name: "Brick", icon: "figure.run.circle", color: .teal),
        WorkoutTypeInfo(name: "Recovery", icon: "figure.mind.and.body", color: .gray),
    ]

    /// Returns the WorkoutTypeInfo for a given name, falling back to a generic custom type.
    static func info(for name: String) -> WorkoutTypeInfo {
        if let builtIn = builtInTypes.first(where: { $0.name.lowercased() == name.lowercased() }) {
            return builtIn
        }
        return WorkoutTypeInfo(name: name, icon: "figure.mixed.cardio", color: .indigo, isBuiltIn: false)
    }

    /// Whether a given workout type string is a cardio-oriented workout.
    static func isCardioType(_ type: String) -> Bool {
        let cardioTypes: Set<String> = ["swim", "bike", "run", "brick", "recovery"]
        return cardioTypes.contains(type.lowercased())
    }
}

// MARK: - WorkoutTypePickerView

/// Grid-based picker for selecting a workout type, with support for custom types.
struct WorkoutTypePickerView: View {
    let onSelect: (String) -> Void
    @State private var customTypeName: String = ""
    @State private var isAddingCustom: Bool = false
    @State private var customTypes: [WorkoutTypeInfo] = []

    private let columns = [
        GridItem(.flexible(), spacing: 16),
        GridItem(.flexible(), spacing: 16),
    ]

    var body: some View {
        ScrollView {
            LazyVGrid(columns: columns, spacing: 16) {
                // Built-in types
                ForEach(WorkoutTypeInfo.builtInTypes) { typeInfo in
                    WorkoutTypeCard(typeInfo: typeInfo) {
                        onSelect(typeInfo.name)
                    }
                }

                // Custom types
                ForEach(customTypes) { typeInfo in
                    WorkoutTypeCard(typeInfo: typeInfo) {
                        onSelect(typeInfo.name)
                    }
                }

                // Add custom type card
                addCustomCard
            }
            .padding(.horizontal)
        }
        .alert("New Workout Type", isPresented: $isAddingCustom) {
            TextField("Type name", text: $customTypeName)
                .textInputAutocapitalization(.words)
            Button("Add") {
                addCustomType()
            }
            .disabled(customTypeName.trimmingCharacters(in: .whitespaces).isEmpty)
            Button("Cancel", role: .cancel) {
                customTypeName = ""
            }
        } message: {
            Text("Enter a name for your custom workout type.")
        }
    }

    // MARK: - Add Custom Card

    private var addCustomCard: some View {
        Button {
            customTypeName = ""
            isAddingCustom = true
        } label: {
            VStack(spacing: 12) {
                Image(systemName: "plus.circle.fill")
                    .font(.system(size: 36))
                    .foregroundStyle(.secondary)

                Text("Custom")
                    .font(.headline)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity)
            .frame(height: 120)
            .background(
                RoundedRectangle(cornerRadius: 16)
                    .strokeBorder(.secondary.opacity(0.3), style: StrokeStyle(lineWidth: 2, dash: [8]))
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Add custom workout type")
    }

    // MARK: - Actions

    private func addCustomType() {
        let name = customTypeName.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }

        // Prevent duplicates
        let allNames = WorkoutTypeInfo.builtInTypes.map(\.name) + customTypes.map(\.name)
        guard !allNames.contains(where: { $0.lowercased() == name.lowercased() }) else {
            customTypeName = ""
            return
        }

        let newType = WorkoutTypeInfo(
            name: name,
            icon: "figure.mixed.cardio",
            color: .indigo,
            isBuiltIn: false
        )
        customTypes.append(newType)
        customTypeName = ""
        onSelect(name)
    }
}

// MARK: - WorkoutTypeCard

/// A single tappable card representing a workout type in the picker grid.
struct WorkoutTypeCard: View {
    let typeInfo: WorkoutTypeInfo
    let onTap: () -> Void

    @State private var isPressed: Bool = false

    var body: some View {
        Button(action: onTap) {
            VStack(spacing: 12) {
                Image(systemName: typeInfo.icon)
                    .font(.system(size: 36))
                    .foregroundStyle(typeInfo.color)

                Text(typeInfo.name)
                    .font(.headline)
                    .foregroundStyle(.primary)
            }
            .frame(maxWidth: .infinity)
            .frame(height: 120)
            .background(typeInfo.color.opacity(0.1), in: RoundedRectangle(cornerRadius: 16))
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .strokeBorder(typeInfo.color.opacity(0.3), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .scaleEffect(isPressed ? 0.95 : 1.0)
        .animation(.easeInOut(duration: 0.15), value: isPressed)
        .accessibilityLabel("\(typeInfo.name) workout")
        .accessibilityAddTraits(.isButton)
    }
}

// MARK: - Previews

#Preview("Workout Type Picker") {
    NavigationStack {
        WorkoutTypePickerView { type in
            print("Selected: \(type)")
        }
        .navigationTitle("Start Workout")
    }
}

#Preview("Workout Type Card - Swim") {
    WorkoutTypeCard(
        typeInfo: WorkoutTypeInfo(name: "Swim", icon: "figure.pool.swim", color: .blue),
        onTap: {}
    )
    .frame(width: 170, height: 120)
    .padding()
}

#Preview("Workout Type Card - Strength") {
    WorkoutTypeCard(
        typeInfo: WorkoutTypeInfo(name: "Strength", icon: "figure.strengthtraining.traditional", color: .purple),
        onTap: {}
    )
    .frame(width: 170, height: 120)
    .padding()
}
