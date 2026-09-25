# Functionality Ideas & Roadmap

Exploration of potential future functionality, community-requested features, architectural proposals, and an exhaustive pros-and-cons analysis for each enhancement.

---

## 1. Feature Evaluation Matrix

| Proposal | Primary Benefit | Implementation Complexity | Dependency Impact | Evaluation Status |
| :--- | :--- | :--- | :--- | :--- |
| **Multi-Keybind Marker Channels** | Instant categorized markers mid-game | Low (Lua frontend hotkey expansion) | Zero external dependencies | **High Priority** |
| **Realtime Dock Marker Drawer** | Visual marker list with in-dock renaming | Medium (CSS/JS expansion in CEF dock) | Zero external dependencies | **High Priority** |
| **OBS Framerate Auto-Detection** | Frame-perfect XML timebase matching | Low (OBS WebSocket `GetVideoSettings`) | Zero external dependencies | **High Priority** |
| **Stream Deck / Touch Portal Action** | Physical hardware button tagging | Medium (Local REST API triggers) | Zero external dependencies | **Medium Priority** |
| **Marker Span / Duration Ranges** | Support for clip start/end marker ranges | High (State machine & XML schema update) | Zero external dependencies | **Under Evaluation** |
| **JSON Timeline Metadata Output** | Automation for programmatic editors | Low (Additional serializer in `server.py`) | Zero external dependencies | **Under Evaluation** |
| **Twitch Channel Points Trigger** | Audience-driven highlight timestamps | High (Twitch EventSub / OAuth token) | Requires OAuth handling | **Low Priority** |
| **Cloud Storage Auto-Sync** | Immediate remote backup for off-site editors | High (Rclone / Cloud API client) | External network dependencies | **Low Priority** |

---

## 2. In-Depth Feature Proposals & Pros-Cons Analysis

### Proposal 1: Multi-Keybind Marker Channels (F8 Clutch, F9 Ace, F10 Whiff)
Allows assigning distinct OBS hotkeys to specific marker categories. Pressing F8 saves a "Clutch" marker, F9 saves an "Ace", and F10 saves a "Funny" marker directly with zero typing.

#### Proposed Workflow
- In `marker_service.lua`, register multiple frontend hotkeys:
  - `marker_tool.freeze_clutch` -> writes `freeze:Clutch` into flag file.
  - `marker_tool.freeze_ace` -> writes `freeze:Ace` into flag file.
  - `marker_tool.freeze_funny` -> writes `freeze:Funny` into flag file.
- `server.py` reads the category token and auto-names the marker.

#### Pros & Cons
- Pros: Eliminates the need to look at the dock or type labels during intense gameplay; maintains 100% anti-cheat safety through OBS native hotkey system.
- Cons: Consumes multiple hotkey slots in OBS; requires user to configure multiple keybinds.

---

### Proposal 2: Realtime Dock Marker Drawer (List & Rename)
An expandable drawer beneath the 40px dock displaying recorded markers with live timestamps, label editing, and individual delete buttons.

#### Proposed Workflow
- Clicking an expand arrow slides down a list of active session markers.
- Streamers can edit names or delete specific markers during match intermissions without waiting for post-production.

#### Pros & Cons
- Pros: Provides visual confirmation of all saved markers; allows fixing typos during stream breaks.
- Cons: Increases vertical dock height beyond the 40px ultra-compact profile; requires collapse/expand state persistence.

---

### Proposal 3: OBS Framerate Auto-Detection (24fps, 30fps, 59.94fps, 60fps)
Automatically fetch OBS Studio's exact recording framerate (`fpsNumerator` and `fpsDenominator`) via WebSocket v5 `GetVideoSettings` request.

#### Proposed Workflow
- During dock initialization, send `GetVideoSettings` request over WebSocket v5.
- Transmit the exact framerate ratio to `server.py` via `/api/config`.
- `server.py` calculates timeline frames dynamically:
  `frame_in = int(round(total_seconds * (fps_num / fps_den)))`

#### Pros & Cons
- Pros: Guarantees frame-accurate marker placement for cinematic 24fps projects, 30fps podcasts, and broadcast 59.94fps streams.
- Cons: Adds slight complexity to XML export math; default 60fps already covers 95%+ of gaming creators.

---

### Proposal 4: Stream Deck & Touch Portal Integration
Provide direct Stream Deck and Touch Portal button profiles that invoke the local REST API (`http://127.0.0.1:8765/api/save_marker`).

#### Proposed Workflow
- Distribute pre-configured Stream Deck button profiles.
- Stream Deck sends an HTTP POST with `{ "name": "Highlight" }`.

#### Pros & Cons
- Pros: Seamless integration for creators with hardware control pads; tactile feedback without occupying keyboard hotkeys.
- Cons: Requires creator to own external hardware; existing keyboard hotkey already works universally.

---

### Proposal 5: Marker Span / Duration Ranges (In & Out Points)
Support marking duration intervals (e.g. a 45-second round) rather than an instantaneous timestamp.

#### Proposed Workflow
- First hotkey press sets `Marker In`; second hotkey press sets `Marker Out`.
- Serializes duration into Premiere XML `<in>` / `<out>` tags and DaVinci Resolve duration markers.

#### Pros & Cons
- Pros: Directly delineates highlight clip boundaries on the editing timeline.
- Cons: Doubles cognitive load during fast-paced games (streamers often forget to close open markers); complicates the ultra-compact dock UI.

---

### Proposal 6: Programmatic JSON Timeline Metadata Export
Simultaneously generate a `markers.json` file structured for automated Python video editing scripts (e.g. MoviePy, DaVinci Resolve Python API).

#### Proposed Structure
```json
{
  "recording_session": "2026-09-25_06-30-00",
  "framerate": 60.0,
  "markers": [
    {
      "timecode": "00:03:15",
      "seconds": 195.0,
      "frame": 11700,
      "label": "Ace Round 4"
    }
  ]
}
```

#### Pros & Cons
- Pros: Enables headless CLI editing pipelines, automated highlight reel generators, and Discord bot notifications.
- Cons: Adds a fifth file to the output folder; standard CSV and XML already cover most automation use cases.

---

### Proposal 7: Twitch Channel Points & Chat Trigger
Allow Twitch stream viewers to trigger markers via Channel Points redemptions or moderator chat commands (`!mark`).

#### Proposed Workflow
- Python backend listens to Twitch EventSub WebSocket.
- Upon redemption, writes an audience-voted marker into the recording timeline.

#### Pros & Cons
- Pros: High viewer engagement; crowdsourced highlight curation.
- Cons: Requires internet connectivity, Twitch OAuth tokens, and bot credentials; opens the timeline to chat spam and trolling.

---

### Proposal 8: Cloud Storage Auto-Sync
Automatically upload marker files to Google Drive, Dropbox, or a shared team NAS the instant recording stops.

#### Proposed Workflow
- On `/api/reset_session`, execute background sync script copying `Markers_YYYY-MM-DD_HH-MM-SS` to cloud storage.

#### Pros & Cons
- Pros: Remote video editors receive timeline markers before raw video footage even finishes uploading.
- Cons: Introduces cloud API authentication dependencies; creators can achieve the same result by setting OBS recording directory to a cloud-synced folder.

---

## 3. Guiding Architectural Principles for Future Features

To preserve the speed, safety, and reliability of OBS Marker Tool, all future feature implementations must comply with three core rules:

1. **Zero External Runtime Dependencies**: The core tool must remain executable using standard Python 3.8+ and native OBS Studio without requiring `pip install`.
2. **Anti-Cheat Ban Immunity**: No feature may inject code into game processes, install OS-level keyloggers, or capture game framebuffers.
3. **Ergonomic Minimalism**: The dock UI must never exceed 40px in standard mode and must never emit distracting audio or blinding light in dark rooms.
