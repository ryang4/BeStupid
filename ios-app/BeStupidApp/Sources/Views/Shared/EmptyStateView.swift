import SwiftUI

/// A centered empty-state placeholder with icon, title, message, and optional action button.
///
/// Used when content is not yet available -- no daily logs, no workouts scheduled,
/// no metrics recorded, etc.
struct EmptyStateView: View {
    let icon: String
    let title: String
    let message: String
    let actionTitle: String?
    let action: (() -> Void)?

    init(
        icon: String,
        title: String,
        message: String,
        actionTitle: String? = nil,
        action: (() -> Void)? = nil
    ) {
        self.icon = icon
        self.title = title
        self.message = message
        self.actionTitle = actionTitle
        self.action = action
    }

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: icon)
                .font(.system(size: 48))
                .foregroundStyle(.secondary)

            Text(title)
                .font(.title3)
                .fontWeight(.semibold)

            Text(message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 280)

            if let actionTitle, let action {
                Button(action: action) {
                    Text(actionTitle)
                        .fontWeight(.medium)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.regular)
                .padding(.top, 4)
            }
        }
        .padding(32)
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Preview

#Preview("With Action") {
    EmptyStateView(
        icon: "doc.text",
        title: "No Log Today",
        message: "Start tracking your day by creating a new daily log.",
        actionTitle: "Create Log",
        action: {}
    )
}

#Preview("Without Action") {
    EmptyStateView(
        icon: "chart.xyaxis.line",
        title: "No Data Yet",
        message: "Metrics will appear here once you start logging."
    )
}
