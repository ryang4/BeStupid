import SwiftUI

// MARK: - HeartRateZone

/// Heart rate training zones for triathlon training.
enum HeartRateZone: Sendable {
    case recovery    // < 120 bpm
    case aerobic     // 120-140 bpm
    case tempo       // 140-160 bpm
    case threshold   // 160-175 bpm
    case max         // 175+ bpm

    init(bpm: Int) {
        switch bpm {
        case ..<120:
            self = .recovery
        case 120..<140:
            self = .aerobic
        case 140..<160:
            self = .tempo
        case 160..<175:
            self = .threshold
        default:
            self = .max
        }
    }

    var name: String {
        switch self {
        case .recovery: return "Recovery"
        case .aerobic: return "Aerobic"
        case .tempo: return "Tempo"
        case .threshold: return "Threshold"
        case .max: return "Max"
        }
    }

    var zoneNumber: Int {
        switch self {
        case .recovery: return 1
        case .aerobic: return 2
        case .tempo: return 3
        case .threshold: return 4
        case .max: return 5
        }
    }

    var color: Color {
        switch self {
        case .recovery: return .gray
        case .aerobic: return .green
        case .tempo: return .yellow
        case .threshold: return .orange
        case .max: return .red
        }
    }

    var range: String {
        switch self {
        case .recovery: return "< 120"
        case .aerobic: return "120-140"
        case .tempo: return "140-160"
        case .threshold: return "160-175"
        case .max: return "175+"
        }
    }
}

// MARK: - CardioTrackingView

/// Simplified tracking view for cardio workouts (swim, bike, run).
/// Displays distance input with unit picker, elapsed time, heart rate with zone indicator,
/// and a live pace calculation.
struct CardioTrackingView: View {
    @Binding var distance: String
    @Binding var distanceUnit: DistanceUnit
    let elapsedSeconds: Int
    let currentHeartRate: Int?

    var body: some View {
        VStack(spacing: 24) {
            timerSection
            heartRateSection
            distanceSection
            paceSection
        }
        .padding(.horizontal)
    }

    // MARK: - Timer Section

    private var timerSection: some View {
        WorkoutTimerView(elapsedSeconds: elapsedSeconds, isActive: true)
    }

    // MARK: - Heart Rate Section

    @ViewBuilder
    private var heartRateSection: some View {
        if let bpm = currentHeartRate {
            let zone = HeartRateZone(bpm: bpm)

            VStack(spacing: 8) {
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Image(systemName: "heart.fill")
                        .foregroundStyle(zone.color)
                        .symbolEffect(.pulse, options: .repeating)
                    Text("\(bpm)")
                        .font(.system(size: 40, weight: .bold, design: .rounded))
                    Text("bpm")
                        .font(.headline)
                        .foregroundStyle(.secondary)
                }

                HeartRateZoneBar(currentZone: zone)
            }
            .padding()
            .background(zone.color.opacity(0.1), in: RoundedRectangle(cornerRadius: 16))
            .accessibilityElement(children: .combine)
            .accessibilityLabel("Heart rate \(bpm) beats per minute, zone \(zone.zoneNumber) \(zone.name)")
        } else {
            VStack(spacing: 8) {
                HStack(spacing: 4) {
                    Image(systemName: "heart.slash")
                        .foregroundStyle(.secondary)
                    Text("No Heart Rate Data")
                        .font(.headline)
                        .foregroundStyle(.secondary)
                }
                Text("Connect a heart rate monitor for live data")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }
            .padding()
            .background(Color.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 16))
        }
    }

    // MARK: - Distance Section

    private var distanceSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Distance")
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundStyle(.secondary)

            HStack(spacing: 12) {
                TextField("0.0", text: $distance)
                    .font(.system(size: 32, weight: .bold, design: .rounded))
                    .keyboardType(.decimalPad)
                    .textFieldStyle(.roundedBorder)
                    .frame(maxWidth: .infinity)

                Picker("Unit", selection: $distanceUnit) {
                    ForEach(DistanceUnit.allCases, id: \.self) { unit in
                        Text(unit.displayName).tag(unit)
                    }
                }
                .pickerStyle(.menu)
                .tint(.accentColor)
            }
        }
    }

    // MARK: - Pace Section

    @ViewBuilder
    private var paceSection: some View {
        if let paceString = computedPace {
            HStack(spacing: 8) {
                Image(systemName: "speedometer")
                    .foregroundStyle(.accentColor)
                Text("Pace: \(paceString)")
                    .font(.title3)
                    .fontWeight(.semibold)
            }
            .padding()
            .frame(maxWidth: .infinity)
            .background(Color.accentColor.opacity(0.1), in: RoundedRectangle(cornerRadius: 12))
        }
    }

    // MARK: - Pace Computation

    private var computedPace: String? {
        guard let dist = Double(distance), dist > 0, elapsedSeconds > 0 else { return nil }

        let elapsedMinutes = Double(elapsedSeconds) / 60.0

        switch distanceUnit {
        case .miles:
            let pacePerMile = elapsedMinutes / dist
            return formatPace(pacePerMile, unit: "mi")
        case .kilometers:
            let pacePerKm = elapsedMinutes / dist
            return formatPace(pacePerKm, unit: "km")
        case .meters:
            let km = dist / 1000.0
            guard km > 0 else { return nil }
            let pacePerKm = elapsedMinutes / km
            return formatPace(pacePerKm, unit: "km")
        }
    }

    private func formatPace(_ minutesPerUnit: Double, unit: String) -> String {
        let totalSeconds = Int(minutesPerUnit * 60)
        let mins = totalSeconds / 60
        let secs = totalSeconds % 60
        return String(format: "%d:%02d / %@", mins, secs, unit)
    }
}

// MARK: - HeartRateZoneBar

/// A horizontal bar showing all 5 heart rate zones with the current zone highlighted.
struct HeartRateZoneBar: View {
    let currentZone: HeartRateZone

    private static let allZones: [HeartRateZone] = [.recovery, .aerobic, .tempo, .threshold, .max]

    var body: some View {
        VStack(spacing: 4) {
            HStack(spacing: 2) {
                ForEach(Self.allZones, id: \.zoneNumber) { zone in
                    RoundedRectangle(cornerRadius: 3)
                        .fill(zone.color.opacity(zone.zoneNumber == currentZone.zoneNumber ? 1.0 : 0.25))
                        .frame(height: zone.zoneNumber == currentZone.zoneNumber ? 12 : 8)
                        .animation(.easeInOut(duration: 0.3), value: currentZone.zoneNumber)
                }
            }

            HStack {
                Text("Z\(currentZone.zoneNumber) - \(currentZone.name)")
                    .font(.caption2)
                    .fontWeight(.semibold)
                    .foregroundStyle(currentZone.color)
                Spacer()
                Text(currentZone.range + " bpm")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

// MARK: - Previews

#Preview("Cardio - With HR") {
    CardioTrackingView(
        distance: .constant("3.2"),
        distanceUnit: .constant(.miles),
        elapsedSeconds: 1847,
        currentHeartRate: 148
    )
}

#Preview("Cardio - No HR") {
    CardioTrackingView(
        distance: .constant(""),
        distanceUnit: .constant(.kilometers),
        elapsedSeconds: 452,
        currentHeartRate: nil
    )
}

#Preview("Cardio - Max Zone") {
    CardioTrackingView(
        distance: .constant("1.5"),
        distanceUnit: .constant(.miles),
        elapsedSeconds: 720,
        currentHeartRate: 182
    )
}

#Preview("HR Zone Bar - Aerobic") {
    HeartRateZoneBar(currentZone: .aerobic)
        .padding()
}

#Preview("HR Zone Bar - Threshold") {
    HeartRateZoneBar(currentZone: .threshold)
        .padding()
}
