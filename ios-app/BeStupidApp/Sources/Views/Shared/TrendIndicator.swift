import SwiftUI

/// Displays a directional trend arrow with contextual coloring.
///
/// The color adapts to the metric context: for weight, a downward trend
/// is positive (green), while for sleep/mood/energy, an upward trend
/// is positive.
struct TrendIndicator: View {
    let direction: TrendDirection
    let field: MetricField?
    let size: CGFloat

    init(direction: TrendDirection, field: MetricField? = nil, size: CGFloat = 14) {
        self.direction = direction
        self.field = field
        self.size = size
    }

    private var resolvedColor: Color {
        if let field {
            return direction.color(for: field)
        }
        return direction.color
    }

    var body: some View {
        Image(systemName: direction.systemImage)
            .font(.system(size: size, weight: .semibold))
            .foregroundStyle(resolvedColor)
            .accessibilityLabel(accessibilityDescription)
    }

    private var accessibilityDescription: String {
        switch direction {
        case .up: return "Trending up"
        case .down: return "Trending down"
        case .stable: return "Stable trend"
        case .insufficient: return "Not enough data for trend"
        }
    }
}

// MARK: - Preview

#Preview("All Trends") {
    VStack(spacing: 20) {
        HStack(spacing: 24) {
            VStack {
                Text("Weight Up").font(.caption)
                TrendIndicator(direction: .up, field: .weight, size: 20)
            }
            VStack {
                Text("Weight Down").font(.caption)
                TrendIndicator(direction: .down, field: .weight, size: 20)
            }
            VStack {
                Text("Sleep Up").font(.caption)
                TrendIndicator(direction: .up, field: .sleep, size: 20)
            }
            VStack {
                Text("Stable").font(.caption)
                TrendIndicator(direction: .stable, size: 20)
            }
            VStack {
                Text("Insufficient").font(.caption)
                TrendIndicator(direction: .insufficient, size: 20)
            }
        }
    }
    .padding()
}
