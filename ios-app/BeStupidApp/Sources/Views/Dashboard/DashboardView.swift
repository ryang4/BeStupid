import SwiftUI

/// The main dashboard screen -- the first thing users see when opening the app.
///
/// Displays today's status at a glance: scheduled workout, key metrics,
/// todo checklist, habits, and a week overview.
struct DashboardView: View {
    @Environment(AppState.self) private var appState
    @State private var viewModel = DashboardViewModel()

    var body: some View {
        NavigationStack {
            ZStack {
                ScrollView {
                    VStack(spacing: 16) {
                        headerSection
                        todayWorkoutCard
                        metricsGrid
                        todosSection
                        habitsSection
                        weekOverview
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 8)
                    .padding(.bottom, 24)
                }
                .navigationTitle("Dashboard")
                .refreshable {
                    await viewModel.refresh()
                }
                .task {
                    await viewModel.loadDashboard()
                }
                .sheet(isPresented: $viewModel.isEditingMetric) {
                    MetricsQuickLogView(
                        field: viewModel.editingField ?? .weight,
                        value: $viewModel.editingValue,
                        onSave: { value in
                            Task {
                                await viewModel.updateMetric(
                                    field: viewModel.editingField ?? .weight,
                                    value: value
                                )
                            }
                        }
                    )
                    .presentationDetents([.medium])
                }

                LoadingOverlay(
                    message: "Loading dashboard...",
                    isVisible: viewModel.isLoading
                )
            }
        }
    }

    // MARK: - Header Section

    private var headerSection: some View {
        HStack(alignment: .center) {
            VStack(alignment: .leading, spacing: 2) {
                Text(formattedDate)
                    .font(.title3)
                    .fontWeight(.semibold)

                if let briefing = viewModel.todayLog?.dailyBriefing {
                    Text(briefing)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
            }

            Spacer()

            syncStatusIndicator
        }
        .padding(.vertical, 4)
    }

    private var formattedDate: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEEE, MMM d"
        return formatter.string(from: Date())
    }

    private var syncStatusIndicator: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(syncDotColor)
                .frame(width: 8, height: 8)

            Text(syncStatusLabel)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(Color(.systemGray6), in: Capsule())
    }

    private var syncDotColor: Color {
        switch appState.syncStatus {
        case .idle:
            return .gray
        case .syncing:
            return .yellow
        case .success:
            return .green
        case .error:
            return .red
        }
    }

    private var syncStatusLabel: String {
        switch appState.syncStatus {
        case .idle:
            return "Idle"
        case .syncing:
            return "Syncing"
        case .success(let date):
            let formatter = RelativeDateTimeFormatter()
            formatter.unitsStyle = .abbreviated
            return formatter.localizedString(for: date, relativeTo: Date())
        case .error:
            return "Error"
        }
    }

    // MARK: - Today's Workout Card

    @ViewBuilder
    private var todayWorkoutCard: some View {
        if viewModel.isLoading {
            EmptyView()
        } else if let workoutType = viewModel.todayWorkoutType {
            TodayCardView(
                workoutType: workoutType,
                workoutDescription: viewModel.todayWorkoutDescription,
                protocolPhase: protocolPhaseLabel,
                isWorkoutActive: appState.hasActiveWorkout,
                onStartWorkout: {
                    appState.selectedTab = .workout
                }
            )
        } else {
            NoWorkoutCardView()
        }
    }

    private var protocolPhaseLabel: String? {
        guard let proto = viewModel.currentProtocol else { return nil }
        return "\(proto.phase) - \(proto.weekNumber)"
    }

    // MARK: - Metrics Grid

    private var metricsGrid: some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            MetricBadge(
                title: "Weight",
                value: viewModel.todayLog?.weight.map { String(format: "%.1f", $0) } ?? "",
                unit: "lbs",
                trend: viewModel.weightTrend,
                field: .weight,
                color: .blue,
                onTap: { viewModel.startQuickLog(field: .weight) }
            )

            MetricBadge(
                title: "Sleep",
                value: viewModel.todayLog?.sleep.map { String(format: "%.1f", $0) } ?? "",
                unit: "hrs",
                trend: computeSleepTrend(),
                field: .sleep,
                color: .indigo,
                onTap: { viewModel.startQuickLog(field: .sleep) }
            )

            MetricBadge(
                title: "Mood",
                value: viewModel.todayLog?.moodAM.map { String(format: "%.0f", $0) } ?? "",
                unit: "/10",
                trend: viewModel.moodTrend,
                field: .moodAM,
                color: .orange,
                onTap: { viewModel.startQuickLog(field: .moodAM) }
            )

            MetricBadge(
                title: "Energy",
                value: viewModel.todayLog?.energy.map { String(format: "%.0f", $0) } ?? "",
                unit: "/10",
                trend: computeEnergyTrend(),
                field: .energy,
                color: .green,
                onTap: { viewModel.startQuickLog(field: .energy) }
            )
        }
    }

    private func computeSleepTrend() -> TrendDirection {
        guard let points = viewModel.recentMetrics[.sleep], points.count >= 3 else {
            return .insufficient
        }
        let sorted = points.sorted { $0.date < $1.date }
        let recent = Array(sorted.suffix(sorted.count / 2))
        let older = Array(sorted.prefix(sorted.count / 2))
        guard !recent.isEmpty, !older.isEmpty else { return .insufficient }
        let recentAvg = recent.reduce(0.0) { $0 + $1.value } / Double(recent.count)
        let olderAvg = older.reduce(0.0) { $0 + $1.value } / Double(older.count)
        let pct = abs(recentAvg - olderAvg) / max(olderAvg, 0.01)
        if pct < 0.02 { return .stable }
        return recentAvg > olderAvg ? .up : .down
    }

    private func computeEnergyTrend() -> TrendDirection {
        guard let points = viewModel.recentMetrics[.energy], points.count >= 3 else {
            return .insufficient
        }
        let sorted = points.sorted { $0.date < $1.date }
        let recent = Array(sorted.suffix(sorted.count / 2))
        let older = Array(sorted.prefix(sorted.count / 2))
        guard !recent.isEmpty, !older.isEmpty else { return .insufficient }
        let recentAvg = recent.reduce(0.0) { $0 + $1.value } / Double(recent.count)
        let olderAvg = older.reduce(0.0) { $0 + $1.value } / Double(older.count)
        let pct = abs(recentAvg - olderAvg) / max(olderAvg, 0.01)
        if pct < 0.02 { return .stable }
        return recentAvg > olderAvg ? .up : .down
    }

    // MARK: - Todos Section

    @ViewBuilder
    private var todosSection: some View {
        if let log = viewModel.todayLog, !log.todos.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("Todos")
                        .font(.headline)

                    Spacer()

                    if let rate = log.todoCompletionRate {
                        Text("\(Int(rate * 100))%")
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundStyle(completionRateColor(rate))
                            .padding(.horizontal, 8)
                            .padding(.vertical, 3)
                            .background(completionRateColor(rate).opacity(0.12), in: Capsule())
                    }
                }

                VStack(spacing: 0) {
                    ForEach(Array(log.todos.enumerated()), id: \.element.id) { index, todo in
                        TodoRowView(
                            todo: todo,
                            onToggle: {
                                Task { await viewModel.toggleTodo(at: index) }
                            }
                        )

                        if index < log.todos.count - 1 {
                            Divider()
                                .padding(.leading, 36)
                        }
                    }
                }
                .padding(12)
                .background(.background, in: RoundedRectangle(cornerRadius: 12))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(Color.primary.opacity(0.08), lineWidth: 1)
                )
            }
        } else if !viewModel.isLoading {
            EmptyStateView(
                icon: "checklist",
                title: "No Todos",
                message: "Add todos through the Telegram bot or create a daily log."
            )
        }
    }

    // MARK: - Habits Section

    @ViewBuilder
    private var habitsSection: some View {
        if let log = viewModel.todayLog, !log.habits.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("Habits")
                        .font(.headline)

                    Spacer()

                    if let rate = log.habitCompletionRate {
                        Text("\(Int(rate * 100))%")
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundStyle(completionRateColor(rate))
                            .padding(.horizontal, 8)
                            .padding(.vertical, 3)
                            .background(completionRateColor(rate).opacity(0.12), in: Capsule())
                    }
                }

                VStack(spacing: 0) {
                    ForEach(Array(log.habits.enumerated()), id: \.element.id) { index, habit in
                        HabitRowView(
                            habit: habit,
                            onToggle: {
                                Task { await viewModel.toggleHabit(at: index) }
                            }
                        )

                        if index < log.habits.count - 1 {
                            Divider()
                                .padding(.leading, 36)
                        }
                    }
                }
                .padding(12)
                .background(.background, in: RoundedRectangle(cornerRadius: 12))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(Color.primary.opacity(0.08), lineWidth: 1)
                )
            }
        }
    }

    // MARK: - Week Overview

    @ViewBuilder
    private var weekOverview: some View {
        if !viewModel.weekSummary.isEmpty {
            WeekAtAGlanceView(days: viewModel.weekSummary)
        }
    }

    // MARK: - Helpers

    private func completionRateColor(_ rate: Double) -> Color {
        if rate >= 0.8 { return .green }
        if rate >= 0.5 { return .orange }
        return .red
    }
}

// MARK: - TodoRowView

/// A single todo item row with a tappable checkbox.
private struct TodoRowView: View {
    let todo: TodoItem
    let onToggle: () -> Void

    var body: some View {
        Button(action: onToggle) {
            HStack(spacing: 12) {
                Image(systemName: todo.isCompleted ? "checkmark.circle.fill" : "circle")
                    .font(.system(size: 20))
                    .foregroundStyle(todo.isCompleted ? .green : .secondary)

                Text(todo.text)
                    .font(.subheadline)
                    .strikethrough(todo.isCompleted)
                    .foregroundStyle(todo.isCompleted ? .secondary : .primary)

                Spacer()
            }
            .padding(.vertical, 6)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(todo.text), \(todo.isCompleted ? "completed" : "not completed")")
        .accessibilityHint("Double tap to toggle")
    }
}

// MARK: - HabitRowView

/// A single habit entry row with a tappable checkbox.
private struct HabitRowView: View {
    let habit: HabitEntry
    let onToggle: () -> Void

    var body: some View {
        Button(action: onToggle) {
            HStack(spacing: 12) {
                Image(systemName: habit.isCompleted ? "checkmark.diamond.fill" : "diamond")
                    .font(.system(size: 18))
                    .foregroundStyle(habit.isCompleted ? .purple : .secondary)

                Text(habit.name)
                    .font(.subheadline)
                    .strikethrough(habit.isCompleted)
                    .foregroundStyle(habit.isCompleted ? .secondary : .primary)

                Spacer()
            }
            .padding(.vertical, 6)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(habit.name), \(habit.isCompleted ? "completed" : "not completed")")
        .accessibilityHint("Double tap to toggle")
    }
}

// MARK: - Preview

#Preview("Dashboard") {
    DashboardView()
        .environment(AppState())
}

#Preview("Dashboard - Syncing") {
    let state = AppState()
    state.syncStatus = .syncing
    return DashboardView()
        .environment(state)
}

#Preview("Dashboard - Error") {
    let state = AppState()
    state.syncStatus = .error("Network unreachable")
    return DashboardView()
        .environment(state)
}
