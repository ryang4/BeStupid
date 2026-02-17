import Foundation
import HealthKit

// MARK: - Supporting Types

/// Aggregated sleep data for a single night.
struct SleepData: Sendable, Equatable {
    let totalHours: Double
    let inBedHours: Double
    let deepSleepHours: Double?
    let remSleepHours: Double?
    let lightSleepHours: Double?
    let awakeHours: Double?
    let startTime: Date?
    let endTime: Date?

    static let empty = SleepData(
        totalHours: 0,
        inBedHours: 0,
        deepSleepHours: nil,
        remSleepHours: nil,
        lightSleepHours: nil,
        awakeHours: nil,
        startTime: nil,
        endTime: nil
    )
}

/// A single weight measurement from HealthKit.
struct WeightSample: Sendable, Equatable, Identifiable {
    let id: UUID
    let date: Date
    let weightLbs: Double
    let source: String
}

// MARK: - Errors

enum HealthKitServiceError: Error, LocalizedError, Sendable {
    case healthKitNotAvailable
    case authorizationDenied
    case workoutNotFinished
    case duplicateWorkout
    case invalidWorkoutType(String)
    case queryFailed(String)

    var errorDescription: String? {
        switch self {
        case .healthKitNotAvailable:
            return "HealthKit is not available on this device."
        case .authorizationDenied:
            return "HealthKit authorization was denied."
        case .workoutNotFinished:
            return "Cannot save an active workout. Finish it first."
        case .duplicateWorkout:
            return "A workout with the same start time already exists in HealthKit."
        case .invalidWorkoutType(let type):
            return "Unknown workout type: \(type)"
        case .queryFailed(let reason):
            return "HealthKit query failed: \(reason)"
        }
    }
}

// MARK: - Protocol (Dependency Inversion)

/// Abstracts HealthKit operations for testability.
protocol HealthDataProvider: Sendable {
    func requestAuthorization() async throws
    var isAuthorized: Bool { get async }

    // Write
    func saveWorkout(_ session: WorkoutSession) async throws

    // Read
    func fetchHeartRate(from startDate: Date, to endDate: Date) async throws -> [HeartRateSample]
    func fetchSleepAnalysis(for date: Date) async throws -> SleepData
    func fetchWeight(from startDate: Date, to endDate: Date) async throws -> [WeightSample]
    func fetchSteps(for date: Date) async throws -> Int
    func fetchRestingHeartRate(for date: Date) async throws -> Int?

    // Live
    func startLiveHeartRate() -> AsyncStream<Int>
    func stopLiveHeartRate()
}

// MARK: - Workout Type Mapping

/// Maps user-facing workout type strings to HealthKit activity types.
enum WorkoutTypeMapping {
    static func activityType(for workoutType: String) -> HKWorkoutActivityType {
        switch workoutType.lowercased() {
        case "swim", "swimming":
            return .swimming
        case "bike", "cycling":
            return .cycling
        case "run", "running":
            return .running
        case "strength", "weights":
            return .traditionalStrengthTraining
        case "brick", "mixed":
            return .mixedCardio
        case "recovery", "flexibility", "stretch":
            return .flexibility
        case "walk", "walking":
            return .walking
        case "yoga":
            return .yoga
        default:
            return .other
        }
    }
}

// MARK: - Distance Unit Mapping

extension DistanceUnit {
    /// Converts this distance unit to the corresponding HealthKit unit.
    var hkUnit: HKUnit {
        switch self {
        case .meters:
            return .meter()
        case .kilometers:
            return .meterUnit(with: .kilo)
        case .miles:
            return .mile()
        }
    }
}

// MARK: - HealthKitService

/// Production HealthKit service backed by HKHealthStore.
/// Uses actor isolation for thread safety.
actor HealthKitService: HealthDataProvider {
    private let healthStore: HKHealthStore
    private var heartRateQuery: HKAnchoredObjectQuery?
    private var heartRateContinuation: AsyncStream<Int>.Continuation?
    private var authorized: Bool = false

    // MARK: - Types we read and write

    private static let readTypes: Set<HKSampleType> = [
        HKQuantityType(.heartRate),
        HKCategoryType(.sleepAnalysis),
        HKQuantityType(.bodyMass),
        HKQuantityType(.stepCount),
        HKQuantityType(.restingHeartRate),
        HKQuantityType(.activeEnergyBurned),
        HKQuantityType(.distanceWalkingRunning),
        HKQuantityType(.distanceCycling),
        HKQuantityType(.distanceSwimming),
    ]

    private static let writeTypes: Set<HKSampleType> = [
        HKQuantityType(.bodyMass),
        HKQuantityType(.activeEnergyBurned),
        .workoutType(),
    ]

    // MARK: - Init

    init() {
        self.healthStore = HKHealthStore()
    }

    /// Designated initializer for injection (used internally for testing seams).
    init(healthStore: HKHealthStore) {
        self.healthStore = healthStore
    }

    /// Whether HealthKit is available on this device.
    static var isAvailable: Bool {
        HKHealthStore.isHealthDataAvailable()
    }

    // MARK: - Authorization

    func requestAuthorization() async throws {
        guard Self.isAvailable else {
            throw HealthKitServiceError.healthKitNotAvailable
        }
        try await healthStore.requestAuthorization(
            toShare: Self.writeTypes,
            read: Self.readTypes
        )
        authorized = true
    }

    var isAuthorized: Bool {
        authorized
    }

    // MARK: - Save Workout

    func saveWorkout(_ session: WorkoutSession) async throws {
        guard !session.isActive, session.endTime != nil else {
            throw HealthKitServiceError.workoutNotFinished
        }

        guard let endTime = session.endTime else {
            throw HealthKitServiceError.workoutNotFinished
        }

        // Deduplication: check for existing workout with same start time
        let isDuplicate = try await workoutExistsWithStartTime(session.startTime)
        if isDuplicate {
            throw HealthKitServiceError.duplicateWorkout
        }

        let activityType = WorkoutTypeMapping.activityType(for: session.workoutType)
        let duration = endTime.timeIntervalSince(session.startTime)

        // Build the workout
        let configuration = HKWorkoutConfiguration()
        configuration.activityType = activityType

        let builder = HKWorkoutBuilder(healthStore: healthStore, configuration: configuration, device: .local())
        try await builder.beginCollection(at: session.startTime)

        // Add distance samples if present
        if let totalDistance = session.totalDistance, let unit = session.distanceUnit {
            let distanceType = distanceQuantityType(for: activityType)
            let distanceQuantity = HKQuantity(unit: unit.hkUnit, doubleValue: totalDistance)
            let distanceSample = HKQuantitySample(
                type: distanceType,
                quantity: distanceQuantity,
                start: session.startTime,
                end: endTime
            )
            try await builder.addSamples([distanceSample])
        }

        // Add heart rate samples if present
        if !session.heartRateSamples.isEmpty {
            let heartRateType = HKQuantityType(.heartRate)
            let bpmUnit = HKUnit.count().unitDivided(by: .minute())
            let hrSamples: [HKQuantitySample] = session.heartRateSamples.map { sample in
                let quantity = HKQuantity(unit: bpmUnit, doubleValue: Double(sample.bpm))
                return HKQuantitySample(
                    type: heartRateType,
                    quantity: quantity,
                    start: sample.timestamp,
                    end: sample.timestamp
                )
            }
            try await builder.addSamples(hrSamples)
        }

        try await builder.endCollection(at: endTime)
        try await builder.finishWorkout()
    }

    // MARK: - Fetch Heart Rate

    func fetchHeartRate(from startDate: Date, to endDate: Date) async throws -> [HeartRateSample] {
        let heartRateType = HKQuantityType(.heartRate)
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let sortDescriptor = SortDescriptor(\HKQuantitySample.startDate, order: .forward)

        let bpmUnit = HKUnit.count().unitDivided(by: .minute())

        let descriptor = HKSampleQueryDescriptor(
            predicates: [.quantitySample(type: heartRateType, predicate: predicate)],
            sortDescriptors: [sortDescriptor]
        )

        let results = try await descriptor.result(for: healthStore)

        return results.map { sample in
            HeartRateSample(
                timestamp: sample.startDate,
                bpm: Int(sample.quantity.doubleValue(for: bpmUnit))
            )
        }
    }

    // MARK: - Fetch Sleep Analysis

    func fetchSleepAnalysis(for date: Date) async throws -> SleepData {
        let calendar = Calendar.current
        // Look at the sleep window: previous day 6pm to requested day noon
        guard let windowStart = calendar.date(bySettingHour: 18, minute: 0, second: 0, of: calendar.date(byAdding: .day, value: -1, to: date)!) else {
            return .empty
        }
        guard let windowEnd = calendar.date(bySettingHour: 12, minute: 0, second: 0, of: date) else {
            return .empty
        }

        let sleepType = HKCategoryType(.sleepAnalysis)
        let predicate = HKQuery.predicateForSamples(withStart: windowStart, end: windowEnd, options: .strictStartDate)
        let sortDescriptor = SortDescriptor(\HKCategorySample.startDate, order: .forward)

        let descriptor = HKSampleQueryDescriptor(
            predicates: [.categorySample(type: sleepType, predicate: predicate)],
            sortDescriptors: [sortDescriptor]
        )

        let results = try await descriptor.result(for: healthStore)

        guard !results.isEmpty else {
            return .empty
        }

        var inBedSeconds: Double = 0
        var deepSleepSeconds: Double = 0
        var remSleepSeconds: Double = 0
        var lightSleepSeconds: Double = 0
        var awakeSeconds: Double = 0
        var earliestStart: Date?
        var latestEnd: Date?

        for sample in results {
            let sampleDuration = sample.endDate.timeIntervalSince(sample.startDate)

            if earliestStart == nil || sample.startDate < earliestStart! {
                earliestStart = sample.startDate
            }
            if latestEnd == nil || sample.endDate > latestEnd! {
                latestEnd = sample.endDate
            }

            guard let value = HKCategoryValueSleepAnalysis(rawValue: sample.value) else {
                continue
            }

            switch value {
            case .inBed:
                inBedSeconds += sampleDuration
            case .asleepCore:
                lightSleepSeconds += sampleDuration
            case .asleepDeep:
                deepSleepSeconds += sampleDuration
            case .asleepREM:
                remSleepSeconds += sampleDuration
            case .awake:
                awakeSeconds += sampleDuration
            case .asleepUnspecified:
                lightSleepSeconds += sampleDuration
            @unknown default:
                break
            }
        }

        let actualSleepSeconds = deepSleepSeconds + remSleepSeconds + lightSleepSeconds
        let totalInBedSeconds = inBedSeconds + actualSleepSeconds + awakeSeconds

        return SleepData(
            totalHours: actualSleepSeconds / 3600.0,
            inBedHours: totalInBedSeconds / 3600.0,
            deepSleepHours: deepSleepSeconds > 0 ? deepSleepSeconds / 3600.0 : nil,
            remSleepHours: remSleepSeconds > 0 ? remSleepSeconds / 3600.0 : nil,
            lightSleepHours: lightSleepSeconds > 0 ? lightSleepSeconds / 3600.0 : nil,
            awakeHours: awakeSeconds > 0 ? awakeSeconds / 3600.0 : nil,
            startTime: earliestStart,
            endTime: latestEnd
        )
    }

    // MARK: - Fetch Weight

    func fetchWeight(from startDate: Date, to endDate: Date) async throws -> [WeightSample] {
        let weightType = HKQuantityType(.bodyMass)
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let sortDescriptor = SortDescriptor(\HKQuantitySample.startDate, order: .forward)

        let descriptor = HKSampleQueryDescriptor(
            predicates: [.quantitySample(type: weightType, predicate: predicate)],
            sortDescriptors: [sortDescriptor]
        )

        let results = try await descriptor.result(for: healthStore)
        let lbsUnit = HKUnit.pound()

        return results.map { sample in
            WeightSample(
                id: UUID(),
                date: sample.startDate,
                weightLbs: sample.quantity.doubleValue(for: lbsUnit),
                source: sample.sourceRevision.source.name
            )
        }
    }

    // MARK: - Fetch Steps

    func fetchSteps(for date: Date) async throws -> Int {
        let calendar = Calendar.current
        let startOfDay = calendar.startOfDay(for: date)
        guard let endOfDay = calendar.date(byAdding: .day, value: 1, to: startOfDay) else {
            return 0
        }

        let stepType = HKQuantityType(.stepCount)
        let predicate = HKQuery.predicateForSamples(withStart: startOfDay, end: endOfDay, options: .strictStartDate)

        let descriptor = HKStatisticsQueryDescriptor(
            predicate: .quantitySample(type: stepType, predicate: predicate),
            options: .cumulativeSum
        )

        let result = try await descriptor.result(for: healthStore)
        guard let sum = result?.sumQuantity() else {
            return 0
        }

        return Int(sum.doubleValue(for: .count()))
    }

    // MARK: - Fetch Resting Heart Rate

    func fetchRestingHeartRate(for date: Date) async throws -> Int? {
        let calendar = Calendar.current
        let startOfDay = calendar.startOfDay(for: date)
        guard let endOfDay = calendar.date(byAdding: .day, value: 1, to: startOfDay) else {
            return nil
        }

        let restingHRType = HKQuantityType(.restingHeartRate)
        let predicate = HKQuery.predicateForSamples(withStart: startOfDay, end: endOfDay, options: .strictStartDate)
        let sortDescriptor = SortDescriptor(\HKQuantitySample.startDate, order: .reverse)

        let descriptor = HKSampleQueryDescriptor(
            predicates: [.quantitySample(type: restingHRType, predicate: predicate)],
            sortDescriptors: [sortDescriptor],
            limit: 1
        )

        let results = try await descriptor.result(for: healthStore)
        guard let sample = results.first else {
            return nil
        }

        let bpmUnit = HKUnit.count().unitDivided(by: .minute())
        return Int(sample.quantity.doubleValue(for: bpmUnit))
    }

    // MARK: - Live Heart Rate

    func startLiveHeartRate() -> AsyncStream<Int> {
        // Stop any existing stream first
        stopLiveHeartRateInternal()

        let (stream, continuation) = AsyncStream<Int>.makeStream()
        self.heartRateContinuation = continuation

        let heartRateType = HKQuantityType(.heartRate)
        let bpmUnit = HKUnit.count().unitDivided(by: .minute())

        // Use anchored object query starting from now
        let predicate = HKQuery.predicateForSamples(withStart: Date(), end: nil, options: .strictStartDate)

        let query = HKAnchoredObjectQuery(
            type: heartRateType,
            predicate: predicate,
            anchor: nil,
            limit: HKObjectQueryNoLimit
        ) { [weak self] _, samples, _, _, error in
            guard error == nil, let quantitySamples = samples as? [HKQuantitySample] else {
                return
            }
            for sample in quantitySamples {
                let bpm = Int(sample.quantity.doubleValue(for: bpmUnit))
                Task { [weak self] in
                    await self?.yieldHeartRate(bpm)
                }
            }
        }

        query.updateHandler = { [weak self] _, samples, _, _, error in
            guard error == nil, let quantitySamples = samples as? [HKQuantitySample] else {
                return
            }
            for sample in quantitySamples {
                let bpm = Int(sample.quantity.doubleValue(for: bpmUnit))
                Task { [weak self] in
                    await self?.yieldHeartRate(bpm)
                }
            }
        }

        self.heartRateQuery = query
        healthStore.execute(query)

        return stream
    }

    func stopLiveHeartRate() {
        stopLiveHeartRateInternal()
    }

    // MARK: - Private Helpers

    private func yieldHeartRate(_ bpm: Int) {
        heartRateContinuation?.yield(bpm)
    }

    private func stopLiveHeartRateInternal() {
        if let query = heartRateQuery {
            healthStore.stop(query)
            heartRateQuery = nil
        }
        heartRateContinuation?.finish()
        heartRateContinuation = nil
    }

    /// Check whether a workout already exists starting at the given time (deduplication).
    private func workoutExistsWithStartTime(_ startTime: Date) async throws -> Bool {
        let tolerance: TimeInterval = 1.0 // 1-second tolerance
        let rangeStart = startTime.addingTimeInterval(-tolerance)
        let rangeEnd = startTime.addingTimeInterval(tolerance)

        let predicate = HKQuery.predicateForSamples(withStart: rangeStart, end: rangeEnd, options: .strictStartDate)
        let sortDescriptor = SortDescriptor(\HKWorkout.startDate, order: .forward)

        let descriptor = HKSampleQueryDescriptor(
            predicates: [.workout(predicate)],
            sortDescriptors: [sortDescriptor],
            limit: 1
        )

        let results = try await descriptor.result(for: healthStore)
        return !results.isEmpty
    }

    /// Returns the appropriate distance quantity type based on workout activity type.
    private func distanceQuantityType(for activityType: HKWorkoutActivityType) -> HKQuantityType {
        switch activityType {
        case .cycling:
            return HKQuantityType(.distanceCycling)
        case .swimming:
            return HKQuantityType(.distanceSwimming)
        default:
            return HKQuantityType(.distanceWalkingRunning)
        }
    }
}
