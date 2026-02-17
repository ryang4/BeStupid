import SwiftUI

/// A tappable card displaying a single metric with its value, unit, and trend direction.
///
/// Used in the Dashboard metrics grid to show weight, sleep, mood, energy at a glance.
/// Tapping opens the quick-log sheet for that metric.
struct MetricBadge: View {
    let title: String
    let value: String
    let unit: String?
    let trend: TrendDirection
    let field: MetricField
    let color: Color
    let onTap: (() -> Void)?

    init(
        title: String,
        value: String,
        unit: String? = nil,
        trend: TrendDirection = .insufficient,
        field: MetricField = .weight,
        color: Color = .blue,
        onTap: (() -> Void)? = nil
    ) {
        self.title = title
        self.value = value
        self.unit = unit
        self.trend = trend
        self.field = field
        self.color = color
        self.onTap = onTap
    }

    var body: some View {
        Button {
            onTap?()
        } label: {
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text(title)
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundStyle(.secondary)

                    Spacer()

                    TrendIndicator(direction: trend, field: field, size: 12)
                }

                HStack(alignment: .firstTextBaseline, spacing: 2) {
                    if value.isEmpty {
                        Text("--")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundStyle(.tertiary)
                    } else {
                        Text(value)
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundStyle(.primary)
                    }

                    if let unit, !value.isEmpty {
                        Text(unit)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(color.opacity(0.08), in: RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .strokeBorder(color.opacity(0.15), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(title): \(value.isEmpty ? "not logged" : value) \(unit ?? "")")
        .accessibilityHint(onTap != nil ? "Double tap to log \(title.lowercased())" : "")
    }
}

// MARK: - Preview

#Preview("Metrics Grid") {
    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
        MetricBadge(
            title: "Weight",
            value: "185.4",
            unit: "lbs",
            trend: .down,
            field: .weight,
            color: .blue,
            onTap: {}
        )

        MetricBadge(
            title: "Sleep",
            value: "7.2",
            unit: "hrs",
            trend: .stable,
            field: .sleep,
            color: .indigo,
            onTap: {}
        )

        MetricBadge(
            title: "Mood",
            value: "7",
            unit: "/10",
            trend: .up,
            field: .moodAM,
            color: .orange,
            onTap: {}
        )

        MetricBadge(
            title: "Energy",
            value: "8",
            unit: "/10",
            trend: .up,
            field: .energy,
            color: .green,
            onTap: {}
        )
    }
    .padding()
}

#Preview("Empty Value") {
    MetricBadge(
        title: "Weight",
        value: "",
        unit: "lbs",
        trend: .insufficient,
        field: .weight,
        color: .blue,
        onTap: {}
    )
    .frame(width: 170)
    .padding()
}
