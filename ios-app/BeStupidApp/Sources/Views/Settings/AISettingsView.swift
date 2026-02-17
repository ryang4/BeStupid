import SwiftUI

struct AISettingsView: View {
    @Binding var useOnDevice: Bool
    @Binding var providerType: String
    @Binding var apiKey: String
    @Binding var model: String
    let isTestingConnection: Bool
    let testResult: String?
    let onTest: () -> Void
    let onSave: () -> Void

    private var availableProviders: [CloudAIProvider.Provider] {
        CloudAIProvider.Provider.allCases
    }

    var body: some View {
        Form {
            onDeviceSection
            if !useOnDevice {
                cloudProviderSection
                connectionTestSection
            }
            infoSection
        }
        .navigationTitle("AI Assistant")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button("Save", action: onSave)
                    .fontWeight(.semibold)
                    .disabled(useOnDevice)
            }
        }
    }

    // MARK: - On-Device Section

    private var onDeviceSection: some View {
        Section {
            Toggle(isOn: $useOnDevice) {
                HStack(spacing: 12) {
                    Image(systemName: "cpu")
                        .font(.title3)
                        .foregroundStyle(.purple)
                        .frame(width: 28)

                    VStack(alignment: .leading, spacing: 2) {
                        Text("Use On-Device AI")
                            .font(.body)
                        Text("Apple Intelligence / Core ML")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
        } header: {
            Text("Processing Mode")
        } footer: {
            Text(useOnDevice
                ? "AI runs entirely on your device. No data is sent to external servers. Works offline."
                : "AI requests will be sent to the selected cloud provider. Requires an internet connection and API key."
            )
        }
    }

    // MARK: - Cloud Provider Section

    private var cloudProviderSection: some View {
        Section {
            Picker("Provider", selection: $providerType) {
                ForEach(availableProviders) { provider in
                    Text(provider.rawValue).tag(provider.rawValue)
                }
            }
            .onChange(of: providerType) { _, newValue in
                if let provider = CloudAIProvider.Provider(rawValue: newValue) {
                    model = provider.defaultModel
                }
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("API Key")
                    .font(.caption)
                    .foregroundStyle(.secondary)

                SecureField("Enter your API key", text: $apiKey)
                    .textContentType(.password)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("Model")
                    .font(.caption)
                    .foregroundStyle(.secondary)

                TextField("Model name", text: $model)
                    .font(.system(.body, design: .monospaced))
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)
            }

            if let provider = CloudAIProvider.Provider(rawValue: providerType) {
                HStack {
                    Text("Endpoint")
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text(provider.defaultEndpoint.host() ?? provider.defaultEndpoint.absoluteString)
                        .font(.caption.monospaced())
                        .foregroundStyle(.secondary)
                }
            }
        } header: {
            Text("Cloud Provider")
        } footer: {
            switch CloudAIProvider.Provider(rawValue: providerType) {
            case .anthropic:
                Text("Uses the Anthropic Messages API. Get your API key from console.anthropic.com.")
            case .openai:
                Text("Uses the OpenAI Chat Completions API. Get your API key from platform.openai.com.")
            case .custom:
                Text("Custom provider using OpenAI-compatible API format. Configure endpoint and model as needed.")
            case nil:
                EmptyView()
            }
        }
    }

    // MARK: - Connection Test

    private var connectionTestSection: some View {
        Section {
            Button {
                onTest()
            } label: {
                HStack {
                    Label("Test Connection", systemImage: "antenna.radiowaves.left.and.right")
                    Spacer()
                    if isTestingConnection {
                        ProgressView()
                            .controlSize(.small)
                    }
                }
            }
            .disabled(isTestingConnection || apiKey.isEmpty)

            if let result = testResult {
                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: testResultIsSuccess ? "checkmark.circle.fill" : "xmark.circle.fill")
                        .foregroundStyle(testResultIsSuccess ? .green : .red)
                        .font(.body)

                    Text(result)
                        .font(.subheadline)
                        .foregroundStyle(testResultIsSuccess ? .primary : .red)
                }
                .padding(.vertical, 4)
            }
        } header: {
            Text("Connection Test")
        }
    }

    // MARK: - Info

    private var infoSection: some View {
        Section {
            VStack(alignment: .leading, spacing: 12) {
                InfoRow(
                    icon: "cpu",
                    title: "On-Device AI",
                    description: "Fast, private, works offline. Best for quick briefings and simple queries. May be less capable for complex analysis."
                )

                Divider()

                InfoRow(
                    icon: "cloud",
                    title: "Cloud AI",
                    description: "More capable models for detailed analysis, workout suggestions, and complex queries. Requires internet and API key. Data is sent to the provider."
                )
            }
        } header: {
            Text("Comparison")
        }
    }

    // MARK: - Helpers

    private var testResultIsSuccess: Bool {
        guard let result = testResult else { return false }
        return result.lowercased().contains("successful")
    }
}

// MARK: - InfoRow

private struct InfoRow: View {
    let icon: String
    let title: String
    let description: String

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundStyle(.purple)
                .frame(width: 28, alignment: .center)

            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.subheadline.weight(.semibold))
                Text(description)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

// MARK: - Preview

#Preview("AI Settings - On Device") {
    @Previewable @State var useOnDevice = true
    @Previewable @State var providerType = "Anthropic"
    @Previewable @State var apiKey = ""
    @Previewable @State var model = "claude-sonnet-4-5-20250929"

    NavigationStack {
        AISettingsView(
            useOnDevice: $useOnDevice,
            providerType: $providerType,
            apiKey: $apiKey,
            model: $model,
            isTestingConnection: false,
            testResult: nil,
            onTest: {},
            onSave: {}
        )
    }
}

#Preview("AI Settings - Cloud Provider") {
    @Previewable @State var useOnDevice = false
    @Previewable @State var providerType = "Anthropic"
    @Previewable @State var apiKey = "sk-ant-api03-..."
    @Previewable @State var model = "claude-sonnet-4-5-20250929"

    NavigationStack {
        AISettingsView(
            useOnDevice: $useOnDevice,
            providerType: $providerType,
            apiKey: $apiKey,
            model: $model,
            isTestingConnection: false,
            testResult: "Connection successful. Model: claude-sonnet-4-5-20250929",
            onTest: {},
            onSave: {}
        )
    }
}

#Preview("AI Settings - Testing Connection") {
    @Previewable @State var useOnDevice = false
    @Previewable @State var providerType = "OpenAI"
    @Previewable @State var apiKey = "sk-..."
    @Previewable @State var model = "gpt-4o"

    NavigationStack {
        AISettingsView(
            useOnDevice: $useOnDevice,
            providerType: $providerType,
            apiKey: $apiKey,
            model: $model,
            isTestingConnection: true,
            testResult: nil,
            onTest: {},
            onSave: {}
        )
    }
}
