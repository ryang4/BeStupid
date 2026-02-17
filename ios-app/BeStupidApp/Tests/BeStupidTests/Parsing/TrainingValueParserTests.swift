import Testing
@testable import BeStupidApp

// MARK: - TrainingValueParserTests

@Suite("TrainingValueParser")
struct TrainingValueParserTests {

    // MARK: - Distance/Duration Combined

    @Test("Parses meters with MM:SS duration")
    func metersWithTime() {
        let result = TrainingValueParser.parse("750m/33:39")
        #expect(result.distance == 750.0)
        #expect(result.distanceUnit == .meters)
        // 33 min + 39 sec = 33 + 39/60 = 33.65
        #expect(result.durationMinutes != nil)
        #expect(result.durationMinutes! >= 33.64)
        #expect(result.durationMinutes! <= 33.66)
    }

    @Test("Parses plain number with plain duration")
    func plainNumberWithDuration() {
        let result = TrainingValueParser.parse("4.5/45")
        #expect(result.distance == 4.5)
        #expect(result.durationMinutes == 45.0)
    }

    @Test("Parses kilometers with MM:SS duration")
    func kilometersWithTime() {
        let result = TrainingValueParser.parse("1.2km/35:00")
        #expect(result.distance == 1.2)
        #expect(result.distanceUnit == .kilometers)
        #expect(result.durationMinutes == 35.0)
    }

    @Test("Parses miles with MM:SS duration")
    func milesWithTime() {
        let result = TrainingValueParser.parse("3.1mi/28:30")
        #expect(result.distance == 3.1)
        #expect(result.distanceUnit == .miles)
        #expect(result.durationMinutes == 28.5)
    }

    // MARK: - Duration Only

    @Test("Parses MM:SS time only")
    func timeOnly() {
        let result = TrainingValueParser.parse("30:00")
        #expect(result.distance == nil)
        #expect(result.durationMinutes == 30.0)
    }

    @Test("Parses plain minutes only")
    func minutesOnly() {
        let result = TrainingValueParser.parse("45")
        #expect(result.distance == nil)
        #expect(result.durationMinutes == 45.0)
    }

    @Test("Parses MM:SS with seconds")
    func timeWithSeconds() {
        let result = TrainingValueParser.parse("45:30")
        #expect(result.distance == nil)
        #expect(result.durationMinutes == 45.5)
    }

    // MARK: - Distance Only

    @Test("Parses distance with meter suffix only")
    func distanceMetersOnly() {
        let result = TrainingValueParser.parse("750m")
        #expect(result.distance == 750.0)
        #expect(result.distanceUnit == .meters)
        #expect(result.durationMinutes == nil)
    }

    @Test("Parses distance with km suffix only")
    func distanceKmOnly() {
        let result = TrainingValueParser.parse("5.0km")
        #expect(result.distance == 5.0)
        #expect(result.distanceUnit == .kilometers)
        #expect(result.durationMinutes == nil)
    }

    // MARK: - Edge Cases

    @Test("Handles empty string")
    func emptyString() {
        let result = TrainingValueParser.parse("")
        #expect(result.distance == nil)
        #expect(result.durationMinutes == nil)
    }

    @Test("Handles whitespace-only string")
    func whitespace() {
        let result = TrainingValueParser.parse("   ")
        #expect(result.distance == nil)
        #expect(result.durationMinutes == nil)
    }

    // MARK: - Default Unit Inference

    @Test("Default unit for swim is meters")
    func swimDefaultUnit() {
        let unit = TrainingValueParser.defaultUnit(for: "swim")
        #expect(unit == .meters)
    }

    @Test("Default unit for swimming is meters")
    func swimmingDefaultUnit() {
        let unit = TrainingValueParser.defaultUnit(for: "swimming")
        #expect(unit == .meters)
    }

    @Test("Default unit for run is miles")
    func runDefaultUnit() {
        let unit = TrainingValueParser.defaultUnit(for: "run")
        #expect(unit == .miles)
    }

    @Test("Default unit for running is miles")
    func runningDefaultUnit() {
        let unit = TrainingValueParser.defaultUnit(for: "running")
        #expect(unit == .miles)
    }

    @Test("Default unit for bike is kilometers")
    func bikeDefaultUnit() {
        let unit = TrainingValueParser.defaultUnit(for: "bike")
        #expect(unit == .kilometers)
    }

    @Test("Default unit for cycling is kilometers")
    func cyclingDefaultUnit() {
        let unit = TrainingValueParser.defaultUnit(for: "cycling")
        #expect(unit == .kilometers)
    }

    @Test("Default unit for unknown activity is meters")
    func unknownDefaultUnit() {
        let unit = TrainingValueParser.defaultUnit(for: "yoga")
        #expect(unit == .meters)
    }

    @Test("Default unit is case-insensitive")
    func caseInsensitiveUnit() {
        let unit = TrainingValueParser.defaultUnit(for: "SWIM")
        #expect(unit == .meters)
    }

    // MARK: - Time String Parsing

    @Test("parseTimeString parses standard time")
    func parseTimeStandard() {
        let result = TrainingValueParser.parseTimeString("33:39")
        #expect(result != nil)
        #expect(result! >= 33.64)
        #expect(result! <= 33.66)
    }

    @Test("parseTimeString parses exact minutes")
    func parseTimeExact() {
        let result = TrainingValueParser.parseTimeString("30:00")
        #expect(result == 30.0)
    }

    @Test("parseTimeString returns nil for invalid format")
    func parseTimeInvalid() {
        let result = TrainingValueParser.parseTimeString("abc")
        #expect(result == nil)
    }

    @Test("parseTimeString returns nil for single number")
    func parseTimeSingleNumber() {
        let result = TrainingValueParser.parseTimeString("45")
        #expect(result == nil)
    }

    // MARK: - Distance String Parsing

    @Test("parseDistanceString parses meters")
    func parseDistanceMeters() {
        let result = TrainingValueParser.parseDistanceString("750m")
        #expect(result != nil)
        #expect(result?.0 == 750.0)
        #expect(result?.1 == .meters)
    }

    @Test("parseDistanceString parses kilometers")
    func parseDistanceKm() {
        let result = TrainingValueParser.parseDistanceString("1.2km")
        #expect(result != nil)
        #expect(result?.0 == 1.2)
        #expect(result?.1 == .kilometers)
    }

    @Test("parseDistanceString parses miles")
    func parseDistanceMiles() {
        let result = TrainingValueParser.parseDistanceString("3.1mi")
        #expect(result != nil)
        #expect(result?.0 == 3.1)
        #expect(result?.1 == .miles)
    }

    @Test("parseDistanceString parses plain number as meters")
    func parseDistancePlain() {
        let result = TrainingValueParser.parseDistanceString("750")
        #expect(result != nil)
        #expect(result?.0 == 750.0)
        #expect(result?.1 == .meters)
    }

    @Test("parseDistanceString returns nil for non-numeric")
    func parseDistanceNonNumeric() {
        let result = TrainingValueParser.parseDistanceString("abc")
        #expect(result == nil)
    }
}
