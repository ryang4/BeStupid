import Foundation
#if canImport(FoundationModels)
import FoundationModels
#endif

/// On-device AI using Apple Foundation Models (iOS 26+).
/// Free, private, works offline. The on-device model is ~3B parameters,
/// so prompts are kept concise and structured as compact tables.
actor OnDeviceAIProvider: AIService {
    let providerName = "Apple On-Device"
    let isAvailableOffline = true

    #if canImport(FoundationModels)
    private var session: LanguageModelSession?
    #endif

    var isAvailable: Bool {
        get async {
            #if canImport(FoundationModels)
            return LanguageModelSession.isAvailable
            #else
            return false
            #endif
        }
    }

    // MARK: - AIService Conformance

    func generateBriefing(context: BriefingContext) async throws -> String {
        let prompt = buildBriefingPrompt(context)
        return try await generate(prompt: prompt)
    }

    func analyzeMetrics(metrics: [MetricSummary], query: String) async throws -> String {
        let prompt = buildMetricsPrompt(metrics: metrics, query: query)
        return try await generate(prompt: prompt)
    }

    func suggestWorkout(protocol proto: ProtocolContext, recovery: RecoveryContext) async throws -> String {
        let prompt = buildWorkoutPrompt(protocol: proto, recovery: recovery)
        return try await generate(prompt: prompt)
    }

    func query(_ question: String, context: QueryContext) async throws -> String {
        let prompt = buildQueryPrompt(question: question, context: context)
        return try await generate(prompt: prompt)
    }

    // MARK: - Generation

    private func generate(prompt: String) async throws -> String {
        #if canImport(FoundationModels)
        guard await Self.checkAvailability() else {
            throw AIError.modelNotLoaded
        }
        do {
            let activeSession = session ?? LanguageModelSession()
            session = activeSession
            let response = try await activeSession.respond(to: prompt)
            return response.content
        } catch {
            throw AIError.generationFailed(error.localizedDescription)
        }
        #else
        throw AIError.providerUnavailable("Foundation Models not available on this platform")
        #endif
    }

    #if canImport(FoundationModels)
    private static func checkAvailability() async -> Bool {
        return LanguageModelSession.isAvailable
    }
    #endif

    // MARK: - Prompt Builders (compact for ~3B on-device model)

    private static let dateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "MM/dd"
        return f
    }()

    private func buildBriefingPrompt(_ context: BriefingContext) -> String {
        var lines: [String] = []
        lines.append("Generate a concise morning briefing.")
        lines.append("")
        lines.append("Day: \(context.dayOfWeek) \(Self.dateFormatter.string(from: context.todayDate))")

        if let workout = context.plannedWorkout {
            lines.append("Workout: \(workout)")
        }

        if let recovery = context.recoveryStatus {
            lines.append("Recovery: \(recovery)")
        }

        if !context.todosForToday.isEmpty {
            lines.append("Todos: \(context.todosForToday.joined(separator: "; "))")
        }

        if !context.activeGoals.isEmpty {
            lines.append("Goals: \(context.activeGoals.joined(separator: "; "))")
        }

        let significantStreaks = context.streaks.filter { $0.value >= 3 }
        if !significantStreaks.isEmpty {
            let streakStr = significantStreaks.map { "\($0.key):\($0.value)d" }.joined(separator: ", ")
            lines.append("Streaks: \(streakStr)")
        }

        if !context.recentMetrics.isEmpty {
            lines.append("")
            lines.append("Last 7d metrics (date|wt|sleep|mood|energy|workout):")
            for m in context.recentMetrics.suffix(7) {
                let date = Self.dateFormatter.string(from: m.date)
                let wt = m.weight.map { String(format: "%.1f", $0) } ?? "-"
                let sl = m.sleep.map { String(format: "%.1f", $0) } ?? "-"
                let mood = m.moodAM.map { String(format: "%.0f", $0) } ?? "-"
                let eng = m.energy.map { String(format: "%.0f", $0) } ?? "-"
                let wk = m.workoutType ?? (m.workoutCompleted ? "yes" : "-")
                lines.append("\(date)|\(wt)|\(sl)|\(mood)|\(eng)|\(wk)")
            }
        }

        lines.append("")
        lines.append("Format: 3-5 bullet points covering today's plan, notable trends, and motivation. Keep it under 200 words.")

        return lines.joined(separator: "\n")
    }

    private func buildMetricsPrompt(metrics: [MetricSummary], query: String) -> String {
        var lines: [String] = []
        lines.append("Analyze these metrics and answer the question.")
        lines.append("")
        lines.append("Question: \(query)")
        lines.append("")
        lines.append("Data (date|wt|sleep|sleepQ|mood|energy|workout|todoRate):")

        for m in metrics.suffix(14) {
            let date = Self.dateFormatter.string(from: m.date)
            let wt = m.weight.map { String(format: "%.1f", $0) } ?? "-"
            let sl = m.sleep.map { String(format: "%.1f", $0) } ?? "-"
            let sq = m.sleepQuality.map { String(format: "%.0f", $0) } ?? "-"
            let mood = m.moodAM.map { String(format: "%.0f", $0) } ?? "-"
            let eng = m.energy.map { String(format: "%.0f", $0) } ?? "-"
            let wk = m.workoutType ?? (m.workoutCompleted ? "yes" : "-")
            let todo = m.todoCompletionRate.map { String(format: "%.0f%%", $0 * 100) } ?? "-"
            lines.append("\(date)|\(wt)|\(sl)|\(sq)|\(mood)|\(eng)|\(wk)|\(todo)")
        }

        lines.append("")
        lines.append("Respond with a clear analysis in 2-4 sentences. Highlight trends and actionable insights.")

        return lines.joined(separator: "\n")
    }

    private func buildWorkoutPrompt(protocol proto: ProtocolContext, recovery: RecoveryContext) -> String {
        var lines: [String] = []
        lines.append("Suggest workout modifications based on recovery status.")
        lines.append("")
        lines.append("Phase: \(proto.currentPhase)")
        lines.append("Planned: \(proto.todayWorkout)")

        if !proto.trainingGoals.isEmpty {
            lines.append("Goals: \(proto.trainingGoals.joined(separator: "; "))")
        }

        lines.append("")
        lines.append("Recovery data:")

        if let score = recovery.recoveryScore {
            lines.append("  Score: \(String(format: "%.0f", score))")
        }
        if let status = recovery.recoveryStatus {
            lines.append("  Status: \(status)")
        }
        if let hrv = recovery.hrvStatus {
            lines.append("  HRV: \(hrv)")
        }
        if let sleep = recovery.sleepScore {
            lines.append("  Sleep: \(sleep)")
        }
        if let battery = recovery.bodyBattery {
            lines.append("  Body Battery: \(battery)")
        }
        if let readiness = recovery.trainingReadiness {
            lines.append("  Readiness: \(readiness)")
        }
        if let load = recovery.recentTrainingLoad {
            lines.append("  Recent Load: \(load)")
        }

        lines.append("")
        lines.append("Schedule this week:")
        for entry in proto.weeklySchedule {
            lines.append("  \(entry.day): \(entry.type) - \(entry.workout)")
        }

        lines.append("")
        lines.append("Respond with: (1) Go/Modify/Skip recommendation, (2) specific modifications if needed, (3) reasoning in 1-2 sentences.")

        return lines.joined(separator: "\n")
    }

    private func buildQueryPrompt(question: String, context: QueryContext) -> String {
        var lines: [String] = []
        lines.append("Answer this question about the user's fitness and productivity data.")
        lines.append("")
        lines.append("Question: \(question)")

        if let proto = context.currentProtocol {
            lines.append("")
            lines.append("Current protocol: \(proto)")
        }

        if !context.activeGoals.isEmpty {
            lines.append("Goals: \(context.activeGoals.joined(separator: "; "))")
        }

        if !context.memoryItems.isEmpty {
            lines.append("")
            lines.append("Relevant context:")
            for item in context.memoryItems.prefix(5) {
                lines.append("- \(item)")
            }
        }

        if !context.recentLogs.isEmpty {
            lines.append("")
            lines.append("Recent log summaries:")
            for log in context.recentLogs.prefix(7) {
                lines.append("- \(log)")
            }
        }

        lines.append("")
        lines.append("Answer concisely in 2-4 sentences. Be specific and reference the data when possible.")

        return lines.joined(separator: "\n")
    }
}
