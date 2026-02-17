import Foundation

// MARK: - ExerciseCategory

enum ExerciseCategory: String, Codable, Sendable, CaseIterable, Equatable {
    case strength
    case cardio
    case flexibility
    case balance

    var displayName: String {
        switch self {
        case .strength: return "Strength"
        case .cardio: return "Cardio"
        case .flexibility: return "Flexibility"
        case .balance: return "Balance"
        }
    }
}

// MARK: - Exercise

struct Exercise: Identifiable, Codable, Sendable, Equatable, Hashable {
    let id: UUID
    var name: String
    var category: ExerciseCategory
    var muscleGroup: String?
    var equipment: String?
    var isCustom: Bool

    init(
        id: UUID = UUID(),
        name: String,
        category: ExerciseCategory,
        muscleGroup: String? = nil,
        equipment: String? = nil,
        isCustom: Bool = true
    ) {
        self.id = id
        self.name = name
        self.category = category
        self.muscleGroup = muscleGroup
        self.equipment = equipment
        self.isCustom = isCustom
    }
}
