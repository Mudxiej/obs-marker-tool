# Security Policy

## Supported Versions

| Version | Supported |
| :--- | :--- |
| 1.0.x | Yes |
| < 1.0 | No |

---

## Anti-Cheat Safety & Integrity Disclosure

OBS Marker Tool is designed specifically for streamers and competitive gamers who play games protected by kernel-level anti-cheat drivers (e.g., Riot Vanguard, BattlEye, Easy Anti-Cheat, Ricochet).

- **No OS-Level Keylogging**: Hotkeys are captured strictly via OBS Studio's internal `obs_hotkey_register_frontend` API. The tool never injects global Windows hooks (`WH_KEYBOARD_LL`, `SetWindowsHookEx`) or uses raw input polling.
- **No Process Memory Injection**: The tool does not attach to, read, or manipulate game process memory.
- **No Direct3D / Vulkan Hooks**: Visual feedback (Electric Cyan flash) is rendered inside OBS Studio's native browser dock, not drawn over the game surface.
- **Loopback-Only Network Scope**: The embedded HTTP daemon binds exclusively to `127.0.0.1:8765`. It rejects external connections and requires no internet access.

---

## Reporting a Vulnerability

If you discover a security vulnerability or security concern:

1. **Do not open a public issue.**
2. Report the vulnerability via [GitHub Private Vulnerability Reporting](https://github.com/Mudxiej/obs-marker-tool/security/advisories/new).
3. If Private Vulnerability Reporting is unavailable, open a private discussion topic in the **Security** category or contact the maintainer directly.

### What to Include:
- A clear description of the vulnerability.
- Proof of concept or reproduction steps.
- Potential impact on the user or system.

We will review reports within 48 hours and coordinate patch releases prior to public disclosure.
