import Foundation
import Security

#if canImport(AuthenticationServices)
import AuthenticationServices
#endif

// MARK: - Credential Error Types

enum CredentialError: Error, Sendable, Equatable, LocalizedError {
    case keychainSaveFailed(status: Int32)
    case keychainLoadFailed(status: Int32)
    case keychainDeleteFailed(status: Int32)
    case keychainDataCorrupted
    case noCredentialsFound
    case oauthFailed(String)
    case oauthCancelled
    case oauthInvalidResponse(String)
    case tokenExchangeFailed(String)
    case missingClientId

    var errorDescription: String? {
        switch self {
        case .keychainSaveFailed(let status):
            return "Failed to save credentials to Keychain (OSStatus: \(status))."
        case .keychainLoadFailed(let status):
            return "Failed to load credentials from Keychain (OSStatus: \(status))."
        case .keychainDeleteFailed(let status):
            return "Failed to delete credentials from Keychain (OSStatus: \(status))."
        case .keychainDataCorrupted:
            return "Keychain data is corrupted and could not be decoded."
        case .noCredentialsFound:
            return "No GitHub credentials found in Keychain."
        case .oauthFailed(let detail):
            return "GitHub OAuth failed: \(detail)"
        case .oauthCancelled:
            return "GitHub OAuth was cancelled by the user."
        case .oauthInvalidResponse(let detail):
            return "Invalid OAuth response: \(detail)"
        case .tokenExchangeFailed(let detail):
            return "Token exchange failed: \(detail)"
        case .missingClientId:
            return "GitHub OAuth client ID is not configured."
        }
    }
}

// MARK: - OAuth Token Response

struct OAuthTokenResponse: Sendable, Equatable {
    let accessToken: String
    let tokenType: String
    let scope: String

    init?(from queryString: String) {
        var params: [String: String] = [:]
        for pair in queryString.split(separator: "&") {
            let parts = pair.split(separator: "=", maxSplits: 1)
            if parts.count == 2 {
                let key = String(parts[0])
                let value = String(parts[1]).removingPercentEncoding ?? String(parts[1])
                params[key] = value
            }
        }

        // Check for error response.
        if params["error"] != nil {
            return nil
        }

        guard let token = params["access_token"],
              let type = params["token_type"] else {
            return nil
        }

        self.accessToken = token
        self.tokenType = type
        self.scope = params["scope"] ?? ""
    }
}

// MARK: - Keychain Operations Protocol (for testing)

protocol KeychainOperations: Sendable {
    func add(query: CFDictionary) -> OSStatus
    func copyMatching(query: CFDictionary, result: UnsafeMutablePointer<CFTypeRef?>) -> OSStatus
    func delete(query: CFDictionary) -> OSStatus
    func update(query: CFDictionary, attributes: CFDictionary) -> OSStatus
}

/// Default implementation that delegates to the Security framework.
final class SystemKeychain: KeychainOperations, Sendable {
    func add(query: CFDictionary) -> OSStatus {
        SecItemAdd(query, nil)
    }

    func copyMatching(query: CFDictionary, result: UnsafeMutablePointer<CFTypeRef?>) -> OSStatus {
        SecItemCopyMatching(query, result)
    }

    func delete(query: CFDictionary) -> OSStatus {
        SecItemDelete(query)
    }

    func update(query: CFDictionary, attributes: CFDictionary) -> OSStatus {
        SecItemUpdate(query, attributes)
    }
}

// MARK: - Stored Credential (Codable wrapper for Keychain serialization)

private struct StoredCredential: Codable, Sendable {
    let username: String
    let token: String

    init(from credentials: GitCredentials) {
        self.username = credentials.username
        self.token = credentials.token
    }

    func toGitCredentials() -> GitCredentials {
        GitCredentials(username: username, token: token)
    }
}

// MARK: - GitCredentialManager

actor GitCredentialManager {
    static let serviceName = "com.bestupid.github"
    private static let accountName = "github-token"
    private static let callbackScheme = "bestupid"
    private static let githubAuthorizeURL = "https://github.com/login/oauth/authorize"
    private static let githubTokenURL = "https://github.com/login/oauth/access_token"

    private let keychain: KeychainOperations
    private let urlSession: URLSession

    init(
        keychain: KeychainOperations = SystemKeychain(),
        urlSession: URLSession = .shared
    ) {
        self.keychain = keychain
        self.urlSession = urlSession
    }

    // MARK: - Save Credentials

    /// Stores the given credentials in the Keychain, replacing any existing entry.
    func saveCredentials(_ credentials: GitCredentials) throws {
        let stored = StoredCredential(from: credentials)
        let data = try JSONEncoder().encode(stored)

        // Build the base query.
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: Self.serviceName,
            kSecAttrAccount as String: Self.accountName,
        ]

        // Delete any existing item first (ignore errors -- may not exist).
        _ = keychain.delete(query as CFDictionary)

        // Add the new item.
        var addQuery = query
        addQuery[kSecValueData as String] = data
        addQuery[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly

        let status = keychain.add(addQuery as CFDictionary)
        guard status == errSecSuccess else {
            throw CredentialError.keychainSaveFailed(status: status)
        }
    }

    // MARK: - Load Credentials

    /// Retrieves stored credentials from the Keychain, or returns nil if none exist.
    func loadCredentials() throws -> GitCredentials? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: Self.serviceName,
            kSecAttrAccount as String: Self.accountName,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]

        var result: CFTypeRef?
        let status = keychain.copyMatching(query as CFDictionary, result: &result)

        if status == errSecItemNotFound {
            return nil
        }

        guard status == errSecSuccess else {
            throw CredentialError.keychainLoadFailed(status: status)
        }

        guard let data = result as? Data else {
            throw CredentialError.keychainDataCorrupted
        }

        do {
            let stored = try JSONDecoder().decode(StoredCredential.self, from: data)
            return stored.toGitCredentials()
        } catch {
            throw CredentialError.keychainDataCorrupted
        }
    }

    // MARK: - Delete Credentials

    /// Removes stored credentials from the Keychain.
    func deleteCredentials() throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: Self.serviceName,
            kSecAttrAccount as String: Self.accountName,
        ]

        let status = keychain.delete(query as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw CredentialError.keychainDeleteFailed(status: status)
        }
    }

    // MARK: - GitHub OAuth Flow

    /// Initiates the GitHub OAuth web flow using ASWebAuthenticationSession.
    ///
    /// Flow:
    /// 1. Opens GitHub authorization page in a system browser sheet.
    /// 2. User authorizes the app, GitHub redirects back with an authorization code.
    /// 3. Exchanges the authorization code for an access token via POST to GitHub.
    /// 4. Stores the token in Keychain and returns the credentials.
    ///
    /// - Parameters:
    ///   - clientId: The GitHub OAuth App client ID.
    ///   - clientSecret: The GitHub OAuth App client secret.
    ///   - presentationAnchor: The window to present the authentication session in.
    /// - Returns: The authenticated `GitCredentials`.
    #if canImport(AuthenticationServices) && canImport(UIKit)
    func authenticateWithGitHub(
        clientId: String,
        clientSecret: String,
        presentationAnchor: ASPresentationAnchor
    ) async throws -> GitCredentials {
        guard !clientId.isEmpty else {
            throw CredentialError.missingClientId
        }

        // Step 1: Build the authorization URL.
        let scope = "repo"
        let state = UUID().uuidString

        var authComponents = URLComponents(string: Self.githubAuthorizeURL)!
        authComponents.queryItems = [
            URLQueryItem(name: "client_id", value: clientId),
            URLQueryItem(name: "redirect_uri", value: "\(Self.callbackScheme)://oauth-callback"),
            URLQueryItem(name: "scope", value: scope),
            URLQueryItem(name: "state", value: state),
        ]

        guard let authURL = authComponents.url else {
            throw CredentialError.oauthFailed("Could not construct authorization URL.")
        }

        // Step 2: Present the authentication session and await the callback.
        let callbackURL = try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<URL, Error>) in
            let session = ASWebAuthenticationSession(
                url: authURL,
                callbackURLScheme: Self.callbackScheme
            ) { url, error in
                if let error {
                    if (error as NSError).code == ASWebAuthenticationSessionError.canceledLogin.rawValue {
                        continuation.resume(throwing: CredentialError.oauthCancelled)
                    } else {
                        continuation.resume(throwing: CredentialError.oauthFailed(error.localizedDescription))
                    }
                    return
                }

                guard let url else {
                    continuation.resume(throwing: CredentialError.oauthFailed("No callback URL received."))
                    return
                }

                continuation.resume(returning: url)
            }

            session.presentationContextProvider = OAuthPresentationProvider(anchor: presentationAnchor)
            session.prefersEphemeralWebBrowserSession = true
            session.start()
        }

        // Step 3: Extract the authorization code from the callback URL.
        guard let components = URLComponents(url: callbackURL, resolvingAgainstBaseURL: false),
              let queryItems = components.queryItems else {
            throw CredentialError.oauthInvalidResponse("Could not parse callback URL: \(callbackURL)")
        }

        // Verify state parameter to prevent CSRF.
        let returnedState = queryItems.first(where: { $0.name == "state" })?.value
        guard returnedState == state else {
            throw CredentialError.oauthFailed("OAuth state mismatch -- possible CSRF attack.")
        }

        guard let code = queryItems.first(where: { $0.name == "code" })?.value else {
            let errorDesc = queryItems.first(where: { $0.name == "error_description" })?.value ?? "Unknown error"
            throw CredentialError.oauthFailed(errorDesc)
        }

        // Step 4: Exchange the authorization code for an access token.
        let tokenCredentials = try await exchangeCodeForToken(
            code: code,
            clientId: clientId,
            clientSecret: clientSecret
        )

        // Step 5: Store credentials in Keychain.
        try saveCredentials(tokenCredentials)

        return tokenCredentials
    }
    #endif

    // MARK: - Token Exchange (also usable standalone for testing)

    /// Exchanges a GitHub authorization code for an access token.
    func exchangeCodeForToken(
        code: String,
        clientId: String,
        clientSecret: String
    ) async throws -> GitCredentials {
        guard var components = URLComponents(string: Self.githubTokenURL) else {
            throw CredentialError.tokenExchangeFailed("Invalid token URL.")
        }

        components.queryItems = [
            URLQueryItem(name: "client_id", value: clientId),
            URLQueryItem(name: "client_secret", value: clientSecret),
            URLQueryItem(name: "code", value: code),
        ]

        guard let tokenURL = components.url else {
            throw CredentialError.tokenExchangeFailed("Could not build token exchange URL.")
        }

        var request = URLRequest(url: tokenURL)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Accept")

        let (data, response) = try await urlSession.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw CredentialError.tokenExchangeFailed("Invalid HTTP response.")
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? "No body"
            throw CredentialError.tokenExchangeFailed(
                "HTTP \(httpResponse.statusCode): \(body)"
            )
        }

        guard let responseString = String(data: data, encoding: .utf8) else {
            throw CredentialError.tokenExchangeFailed("Could not decode response body.")
        }

        guard let tokenResponse = OAuthTokenResponse(from: responseString) else {
            throw CredentialError.oauthInvalidResponse(
                "Failed to parse token response: \(responseString)"
            )
        }

        // Fetch the authenticated user's login name for the credential.
        let username = try await fetchAuthenticatedUsername(token: tokenResponse.accessToken)

        return GitCredentials(username: username, token: tokenResponse.accessToken)
    }

    // MARK: - Fetch Authenticated Username

    /// Fetches the authenticated GitHub user's login name using the given token.
    private func fetchAuthenticatedUsername(token: String) async throws -> String {
        guard let userURL = URL(string: "https://api.github.com/user") else {
            throw CredentialError.tokenExchangeFailed("Invalid GitHub API URL.")
        }

        var request = URLRequest(url: userURL)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")

        let (data, response) = try await urlSession.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw CredentialError.tokenExchangeFailed("Failed to fetch GitHub username.")
        }

        // Parse just the "login" field from the JSON response.
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let login = json["login"] as? String else {
            throw CredentialError.tokenExchangeFailed("Could not parse username from GitHub API response.")
        }

        return login
    }
}

// MARK: - OAuth Presentation Context Provider

#if canImport(AuthenticationServices) && canImport(UIKit)
/// Provides the presentation anchor for ASWebAuthenticationSession.
private final class OAuthPresentationProvider: NSObject, ASWebAuthenticationPresentationContextProviding, Sendable {
    private let anchor: ASPresentationAnchor

    init(anchor: ASPresentationAnchor) {
        self.anchor = anchor
    }

    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        anchor
    }
}
#endif
