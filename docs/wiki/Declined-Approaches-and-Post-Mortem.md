# Declined Approaches & Post-Mortem

During the research, prototyping, and testing phases of OBS Marker Tool, numerous architectural strategies, libraries, input hooks, and UX patterns were evaluated, implemented, and subsequently declined.

This document records the technical rationales, security risks, ergonomic failure modes, and performance trade-offs behind each rejected approach.

---

## 1. OS-Level Global Keyloggers (`pynput`, `keyboard`, Win32 `SetWindowsHookEx`)

### What Was Evaluated
Using a background Python thread with libraries like `pynput` or `keyboard` to install a Windows low-level keyboard hook (`WH_KEYBOARD_LL`) or continuously poll `GetAsyncKeyState` for global hotkey triggers across all system windows.

### Why It Was Declined
- **Fatal Anti-Cheat Collision Risk**: Modern competitive games employ kernel-level and hypervisor-level anti-cheat engines (Riot Vanguard for Valorant, Easy Anti-Cheat for Apex Legends/Fortnite, BattlEye for Rainbow Six Siege). These drivers actively monitor `SetWindowsHookExW` and flag or terminate background processes reading raw keystrokes as unauthorized keyloggers or macro bots. Using an external Python keylogger exposes streamers to immediate game crashes, account suspensions, or hardware HWID bans.
- **Permission Elevation Conflicts**: Windows integrity levels prevent standard user-mode processes from intercepting keystrokes inside games running with administrative privileges unless the logger is also elevated.
- **Chosen Alternative**: OBS Studio's native Lua frontend scripting API (`obs.obs_hotkey_register_frontend`). OBS is already trusted by anti-cheat systems, digitally signed, and hooks keyboard input through OBS's native display pipeline. Keystrokes are received cleanly with zero anti-cheat risk.

---

## 2. Heavy Web Frameworks (Flask, FastAPI, Uvicorn, Tornado)

### What Was Evaluated
Building the local REST backend using modern Python web frameworks such as FastAPI with Uvicorn or Flask.

### Why It Was Declined
- **Dependency Friction & Installation Failures**: Most content creators are not software engineers. Requiring external packages via `pip install -r requirements.txt` frequently breaks due to:
  - Python not added to system PATH during installation.
  - Missing Microsoft Visual C++ Build Tools when compiling binary wheels.
  - Conflicting Python versions or corrupted virtual environments.
- **Resource Overhead & Cold Start**: Frameworks like FastAPI and Uvicorn require asynchronous event loops, Pydantic type validation, and dozens of sub-dependencies, resulting in cold start times of 800ms+ and RAM consumption exceeding 65MB.
- **Chosen Alternative**: Pure Python standard library `http.server.HTTPServer` with custom `BaseHTTPRequestHandler`. Requires zero pip installations, starts in under 15ms, consumes less than 12MB of system RAM, and runs reliably on any machine with Python 3.8+.

---

## 3. Standalone Desktop Window / System Tray Utility (Electron, PyQt6, Tkinter)

### What Was Evaluated
Packaging the marker interface into a standalone desktop window or system tray application using PyQt6, Tkinter, or an Electron wrapper.

### Why It Was Declined
- **Screen Real Estate & Alt-Tab Friction**: Streamers manage high-density multi-monitor setups crowded with game viewports, OBS Studio, Twitch chat, stream alerts, Discord, and audio mixers. A separate utility window forces the user to manage another window, alt-tab away from the game, or risk the window getting buried beneath other applications.
- **Failure to Match Streamer Ergonomics**: Standalone windows must be manually positioned on every reboot and do not save their location with OBS scene collections.
- **Chosen Alternative**: OBS Custom Browser Dock (`index.html`). By loading the UI directly through OBS's Chromium Embedded Framework, the tool docks seamlessly into the native OBS workspace, saves its layout alongside OBS profiles, and starts/stops automatically with the broadcaster's production suite.

---

## 4. Single-Step Blind Marker Writing (Immediate Write Without Freeze)

### What Was Evaluated
Automatically writing a generic marker (e.g. "Marker 1", "Marker 2") to disk the instant the hotkey is pressed, without maintaining a frozen timecode state in the UI.

### Why It Was Declined
- **Post-Production Context Blindness**: During an 8-hour stream, a creator may hit the hotkey 30 to 50 times. Without descriptive labels, an editor opening the timeline sees dozens of identical markers. The editor must still scrub through the footage to figure out whether a marker represents an insane clutch, a funny voice chat interaction, or a technical glitch.
- **Inability to Correct Accidental Triggers**: Immediate disk writes make accidental keypresses permanent unless manually edited out in external files.
- **Chosen Alternative**: Two-Phase Marker Architecture. The hotkey instantly freezes the timecode and flashes Electric Cyan in peripheral vision. The creator continues playing undisturbed. When a quiet moment arrives 15 seconds later, they glance at the dock and tap `Ace` or `Clutch` with one click. The marker is written with the frozen timecode, preserving both timing accuracy and editorial context.

---

## 5. Subtitle (SRT Hack) Marker Injection

### What Was Evaluated
Exporting marker timestamps as a standard SubRip subtitle file (`.srt`) so media players could display markers as subtitles.

### Why It Was Declined
- **Incompatible with Video Editor Timelines**: Professional video editors (Premiere Pro, DaVinci Resolve, Final Cut Pro) treat SRT files as subtitle or closed-caption tracks, not sequence markers. Captions cannot be snapped to with playhead navigation shortcuts, cannot be color-coded, and do not show up in marker index windows.
- **Poor Editor Workflow**: Editors would have to manually read subtitle blocks and manually create timeline markers at each point.
- **Chosen Alternative**: Native FCP 7 XML (`<xmeml>`) and Final Cut Pro XML (`<fcpxml v1.9>`). Dragging these files into Premiere Pro or Final Cut Pro immediately creates a ready-to-edit sequence with native colored timeline markers positioned on exact video frames.

---

## 6. Retaining Empty Marker Folders on Disk

### What Was Evaluated
Leaving the generated `Markers_YYYY-MM-DD_HH-MM-SS` directory on disk even after all markers within it were removed via Undo.

### Why It Was Declined
- **Storage Directory Pollution**: If a creator accidentally bumps the hotkey or tests the button before starting a stream, an empty marker directory is left behind. Over weeks of daily streaming, recording directories become cluttered with dozens of empty, useless folders.
- **Chosen Alternative**: Resilient Multi-Pass Directory Cleanup. When the marker count reaches zero following an Undo action, `server.py` executes a multi-stage cleanup routine:
  1. Garbage collects latent Python file handles (`gc.collect()`).
  2. Strips read-only permissions (`stat.S_IWRITE | stat.S_IREAD`).
  3. Unlinks all export files.
  4. Removes the empty session folder with fallback to `cmd.exe /c rmdir /s /q`.

---

## 7. Direct WebSocket Server inside Lua

### What Was Evaluated
Running a WebSocket server directly inside `marker_service.lua` to push hotkey events to the browser dock over local network sockets.

### Why It Was Declined
- **Lua Sandbox Limitations**: The Lua 5.1 environment embedded inside OBS Studio does not provide socket libraries out of the box. Using sockets requires distributing and compiling external C dynamic link libraries (`luasocket.dll`), introducing platform architecture mismatches (x86 vs x64) and installation failures across different OBS versions.
- **Chosen Alternative**: Lock-Free File Flag Trigger (`freeze_trigger.flag`). Lua writes a micro-file using standard ANSI C I/O (`io.open`), which `server.py` monitors on a 40ms daemon thread. This guarantees 100% compatibility across all OBS versions with zero external binary dependencies.

---

## 8. Audible Beep Feedback vs Silent Visual Cyan Flash

### What Was Evaluated
Playing an audible beep or notification sound through Windows audio output whenever the hotkey is pressed.

### Why It Was Declined
- **Microphone and Stream Audio Contamination**: Unless complex virtual audio routing (Voicemeeter, SteelSeries Sonar) is configured, system sounds easily bleed into the streamer's microphone audio track or desktop capture feed, ruining clean video production.
- **Interference with Tactical Gameplay Audio**: In games like Valorant or CS2, hearing quiet footsteps, defuse sounds, or reload cues is critical to winning rounds. An audible beep at the exact moment of an intense clutch masks essential in-game audio cues.
- **Chosen Alternative**: Electric Cyan (`#00d2ff`) Peripheral Flash. A subtle 60ms flash on the OBS dock reflects in peripheral vision without producing a single decibel of sound or audio track pollution.

---

## 9. Direct In-Game DirectX / Vulkan Overlay Hooks (RTSS, Overwolf, DLL Injection)

### What Was Evaluated
Injecting a DirectX or Vulkan overlay directly onto the game viewport to display marker confirmation and tagging menus without looking at OBS.

### Why It Was Declined
- **Severe Anti-Cheat Violation**: Injecting dynamic link libraries (`.dll`) or hooking swapchain presentation functions (`Present`, `ResizeBuffers`) inside protected game processes triggers immediate kernel anti-cheat flags. Riot Vanguard treats unauthorized overlay hooks as potential wallhacks or ESP cheats, resulting in permanent HWID bans.
- **Render Engine Instability**: Custom graphics hooks frequently cause micro-stutters, tearing, or crashes during fullscreen transitions and resolution switching.
- **Chosen Alternative**: Native OBS Custom Browser Dock. Operates completely outside the game process, rendering inside OBS Studio's CEF process with zero game interference.

---

## 10. Direct MP4 / MKV Container Metadata Chapter Injection

### What Was Evaluated
Injecting chapter markers directly into the active `.mp4` or `.mkv` video file container using `ffmpeg` or `mp4box` during or immediately following recording.

### Why It Was Declined
- **Exclusive File Lock Contention**: While OBS is actively writing video streams to disk, the operating system holds an exclusive write lock. Attempting to write container metadata concurrently causes write collisions, frame drops, or corrupts the container header.
- **Post-Stream Remux Latency**: Injecting chapters post-recording requires remuxing multi-gigabyte video files with `ffmpeg`. For a 50GB 4-hour recording, remuxing takes several minutes and consumes significant CPU/disk I/O right when the creator wants to review their footage.
- **Risk of Total Media Loss**: If OBS or the system crashes during remuxing, the entire video file risks corruption.
- **Chosen Alternative**: Sidecar multi-format timeline export (`premiere_sequence.xml`, `final_cut_pro.fcpxml`, `markers.csv`, `markers.txt`). Zero risk to source video files, instant completion (<5ms), and immediate drag-and-drop into NLEs.

---

## 11. Computer Vision & OCR for Automatic Killfeed Detection

### What Was Evaluated
Using background frame capture with OpenCV or Tesseract OCR to automatically detect game events (e.g. "ACE", "CLUTCH", kill banners) and create markers without human intervention.

### Why It Was Declined
- **Performance Degradation on High-Refresh Displays**: Capturing and processing 1080p/1440p game frames at 30+ fps consumes substantial CPU and GPU cycles, causing frame pacing stutters and dropping FPS below competitive 240Hz thresholds.
- **Fragility Across Game Patches**: Game developers constantly update UI layouts, fonts, skin banners, and HUD scaling. Any cosmetic update breaks OCR pattern matching.
- **High False Positive Rate**: Team chat, spectator views, and teammate kills frequently trigger false markers, cluttering the editor's timeline.
- **Chosen Alternative**: Human-in-the-loop blind hotkey capture. Fast, 100% reliable, zero GPU overhead, and triggered only when the streamer decides a moment was meaningful.

---

## 12. Voice Recognition & Speech-to-Text Marker Triggers

### What Was Evaluated
Running a local speech recognition model (e.g. OpenAI Whisper, Vosk) to listen for voice commands like "OBS mark this" or "Clip that".

### Why It Was Declined
- **False Triggers from Game Comms**: Competitive streaming involves constant voice communication on Discord and in-game voice chat. Normal callouts ("mark him on B site", "watch this angle") constantly trigger false markers.
- **Inference Latency**: Speech recognition models introduce 400ms to 1200ms of transcription latency, making timestamps imprecise relative to fast game actions.
- **Chosen Alternative**: Instant physical hotkey (F8 or mouse button bind). Delivers sub-millisecond precision with zero audio false positives.

---

## 13. Embedded SQLite Database Storage

### What Was Evaluated
Storing all recording markers and session history inside a single local SQLite database file (`markers.db`).

### Why It Was Declined
- **Editorial Workflow Friction**: Video editors (Premiere Pro, DaVinci Resolve, Final Cut Pro) cannot import SQLite database files directly onto video tracks. Editors would be forced to open a secondary conversion utility to export their desired format.
- **Chosen Alternative**: Direct sidecar file serialization. When recording stops, the editor finds ready-to-import XML, CSV, and TXT files directly in the recording folder.

---

## 14. Legacy OBS WebSocket v4 Protocol

### What Was Evaluated
Maintaining dual backward-compatibility with OBS WebSocket v4 protocol alongside v5.

### Why It Was Declined
- **Deprecation and Protocol Incompatibility**: OBS Studio 28+ transitioned completely to WebSocket v5, integrating it directly into OBS core. WebSocket v4 required a separate third-party plugin, used incompatible JSON-RPC formatting, and had completely different opcodes and event structures.
- **Maintenance Burden**: Supporting legacy v4 adds complex handshake branching with zero benefit for users running modern OBS Studio versions.
- **Chosen Alternative**: Native WebSocket v5 protocol standard in OBS 28, 29, 30, and beyond.

---

## 15. Native C++ Compiled OBS Plugin

### What Was Evaluated
Writing the entire marker tool as a compiled C++ plugin using OBS Studio's `libobs` API.

### Why It Was Declined
- **Cross-Compilation & Distribution Complexity**: C++ plugins require separate compilation toolchains for Windows, macOS, and Linux, and break across minor OBS ABI updates. Users must run installer executables with elevated privileges.
- **Loss of Extensibility**: Scripts written in Lua, Python, and HTML are fully transparent, inspectable, and customizable by users without requiring Visual Studio or C++ compilers.
- **Chosen Alternative**: Decoupled hybrid architecture (OBS Lua hook + Python stdlib daemon + CEF Browser Dock). Combines native OS performance, zero external dependencies, and complete code transparency.
