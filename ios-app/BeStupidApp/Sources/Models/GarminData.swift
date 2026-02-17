import Foundation

// MARK: - GarminActivity

struct GarminActivity: Identifiable, Codable, Sendable, Equatable {
    let id: UUID
    var type: String
    var name: String
    var startTime: Date
    var durationMinutes: Double
    var distanceKm: Double?
    var calories: Int?
    var avgHR: Int?
    var maxHR: Int?
    var avgPaceMinPerKm: Double?
    var elevationGainM: Double?

    init(
        id: UUID = UUID(),
        type: String,
        name: String,
        startTime: Date,
        durationMinutes: Double,
        distanceKm: Double? = nil,
        calories: Int? = nil,
        avgHR: Int? = nil,
        maxHR: Int? = nil,
        avgPaceMinPerKm: Double? = nil,
        elevationGainM: Double? = nil
    ) {
        self.id = id
        self.type = type
        self.name = name
        self.startTime = startTime
        self.durationMinutes = durationMinutes
        self.distanceKm = distanceKm
        self.calories = calories
        self.avgHR = avgHR
        self.maxHR = maxHR
        self.avgPaceMinPerKm = avgPaceMinPerKm
        self.elevationGainM = elevationGainM
    }

    /// Distance in miles, converted from km.
    var distanceMiles: Double? {
        distanceKm.map { $0 / 1.609344 }
    }
}

// MARK: - GarminDayData

struct GarminDayData: Identifiable, Codable, Sendable, Equatable {
    let id: UUID
    var date: Date
    var syncedAt: Date

    // Sleep
    var sleepScore: Int?
    var sleepHours: Double?
    var deepSleepHours: Double?
    var lightSleepHours: Double?
    var remSleepHours: Double?

    // HRV
    var hrvOvernight: Int?
    var hrvWeeklyAvg: Int?
    var hrvStatus: String?

    // Body Battery
    var bodyBatteryStart: Int?
    var bodyBatteryEnd: Int?

    // Training
    var trainingReadiness: Int?
    var readinessStatus: String?
    var vo2maxRun: Double?
    var vo2maxBike: Double?

    // Recovery
    var recoveryScore: Double?
    var recoveryStatus: String?

    // Stress
    var stressAvg: Int?
    var restingHR: Int?

    // Activities
    var activities: [GarminActivity]

    init(
        id: UUID = UUID(),
        date: Date,
        syncedAt: Date = Date(),
        sleepScore: Int? = nil,
        sleepHours: Double? = nil,
        deepSleepHours: Double? = nil,
        lightSleepHours: Double? = nil,
        remSleepHours: Double? = nil,
        hrvOvernight: Int? = nil,
        hrvWeeklyAvg: Int? = nil,
        hrvStatus: String? = nil,
        bodyBatteryStart: Int? = nil,
        bodyBatteryEnd: Int? = nil,
        trainingReadiness: Int? = nil,
        readinessStatus: String? = nil,
        vo2maxRun: Double? = nil,
        vo2maxBike: Double? = nil,
        recoveryScore: Double? = nil,
        recoveryStatus: String? = nil,
        stressAvg: Int? = nil,
        restingHR: Int? = nil,
        activities: [GarminActivity] = []
    ) {
        self.id = id
        self.date = date
        self.syncedAt = syncedAt
        self.sleepScore = sleepScore
        self.sleepHours = sleepHours
        self.deepSleepHours = deepSleepHours
        self.lightSleepHours = lightSleepHours
        self.remSleepHours = remSleepHours
        self.hrvOvernight = hrvOvernight
        self.hrvWeeklyAvg = hrvWeeklyAvg
        self.hrvStatus = hrvStatus
        self.bodyBatteryStart = bodyBatteryStart
        self.bodyBatteryEnd = bodyBatteryEnd
        self.trainingReadiness = trainingReadiness
        self.readinessStatus = readinessStatus
        self.vo2maxRun = vo2maxRun
        self.vo2maxBike = vo2maxBike
        self.recoveryScore = recoveryScore
        self.recoveryStatus = recoveryStatus
        self.stressAvg = stressAvg
        self.restingHR = restingHR
        self.activities = activities
    }

    /// Body battery drain across the day (start - end). Positive means net drain.
    var bodyBatteryDrain: Int? {
        guard let start = bodyBatteryStart, let end = bodyBatteryEnd else { return nil }
        return start - end
    }

    /// Total activity calories for the day.
    var totalActivityCalories: Int {
        activities.compactMap(\.calories).reduce(0, +)
    }

    /// Total activity duration in minutes for the day.
    var totalActivityMinutes: Double {
        activities.reduce(0.0) { $0 + $1.durationMinutes }
    }
}
