import Foundation

// MARK: - MetricsJSONParser

/// Parses JSON metric files from the BeStupid data directory.
///
/// Handles two formats:
/// - `data/daily_metrics.json` -- manual/parsed daily metrics
/// - `data/garmin_metrics.json` -- Garmin-synced health data
///
/// Uses `Codable` intermediate types for JSON decoding, then maps to
/// the app's domain models (`MetricDataPoint` and `GarminDayData`).
enum MetricsJSONParser: Sendable {

    // MARK: - Date Formatter

    private static let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(identifier: "UTC")
        return formatter
    }()

    private static func makeDecoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .formatted(dateFormatter)
        return decoder
    }

    // MARK: - Daily Metrics

    /// Parse `daily_metrics.json` into an array of `MetricDataPoint` values.
    ///
    /// Each JSON entry may produce multiple `MetricDataPoint` values (one per field).
    ///
    /// - Parameter data: Raw JSON data.
    /// - Returns: An array of metric data points extracted from all entries.
    /// - Throws: `DecodingError` if the JSON structure is invalid.
    static func parseDailyMetrics(from data: Data) throws -> [MetricDataPoint] {
        let decoded = try makeDecoder().decode(DailyMetricsFile.self, from: data)
        var points: [MetricDataPoint] = []

        for entry in decoded.entries {
            let date = entry.date

            // Sleep
            if let sleepHours = entry.sleep?.hours {
                points.append(MetricDataPoint(date: date, field: .sleep, value: sleepHours, source: .parsed))
            }
            if let sleepQuality = entry.sleep?.quality {
                points.append(MetricDataPoint(date: date, field: .sleepQuality, value: sleepQuality, source: .parsed))
            }

            // Weight
            if let weight = entry.weightLbs {
                points.append(MetricDataPoint(date: date, field: .weight, value: weight, source: .parsed))
            }

            // Mood
            if let moodAM = entry.mood?.morning {
                points.append(MetricDataPoint(date: date, field: .moodAM, value: moodAM, source: .parsed))
            }
            if let moodPM = entry.mood?.bedtime {
                points.append(MetricDataPoint(date: date, field: .moodPM, value: moodPM, source: .parsed))
            }

            // Energy & Focus
            if let energy = entry.energy {
                points.append(MetricDataPoint(date: date, field: .energy, value: energy, source: .parsed))
            }
            if let focus = entry.focus {
                points.append(MetricDataPoint(date: date, field: .focus, value: focus, source: .parsed))
            }

            // Training activities -> distance/duration metrics
            if let training = entry.training {
                for activity in training.activities {
                    let activityType = activity.type.lowercased()
                    switch activityType {
                    case "swim":
                        if let dist = activity.distance {
                            points.append(MetricDataPoint(date: date, field: .swimDistance, value: dist, source: .parsed))
                        }
                        if let dur = activity.durationMinutes {
                            points.append(MetricDataPoint(date: date, field: .swimDuration, value: dur, source: .parsed))
                        }
                    case "bike", "cycling":
                        if let dist = activity.distance {
                            points.append(MetricDataPoint(date: date, field: .bikeDistance, value: dist, source: .parsed))
                        }
                        if let dur = activity.durationMinutes {
                            points.append(MetricDataPoint(date: date, field: .bikeDuration, value: dur, source: .parsed))
                        }
                    case "run", "running":
                        if let dist = activity.distance {
                            points.append(MetricDataPoint(date: date, field: .runDistance, value: dist, source: .parsed))
                        }
                        if let dur = activity.durationMinutes {
                            points.append(MetricDataPoint(date: date, field: .runDuration, value: dur, source: .parsed))
                        }
                    default:
                        break
                    }
                }
            }

            // Nutrition
            if let nutrition = entry.nutrition {
                if let cal = nutrition.calories {
                    points.append(MetricDataPoint(date: date, field: .calories, value: Double(cal), source: .parsed))
                }
                if let pro = nutrition.proteinG {
                    points.append(MetricDataPoint(date: date, field: .protein, value: Double(pro), source: .parsed))
                }
            }

            // Todo completion
            if let todos = entry.todos, let rate = todos.completionRate {
                points.append(MetricDataPoint(date: date, field: .todoCompletion, value: rate * 100, source: .parsed))
            }

            // Habit completion
            if let habits = entry.habits, let rate = habits.completionRate {
                points.append(MetricDataPoint(date: date, field: .habitCompletion, value: rate * 100, source: .parsed))
            }
        }

        return points
    }

    // MARK: - Garmin Metrics

    /// Parse `garmin_metrics.json` into an array of `GarminDayData` values.
    ///
    /// - Parameter data: Raw JSON data.
    /// - Returns: An array of Garmin day data entries.
    /// - Throws: `DecodingError` if the JSON structure is invalid.
    static func parseGarminMetrics(from data: Data) throws -> [GarminDayData] {
        let decoded = try makeDecoder().decode(GarminMetricsFile.self, from: data)

        return decoded.entries.map { entry in
            let activities = entry.activities.map { activity in
                GarminActivity(
                    type: activity.type,
                    name: activity.name ?? "",
                    startTime: entry.date,
                    durationMinutes: activity.durationMinutes,
                    distanceKm: activity.distanceKm,
                    avgHR: activity.avgHR,
                    maxHR: activity.maxHR
                )
            }

            return GarminDayData(
                date: entry.date,
                sleepScore: entry.sleep?.score,
                sleepHours: entry.sleep?.totalHours,
                deepSleepHours: entry.sleep?.deepHours,
                hrvOvernight: entry.hrv?.overnightAvg,
                hrvStatus: entry.hrv?.status,
                bodyBatteryStart: entry.bodyBattery?.startLevel,
                bodyBatteryEnd: entry.bodyBattery?.endLevel,
                trainingReadiness: entry.training?.readinessScore,
                readinessStatus: entry.training?.readinessStatus,
                vo2maxRun: entry.training?.vo2maxRun,
                recoveryScore: entry.recovery?.score,
                recoveryStatus: entry.recovery?.status,
                stressAvg: entry.stress?.avgStress,
                restingHR: entry.restingHR,
                activities: activities
            )
        }
    }
}

// MARK: - JSON Codable Types (Internal)

/// Top-level structure for daily_metrics.json.
private struct DailyMetricsFile: Codable, Sendable {
    let version: String
    let entries: [DailyMetricEntry]
}

/// A single entry in daily_metrics.json.
private struct DailyMetricEntry: Codable, Sendable {
    let date: Date
    let sleep: SleepData?
    let weightLbs: Double?
    let mood: MoodData?
    let energy: Double?
    let focus: Double?
    let training: TrainingData?
    let todos: TodoData?
    let habits: HabitData?
    let nutrition: NutritionData?

    enum CodingKeys: String, CodingKey {
        case date, sleep, mood, energy, focus, training, todos, habits, nutrition
        case weightLbs = "weight_lbs"
    }
}

private struct SleepData: Codable, Sendable {
    let hours: Double?
    let quality: Double?
}

private struct MoodData: Codable, Sendable {
    let morning: Double?
    let bedtime: Double?
}

private struct TrainingData: Codable, Sendable {
    let workoutType: String?
    let activities: [ActivityData]
    let strengthExercises: [StrengthExerciseData]?

    enum CodingKeys: String, CodingKey {
        case activities
        case workoutType = "workout_type"
        case strengthExercises = "strength_exercises"
    }
}

private struct ActivityData: Codable, Sendable {
    let type: String
    let distance: Double?
    let distanceUnit: String?
    let durationMinutes: Double?
    let avgHR: Int?

    enum CodingKeys: String, CodingKey {
        case type, distance
        case distanceUnit = "distance_unit"
        case durationMinutes = "duration_minutes"
        case avgHR = "avg_hr"
    }
}

private struct StrengthExerciseData: Codable, Sendable {
    let exercise: String
    let sets: Int
    let reps: Int
    let weightLbs: Double

    enum CodingKeys: String, CodingKey {
        case exercise, sets, reps
        case weightLbs = "weight_lbs"
    }
}

private struct TodoData: Codable, Sendable {
    let total: Int?
    let completed: Int?
    let completionRate: Double?

    enum CodingKeys: String, CodingKey {
        case total, completed
        case completionRate = "completion_rate"
    }
}

private struct HabitData: Codable, Sendable {
    let completed: [String]?
    let missed: [String]?
    let completionRate: Double?

    enum CodingKeys: String, CodingKey {
        case completed, missed
        case completionRate = "completion_rate"
    }
}

private struct NutritionData: Codable, Sendable {
    let calories: Int?
    let proteinG: Int?

    enum CodingKeys: String, CodingKey {
        case calories
        case proteinG = "protein_g"
    }
}

// MARK: - Garmin JSON Types

/// Top-level structure for garmin_metrics.json.
private struct GarminMetricsFile: Codable, Sendable {
    let version: String
    let entries: [GarminEntry]
}

/// A single entry in garmin_metrics.json.
private struct GarminEntry: Codable, Sendable {
    let date: Date
    let sleep: GarminSleepData?
    let hrv: GarminHRVData?
    let bodyBattery: GarminBodyBatteryData?
    let training: GarminTrainingData?
    let stress: GarminStressData?
    let restingHR: Int?
    let activities: [GarminActivityData]
    let recovery: GarminRecoveryData?

    enum CodingKeys: String, CodingKey {
        case date, sleep, hrv, training, stress, activities, recovery
        case bodyBattery = "body_battery"
        case restingHR = "resting_hr"
    }
}

private struct GarminSleepData: Codable, Sendable {
    let totalHours: Double?
    let deepHours: Double?
    let score: Int?

    enum CodingKeys: String, CodingKey {
        case score
        case totalHours = "total_hours"
        case deepHours = "deep_hours"
    }
}

private struct GarminHRVData: Codable, Sendable {
    let overnightAvg: Int?
    let status: String?

    enum CodingKeys: String, CodingKey {
        case status
        case overnightAvg = "overnight_avg"
    }
}

private struct GarminBodyBatteryData: Codable, Sendable {
    let startLevel: Int?
    let endLevel: Int?

    enum CodingKeys: String, CodingKey {
        case startLevel = "start_level"
        case endLevel = "end_level"
    }
}

private struct GarminTrainingData: Codable, Sendable {
    let readinessScore: Int?
    let readinessStatus: String?
    let vo2maxRun: Double?

    enum CodingKeys: String, CodingKey {
        case readinessScore = "readiness_score"
        case readinessStatus = "readiness_status"
        case vo2maxRun = "vo2max_run"
    }
}

private struct GarminStressData: Codable, Sendable {
    let avgStress: Int?

    enum CodingKeys: String, CodingKey {
        case avgStress = "avg_stress"
    }
}

private struct GarminActivityData: Codable, Sendable {
    let type: String
    let name: String?
    let durationMinutes: Double
    let distanceKm: Double?
    let avgHR: Int?
    let maxHR: Int?

    enum CodingKeys: String, CodingKey {
        case type, name
        case durationMinutes = "duration_minutes"
        case distanceKm = "distance_km"
        case avgHR = "avg_hr"
        case maxHR = "max_hr"
    }
}

private struct GarminRecoveryData: Codable, Sendable {
    let score: Double?
    let status: String?
}
