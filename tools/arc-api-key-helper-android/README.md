# ARC API Key Setup Helper (Android)

A large-text, voice-guided launcher for the GitHub repository secret settings used by the ARC-AGI-3 workflow.

## Security model

- The app has no API-key input field.
- It does not request network permission.
- It does not store credentials, use a clipboard, or call the GitHub API.
- The API key is entered only on GitHub's own HTTPS settings page.
- The app opens the repository Actions page so the user can inspect workflow runs.

This is deliberate: a masked field inside a third-party app would still expose the underlying value to that app. This helper keeps the credential-entry step on GitHub.

## Build

The GitHub Actions workflow in this directory builds a debug APK and uploads it as an artifact. It does not sign a release APK for distribution.

## Target repository

- Repository: https://github.com/ytpokerspace/Slush-vm
- Secret name: `ARC_API_KEY`
