import SwiftUI

struct LogListView: View {
    @State private var viewModel = LogViewModel()

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                Picker("View", selection: $viewModel.viewMode) {
                    ForEach(LogViewMode.allCases, id: \.self) { mode in
                        Text(mode.rawValue).tag(mode)
                    }
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)
                .padding(.vertical, 8)

                if viewModel.isLoading {
                    Spacer()
                    ProgressView("Loading logs...")
                        .frame(maxWidth: .infinity)
                    Spacer()
                } else if let error = viewModel.errorMessage {
                    Spacer()
                    ContentUnavailableView(
                        "Failed to Load",
                        systemImage: "exclamationmark.triangle",
                        description: Text(error)
                    )
                    Spacer()
                } else if viewModel.viewMode == .list {
                    listContent
                } else {
                    calendarContent
                }
            }
            .navigationTitle("Logs")
            .searchable(text: $viewModel.searchText, prompt: "Search logs...")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    NavigationLink {
                        if let proto = viewModel.currentProtocol {
                            ProtocolView(trainingProtocol: proto)
                        } else {
                            ContentUnavailableView(
                                "No Protocol",
                                systemImage: "calendar.badge.exclamationmark",
                                description: Text("No weekly protocol is loaded.")
                            )
                        }
                    } label: {
                        Label("Protocol", systemImage: "calendar.badge.clock")
                    }
                }
            }
            .task {
                await viewModel.loadLogs()
                await viewModel.loadProtocol()
            }
            .sheet(isPresented: $viewModel.isEditing) {
                if var editingLog = viewModel.editingLog {
                    LogEditorView(
                        log: Binding(
                            get: { viewModel.editingLog ?? editingLog },
                            set: { viewModel.editingLog = $0 }
                        ),
                        onSave: {
                            Task { await viewModel.saveEdit() }
                        },
                        onCancel: {
                            viewModel.cancelEdit()
                        }
                    )
                }
            }
        }
    }

    // MARK: - List Content

    @ViewBuilder
    private var listContent: some View {
        if viewModel.filteredLogs.isEmpty {
            ContentUnavailableView.search(text: viewModel.searchText)
        } else {
            List {
                ForEach(viewModel.sortedMonthKeys, id: \.self) { monthKey in
                    Section(monthKey) {
                        if let monthLogs = viewModel.logsByMonth[monthKey] {
                            ForEach(monthLogs.sorted(by: { $0.date > $1.date })) { log in
                                NavigationLink {
                                    LogDetailView(log: log) {
                                        viewModel.startEditing(log)
                                    }
                                } label: {
                                    LogRowView(log: log)
                                }
                            }
                        }
                    }
                }
            }
            .listStyle(.insetGrouped)
        }
    }

    // MARK: - Calendar Content

    @ViewBuilder
    private var calendarContent: some View {
        VStack(spacing: 0) {
            calendarHeader
            calendarWeekdayLabels
            calendarGrid

            Divider()
                .padding(.top, 8)

            if let selectedLog = viewModel.selectedLog {
                NavigationLink {
                    LogDetailView(log: selectedLog) {
                        viewModel.startEditing(selectedLog)
                    }
                } label: {
                    calendarSelectedLogCard(selectedLog)
                }
                .buttonStyle(.plain)
                .padding()
            } else {
                Spacer()
                Text("Select a day to view its log")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                Spacer()
            }
        }
    }

    private var calendarHeader: some View {
        HStack {
            Button {
                viewModel.changeMonth(by: -1)
            } label: {
                Image(systemName: "chevron.left")
                    .font(.title3.weight(.semibold))
            }

            Spacer()

            Text(viewModel.selectedMonthLabel)
                .font(.title3.weight(.semibold))

            Spacer()

            Button {
                viewModel.changeMonth(by: 1)
            } label: {
                Image(systemName: "chevron.right")
                    .font(.title3.weight(.semibold))
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
    }

    private var calendarWeekdayLabels: some View {
        let labels = ["S", "M", "T", "W", "T", "F", "S"]
        return LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 7), spacing: 4) {
            ForEach(labels.indices, id: \.self) { index in
                Text(labels[index])
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity)
            }
        }
        .padding(.horizontal, 12)
    }

    private var calendarGrid: some View {
        LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 7), spacing: 4) {
            ForEach(viewModel.calendarDays) { day in
                if let date = day.date {
                    CalendarDayCell(
                        dayNumber: day.dayNumber,
                        hasLog: day.hasLog,
                        isSelected: isSelected(date),
                        isToday: Calendar.current.isDateInToday(date)
                    )
                    .onTapGesture {
                        Task { await viewModel.selectDate(date) }
                    }
                } else {
                    Color.clear
                        .frame(height: 40)
                }
            }
        }
        .padding(.horizontal, 12)
    }

    private func isSelected(_ date: Date) -> Bool {
        guard let selected = viewModel.selectedLog else { return false }
        return Calendar.current.isDate(date, inSameDayAs: selected.date)
    }

    private func calendarSelectedLogCard(_ log: DailyLog) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(log.title)
                    .font(.headline)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            HStack(spacing: 16) {
                if let workout = log.plannedWorkout {
                    Label(workout, systemImage: workoutIcon(for: workout))
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                if let weight = log.weight {
                    Label(String(format: "%.1f lbs", weight), systemImage: "scalemass")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                if let sleep = log.sleep {
                    Label(String(format: "%.1f hrs", sleep), systemImage: "moon.zzz")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding()
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - LogRowView

private struct LogRowView: View {
    let log: DailyLog

    private var dateLabel: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEE, MMM d"
        return formatter.string(from: log.date)
    }

    var body: some View {
        HStack(spacing: 12) {
            workoutIconView
                .frame(width: 36, height: 36)

            VStack(alignment: .leading, spacing: 4) {
                Text(dateLabel)
                    .font(.headline)

                HStack(spacing: 12) {
                    if let workout = log.plannedWorkout {
                        Text(workout)
                            .font(.subheadline)
                            .foregroundStyle(.blue)
                    }

                    if let rate = log.todoCompletionRate {
                        Text("\(Int(rate * 100))% todos")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 4) {
                if let weight = log.weight {
                    Text(String(format: "%.1f", weight))
                        .font(.subheadline.monospacedDigit())
                    Text("lbs")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding(.vertical, 4)
    }

    @ViewBuilder
    private var workoutIconView: some View {
        let iconName = workoutIcon(for: log.plannedWorkout ?? "")
        Image(systemName: iconName)
            .font(.system(size: 16, weight: .semibold))
            .foregroundStyle(.white)
            .frame(width: 36, height: 36)
            .background(workoutColor(for: log.plannedWorkout ?? ""), in: RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - CalendarDayCell

private struct CalendarDayCell: View {
    let dayNumber: Int
    let hasLog: Bool
    let isSelected: Bool
    let isToday: Bool

    var body: some View {
        VStack(spacing: 2) {
            Text("\(dayNumber)")
                .font(.system(.body, design: .rounded).weight(isToday ? .bold : .regular))
                .foregroundStyle(foregroundColor)

            Circle()
                .fill(hasLog ? Color.blue : Color.clear)
                .frame(width: 6, height: 6)
        }
        .frame(height: 40)
        .frame(maxWidth: .infinity)
        .background(backgroundColor, in: RoundedRectangle(cornerRadius: 8))
    }

    private var foregroundColor: Color {
        if isSelected { return .white }
        if isToday { return .blue }
        return .primary
    }

    private var backgroundColor: Color {
        if isSelected { return .blue }
        if isToday { return .blue.opacity(0.1) }
        return .clear
    }
}

// MARK: - Helpers

private func workoutIcon(for type: String) -> String {
    switch type.lowercased() {
    case "swim", "swimming": return "figure.pool.swim"
    case "bike", "cycling": return "figure.outdoor.cycle"
    case "run", "running": return "figure.run"
    case "strength", "weights": return "dumbbell"
    case "brick", "mixed": return "figure.mixed.cardio"
    case "recovery", "rest": return "figure.cooldown"
    default: return "figure.walk"
    }
}

private func workoutColor(for type: String) -> Color {
    switch type.lowercased() {
    case "swim", "swimming": return .cyan
    case "bike", "cycling": return .green
    case "run", "running": return .orange
    case "strength", "weights": return .purple
    case "brick", "mixed": return .red
    case "recovery", "rest": return .mint
    default: return .gray
    }
}

// MARK: - Preview

#Preview("Log List - List View") {
    LogListView()
        .environment(AppState())
}

#Preview("Log List - Calendar View") {
    @Previewable @State var viewModel = LogViewModel()
    NavigationStack {
        LogListView()
    }
    .environment(AppState())
}
