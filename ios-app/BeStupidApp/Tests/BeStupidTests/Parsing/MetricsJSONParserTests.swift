import Testing
import Foundation
@testable import BeStupidApp

// MARK: - MetricsJSONParserTests

@Suite("MetricsJSONParser")
struct MetricsJSONParserTests {

    // MARK: - Daily Metrics

    @Test("Parses daily metrics JSON")
    func parseDailyMetrics() throws {
        let json = """
        {
          "version": "1.0",
          "entries": [{
            "date": "2025-12-16",
            "sleep": {"hours": 6.13, "quality": 7.4},
            "weight_lbs": 244.0,
            "mood": {"morning": 5.0, "bedtime": 6.0},
            "energy": 7.2,
            "focus": 6.5,
            "training": {
              "workout_type": "swim",
              "activities": [{"type": "swim", "distance": 750.0, "distance_unit": "m", "duration_minutes": 33.65, "avg_hr": 117}],
              "strength_exercises": [{"exercise": "Dumbbell bench press", "sets": 3, "reps": 10, "weight_lbs": 60}]
            },
            "todos": {"total": 7, "completed": 7, "completion_rate": 1.0},
            "habits": {"completed": ["ai_automation", "yoga"], "missed": [], "completion_rate": 1.0},
            "nutrition": {"calories": 2720, "protein_g": 85}
          }]
        }
        """
        let data = json.data(using: .utf8)!
        let points = try MetricsJSONParser.parseDailyMetrics(from: data)

        // Should have multiple metric data points from one entry
        #expect(!points.isEmpty)

        // Check specific metrics
        let sleepPoints = points.filter { $0.field == .sleep }
        #expect(sleepPoints.count == 1)
        #expect(sleepPoints[0].value == 6.13)
        #expect(sleepPoints[0].source == .parsed)

        let weightPoints = points.filter { $0.field == .weight }
        #expect(weightPoints.count == 1)
        #expect(weightPoints[0].value == 244.0)

        let moodAMPoints = points.filter { $0.field == .moodAM }
        #expect(moodAMPoints.count == 1)
        #expect(moodAMPoints[0].value == 5.0)

        let moodPMPoints = points.filter { $0.field == .moodPM }
        #expect(moodPMPoints.count == 1)
        #expect(moodPMPoints[0].value == 6.0)

        let energyPoints = points.filter { $0.field == .energy }
        #expect(energyPoints.count == 1)
        #expect(energyPoints[0].value == 7.2)

        let swimDistPoints = points.filter { $0.field == .swimDistance }
        #expect(swimDistPoints.count == 1)
        #expect(swimDistPoints[0].value == 750.0)

        let swimDurPoints = points.filter { $0.field == .swimDuration }
        #expect(swimDurPoints.count == 1)
        #expect(swimDurPoints[0].value == 33.65)

        let calPoints = points.filter { $0.field == .calories }
        #expect(calPoints.count == 1)
        #expect(calPoints[0].value == 2720.0)

        let proteinPoints = points.filter { $0.field == .protein }
        #expect(proteinPoints.count == 1)
        #expect(proteinPoints[0].value == 85.0)

        let todoPoints = points.filter { $0.field == .todoCompletion }
        #expect(todoPoints.count == 1)
        #expect(todoPoints[0].value == 100.0) // 1.0 * 100

        let habitPoints = points.filter { $0.field == .habitCompletion }
        #expect(habitPoints.count == 1)
        #expect(habitPoints[0].value == 100.0) // 1.0 * 100
    }

    @Test("Parses daily metrics with partial data")
    func partialDailyMetrics() throws {
        let json = """
        {
          "version": "1.0",
          "entries": [{
            "date": "2025-12-17",
            "weight_lbs": 243.5,
            "energy": 8.0
          }]
        }
        """
        let data = json.data(using: .utf8)!
        let points = try MetricsJSONParser.parseDailyMetrics(from: data)

        let weightPoints = points.filter { $0.field == .weight }
        #expect(weightPoints.count == 1)
        #expect(weightPoints[0].value == 243.5)

        let energyPoints = points.filter { $0.field == .energy }
        #expect(energyPoints.count == 1)
        #expect(energyPoints[0].value == 8.0)

        // No sleep, mood, etc. should be present
        let sleepPoints = points.filter { $0.field == .sleep }
        #expect(sleepPoints.isEmpty)
    }

    @Test("Parses empty entries array")
    func emptyEntries() throws {
        let json = """
        {
          "version": "1.0",
          "entries": []
        }
        """
        let data = json.data(using: .utf8)!
        let points = try MetricsJSONParser.parseDailyMetrics(from: data)
        #expect(points.isEmpty)
    }

    @Test("Throws on invalid JSON")
    func invalidJSON() {
        let data = "not json".data(using: .utf8)!
        #expect(throws: DecodingError.self) {
            try MetricsJSONParser.parseDailyMetrics(from: data)
        }
    }

    @Test("Parses multiple entries")
    func multipleEntries() throws {
        let json = """
        {
          "version": "1.0",
          "entries": [
            {"date": "2025-12-16", "weight_lbs": 244.0},
            {"date": "2025-12-17", "weight_lbs": 243.5}
          ]
        }
        """
        let data = json.data(using: .utf8)!
        let points = try MetricsJSONParser.parseDailyMetrics(from: data)
        let weightPoints = points.filter { $0.field == .weight }
        #expect(weightPoints.count == 2)
    }

    // MARK: - Garmin Metrics

    @Test("Parses garmin metrics JSON")
    func parseGarminMetrics() throws {
        let json = """
        {
          "version": "1.0",
          "entries": [{
            "date": "2026-02-15",
            "sleep": {"total_hours": 7.25, "deep_hours": 1.5, "score": 82},
            "hrv": {"overnight_avg": 52, "status": "BALANCED"},
            "body_battery": {"start_level": 78, "end_level": 45},
            "training": {"readiness_score": 78, "readiness_status": "READY", "vo2max_run": 52.3},
            "stress": {"avg_stress": 35},
            "resting_hr": 52,
            "activities": [{"type": "running", "name": "Morning run", "duration_minutes": 45.5, "distance_km": 7.2, "avg_hr": 152}],
            "recovery": {"score": 76.5, "status": "good"}
          }]
        }
        """
        let data = json.data(using: .utf8)!
        let entries = try MetricsJSONParser.parseGarminMetrics(from: data)

        #expect(entries.count == 1)
        let entry = entries[0]

        // Sleep
        #expect(entry.sleepScore == 82)
        #expect(entry.sleepHours == 7.25)
        #expect(entry.deepSleepHours == 1.5)

        // HRV
        #expect(entry.hrvOvernight == 52)
        #expect(entry.hrvStatus == "BALANCED")

        // Body Battery
        #expect(entry.bodyBatteryStart == 78)
        #expect(entry.bodyBatteryEnd == 45)
        #expect(entry.bodyBatteryDrain == 33)

        // Training
        #expect(entry.trainingReadiness == 78)
        #expect(entry.readinessStatus == "READY")
        #expect(entry.vo2maxRun == 52.3)

        // Stress & HR
        #expect(entry.stressAvg == 35)
        #expect(entry.restingHR == 52)

        // Recovery
        #expect(entry.recoveryScore == 76.5)
        #expect(entry.recoveryStatus == "good")

        // Activities
        #expect(entry.activities.count == 1)
        let activity = entry.activities[0]
        #expect(activity.type == "running")
        #expect(activity.name == "Morning run")
        #expect(activity.durationMinutes == 45.5)
        #expect(activity.distanceKm == 7.2)
        #expect(activity.avgHR == 152)
    }

    @Test("Parses garmin metrics with minimal data")
    func minimalGarminMetrics() throws {
        let json = """
        {
          "version": "1.0",
          "entries": [{
            "date": "2026-02-16",
            "resting_hr": 55,
            "activities": []
          }]
        }
        """
        let data = json.data(using: .utf8)!
        let entries = try MetricsJSONParser.parseGarminMetrics(from: data)

        #expect(entries.count == 1)
        #expect(entries[0].restingHR == 55)
        #expect(entries[0].activities.isEmpty)
        #expect(entries[0].sleepScore == nil)
        #expect(entries[0].hrvOvernight == nil)
    }

    @Test("Parses garmin metrics with multiple activities")
    func multipleGarminActivities() throws {
        let json = """
        {
          "version": "1.0",
          "entries": [{
            "date": "2026-02-15",
            "activities": [
              {"type": "cycling", "name": "Indoor ride", "duration_minutes": 30.0, "avg_hr": 140},
              {"type": "running", "name": "Brick run", "duration_minutes": 20.0, "distance_km": 3.5, "avg_hr": 155}
            ]
          }]
        }
        """
        let data = json.data(using: .utf8)!
        let entries = try MetricsJSONParser.parseGarminMetrics(from: data)

        #expect(entries[0].activities.count == 2)
        #expect(entries[0].activities[0].type == "cycling")
        #expect(entries[0].activities[1].type == "running")
        #expect(entries[0].totalActivityMinutes == 50.0)
    }

    @Test("Throws on invalid garmin JSON")
    func invalidGarminJSON() {
        let data = "invalid".data(using: .utf8)!
        #expect(throws: DecodingError.self) {
            try MetricsJSONParser.parseGarminMetrics(from: data)
        }
    }
}
