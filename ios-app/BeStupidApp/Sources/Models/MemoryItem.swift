import Foundation

// MARK: - MemoryCategory

enum MemoryCategory: String, Codable, Sendable, CaseIterable, Equatable {
    case people
    case projects
    case decisions
    case commitments

    var displayName: String {
        switch self {
        case .people: return "People"
        case .projects: return "Projects"
        case .decisions: return "Decisions"
        case .commitments: return "Commitments"
        }
    }
}

// MARK: - Interaction

struct Interaction: Identifiable, Codable, Sendable, Equatable {
    let id: UUID
    var date: Date
    var note: String

    init(
        id: UUID = UUID(),
        date: Date = Date(),
        note: String
    ) {
        self.id = id
        self.date = date
        self.note = note
    }
}

// MARK: - MemoryItem

struct MemoryItem: Identifiable, Codable, Sendable, Equatable {
    let id: UUID
    var category: MemoryCategory
    var slug: String
    var name: String
    var status: String?
    var created: Date
    var updated: Date
    var fields: [String: String]
    var interactions: [Interaction]

    init(
        id: UUID = UUID(),
        category: MemoryCategory,
        slug: String,
        name: String,
        status: String? = nil,
        created: Date = Date(),
        updated: Date = Date(),
        fields: [String: String] = [:],
        interactions: [Interaction] = []
    ) {
        self.id = id
        self.category = category
        self.slug = slug
        self.name = name
        self.status = status
        self.created = created
        self.updated = updated
        self.fields = fields
        self.interactions = interactions
    }

    /// Adds a new interaction and updates the `updated` timestamp.
    mutating func addInteraction(note: String, date: Date = Date()) {
        interactions.append(Interaction(date: date, note: note))
        updated = date
    }

    /// Returns the most recent interaction, if any.
    var latestInteraction: Interaction? {
        interactions.max(by: { $0.date < $1.date })
    }
}
