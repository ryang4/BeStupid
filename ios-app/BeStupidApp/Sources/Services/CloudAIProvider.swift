import Foundation

/// Cloud AI provider supporting multiple backends (Anthropic, OpenAI, custom).
/// Conforms to ``AIService`` so it is a drop-in replacement for on-device.
actor CloudAIProvider: AIService {
    let providerName: String
    let isAvailableOffline = false

    private let provider: Provider
    private let endpoint: URL
    private let apiKey: String
    private let model: String
    private let urlSession: URLSession

    // MARK: - Supported Providers

    /// Supported cloud AI providers.
    enum Provider: String, Sendable, CaseIterable, Identifiable {
        case anthropic = "Anthropic"
        case openai = "OpenAI"
        case custom = "Custom"

        var id: String { rawValue }

        var defaultEndpoint: URL {
            switch self {
            case .anthropic:
                return URL(string: "https://api.anthropic.com/v1/messages")!
            case .openai:
                return URL(string: "https://api.openai.com/v1/chat/completions")!
            case .custom:
                return URL(string: "http://localhost:8080/v1/chat/completions")!
            }
        }

        var defaultModel: String {
            switch self {
            case .anthropic: return "claude-sonnet-4-5-20250929"
            case .openai: return "gpt-4o"
            case .custom: return "default"
            }
        }
    }

    // MARK: - Initialization

    init(
        provider: Provider,
        apiKey: String,
        model: String? = nil,
        endpoint: URL? = nil
    ) {
        self.provider = provider
        self.providerName = provider.rawValue
        self.endpoint = endpoint ?? provider.defaultEndpoint
        self.apiKey = apiKey
        self.model = model ?? provider.defaultModel

        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 60
        config.timeoutIntervalForResource = 120
        self.urlSession = URLSession(configuration: config)
    }

    // MARK: - Availability

    var isAvailable: Bool {
        get async {
            !apiKey.isEmpty
        }
    }

    // MARK: - AIService Conformance

    func generateBriefing(context: BriefingContext) async throws -> String {
        let system = """
            You are a personal productivity and fitness coach. Generate concise, \
            actionable morning briefings. Reference specific data points and trends. \
            Keep the tone direct and motivating.
            """
        let user = buildBriefingUserPrompt(context)
        return try await sendRequest(systemPrompt: system, userPrompt: user)
    }

    func analyzeMetrics(metrics: [MetricSummary], query: String) async throws -> String {
        let system = """
            You are a data analyst specializing in fitness and wellness metrics. \
            Identify trends, correlations, and actionable insights from the data provided. \
            Be specific with numbers and timeframes.
            """
        let user = buildMetricsUserPrompt(metrics: metrics, query: query)
        return try await sendRequest(systemPrompt: system, userPrompt: user)
    }

    func suggestWorkout(protocol proto: ProtocolContext, recovery: RecoveryContext) async throws -> String {
        let system = """
            You are an experienced strength and conditioning coach. Given a training protocol \
            and recovery data, recommend whether to proceed as planned, modify the workout, \
            or skip/substitute. Prioritize injury prevention and long-term progress.
            """
        let user = buildWorkoutUserPrompt(protocol: proto, recovery: recovery)
        return try await sendRequest(systemPrompt: system, userPrompt: user)
    }

    func query(_ question: String, context: QueryContext) async throws -> String {
        let system = """
            You are a personal AI assistant with access to the user's fitness logs, \
            training protocol, goals, and notes. Answer questions accurately using the \
            provided context. If the data doesn't contain enough information, say so.
            """
        let user = buildQueryUserPrompt(question: question, context: context)
        return try await sendRequest(systemPrompt: system, userPrompt: user)
    }

    // MARK: - HTTP Implementation

    private func sendRequest(systemPrompt: String, userPrompt: String) async throws -> String {
        guard !apiKey.isEmpty else {
            throw AIError.invalidAPIKey
        }

        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        switch provider {
        case .anthropic:
            request.setValue(apiKey, forHTTPHeaderField: "x-api-key")
            request.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
            request.httpBody = buildAnthropicRequestBody(system: systemPrompt, user: userPrompt)
        case .openai:
            request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
            request.httpBody = buildOpenAIRequestBody(system: systemPrompt, user: userPrompt)
        case .custom:
            request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
            request.httpBody = buildOpenAIRequestBody(system: systemPrompt, user: userPrompt)
        }

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await urlSession.data(for: request)
        } catch let urlError as URLError {
            throw AIError.networkError(urlError.localizedDescription)
        } catch {
            throw AIError.networkError(error.localizedDescription)
        }

        guard let httpResponse = response as? HTTPURLResponse else {
            throw AIError.invalidResponse
        }

        switch httpResponse.statusCode {
        case 200...299:
            return try parseResponse(data)
        case 401:
            throw AIError.invalidAPIKey
        case 429:
            throw AIError.rateLimited
        case 413:
            throw AIError.contextTooLarge
        default:
            let body = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw AIError.generationFailed("HTTP \(httpResponse.statusCode): \(body)")
        }
    }

    // MARK: - Request Body Builders

    private func buildAnthropicRequestBody(system: String, user: String) -> Data {
        let body: [String: Any] = [
            "model": model,
            "max_tokens": 1024,
            "system": system,
            "messages": [
                ["role": "user", "content": user]
            ]
        ]
        return (try? JSONSerialization.data(withJSONObject: body)) ?? Data()
    }

    private func buildOpenAIRequestBody(system: String, user: String) -> Data {
        let body: [String: Any] = [
            "model": model,
            "max_tokens": 1024,
            "messages": [
                ["role": "system", "content": system],
                ["role": "user", "content": user]
            ]
        ]
        return (try? JSONSerialization.data(withJSONObject: body)) ?? Data()
    }

    // MARK: - Response Parsing

    private func parseResponse(_ data: Data) throws -> String {
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw AIError.invalidResponse
        }

        // Anthropic format: { "content": [{ "type": "text", "text": "..." }] }
        if let content = json["content"] as? [[String: Any]],
           let first = content.first,
           let text = first["text"] as? String {
            return text
        }

        // OpenAI format: { "choices": [{ "message": { "content": "..." } }] }
        if let choices = json["choices"] as? [[String: Any]],
           let first = choices.first,
           let message = first["message"] as? [String: Any],
           let content = message["content"] as? String {
            return content
        }

        throw AIError.invalidResponse
    }

    // MARK: - User Prompt Builders (richer than on-device, cloud models handle more context)

    private static let dateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd (EEE)"
        return f
    }()

    private static let shortDateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "MM/dd"
        return f
    }()

    private func buildBriefingUserPrompt(_ context: BriefingContext) -> String {
        var sections: [String] = []

        sections.append("## Today: \(context.dayOfWeek), \(Self.dateFormatter.string(from: context.todayDate))")

        if let workout = context.plannedWorkout {
            sections.append("### Planned Workout\n\(workout)")
        }

        if let recovery = context.recoveryStatus {
            sections.append("### Recovery Status\n\(recovery)")
        }

        if !context.todosForToday.isEmpty {
            let todoList = context.todosForToday.map { "- [ ] \($0)" }.joined(separator: "\n")
            sections.append("### Today's Todos\n\(todoList)")
        }

        if !context.activeGoals.isEmpty {
            let goalList = context.activeGoals.map { "- \($0)" }.joined(separator: "\n")
            sections.append("### Active Goals\n\(goalList)")
        }

        if !context.streaks.isEmpty {
            let streakList = context.streaks
                .sorted { $0.value > $1.value }
                .map { "- \($0.key): \($0.value) days" }
                .joined(separator: "\n")
            sections.append("### Habit Streaks\n\(streakList)")
        }

        if !context.recentMetrics.isEmpty {
            var table = "### Last 7 Days Metrics\n"
            table += "| Date | Weight | Sleep | Mood | Energy | Workout | Todos |\n"
            table += "|------|--------|-------|------|--------|---------|-------|\n"
            for m in context.recentMetrics.suffix(7) {
                let date = Self.shortDateFormatter.string(from: m.date)
                let wt = m.weight.map { String(format: "%.1f", $0) } ?? "-"
                let sl = m.sleep.map { String(format: "%.1fh", $0) } ?? "-"
                let mood = m.moodAM.map { String(format: "%.0f/10", $0) } ?? "-"
                let eng = m.energy.map { String(format: "%.0f/10", $0) } ?? "-"
                let wk = m.workoutType ?? (m.workoutCompleted ? "Done" : "-")
                let todo = m.todoCompletionRate.map { String(format: "%.0f%%", $0 * 100) } ?? "-"
                table += "| \(date) | \(wt) | \(sl) | \(mood) | \(eng) | \(wk) | \(todo) |\n"
            }
            sections.append(table)
        }

        sections.append("""
            ### Instructions
            Generate a morning briefing with:
            1. A motivating opener referencing today's focus
            2. Key metrics trends (improving/declining/stable)
            3. Today's workout plan with any recovery-based notes
            4. Top priorities from todos
            5. Relevant streak/goal progress
            Keep it to 5-8 bullet points, under 300 words.
            """)

        return sections.joined(separator: "\n\n")
    }

    private func buildMetricsUserPrompt(metrics: [MetricSummary], query: String) -> String {
        var sections: [String] = []

        sections.append("## Question\n\(query)")

        var table = "## Metrics Data\n"
        table += "| Date | Weight | Sleep | Sleep Q | Mood | Energy | Workout | Todos |\n"
        table += "|------|--------|-------|---------|------|--------|---------|-------|\n"
        for m in metrics.suffix(30) {
            let date = Self.shortDateFormatter.string(from: m.date)
            let wt = m.weight.map { String(format: "%.1f", $0) } ?? "-"
            let sl = m.sleep.map { String(format: "%.1f", $0) } ?? "-"
            let sq = m.sleepQuality.map { String(format: "%.0f", $0) } ?? "-"
            let mood = m.moodAM.map { String(format: "%.0f", $0) } ?? "-"
            let eng = m.energy.map { String(format: "%.0f", $0) } ?? "-"
            let wk = m.workoutType ?? (m.workoutCompleted ? "Done" : "-")
            let todo = m.todoCompletionRate.map { String(format: "%.0f%%", $0 * 100) } ?? "-"
            table += "| \(date) | \(wt) | \(sl) | \(sq) | \(mood) | \(eng) | \(wk) | \(todo) |\n"
        }
        sections.append(table)

        sections.append("""
            ## Instructions
            Analyze the data above and answer the question. Include:
            - Specific numbers and date ranges
            - Trend direction (improving/declining/stable) with evidence
            - Correlations between metrics if relevant
            - Actionable recommendations
            """)

        return sections.joined(separator: "\n\n")
    }

    private func buildWorkoutUserPrompt(protocol proto: ProtocolContext, recovery: RecoveryContext) -> String {
        var sections: [String] = []

        sections.append("## Training Protocol")
        sections.append("Phase: \(proto.currentPhase)")
        sections.append("Today's Planned Workout: \(proto.todayWorkout)")

        if !proto.trainingGoals.isEmpty {
            sections.append("Training Goals: \(proto.trainingGoals.joined(separator: ", "))")
        }

        var schedule = "### Weekly Schedule\n"
        for entry in proto.weeklySchedule {
            schedule += "- **\(entry.day)**: \(entry.type) -- \(entry.workout)\n"
        }
        sections.append(schedule)

        var recovery_section = "## Recovery Data\n"
        if let score = recovery.recoveryScore {
            recovery_section += "- Recovery Score: \(String(format: "%.0f", score))\n"
        }
        if let status = recovery.recoveryStatus {
            recovery_section += "- Recovery Status: \(status)\n"
        }
        if let hrv = recovery.hrvStatus {
            recovery_section += "- HRV Status: \(hrv)\n"
        }
        if let sleep = recovery.sleepScore {
            recovery_section += "- Sleep Score: \(sleep)\n"
        }
        if let battery = recovery.bodyBattery {
            recovery_section += "- Body Battery: \(battery)\n"
        }
        if let readiness = recovery.trainingReadiness {
            recovery_section += "- Training Readiness: \(readiness)\n"
        }
        if let load = recovery.recentTrainingLoad {
            recovery_section += "- Recent Training Load: \(load)\n"
        }
        sections.append(recovery_section)

        sections.append("""
            ## Instructions
            Based on the recovery data and training protocol, provide:
            1. **Recommendation**: GO (proceed as planned), MODIFY (adjust intensity/volume), or SKIP (rest/substitute)
            2. **Modifications** (if applicable): specific changes to sets, reps, intensity, or exercise substitutions
            3. **Reasoning**: 2-3 sentences explaining why, referencing specific recovery metrics
            4. **Alternative** (if SKIP): a recovery-focused alternative activity
            """)

        return sections.joined(separator: "\n\n")
    }

    private func buildQueryUserPrompt(question: String, context: QueryContext) -> String {
        var sections: [String] = []

        sections.append("## Question\n\(question)")

        if let proto = context.currentProtocol {
            sections.append("## Current Training Protocol\n\(proto)")
        }

        if !context.activeGoals.isEmpty {
            let goalList = context.activeGoals.map { "- \($0)" }.joined(separator: "\n")
            sections.append("## Active Goals\n\(goalList)")
        }

        if !context.memoryItems.isEmpty {
            let memList = context.memoryItems.map { "- \($0)" }.joined(separator: "\n")
            sections.append("## Relevant Context\n\(memList)")
        }

        if !context.recentLogs.isEmpty {
            let logList = context.recentLogs.map { "- \($0)" }.joined(separator: "\n")
            sections.append("## Recent Daily Log Summaries\n\(logList)")
        }

        sections.append("""
            ## Instructions
            Answer the question using the provided context. Be specific and reference \
            actual data points when possible. If the available data is insufficient to \
            answer confidently, state what information is missing.
            """)

        return sections.joined(separator: "\n\n")
    }
}
