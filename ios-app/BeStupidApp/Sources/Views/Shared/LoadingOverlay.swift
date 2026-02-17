import SwiftUI

/// A semi-transparent overlay with a spinner and message, used during
/// loading states like git sync operations.
struct LoadingOverlay: View {
    let message: String
    let isVisible: Bool

    var body: some View {
        if isVisible {
            ZStack {
                Color.black.opacity(0.3)
                    .ignoresSafeArea()

                VStack(spacing: 16) {
                    ProgressView()
                        .controlSize(.large)

                    Text(message)
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundStyle(.secondary)
                }
                .padding(24)
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
            }
            .transition(.opacity)
            .animation(.easeInOut(duration: 0.25), value: isVisible)
        }
    }
}

// MARK: - Preview

#Preview("Visible") {
    ZStack {
        VStack {
            Text("Background Content")
                .font(.largeTitle)
            Text("This simulates content behind the overlay")
        }

        LoadingOverlay(message: "Syncing with git...", isVisible: true)
    }
}

#Preview("Hidden") {
    ZStack {
        VStack {
            Text("Background Content")
                .font(.largeTitle)
            Text("No overlay shown")
        }

        LoadingOverlay(message: "Syncing...", isVisible: false)
    }
}
