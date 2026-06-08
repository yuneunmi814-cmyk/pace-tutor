# Distribution (macOS / Windows / Linux)

pace-tutor bundles a Python sidecar (PyInstaller) inside a Tauri app. PyInstaller and
Tauri **cannot cross-compile**, so each platform must be built on its own OS. This is
automated by `.github/workflows/release.yml` (GitHub Actions), which builds all three.

## Trigger a release

```bash
git tag v0.1.0 && git push origin v0.1.0      # or run the "release" workflow manually
```

Each runner (macOS / Windows / Linux):
1. builds the sidecar binary `main-<target-triple>` with PyInstaller,
2. builds the Tauri app (`tauri-action`),
3. uploads installers to a **draft GitHub Release** (`.dmg`, `.msi`/`.exe`, `.deb`/`.AppImage`).

No system `ffmpeg` is required at runtime — `faster-whisper` uses bundled PyAV.
End users still need a running [Ollama](https://ollama.com) for LLM features (the
samples and curated quizzes work without it).

## macOS notarization (so other Macs don't show a Gatekeeper warning)

Notarization requires an **Apple Developer account** ($99/yr) and credentials. These are
**yours to create** — set them as GitHub repo **Secrets**; the workflow consumes them
automatically. Without them the app is ad-hoc signed (runs on the build machine, but
other Macs warn / require right-click→Open).

Required secrets:

| Secret | What it is |
|---|---|
| `APPLE_CERTIFICATE` | base64 of your "Developer ID Application" `.p12` |
| `APPLE_CERTIFICATE_PASSWORD` | password for that `.p12` |
| `APPLE_SIGNING_IDENTITY` | e.g. `Developer ID Application: Your Name (TEAMID)` |
| `APPLE_ID` | your Apple ID email |
| `APPLE_PASSWORD` | an app-specific password (appleid.apple.com) |
| `APPLE_TEAM_ID` | your 10-char Team ID |

> `src-tauri/tauri.conf.json` ships `signingIdentity: "-"` (ad-hoc) for local dev;
> `APPLE_SIGNING_IDENTITY` overrides it in CI. `entitlements.plist`
> (`disable-library-validation`) is required so the bundled Python framework loads.

## Windows / Linux signing

- **Windows**: unsigned by default (SmartScreen may warn). Add an Authenticode cert +
  `tauri-action` signing env to sign — optional.
- **Linux**: `.deb` / `.AppImage` are unsigned (normal for these formats).

## Local one-OS build

```bash
./scripts/build_sidecar.sh           # build sidecar for the current OS
cd ui && npx tauri build             # build the app for the current OS
```
