# macOS Code Signing & Notarization Setup

This guide explains how to configure Apple code signing for automated builds.

**Without signing**: Installers will work, but users see Gatekeeper warnings and must right-click → Open.

**With signing**: Installers open without warnings, like any commercial software.

---

## Prerequisites

- Apple Developer Program membership ($99/year)
- Access to [Apple Developer Portal](https://developer.apple.com/account)
- Access to [App Store Connect](https://appstoreconnect.apple.com) (for app-specific password)

---

## Step 1: Create Certificates

You need TWO certificates from Apple Developer Portal:

### 1.1 Developer ID Application Certificate
Used to sign the plugin binaries (VST3, AU).

1. Go to [Certificates, IDs & Profiles](https://developer.apple.com/account/resources/certificates/list)
2. Click the **+** button
3. Select **Developer ID Application**
4. Follow the prompts (requires creating a Certificate Signing Request from Keychain Access)
5. Download and double-click to install in Keychain

### 1.2 Developer ID Installer Certificate
Used to sign the .pkg installer.

1. Same process as above
2. Select **Developer ID Installer** instead
3. Download and install

---

## Step 2: Export Certificates as .p12

For each certificate:

1. Open **Keychain Access**
2. Find the certificate (search "Developer ID")
3. Expand it to see the private key
4. Select BOTH the certificate AND the private key
5. Right-click → **Export 2 items...**
6. Save as `.p12` format
7. Set a strong password (you'll need this later)

You should have:
- `developer_id_application.p12`
- `developer_id_installer.p12`

---

## Step 3: Base64 Encode the Certificates

The .p12 files need to be base64 encoded for GitHub secrets:

```bash
# Application certificate
base64 -i developer_id_application.p12 -o app_cert_base64.txt

# Installer certificate
base64 -i developer_id_installer.p12 -o installer_cert_base64.txt
```

The contents of these .txt files go into GitHub secrets.

---

## Step 4: Create App-Specific Password

Apple requires an app-specific password for notarization (not your regular Apple ID password).

1. Go to [appleid.apple.com](https://appleid.apple.com)
2. Sign in with your Apple ID
3. Go to **Sign-In and Security** → **App-Specific Passwords**
4. Click **Generate an app-specific password**
5. Name it something like "GitHub Actions Notarization"
6. Copy the generated password (you won't see it again)

---

## Step 5: Find Your Team ID

Your Team ID is a 10-character identifier.

1. Go to [Apple Developer Membership](https://developer.apple.com/account#MembershipDetailsCard)
2. Find **Team ID** in your membership details
3. It looks like: `ABC123XYZ9`

---

## Step 6: Configure GitHub Secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Create these secrets:

| Secret Name | Value |
|-------------|-------|
| `APPLE_CERTIFICATE_APPLICATION` | Contents of `app_cert_base64.txt` |
| `APPLE_CERTIFICATE_INSTALLER` | Contents of `installer_cert_base64.txt` |
| `APPLE_CERTIFICATE_PASSWORD` | Password you set when exporting .p12 |
| `APPLE_ID` | Your Apple ID email |
| `APPLE_TEAM_ID` | Your 10-character Team ID |
| `APPLE_APP_PASSWORD` | App-specific password from Step 4 |
| `APPLE_APP_IDENTITY` | `Developer ID Application: Your Name (TEAM_ID)` |
| `APPLE_PKG_IDENTITY` | `Developer ID Installer: Your Name (TEAM_ID)` |
| `BUNDLE_ID` | Your plugin's bundle ID (e.g., `com.yourcompany.pluginname`) |

### Finding Your Identity Strings

To get the exact identity strings for `APPLE_APP_IDENTITY` and `APPLE_PKG_IDENTITY`:

```bash
security find-identity -v -p codesigning
```

Look for lines like:
```
1) ABC123... "Developer ID Application: Your Name (ABC123XYZ9)"
2) DEF456... "Developer ID Installer: Your Name (ABC123XYZ9)"
```

Use the quoted strings exactly as shown.

---

## Step 7: Update Bundle ID

Make sure `BUNDLE_ID` matches your `CMakeLists.txt`:

```cmake
juce_add_plugin(YourPlugin
    BUNDLE_ID "com.yourcompany.pluginname"  # Must match BUNDLE_ID secret
    ...
)
```

---

## Verification

After setting up secrets, push to main or create a tag. Check the workflow logs:

**If signing is working**, you'll see:
```
=== Signing VST3 ===
=== Signing AU ===
=== Signing package ===
=== Submitting for notarization ===
=== Stapling ticket ===
```

**If secrets are missing**, you'll see:
```
========================================================================
WARNING: BUILDING UNSIGNED INSTALLER
========================================================================
```

---

## Troubleshooting

### "No identity found"
- Certificate not installed or expired
- Wrong identity string in secrets
- Run `security find-identity -v -p codesigning` to verify

### "The specified item could not be found in the keychain"
- Certificate password is wrong
- Base64 encoding is corrupted (re-export and re-encode)

### Notarization fails
- App-specific password expired or revoked (create a new one)
- Apple ID doesn't match Team ID
- Bundle ID mismatch

### "code has no resources but signature indicates they must be present"
- This is normal for JUCE plugins, the workflow handles it with ad-hoc re-signing

---

## Security Notes

- Never commit .p12 files or passwords to the repo
- Rotate app-specific passwords periodically
- GitHub secrets are encrypted and only exposed to workflows
- Consider using environments for production releases

---

## Local Signing (Optional)

To sign locally for testing:

```bash
# Store notarization credentials (one-time)
xcrun notarytool store-credentials "notarytool-profile" \
    --apple-id "your@email.com" \
    --team-id "ABC123XYZ9" \
    --password "your-app-specific-password"

# Run the installer script
./installer/macos/build-pkg.sh 1.0.0
```

Make sure to update the identity strings in `installer/macos/build-pkg.sh` first.
