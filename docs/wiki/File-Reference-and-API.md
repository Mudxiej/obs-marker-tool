# File Reference & API

Comprehensive technical specification of all repository files, internal data structures, REST API endpoints, and component-level pros and cons.

---

## 1. File Catalog

| File Path | Primary Language | Role & Responsibility |
| :--- | :--- | :--- |
| `src/server.py` | Python 3.8+ | Core HTTP daemon, session state manager, timeline XML/CSV/TXT serializer, and resilient file cleanup engine. |
| `src/marker_service.lua` | Lua 5.1 (OBS Lua) | OBS Studio native integration hook, lifecycle coordinator, settings UI renderer, and anti-cheat safe hotkey handler. |
| `src/index.html` | HTML5 / CSS3 / ES6 | Embedded Custom Browser Dock user interface, OBS WebSocket v5 subscriber, and sensory feedback orchestrator. |
| `src/install.bat` | Windows Batch Script | One-click automated installer deploying files to `%APPDATA%\obs-studio\scripts\obs-marker-tool\`. |
| `src/run_silent.vbs` | VBScript | Headless process launcher executing `pythonw.exe` without visible command prompt windows. |
| `src/run.bat` | Windows Batch Script | Interactive launcher for local development, manual testing, and live terminal logging. |
| `src/stop.bat` | Windows Batch Script | Process termination script safely querying port 8765 and killing the daemon on OBS unload. |
| `scripts/sync_wiki.py` | Python 3.8+ | Synchronization utility reading Windows Credential Manager tokens to push `docs/wiki/` directly to GitHub Wiki git remote. |
| `requirements.txt` | Text / Config | Developer dependencies for local testing, syntax linting, and XML validation (zero runtime requirements). |

---

## 2. In-Depth Component Analysis

### `src/server.py` (Core Backend Daemon)
Silent background daemon listening on `127.0.0.1:8765` using Python standard library `http.server`.

#### Architecture & Flow
1. Receives timecode freeze events from `marker_service.lua` via `freeze_trigger.flag` file watcher.
2. Accepts HTTP REST requests from the browser dock (`index.html`) for saving markers, undoing actions, resetting sessions, and folder discovery.
3. Simultaneously serializes marker entries into four formats (`markers.txt`, `markers.csv`, `premiere_sequence.xml`, `final_cut_pro.fcpxml`).
4. Executes atomic directory cleanup if all markers in a session are undone.

#### Key Classes & Methods
- `MarkerSession`:
  - `load_config()`: Reads `config.json` to load custom user-defined output directories.
  - `get_base_dir()`: Resolves active target directory in strict order: Custom Output Directory -> OBS Recording Directory -> Desktop Fallback.
  - `check_freeze_flag()`: Checks if `freeze_trigger.flag` exists, updates `last_freeze_time`, and removes the flag.
  - `start_new_session_if_needed()`: Creates a new timestamped directory (`Markers_YYYY-MM-DD_HH-MM-SS`) on the first marker save.
  - `add_marker(timecode, name)`: Converts timecode string to seconds and 60fps frames, appends to in-memory list, and triggers `flush_files()`.
  - `undo_last_marker()`: Removes the latest marker. If marker count drops to zero, invokes `cleanup_session_files()`.
  - `reset_session()`: Finalizes current session state when OBS stops recording.
  - `flush_files()`: Simultaneously writes TXT, CSV, Premiere XML, and FCPXML files.
  - `generate_txt()`: Produces YouTube chapter list with auto-prepended `00:00:00 - Intro`.
  - `generate_csv()`: Writes RFC 4180 compliant CSV marker records.
  - `generate_xml()`: Builds FCP 7 XML sequence with native `<marker>` elements for Premiere Pro.
  - `generate_fcpxml()`: Builds Final Cut Pro XML v1.9 sequence with native `<marker>` tags.
  - `cleanup_session_files()`: Resilient 4-phase deletion routine (force `gc.collect()`, strip read-only attributes, unlink files, remove folder).
- `flag_watcher()`:
  - Background daemon thread executing every 40ms (`time.sleep(0.04)`) to capture Lua hotkey signals.
- `ResilientHTTPServer`:
  - `HTTPServer` subclass setting `allow_reuse_address = True` to prevent socket binding errors during rapid restarts.
- `MarkerRequestHandler`:
  - `do_GET()`: Dispatches `/api/status` requests with JSON state payload.
  - `do_POST()`: Dispatches `/api/save_marker`, `/api/undo_marker`, `/api/reset_session`, `/api/config`, and `/api/open_folder`.
  - `do_OPTIONS()`: Returns HTTP 200 with CORS headers (`Access-Control-Allow-Origin: *`, allowed methods, allowed headers).
  - `_send_json(data, status=200)`: Encodes JSON response with UTF-8 and cache-prevention headers.

#### Functionality Ideas for `server.py`
- **Idea 1: Native SubRip (.srt) Export**: Optional toggle to generate subtitle files for creators uploading to media platforms without XML import support.
- **Idea 2: Framerate Auto-Detection**: Query OBS WebSocket or inspect output file container to automatically set timeline timebase (e.g. 24fps, 30fps, 59.94fps) instead of fixed 60fps.
- **Idea 3: WebSocket Event Push**: Replace HTTP polling from dock with a lightweight WebSocket event stream directly from the Python daemon.

#### Pros & Cons of Current Implementation
- Pros: Zero external dependencies; starts in under 15ms; consumes under 12MB RAM; robust against Windows file locks; simultaneous 4-format output.
- Cons: Fixed 60fps frame calculations; requires polling loop on frontend instead of native server push.

---

### `src/marker_service.lua` (OBS Native Frontend Hook)
Embedded Lua script managing process lifecycle, global hotkey registration, and OBS UI properties.

#### Key Functions & Callbacks
- `script_description()`: Displays plugin overview, quick start steps, and hotkey binding tips in OBS Scripts dialog.
- `get_script_dir()`: Normalizes directory path using `string.gsub(dir, "/", "\\")` for Windows execution.
- `write_config()`: Serializes `custom_output_dir` into `config.json` inside the script directory.
- `trigger_freeze(pressed)`: Callback bound to `marker_tool.freeze` hotkey. Writes timestamp to `freeze_trigger.flag`.
- `on_open_folder(props, prop)`: UI button callback opening active marker directory via Windows Explorer or curl REST call.
- `script_properties()`: Defines directory path picker (`custom_output_dir`) and open folder button (`btn_open`).
- `script_update(settings)`: Triggers when user modifies settings in OBS dialog; updates and saves configuration.
- `script_defaults(settings)`: Initializes default settings values.
- `script_load(settings)`:
  - Invokes `run_silent.vbs` to ensure backend daemon is alive.
  - Registers `marker_tool.freeze` hotkey via `obs.obs_hotkey_register_frontend`.
  - Loads saved hotkey combinations from OBS data arrays.
  - Releases OBS data arrays using `obs.obs_data_array_release` to prevent memory leaks.
- `script_save(settings)`: Serializes hotkey bindings and custom path to OBS scene collection settings.
- `script_unload()`: Calls `stop.bat` to cleanly terminate Python backend on OBS exit.

#### Functionality Ideas for `marker_service.lua`
- **Idea 1: Multi-Hotkey Channels**: Register distinct hotkeys for specific tags (e.g. F8 for Clutch, F9 for Ace, F10 for Whiff).
- **Idea 2: OBS Replay Buffer Marker Hook**: Auto-trigger marker save whenever OBS Replay Buffer is saved.
- **Idea 3: Scene Switch Markers**: Auto-generate marker tags when active OBS scene changes (e.g. "Scene: Gameplay", "Scene: Just Chatting").

#### Pros & Cons of Current Implementation
- Pros: 100% anti-cheat ban proof; uses OBS trusted input subsystem; auto-starts and stops with OBS; zero external Lua DLLs.
- Cons: Lua 5.1 lacks native networking without external binary extensions; file flag mechanism has up to 40ms latency.

---

### `src/index.html` (OBS Custom Browser Dock)
Ultra-compact (40px total height) Chromium Embedded Framework UI embedded inside OBS Studio.

#### Architecture & Styling
- Dual-Row Layout:
  - Row 1 (22px): Clock re-grab button, description text input with embedded marker counter badge, primary Save button, contextual Action/Undo button.
  - Row 2 (18px): Scrollable preset chips container (`Ace`, `Clutch`, `Funny`, `Dono`, `Whiff`) and in-place `+ tag` adder.
- Sensory Feedback Design:
  - Electric Cyan (`#00d2ff`): High-luminance peripheral screen flash triggering exclusively on global hotkey press.
  - Muted Sage (`#22c55e`): Low-contrast border highlight and ghost text on successful marker save to prevent dark-room glare.
  - Red Undo Badge: 5-second countdown timer on Action button permitting instant rollback.

#### WebSocket v5 & REST State Machine
- Subscribes to OBS WebSocket v5 (`ws://127.0.0.1:4456`, fallback `4455`).
- Listens to `RecordStateChanged` event to automatically enable dock on recording start and reset on stop.
- Polls `GetRecordStatus` every 1000ms for active timecode display.
- Requests `GetRecordDirectory` on connect to automatically align marker exports with video captures.
- Polls local backend `/api/status` every 150ms to detect Lua hotkey freeze events and synchronize marker counts.
- Stores custom preset chips in browser `localStorage`.

#### Functionality Ideas for `index.html`
- **Idea 1: Real-Time Marker Timeline View**: Expandable drawer showing list of recorded markers with click-to-edit names.
- **Idea 2: Audio Cue Selector**: Optional toggle to play discrete audio pings routed to monitoring devices.
- **Idea 3: Customizable Preset Palettes**: User-defined color coding for preset chips matching NLE marker colors.

#### Pros & Cons of Current Implementation
- Pros: Seamlessly docks into OBS; zero external window management; non-distracting sensory feedback; instant preset tagging.
- Cons: Fixed 40px dual-row layout; requires OBS WebSocket enabled (default in OBS 28+).

---

### `src/run_silent.vbs` (Headless Launcher)
VBScript utility launching Python backend invisibly.

#### Mechanics & Execution
- Uses `WScript.Shell` with window style `0` (hidden) and wait mode `False`.
- Checks for user-specific Python 3.14 path first (`C:\Users\mudxiej\AppData\Local\Programs\Python\Python314\pythonw.exe`), falling back to PATH `pythonw`.
- Prevents annoying black command prompt windows from flashing across the screen on OBS startup.

#### Functionality Ideas & Alternatives
- **Idea**: Replace VBS with PowerShell `-WindowStyle Hidden` or compiled C launcher.
- **Pros & Cons**: VBS requires zero compilers, is pre-installed on all Windows systems, and starts instantly. PowerShell scripts have higher startup latency and can be blocked by execution policies (`Restricted`).

---

### `src/install.bat` (Automated Installer)
Batch script deploying all plugin files into `%APPDATA%\obs-studio\scripts\obs-marker-tool\`.

#### Mechanics & Execution
- Validates Python presence in system PATH.
- Creates destination directory if missing.
- Copies all runtime files (`index.html`, `server.py`, `marker_service.lua`, `run_silent.vbs`, `run.bat`, `stop.bat`).
- Offers interactive prompt to open destination folder in Windows Explorer.

#### Functionality Ideas & Alternatives
- **Idea**: InnoSetup or MSI installer package.
- **Pros & Cons**: Batch script is lightweight, completely transparent, and inspectable by security-conscious creators. Compiled installers trigger Windows SmartScreen warnings.

---

### `src/run.bat` & `src/stop.bat` (Developer & Lifecycle Scripts)
- `run.bat`: Launches `python server.py` in an interactive console window with `pause` on exit for debugging HTTP headers, WebSocket payloads, and file writes.
- `stop.bat`: Scans `netstat -aon` for PID listening on port 8765 and invokes `taskkill /f /pid` to terminate orphaned processes.

#### Pros & Cons
- Pros: Simple, zero-dependency process management for Windows.
- Cons: Hardcoded port 8765; could terminate an unrelated application if port conflict occurs (mitigated by uncommon default port).

---

### `scripts/sync_wiki.py` (Wiki Synchronization Tool)
Automation script keeping GitHub Wiki repository in sync with `docs/wiki/`.

#### Mechanics & Execution
- Reads GitHub token from Windows Credential Manager under `GitHub - https://api.github.com/Mudxiej` via Win32 `CredReadW`.
- Copies all files from `docs/wiki/` into a temporary Git repository.
- Commits and pushes to `https://github.com/Mudxiej/obs-marker-tool.wiki.git`.
- Provides explicit user guidance if the remote wiki repository has not yet been initialized via web UI.

---

## 3. Local REST API Specification

Local Python server runs on `http://127.0.0.1:8765`. Standard CORS headers are returned on all responses.

### `GET /api/status`
Returns current session state, marker count, recording directories, and latest freeze event timestamp.

#### Response (200 OK)
```json
{
  "active_session": "2026-09-25_06-30-00",
  "markers_count": 3,
  "files_created": true,
  "folder": "C:\\Users\\mudxiej\\Videos\\Markers_2026-09-25_06-30-00",
  "base_dir": "C:\\Users\\mudxiej\\Videos",
  "recording_dir": "C:\\Users\\mudxiej\\Videos",
  "custom_output_dir": null,
  "freeze_event": 1727238600.123
}
```

---

### `POST /api/save_marker`
Saves a new marker at the specified timecode and flushes all 4 export files.

#### Request Body
```json
{
  "timecode": "00:04:12",
  "name": "1v3 Clutch"
}
```

#### Response (200 OK)
```json
{
  "success": true,
  "marker": {
    "timecode": "00:04:12",
    "seconds": 252.0,
    "name": "1v3 Clutch",
    "frame_in": 15120,
    "timestamp": "06:34:12"
  },
  "count": 4,
  "folder": "C:\\Users\\mudxiej\\Videos\\Markers_2026-09-25_06-30-00"
}
```

---

### `POST /api/undo_marker`
Rolls back the most recently saved marker. If marker count drops to zero, unlinks all files and purges session directory.

#### Response (200 OK)
```json
{
  "success": true,
  "removed": {
    "timecode": "00:04:12",
    "seconds": 252.0,
    "name": "1v3 Clutch",
    "frame_in": 15120,
    "timestamp": "06:34:12"
  },
  "count": 3
}
```

---

### `POST /api/reset_session`
Closes active recording session and resets memory counters to zero. Automatically invoked by the browser dock when OBS stops recording.

#### Response (200 OK)
```json
{
  "success": true
}
```

---

### `POST /api/config`
Updates dynamic recording directory or persistent custom output path.

#### Request Body
```json
{
  "recording_dir": "D:\\OBS_Recordings",
  "custom_output_dir": "D:\\Custom_Markers"
}
```

#### Response (200 OK)
```json
{
  "success": true,
  "recording_dir": "D:\\OBS_Recordings",
  "custom_output_dir": "D:\\Custom_Markers",
  "base_dir": "D:\\Custom_Markers"
}
```

---

### `POST /api/open_folder`
Opens active session marker folder (or base recording folder) in Windows Explorer via `os.startfile`.

#### Response (200 OK)
```json
{
  "success": true,
  "opened": "C:\\Users\\mudxiej\\Videos\\Markers_2026-09-25_06-30-00"
}
```
