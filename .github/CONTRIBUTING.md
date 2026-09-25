# Contributing to OBS Marker Tool

Thank you for your interest in improving OBS Marker Tool. To keep the tool reliable, lightweight, and anti-cheat compliant for streamers and creators, all contributions must adhere to the core principles below.

---

## Architectural Principles

1. **Zero External Dependencies**:
   - The Python backend must run exclusively on the Python standard library.
   - Do not add packages to `requirements.txt` or require `pip install`.
   - The Lua service must run inside the default OBS Studio Lua 5.1/LuaJIT sandbox without external DLLs or LuaRocks.

2. **Anti-Cheat Safety**:
   - Global hotkey detection must remain strictly inside OBS Studio's native hotkey system.
   - Never implement low-level OS keyboard hooks (`SetWindowsHookEx`, `pynput`, `keyboard`), memory scanning, or Direct3D overlay injections that could trigger game anti-cheat systems (Riot Vanguard, Easy Anti-Cheat, BattlEye).

3. **Localhost Security**:
   - The server must only bind to loopback (`127.0.0.1`). Never bind to `0.0.0.0` or expose network sockets externally.

4. **Non-Destructive File Operations**:
   - All session writes and file purges must verify path safety and fail silently or report structured errors without crashing the OBS process.

---

## Development Workflow

### 1. Local Setup
Clone the repository:
```bash
git clone https://github.com/Mudxiej/obs-marker-tool.git
cd obs-marker-tool
```

### 2. Testing Changes
1. Test server daemon locally:
   ```bash
   python src/server.py
   ```
2. Query server endpoints:
   - Status: `http://127.0.0.1:8765/api/session_status`
   - Save: `http://127.0.0.1:8765/api/save_marker?name=Test&time=00:01:00&tc=00:01:00:00`
   - Undo: `http://127.0.0.1:8765/api/undo_marker`
3. Verify output files:
   - Validate Premiere Pro XML schema against FCP 7 XML specification.
   - Validate FCPXML v1.9 against Apple FCPXML DTD.
   - Check RFC 4180 CSV syntax and YouTube chapters formatting.

### 3. Submitting a Pull Request
1. Fork the repository and create your branch from `main`.
2. Ensure your code passes all lint and syntax checks.
3. Open a Pull Request referencing any related issues.
4. Follow the PR template checklist completely.
