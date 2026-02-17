import SwiftUI

// MARK: - WorkoutTimerView

/// Large monospace timer display for the active workout.
/// Pulses subtly when the workout is active and dims when paused.
struct WorkoutTimerView: View {
    let elapsedSeconds: Int
    let isActive: Bool

    @State private var isPulsing: Bool = false

    var body: some View {
        Text(formattedTime)
            .font(.system(size: 56, weight: .bold, design: .monospaced))
            .foregroundStyle(isActive ? Color.accentColor : Color.secondary)
            .contentTransition(.numericText())
            .scaleEffect(isPulsing ? 1.02 : 1.0)
            .animation(.easeInOut(duration: 1.0).repeatForever(autoreverses: true), value: isPulsing)
            .onChange(of: isActive, initial: true) { _, newValue in
                isPulsing = newValue
            }
            .accessibilityLabel("Elapsed time: \(accessibilityTime)")
    }

    // MARK: - Formatting

    private var formattedTime: String {
        let hours = elapsedSeconds / 3600
        let minutes = (elapsedSeconds % 3600) / 60
        let seconds = elapsedSeconds % 60

        if hours > 0 {
            return String(format: "%d:%02d:%02d", hours, minutes, seconds)
        }
        return String(format: "%02d:%02d", minutes, seconds)
    }

    private var accessibilityTime: String {
        let hours = elapsedSeconds / 3600
        let minutes = (elapsedSeconds % 3600) / 60
        let seconds = elapsedSeconds % 60

        var components: [String] = []
        if hours > 0 { components.append("\(hours) hour\(hours == 1 ? "" : "s")") }
        if minutes > 0 { components.append("\(minutes) minute\(minutes == 1 ? "" : "s")") }
        components.append("\(seconds) second\(seconds == 1 ? "" : "s")")
        return components.joined(separator: ", ")
    }
}

// MARK: - RestTimerOverlay

/// Overlay shown during rest periods with a large countdown and skip button.
struct RestTimerOverlay: View {
    let restTimeRemaining: Int
    let onSkip: () -> Void

    var body: some View {
        VStack(spacing: 24) {
            Text("REST")
                .font(.title3)
                .fontWeight(.semibold)
                .foregroundStyle(.secondary)
                .textCase(.uppercase)
                .tracking(4)

            Text(formattedRest)
                .font(.system(size: 72, weight: .bold, design: .monospaced))
                .foregroundStyle(restColor)
                .contentTransition(.numericText())

            Button(action: onSkip) {
                Label("Skip Rest", systemImage: "forward.fill")
                    .font(.headline)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 32)
                    .padding(.vertical, 14)
                    .background(Color.secondary.opacity(0.6), in: Capsule())
            }
            .buttonStyle(.plain)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(.ultraThinMaterial)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Rest timer, \(restTimeRemaining) seconds remaining")
        .accessibilityAddTraits(.updatesFrequently)
    }

    // MARK: - Formatting

    private var formattedRest: String {
        let minutes = restTimeRemaining / 60
        let seconds = restTimeRemaining % 60
        return String(format: "%d:%02d", minutes, seconds)
    }

    private var restColor: Color {
        if restTimeRemaining <= 5 {
            return .red
        } else if restTimeRemaining <= 15 {
            return .orange
        } else {
            return .primary
        }
    }
}

// MARK: - Previews

#Preview("Timer - Active") {
    WorkoutTimerView(elapsedSeconds: 2723, isActive: true)
        .padding()
}

#Preview("Timer - Paused") {
    WorkoutTimerView(elapsedSeconds: 1563, isActive: false)
        .padding()
}

#Preview("Timer - Hours") {
    WorkoutTimerView(elapsedSeconds: 4523, isActive: true)
        .padding()
}

#Preview("Rest Overlay") {
    RestTimerOverlay(restTimeRemaining: 47, onSkip: {})
}

#Preview("Rest Overlay - Low") {
    RestTimerOverlay(restTimeRemaining: 3, onSkip: {})
}
