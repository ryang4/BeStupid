import Foundation

enum DateFormatting {

    // MARK: - Formatters

    /// Formats dates as "yyyy-MM-dd" for daily log file names.
    static let dailyLogFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone.current
        return formatter
    }()

    /// ISO 8601 date formatter for API communication.
    static let isoFormatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    /// Formats week numbers as "W01" through "W53".
    private static let weekNumberFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "'W'ww"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone.current
        return formatter
    }()

    // MARK: - File Name Helpers

    /// Returns the log file name for a given date, e.g. "2026-02-17.md".
    static func logFileName(for date: Date) -> String {
        dailyLogFormatter.string(from: date) + ".md"
    }

    /// Returns the protocol file name for the Monday of the given date's week,
    /// e.g. "protocol_2026-02-10.md".
    static func protocolFileName(for date: Date) -> String {
        let monday = mondayOfWeek(for: date)
        return "protocol_" + dailyLogFormatter.string(from: monday) + ".md"
    }

    /// Returns the ISO week number string, e.g. "W07".
    static func weekNumber(for date: Date) -> String {
        let calendar = Calendar(identifier: .iso8601)
        let weekOfYear = calendar.component(.weekOfYear, from: date)
        return String(format: "W%02d", weekOfYear)
    }

    // MARK: - Input Normalization

    /// Normalize sleep input to decimal hours.
    ///
    /// - "6:35" -> 6.583 (hours:minutes)
    /// - "6.5"  -> 6.5
    /// - "7"    -> 7.0
    /// - "0"    -> nil (zero sleep treated as not entered)
    /// - ""     -> nil
    static func normalizeSleep(_ value: String) -> Double? {
        let trimmed = value.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return nil }

        // Handle "H:MM" or "HH:MM" format
        if trimmed.contains(":") {
            let parts = trimmed.split(separator: ":")
            guard parts.count == 2,
                  let hours = Double(parts[0]),
                  let minutes = Double(parts[1])
            else { return nil }
            let total = hours + (minutes / 60.0)
            return total > 0 ? (total * 1000).rounded() / 1000 : nil
        }

        // Handle plain decimal / integer
        guard let number = Double(trimmed) else { return nil }
        return number > 0 ? number : nil
    }

    /// Normalize a quality/rating score to the 1-10 scale.
    ///
    /// - Values > 10 are assumed to be on a 0-100 scale and divided by 10.
    /// - "80"  -> 8.0
    /// - "7.5" -> 7.5
    /// - "10"  -> 10.0
    /// - ""    -> nil
    static func normalizeQualityScore(_ value: String) -> Double? {
        let trimmed = value.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty, let number = Double(trimmed) else { return nil }
        return number > 10 ? number / 10.0 : number
    }

    // MARK: - Calendar Helpers

    /// Returns the Monday (start of ISO week) for the given date.
    static func mondayOfWeek(for date: Date) -> Date {
        var calendar = Calendar(identifier: .iso8601)
        calendar.firstWeekday = 2 // Monday
        calendar.timeZone = TimeZone.current
        let components = calendar.dateComponents([.yearForWeekOfYear, .weekOfYear], from: date)
        return calendar.date(from: components) ?? date
    }
}
