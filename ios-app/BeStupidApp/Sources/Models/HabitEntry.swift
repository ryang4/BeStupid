import Foundation

struct HabitEntry: Identifiable, Codable, Sendable, Equatable {
    let id: UUID
    var habitId: String
    var name: String
    var isCompleted: Bool

    init(
        id: UUID = UUID(),
        habitId: String,
        name: String,
        isCompleted: Bool = false
    ) {
        self.id = id
        self.habitId = habitId
        self.name = name
        self.isCompleted = isCompleted
    }
}
