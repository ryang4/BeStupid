# BeStupid iOS App - Implementation Plan

## Vision
A portable companion to the BeStupid Telegram bot that gives Ryan direct access to his data and workout tracking on the go — without needing the bot running or internet access.

## Three Core Rules
1. **Not tied to any API provider** — On-device AI default (Apple Foundation Models), pluggable cloud providers via abstraction layer
2. **Works offline** — All features functional without internet; sync when connected
3. **Local data with git backups** — Data stored on-device in same markdown/JSON format as existing system; automated git push to BeStupid repo

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   SwiftUI Views                      │
│  Dashboard │ Workout │ Logs │ Charts │ Settings      │
├─────────────────────────────────────────────────────┤
│                  ViewModels                          │
│  DashboardVM │ WorkoutVM │ LogVM │ ChartsVM          │
├─────────────────────────────────────────────────────┤
│               Domain Services                        │
│  WorkoutService │ MetricsService │ MemoryService     │
│  SyncService │ AIService │ HealthKitService          │
├─────────────────────────────────────────────────────┤
│              Data Layer                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ SwiftData │  │ Markdown │  │ Git Repository   │  │
│  │ (Cache)   │  │ Parser   │  │ (SwiftGitX)      │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
├─────────────────────────────────────────────────────┤
│              Platform Integrations                   │
│  HealthKit │ Foundation Models │ GitHub OAuth        │
└─────────────────────────────────────────────────────┘
```

### Data Flow
```
Git Repo (GitHub)
    ↕ clone/pull/push (SwiftGitX + GitHub OAuth)
Local Git Working Copy (App Documents/)
    ↕ read/write markdown & JSON files
Markdown/JSON Parser Layer
    ↕ parse ↔ serialize
SwiftData Cache (structured models for fast queries/charts)
    ↕
ViewModels → SwiftUI Views
```

---

## Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| UI Framework | SwiftUI (iOS 18+) | Modern declarative UI, native feel |
| Language | Swift 6.2 | Latest with approachable concurrency |
| Local DB | SwiftData | Apple-native, lightweight cache over git files |
| Charts | Swift Charts | Native, performant, great for health data |
| Git | SwiftGitX (libgit2) | On-device git clone/pull/push |
| Auth | ASWebAuthenticationSession | GitHub OAuth device flow |
| AI (on-device) | Apple Foundation Models | Free, private, offline, ~3B params |
| AI (cloud) | Protocol-based abstraction | Swap Anthropic/OpenAI/etc via settings |
| Health | HealthKit | Bidirectional workout + metrics sync |
| Architecture | MVVM + Services | Clean separation, testable |
| Min Deployment | iOS 18.0 | Foundation Models require iOS 18+ |
| Build System | Xcode 16+ / Swift Package Manager | Standard Apple toolchain |

---

## Project Structure

```
BeStupidApp/
├── BeStupidApp.swift                    # App entry point
├── Info.plist                           # Permissions (HealthKit, etc.)
│
├── Models/                              # Data models
│   ├── DailyLog.swift                   # Daily log with metrics
│   ├── WorkoutSession.swift             # Active workout tracking
│   ├── Exercise.swift                   # Exercise definition
│   ├── ExerciseSet.swift                # Set within exercise
│   ├── WeeklyProtocol.swift             # Training protocol
│   ├── Metric.swift                     # Body metrics (weight, sleep, mood)
│   ├── MemoryItem.swift                 # People, decisions, commitments
│   ├── NutritionEntry.swift             # Food log entries
│   └── GarminData.swift                 # Garmin sync data model
│
├── Services/                            # Business logic
│   ├── GitSyncService.swift             # Clone/pull/push via SwiftGitX
│   ├── MarkdownParser.swift             # Parse BeStupid markdown format
│   ├── MarkdownSerializer.swift         # Write back to markdown format
│   ├── MetricsExtractor.swift           # Extract metrics from logs
│   ├── WorkoutService.swift             # Manage workout sessions
│   ├── HealthKitService.swift           # HealthKit bidirectional sync
│   ├── AIService.swift                  # Provider-agnostic AI protocol
│   ├── OnDeviceAIProvider.swift         # Apple Foundation Models impl
│   ├── CloudAIProvider.swift            # Anthropic/OpenAI/etc impl
│   ├── DataSyncCoordinator.swift        # Orchestrate git ↔ local ↔ HealthKit
│   └── NotificationService.swift        # Local reminders
│
├── ViewModels/                          # Presentation logic
│   ├── DashboardViewModel.swift         # Home screen state
│   ├── WorkoutViewModel.swift           # Active workout state
│   ├── LogViewModel.swift               # Daily log viewing/editing
│   ├── ChartsViewModel.swift            # Chart data preparation
│   └── SettingsViewModel.swift          # Git, AI, HealthKit config
│
├── Views/                               # SwiftUI views
│   ├── Dashboard/
│   │   ├── DashboardView.swift          # Main dashboard
│   │   ├── TodayCardView.swift          # Today's status card
│   │   ├── MetricsQuickLogView.swift    # Quick-log weight/sleep/mood
│   │   └── WeekAtAGlanceView.swift      # 7-day mini calendar
│   │
│   ├── Workout/
│   │   ├── WorkoutListView.swift        # Browse workout history
│   │   ├── ActiveWorkoutView.swift      # Real-time workout tracker
│   │   ├── WorkoutTimerView.swift       # Timer + rest intervals
│   │   ├── ExerciseLogView.swift        # Log sets/reps/weight
│   │   ├── CardioTrackingView.swift     # Distance/pace/HR for cardio
│   │   ├── WorkoutSummaryView.swift     # Post-workout summary
│   │   └── WorkoutTypePickerView.swift  # Choose/create workout type
│   │
│   ├── Logs/
│   │   ├── LogListView.swift            # Browse daily logs
│   │   ├── LogDetailView.swift          # View single day's log
│   │   ├── LogEditorView.swift          # Edit log entries
│   │   └── ProtocolView.swift           # View weekly protocol
│   │
│   ├── Charts/
│   │   ├── ChartsContainerView.swift    # Tab container for chart types
│   │   ├── TrainingVolumeChart.swift    # Swim/bike/run weekly volume
│   │   ├── StrengthProgressChart.swift  # Weight x reps over time
│   │   ├── BodyMetricsChart.swift       # Weight trend line
│   │   ├── SleepChart.swift             # Sleep hours + quality
│   │   ├── MoodEnergyChart.swift        # Mood/energy/focus patterns
│   │   └── ComplianceChart.swift        # Todo + habit completion
│   │
│   ├── Settings/
│   │   ├── SettingsView.swift           # Main settings
│   │   ├── GitSettingsView.swift        # Repo URL, auth, sync frequency
│   │   ├── AISettingsView.swift         # Provider selection, API keys
│   │   ├── HealthKitSettingsView.swift  # HealthKit permissions
│   │   └── WorkoutTypeEditorView.swift  # Create/edit workout types
│   │
│   └── Shared/
│       ├── MetricBadge.swift            # Colored metric display
│       ├── TrendIndicator.swift         # Up/down/stable arrow
│       ├── LoadingOverlay.swift         # Sync progress
│       └── EmptyStateView.swift         # No data placeholders
│
├── Parsing/                             # Markdown ↔ Structured data
│   ├── InlineFieldParser.swift          # Parse "Weight:: 244" format
│   ├── StrengthLogParser.swift          # Parse "Bench:: 3x10 @ 60 lbs"
│   ├── TrainingValueParser.swift        # Parse "750m/33:39" format
│   ├── YAMLFrontmatterParser.swift      # Parse YAML in markdown
│   ├── DailyLogParser.swift             # Full daily log → model
│   ├── ProtocolParser.swift             # Weekly protocol → model
│   └── MetricsJSONParser.swift          # daily_metrics.json parser
│
├── Persistence/                         # Local storage
│   ├── SwiftDataContainer.swift         # SwiftData model container
│   ├── CachedDailyLog.swift             # SwiftData cached log
│   ├── CachedMetric.swift               # SwiftData cached metric
│   └── CachedWorkout.swift              # SwiftData cached workout
│
└── Resources/
    ├── Assets.xcassets                  # App icons, colors
    └── Localizable.strings              # String resources
```

---

## Implementation Phases

### Phase 1: Foundation (Steps 1-5)
Core infrastructure — git sync, data parsing, local storage.

### Phase 2: Data Visualization (Steps 6-9)
Dashboard, log viewing, charts for training and body metrics.

### Phase 3: Workout Tracking (Steps 10-13)
Real-time workout logging, exercise library, HealthKit sync.

### Phase 4: AI & Polish (Steps 14-16)
On-device AI integration, cloud provider option, polish and testing.

---

## Step-by-Step Implementation

### Step 1: Xcode Project Setup
**Create the Xcode project with proper configuration.**

- Create new Xcode project: "BeStupidApp", iOS App, SwiftUI lifecycle
- Set minimum deployment target: iOS 18.0
- Configure Swift 6.2 language version
- Add Swift Package dependencies:
  - SwiftGitX (git operations)
  - Or: use libgit2 C library via SPM if SwiftGitX unavailable
- Add capabilities: HealthKit, Background Modes (background fetch)
- Configure Info.plist:
  - `NSHealthShareUsageDescription` — read health data
  - `NSHealthUpdateUsageDescription` — write workout data
- Create folder structure matching project layout above
- Add `.gitignore` for Xcode artifacts

### Step 2: Data Models
**Define Swift models matching existing BeStupid data formats.**

- `DailyLog` — matches content/logs/YYYY-MM-DD.md structure:
  - date, title, plannedWorkout, todos, habits
  - Quick log fields: weight, sleep, sleepQuality, moodAM, moodPM, energy, focus
  - Training output: activities (swim/bike/run with distance/time/HR)
  - Strength log: exercises with sets/reps/weight
  - Nutrition: calories, protein, line items
  - Top 3 for tomorrow
- `WorkoutSession` — for real-time tracking:
  - id, type (user-defined string), startTime, endTime, isActive
  - exercises: [ExerciseSet], notes
  - heartRateData (from HealthKit), distance, route
- `Exercise` — exercise definition:
  - name, category, muscleGroup, isCustom
- `ExerciseSet` — single set:
  - exerciseName, setNumber, reps, weightLbs, duration, distance, restSeconds
- `WeeklyProtocol` — matches content/config/protocol_*.md:
  - weekNumber, phase, focus, schedule (day → workout), targets
- `Metric` — single metric data point:
  - date, field (enum), value, source (manual/garmin/healthkit)
- `MemoryItem` — matches memory/*.json:
  - category (people/projects/decisions/commitments), slug, data dict
- `NutritionEntry` — food log line item:
  - time, food, calories, proteinG, carbsG, fatG
- `GarminData` — matches data/garmin_metrics.json:
  - sleep stages, HRV, body battery, training readiness, recovery

All models conform to `Codable`, `Identifiable`, `Sendable`.

### Step 3: Markdown Parser & Serializer
**Parse existing BeStupid markdown files into Swift models and write them back.**

- `YAMLFrontmatterParser`:
  - Extract YAML between `---` delimiters
  - Parse title, date, tags, phase, week_number
- `InlineFieldParser`:
  - Regex pattern: `^(\w[\w\s]*)::[ \t]*(.+)$`
  - Handle all field types: Weight, Sleep, Mood_AM, etc.
  - Normalize values (Sleep "6:35" → 6.58 hours)
- `StrengthLogParser`:
  - Pattern: `Exercise Name:: NxN @ N lbs`
  - Extract exercise name, sets, reps, weight
- `TrainingValueParser`:
  - Pattern: `750m/33:39` → (distance: 750, unit: .meters, duration: 33.65)
  - Pattern: `4.5/45` → (distance: 4.5, unit: .miles, duration: 45.0)
- `DailyLogParser`:
  - Combine all parsers to produce full `DailyLog` from markdown
  - Section-based parsing (## headers as delimiters)
  - Todo checkbox parsing: `- [ ]` vs `- [x]`
- `ProtocolParser`:
  - Parse weekly schedule table (| Day | Type | Workout |)
  - Extract training goals and targets
- `MarkdownSerializer`:
  - Reverse: `DailyLog` → markdown string in exact BeStupid format
  - Preserve formatting compatibility with bot
  - Use Jinja2-like template approach (Swift string interpolation)
- `MetricsJSONParser`:
  - Parse data/daily_metrics.json
  - Parse data/garmin_metrics.json

### Step 4: Git Sync Service
**On-device git operations for clone, pull, commit, push.**

- `GitSyncService` (actor for thread safety):
  - `clone(repoURL:, to:, credentials:)` — initial clone of BeStupid repo
  - `pull()` — fetch + merge from origin
  - `commit(message:)` — stage all changes + commit
  - `push()` — push to remote
  - `status()` — show changed/untracked files
  - `conflictResolution` — detect conflicts, prefer local changes (user's phone is source of truth for workout data)
- GitHub OAuth via `ASWebAuthenticationSession`:
  - Register OAuth App or use device flow
  - Store token in Keychain (not UserDefaults)
  - Refresh token handling
- Sync scheduling:
  - Auto-pull on app launch (if online)
  - Auto-push after data changes (debounced, 30-second delay)
  - Background fetch for periodic sync
  - Manual sync button in settings
  - Queue changes when offline, push when reconnected
- Conflict handling:
  - For daily logs: merge by section (app's workout data wins, bot's briefing wins)
  - For metrics JSON: merge by date key
  - For memory: last-write-wins with timestamp comparison
- Local repo location: `App Documents/bestupid-repo/`

### Step 5: SwiftData Cache Layer
**Fast local cache for queries and chart rendering.**

- SwiftData models (separate from domain models):
  - `CachedDailyLog` — denormalized for fast queries
  - `CachedMetric` — date + field + value for chart queries
  - `CachedWorkout` — workout sessions for history
  - `CachedExercise` — exercise library
- `DataSyncCoordinator`:
  - On git pull: parse changed markdown → update SwiftData cache
  - On local edit: update SwiftData + write markdown + queue git commit
  - Single source of truth: markdown files in git repo
  - SwiftData is read-optimized cache only (can be rebuilt from git)
- Cache invalidation:
  - Hash-based: store file hash, skip re-parse if unchanged
  - Full rebuild option in settings

### Step 6: Dashboard View
**Main screen — today's status at a glance.**

- `DashboardView`:
  - Today's date and protocol day (e.g., "Strength Day")
  - Quick metrics cards: weight trend, sleep last night, mood, energy
  - Today's planned workout (from protocol) with "Start Workout" button
  - Todo checklist (tap to toggle)
  - Habit tracking (tap to complete)
  - Last sync timestamp + sync button
  - Week-at-a-glance: 7-day row showing workout completion
- `MetricsQuickLogView`:
  - Tap a metric card to quickly update
  - Weight: number pad
  - Sleep: hours:minutes picker
  - Mood/Energy/Focus: 1-10 slider
  - Saves to today's daily log markdown immediately
- `TodayCardView`:
  - Compact card showing key metric with trend arrow
  - Color-coded: green (good), yellow (okay), red (needs attention)

### Step 7: Log Browser
**Browse and edit daily logs.**

- `LogListView`:
  - Scrollable list of daily logs, newest first
  - Each row: date, workout type icon, key metrics summary
  - Calendar view toggle (month grid with dots for logged days)
  - Search by date range
- `LogDetailView`:
  - Full rendered view of a daily log
  - Sections match markdown structure
  - Syntax-highlighted metrics
  - Tap any field to edit inline
- `LogEditorView`:
  - Edit individual fields
  - Add strength exercises
  - Update nutrition log
  - Changes write back to markdown atomically
- `ProtocolView`:
  - View current weekly protocol
  - See training schedule as a weekly timeline
  - Highlight today's planned workout

### Step 8: Training Charts
**Visualize training volume and strength progression.**

- `TrainingVolumeChart` (Swift Charts):
  - Stacked bar chart: weekly swim/bike/run volume
  - X-axis: weeks, Y-axis: duration in minutes
  - Color-coded by activity type
  - Tap bar for details
  - Time range selector: 4w / 8w / 12w / All
- `StrengthProgressChart`:
  - Line chart: weight over time per exercise
  - Exercise picker dropdown
  - Show estimated 1RM trend line
  - Volume load (weight × reps × sets) trend
  - Compare exercises on same chart
- `WorkoutFrequencyChart`:
  - Heat map calendar (GitHub contribution style)
  - Color intensity = workout intensity/duration
  - Activity type filter
- `ComplianceChart`:
  - Weekly protocol adherence (planned vs completed)
  - Habit streak display
  - Todo completion rate over time

### Step 9: Body Metrics Charts
**Visualize weight, sleep, mood, and energy trends.**

- `BodyMetricsChart`:
  - Weight trend line with 7-day moving average
  - Target weight line if configured
  - Date range selector
- `SleepChart`:
  - Dual axis: sleep hours (bars) + quality score (line)
  - Show Garmin sleep stages if available (deep/light/REM stacked)
  - 7-day average overlay
- `MoodEnergyChart`:
  - Multi-line: mood AM, mood PM, energy, focus
  - All on 1-10 scale for easy comparison
  - Highlight weekends vs weekdays
- All charts:
  - Pinch to zoom time range
  - Tap data point for details
  - Share chart as image

### Step 10: Real-Time Workout Tracker
**Active workout logging during gym/training sessions.**

- `ActiveWorkoutView`:
  - Large timer display (elapsed time)
  - Current exercise display
  - "Add Set" quick action
  - Rest timer between sets (auto-start, configurable default)
  - Heart rate display (live from HealthKit if Watch connected)
- `WorkoutTimerView`:
  - Stopwatch mode for timed exercises
  - Countdown mode for rest intervals
  - Haptic feedback on timer completion
- `ExerciseLogView`:
  - Pick exercise from library or create new
  - Log: reps, weight, RPE (rate of perceived exertion)
  - Show last session's numbers for reference
  - Quick "+5 lbs" / "+1 rep" buttons
- `CardioTrackingView`:
  - For swim/bike/run workouts
  - Track distance, duration, pace
  - Heart rate zones display
  - Integration with HealthKit for GPS (if available)
- `WorkoutSummaryView`:
  - Post-workout summary
  - Total volume, duration, estimated calories
  - Compare to last similar workout
  - Save → writes to today's daily log markdown + commits to git

### Step 11: Exercise Library
**User-defined exercise types and workout templates.**

- `WorkoutTypePickerView`:
  - Built-in types: Swim, Bike, Run, Strength, Brick, Recovery
  - Custom types: user creates new categories
  - Each type has: name, icon, color, default fields
- `ExerciseLibrary`:
  - Stored in git repo as `content/config/exercises.json`
  - Fields: name, category, muscle group, equipment
  - Pre-populated with Ryan's current exercises from protocols
  - Add/edit/archive exercises
  - Track personal records per exercise
- `WorkoutTemplate`:
  - Save workout structures as templates
  - Auto-populate from weekly protocol
  - "Repeat last workout" shortcut

### Step 12: HealthKit Integration
**Bidirectional sync with Apple Health.**

- `HealthKitService`:
  - Request permissions: workout, heart rate, steps, sleep, weight
  - **Write to HealthKit:**
    - `HKWorkout` from completed workout sessions
    - Include heart rate samples, route data, calories
    - Activity type mapping: swim→swimming, bike→cycling, run→running
  - **Read from HealthKit:**
    - Heart rate during active workouts (live query)
    - Sleep analysis (duration, stages if from Watch)
    - Step count (daily total)
    - Weight from smart scale
    - Resting heart rate
  - Sync strategy:
    - On workout completion: write to HealthKit immediately
    - On app foreground: read latest HealthKit data
    - Deduplicate: check `HKSource` to avoid double-counting
  - HealthKit → daily log:
    - Auto-populate Sleep field from HealthKit sleep data
    - Auto-populate Weight from HealthKit if newer than manual entry

### Step 13: After-the-Fact Workout Entry
**Quick forms for logging workouts completed elsewhere (Garmin, gym log, etc.).**

- Structured entry form:
  - Pick workout type
  - Date/time (defaults to now)
  - For cardio: distance, duration, avg HR
  - For strength: select exercises, enter sets/reps/weight
  - Notes field
- Parse Garmin data:
  - If garmin_metrics.json exists in git repo, show recent Garmin activities
  - One-tap import: Garmin activity → daily log entry
  - Map Garmin activity types to BeStupid types
- Batch entry: log multiple exercises at once
- Writes to daily log markdown in correct section format

### Step 14: On-Device AI (Foundation Models)
**Private, offline AI for insights and briefings.**

- `AIService` protocol:
  ```swift
  protocol AIService: Sendable {
      func generateBriefing(context: DailyContext) async throws -> String
      func analyzeMetrics(metrics: [Metric], query: String) async throws -> String
      func suggestWorkout(protocol: WeeklyProtocol, recovery: RecoveryData) async throws -> String
  }
  ```
- `OnDeviceAIProvider`:
  - Uses Apple Foundation Models framework
  - `@Generable` for structured output (workout suggestions, metric analysis)
  - Runs fully offline
  - Use cases:
    - Morning briefing generation (like context_briefing.py)
    - "How's my training going?" — trend analysis
    - Workout modification suggestions based on recovery score
    - Natural language query over logs ("When did I last swim?")
- Prompt engineering:
  - Provide recent metrics context (7-day window)
  - Current protocol context
  - Keep prompts concise for on-device model capabilities

### Step 15: Cloud AI Provider (Optional)
**Pluggable cloud AI for higher-quality responses when online.**

- `CloudAIProvider`:
  - Configurable via settings: Anthropic, OpenAI, or custom endpoint
  - API key stored in Keychain
  - Same `AIService` protocol — drop-in replacement
  - Automatic fallback: cloud → on-device when offline
- `AISettingsView`:
  - Toggle: "Use on-device AI only" (default on)
  - Provider picker: Anthropic / OpenAI / Custom
  - API key entry (secure text field)
  - Test connection button
  - Usage indicator (on-device vs cloud)
- No provider-specific code outside `CloudAIProvider` — clean abstraction

### Step 16: Polish, Testing & Packaging
**Final quality pass.**

- Unit tests:
  - Markdown parser tests (use real log files as fixtures)
  - Metric extraction tests
  - Strength log parsing edge cases
  - Git sync mock tests
- UI polish:
  - Dark mode support (auto, light, dark)
  - Dynamic Type support
  - Haptic feedback for workout interactions
  - App icon design
  - Launch screen
- Performance:
  - Lazy loading for log list
  - Chart data pre-computation
  - Background git sync (no UI blocking)
- Error handling:
  - Graceful offline degradation
  - Git conflict resolution UI
  - Sync failure notifications
  - Data validation before write

---

## Key Design Decisions

### Why SwiftData over GRDB/SQLite?
SwiftData is Apple-native, integrates seamlessly with SwiftUI, and is sufficient for a cache layer. The source of truth is the git repo (markdown/JSON files), so we don't need the raw SQL power of GRDB. SwiftData gives us free `@Query` integration with SwiftUI views.

### Why not CoreData?
SwiftData is its successor, simpler API, better SwiftUI integration. No reason to use CoreData for a new project in 2026.

### Why Git on device instead of iCloud/CloudKit?
The user's requirement is explicit: data managed locally with git backups. This maintains compatibility with the existing Telegram bot (both read/write the same repo). iCloud would create a separate data silo.

### Why Foundation Models over just cloud AI?
Rule 1 (no API lock-in) + Rule 2 (offline). Foundation Models are free, private, and work without internet. Cloud AI is optional enhancement, not a dependency.

### Why markdown as source of truth (not SQLite)?
The existing bot reads/writes markdown. Both interfaces must see the same data. Markdown is human-readable, git-friendly, and already proven in the system. SwiftData is just a performance cache.

### Conflict Resolution Strategy
- **Daily logs**: Section-level merge. Workout data from phone wins. Briefing data from bot wins.
- **Metrics JSON**: Merge by date key. Latest timestamp wins per field.
- **Memory items**: Last-write-wins using `updated` timestamp.
- **Protocol files**: Bot-generated only, phone never writes these. No conflicts.

---

## Dependencies (Swift Packages)

1. **SwiftGitX** — On-device git operations (clone/pull/commit/push via libgit2)
   - Fallback: ObjectiveGit or raw libgit2 C bindings if SwiftGitX is insufficient
2. **Yams** — YAML parsing for frontmatter (well-maintained, standard)
3. No other external dependencies — everything else is Apple frameworks

---

## Estimated Scope by Phase

| Phase | Steps | What Ships |
|---|---|---|
| **Phase 1: Foundation** | 1-5 | Git sync working, data parsing, local cache |
| **Phase 2: Visualization** | 6-9 | Dashboard, log browser, all charts |
| **Phase 3: Workouts** | 10-13 | Real-time tracking, HealthKit, exercise library |
| **Phase 4: AI & Polish** | 14-16 | On-device AI, cloud option, tests, polish |

Each phase produces a usable app — Phase 1+2 alone gives you a powerful data viewer.
