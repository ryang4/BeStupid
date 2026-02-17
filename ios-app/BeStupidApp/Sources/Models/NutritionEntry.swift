import Foundation

struct NutritionEntry: Identifiable, Codable, Sendable, Equatable {
    let id: UUID
    var time: String?
    var food: String
    var calories: Int?
    var proteinG: Int?
    var carbsG: Int?
    var fatG: Int?

    init(
        id: UUID = UUID(),
        time: String? = nil,
        food: String,
        calories: Int? = nil,
        proteinG: Int? = nil,
        carbsG: Int? = nil,
        fatG: Int? = nil
    ) {
        self.id = id
        self.time = time
        self.food = food
        self.calories = calories
        self.proteinG = proteinG
        self.carbsG = carbsG
        self.fatG = fatG
    }

    /// Total macronutrient grams (protein + carbs + fat).
    var totalMacrosG: Int {
        (proteinG ?? 0) + (carbsG ?? 0) + (fatG ?? 0)
    }
}
