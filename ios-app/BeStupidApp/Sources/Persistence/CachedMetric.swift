import Foundation
import SwiftData

@Model
final class CachedMetric {

    /// The date of this metric data point.
    var date: Date

    /// The metric field as a raw string (e.g. "weight", "sleep").
    /// Stored as `String` because SwiftData predicates cannot filter on custom enums.
    var field: String

    /// The numeric value of the metric.
    var value: Double

    /// The source of the metric (e.g. "manual", "garmin", "parsed").
    var source: String

    /// Composite key for uniqueness: "yyyy-MM-dd:fieldRawValue".
    /// Ensures only one value per field per day.
    @Attribute(.unique) var compositeKey: String

    // MARK: - Init

    init(from dataPoint: MetricDataPoint) {
        self.date = dataPoint.date
        self.field = dataPoint.field.rawValue
        self.value = dataPoint.value
        self.source = dataPoint.source.rawValue
        self.compositeKey = Self.makeCompositeKey(date: dataPoint.date, field: dataPoint.field)
    }

    // MARK: - Conversion

    /// Converts back to the domain `MetricDataPoint` model.
    func toMetricDataPoint() -> MetricDataPoint {
        MetricDataPoint(
            date: date,
            field: MetricField(rawValue: field) ?? .weight,
            value: value,
            source: MetricSource(rawValue: source) ?? .manual
        )
    }

    // MARK: - Key Generation

    /// Generates the composite key from a date and metric field.
    static func makeCompositeKey(date: Date, field: MetricField) -> String {
        let dateString = DateFormatting.dailyLogFormatter.string(from: date)
        return "\(dateString):\(field.rawValue)"
    }
}
