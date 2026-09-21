# Fingerprint profiles

The browser server ships three profiles. Pick the one that matches the target
site's expected audience.

| Profile | Platform | Use when |
|---------|----------|----------|
| `desktop-win` | Windows 11, Firefox | Most consumer sites |
| `desktop-mac` | macOS, Firefox | Sites that gate on Apple hardware |
| `mobile-android` | Android, Firefox | Mobile-only endpoints |

Pass the profile name with `--profile` when opening a session.
