import SwiftUI

struct HealthKitSettingsView: View {
    let isAuthorized: Bool
    @Binding var syncWorkouts: Bool
    @Binding var importSleep: Bool
    @Binding var importWeight: Bool
    @Binding var importHeartRate: Bool
    let onRequestAccess: () -> Void

    var body: some View {
        Form {
            authorizationSection
            if isAuthorized {
                exportSection
                importSection
            }
            dataTypesInfoSection
        }
        .navigationTitle("Health Data")
        .navigationBarTitleDisplayMode(.inline)
    }

    // MARK: - Authorization

    private var authorizationSection: some View {
        Section {
            HStack(spacing: 12) {
                Image(systemName: isAuthorized ? "heart.circle.fill" : "heart.slash.circle")
                    .font(.largeTitle)
                    .foregroundStyle(isAuthorized ? .red : .secondary)
                    .symbolEffect(.pulse, options: .repeating, isActive: !isAuthorized)

                VStack(alignment: .leading, spacing: 4) {
                    Text(isAuthorized ? "Connected to HealthKit" : "Not Connected")
                        .font(.headline)

                    Text(isAuthorized
                        ? "BeStupid can read and write health data."
                        : "Grant access to sync workout and health data.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(.vertical, 4)

            if !isAuthorized {
                Button {
                    onRequestAccess()
                } label: {
                    HStack {
                        Spacer()
                        Label("Connect to Apple Health", systemImage: "heart.fill")
                            .font(.body.weight(.semibold))
                        Spacer()
                    }
                }
                .buttonStyle(.borderedProminent)
                .tint(.red)
                .listRowInsets(EdgeInsets(top: 8, leading: 16, bottom: 8, trailing: 16))
            }
        } header: {
            Text("Authorization")
        } footer: {
            if !isAuthorized {
                Text("You can change HealthKit permissions at any time in Settings > Privacy & Security > Health > BeStupid.")
            }
        }
    }

    // MARK: - Export (Write to HealthKit)

    private var exportSection: some View {
        Section {
            Toggle(isOn: $syncWorkouts) {
                HealthToggleLabel(
                    icon: "figure.run",
                    color: .green,
                    title: "Sync Workouts",
                    description: "Write completed workouts to Apple Health"
                )
            }
        } header: {
            Text("Export to Health")
        } footer: {
            Text("When enabled, finished workout sessions (swim, bike, run, strength) are saved to Apple Health with duration, distance, and heart rate data.")
        }
    }

    // MARK: - Import (Read from HealthKit)

    private var importSection: some View {
        Section {
            Toggle(isOn: $importSleep) {
                HealthToggleLabel(
                    icon: "moon.zzz.fill",
                    color: .indigo,
                    title: "Import Sleep",
                    description: "Read sleep stages and duration"
                )
            }

            Toggle(isOn: $importWeight) {
                HealthToggleLabel(
                    icon: "scalemass.fill",
                    color: .blue,
                    title: "Import Weight",
                    description: "Read body mass measurements"
                )
            }

            Toggle(isOn: $importHeartRate) {
                HealthToggleLabel(
                    icon: "heart.fill",
                    color: .red,
                    title: "Import Heart Rate",
                    description: "Read resting and workout heart rate"
                )
            }
        } header: {
            Text("Import from Health")
        } footer: {
            Text("Imported data is used to auto-fill daily log metrics and power dashboard charts. Data stays on your device.")
        }
    }

    // MARK: - Data Types Info

    private var dataTypesInfoSection: some View {
        Section {
            VStack(alignment: .leading, spacing: 12) {
                Text("Data BeStupid accesses:")
                    .font(.subheadline.weight(.semibold))

                DataTypeRow(icon: "figure.run", label: "Workouts", access: "Read & Write")
                DataTypeRow(icon: "heart.fill", label: "Heart Rate", access: "Read")
                DataTypeRow(icon: "moon.zzz.fill", label: "Sleep Analysis", access: "Read")
                DataTypeRow(icon: "scalemass.fill", label: "Body Mass", access: "Read & Write")
                DataTypeRow(icon: "flame.fill", label: "Active Energy", access: "Read & Write")
                DataTypeRow(icon: "shoeprints.fill", label: "Steps", access: "Read")
                DataTypeRow(icon: "waveform.path.ecg", label: "Resting Heart Rate", access: "Read")
                DataTypeRow(icon: "arrow.left.and.right", label: "Distance (Run/Bike/Swim)", access: "Read")
            }
        } header: {
            Text("Data Access Details")
        }
    }
}

// MARK: - HealthToggleLabel

private struct HealthToggleLabel: View {
    let icon: String
    let color: Color
    let title: String
    let description: String

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(.white)
                .frame(width: 30, height: 30)
                .background(color, in: RoundedRectangle(cornerRadius: 7))

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.body)
                Text(description)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

// MARK: - DataTypeRow

private struct DataTypeRow: View {
    let icon: String
    let label: String
    let access: String

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.caption)
                .foregroundStyle(.secondary)
                .frame(width: 20, alignment: .center)

            Text(label)
                .font(.caption)

            Spacer()

            Text(access)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(Color(.tertiarySystemFill), in: Capsule())
        }
    }
}

// MARK: - Preview

#Preview("HealthKit - Connected") {
    @Previewable @State var syncWorkouts = true
    @Previewable @State var importSleep = true
    @Previewable @State var importWeight = true
    @Previewable @State var importHeartRate = true

    NavigationStack {
        HealthKitSettingsView(
            isAuthorized: true,
            syncWorkouts: $syncWorkouts,
            importSleep: $importSleep,
            importWeight: $importWeight,
            importHeartRate: $importHeartRate,
            onRequestAccess: {}
        )
    }
}

#Preview("HealthKit - Not Connected") {
    @Previewable @State var syncWorkouts = true
    @Previewable @State var importSleep = true
    @Previewable @State var importWeight = true
    @Previewable @State var importHeartRate = true

    NavigationStack {
        HealthKitSettingsView(
            isAuthorized: false,
            syncWorkouts: $syncWorkouts,
            importSleep: $importSleep,
            importWeight: $importWeight,
            importHeartRate: $importHeartRate,
            onRequestAccess: {}
        )
    }
}
