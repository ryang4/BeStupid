import Foundation
import SwiftData

/// Central configuration for the SwiftData persistence layer.
///
/// This enum provides factory methods for creating `ModelContainer` instances
/// with the correct schema. The cache can always be rebuilt from the git repo,
/// so data loss from schema migrations is acceptable -- we use the default
/// lightweight migration strategy.
enum PersistenceConfiguration {

    /// All SwiftData model types managed by this container.
    static let modelTypes: [any PersistentModel.Type] = [
        CachedDailyLog.self,
        CachedMetric.self,
        CachedWorkout.self,
        CachedExercise.self,
    ]

    /// Creates the production model container.
    ///
    /// - Parameter inMemory: When `true`, the store is held only in memory
    ///   (useful for tests and SwiftUI previews). Defaults to `false`.
    /// - Returns: A fully configured `ModelContainer`.
    /// - Throws: If the container cannot be created (e.g. schema conflict).
    static func createContainer(inMemory: Bool = false) throws -> ModelContainer {
        let schema = Schema(modelTypes)
        let configuration = ModelConfiguration(
            isStoredInMemoryOnly: inMemory
        )
        return try ModelContainer(for: schema, configurations: [configuration])
    }

    /// Creates an in-memory container suitable for testing and SwiftUI previews.
    ///
    /// This is a convenience wrapper around `createContainer(inMemory: true)`.
    static func previewContainer() throws -> ModelContainer {
        try createContainer(inMemory: true)
    }
}
