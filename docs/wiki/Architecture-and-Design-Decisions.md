# Architecture & Design Decisions

This document details the architectural foundation, inter-process communication mechanisms, ergonomic engineering, and core design choices of OBS Marker Tool.

---

## 1. System Architecture Overview

OBS Marker Tool implements a decoupled three-tier architecture:

| Tier | Component | Environment | Execution Details |
| :--- | :--- | :--- | :--- |
| **Presentation Tier** | `src/index.html` | OBS Chromium Embedded Framework (CEF) | Embedded Custom Browser Dock. Communicates with OBS WebSocket v5 for real-time recording state and sends REST calls to the local Python backend. |
| **Native Integration Tier** | `src/marker_service.lua` | OBS Studio Lua 5.1 Runtime | Native frontend script hooked into OBS startup/shutdown. Manages daemon lifecycle, native UI properties, and registers global hotkeys via OBS internal input subsystem. |
| **Storage & Export Tier** | `src/server.py` | Python Standard Library (`pythonw.exe`) | Silent background HTTP daemon listening on `127.0.0.1:8765`. Handles atomic multi-format timeline exports, file locking resiliency, and folder cleanup. |

---

## 2. Inter-Process Communication (IPC)

The system coordinates three independent execution environments using three lightweight, decoupled protocols:

### A. OBS WebSocket v5 (Timecode & State Sync)
- **Transport**: Native WebSocket connection over `ws://127.0.0.1:4456` (falling back to `4455`).
- **Events Subscribed**: `RecordStateChanged` (Event subscription bitmask 65).
- **Requests**:
  - `GetRecordStatus`: Polled every 1000ms and immediately upon freeze to extract `outputTimecode` and `outputActive`.
  - `GetRecordDirectory`: Auto-discovers the active OBS recording folder and pushes it to the Python backend via `/api/config`.

### B. Lock-Free File Flag Trigger (`freeze_trigger.flag`)
- **Transport**: Atomic filesystem flag file located in the script directory.
- **Mechanism**:
  - When the user presses the global hotkey registered in OBS, `marker_service.lua` writes an integer timestamp to `freeze_trigger.flag`.
  - A background daemon thread in `server.py` checks for the flag file at 40ms intervals (`time.sleep(0.04)`).
  - Upon detection, the server updates `last_freeze_time` and immediately unlinks the flag file.
- **Advantage**: Zero external Lua dependencies. Eliminates complex socket binding or luarocks requirements inside the OBS Lua sandbox.

### C. Local REST API (State & Export Management)
- **Transport**: HTTP/1.1 over `127.0.0.1:8765`.
- **Latency**: Sub-millisecond local loopback response.
- **Operations**: Marker creation, 5-second undo rollback, folder opening via Windows shell, and dynamic directory updates.

---

## 3. Ergonomic Design & Sensory Feedback

Gaming streamers and content creators operate under heavy cognitive load, often in dimly lit rooms. UI elements must communicate status instantly without peripheral distraction.

### Electric Cyan Peripheral Flash (`#00d2ff`)
- **Trigger**: In-game global hotkey freeze (e.g. F8).
- **Visual Timing**: 60ms instant attack to 85% opacity, followed by a smooth 1200ms ease-out exponential decay.
- **Ergonomic Rationale**: The streamer's eyes remain locked onto their crosshair or gameplay. The high-luminance cyan tint reflects in peripheral vision, confirming the marker timestamp was captured without requiring them to glance over at OBS.
- **Key Detail**: UI mouse clicks on the clock button freeze the timestamp cleanly without triggering this flash, preventing visual fatigue during manual editing.

### Muted Sage Save Feedback (`#22c55e`)
- **Trigger**: Marker saved via Enter, Save button, or Preset chip.
- **Visual Feedback**: The text input field transitions its border to a soft muted sage tint, accompanied by a `"Saved!"` placeholder text.
- **Duration**: Remains visible for 5 seconds, followed by a 500ms fade back to default.
- **Ergonomic Rationale**: Earlier designs used a full-screen green flash on save. In dark streaming rooms, rapid consecutive saves caused intense glare and eye fatigue. Replacing full-screen flashes with localized input frame feedback provides clear confirmation with zero glare.

### Dual-Row Ultra-Compact Profile
- **Total Height**: Exactly 40px (Row 1: 22px, Row 2: 18px).
- **Layout Strategy**:
  - Row 1: Clock re-grab button, description text input with embedded counter badge, primary Save button, and contextual Action/Undo button.
  - Row 2: Horizontally scrollable preset chips container and in-place morphing `+ tag` adder.
- **OBS Placement**: Fits flush directly above or below the OBS Audio Mixer or Scene Selector without consuming vertical canvas real estate.

---

## 4. Architectural Decision Records (ADRs)

### ADR-01: Zero External Python Dependencies (Standard Library Only)
- **Context**: Video creators have varied technical backgrounds. Asking users to run `pip install` often leads to broken PATH errors, missing compilers, or environment conflicts.
- **Decision**: Restrict `server.py` exclusively to Python standard library modules (`http.server`, `urllib`, `pathlib`, `json`, `threading`, `shutil`, `subprocess`, `stat`, `gc`).
- **Consequences**:
  - Pros: 100% install reliability. Instant startup (<15ms). Memory footprint under 12MB RAM. Zero dependency rot.
  - Cons: Manual HTTP request routing and XML serialization without third-party frameworks.

### ADR-02: OBS Native Lua Hotkey Registration
- **Context**: Capturing global hotkeys during fullscreen games typically uses OS-level keyboard hooks (`pynput`, `SetWindowsHookEx`).
- **Decision**: Register hotkeys exclusively through OBS Studio's internal frontend scripting API (`obs.obs_hotkey_register_frontend`).
- **Consequences**:
  - Pros: Zero risk of game bans from anti-cheat systems (Vanguard, EAC, BattlEye). OBS handles keybind conflicts, modifier combinations, and profile persistence automatically.
  - Cons: Hotkey only fires while OBS Studio is running (which aligns perfectly with recording workflows).

### ADR-03: Two-Phase Marker Architecture (Freeze then Tag)
- **Context**: A common complaint with automated marker tools is that markers saved mid-fight end up with meaningless default names ("Marker 1", "Marker 2"), creating extra work for editors.
- **Decision**: Implement a two-phase capture model:
  1. Phase 1 (Capture): Blind hotkey tap freezes the exact timecode instantaneously and changes the clock icon to picked state.
  2. Phase 2 (Annotate): The streamer can type a custom note or click a preset chip (`Ace`, `Clutch`) immediately or during a match pause. The marker always saves at the frozen timestamp, not the time of annotation.
- **Consequences**:
  - Pros: High-precision timestamps combined with rich context.
  - Cons: Requires handling state where a frozen timestamp is cleared or overwritten.

### ADR-04: Simultaneous 4-Format Multi-NLE Serialization
- **Context**: Creators collaborate with editors using diverse editing suites (Premiere Pro, DaVinci Resolve, Final Cut Pro) and also post YouTube chapters.
- **Decision**: On every save, serialize the entire marker list simultaneously into four files:
  1. `markers.txt`: Formatted for YouTube video description chapters with auto-prepended `00:00:00 - Intro`.
  2. `markers.csv`: Standard CSV with RFC 4180 quotes for DaVinci Resolve and Premiere CSV marker import.
  3. `premiere_sequence.xml`: FCP 7 XML sequence for Premiere Pro drag-and-drop.
  4. `final_cut_pro.fcpxml`: FCPXML v1.9 sequence for Apple Final Cut Pro and DaVinci XML import.
- **Consequences**:
  - Pros: Zero configuration required. Any editor on the team can pick their preferred format.
  - Cons: Four file writes per marker (mitigated by microscopic file sizes <10KB).

### ADR-05: Atomic 5-Second Undo with Auto-Purging
- **Context**: Accidental hotkey taps create unnecessary files on disk.
- **Decision**: Provide a contextual Red Undo button active for 5 seconds following any save. If the last marker is undone and 0 markers remain, completely delete the marker files and the containing folder from disk.
- **Consequences**:
  - Pros: Keeps the user's storage drive completely clean of empty directories.
  - Cons: Required implementing robust multi-pass file deletion with permission stripping to overcome Windows filesystem handle locks.

### ADR-06: Embedded Chromium Embedded Framework (CEF) Dock
- **Context**: Users need immediate visual confirmation and controls without losing focus during streams.
- **Decision**: Render the entire presentation tier as an OBS Custom Browser Dock using web standards (HTML5/CSS3/ES6).
- **Consequences**:
  - Pros: Docks directly inside OBS Studio; layout persists across OBS profiles; starts/stops with OBS; zero third-party window management.
  - Cons: Requires OBS Studio 28+ with browser dock support.

### ADR-07: Lock-Free File-Flag IPC (`freeze_trigger.flag`)
- **Context**: Notifying the Python server of hotkey presses from OBS Lua without installing socket libraries.
- **Decision**: Lua writes an atomic timestamp file (`freeze_trigger.flag`); Python polls at 40ms intervals and immediately unlinks the flag.
- **Consequences**:
  - Pros: 100% dependency-free; zero native DLL compilation; works across all OBS versions.
  - Cons: Introduce up to 40ms polling latency (negligible for video editing marker placement).
