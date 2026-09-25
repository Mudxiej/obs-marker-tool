# OBS Marker Tool Documentation

Zero-overhead recording marker engine for OBS Studio. Enables instant mid-game timestamp capture, native timeline marker export for Adobe Premiere Pro, Apple Final Cut Pro, DaVinci Resolve, and automatic YouTube Chapters generation.

---

## Mission & Problem Statement

Live streaming and competitive gaming demand 100% focus. Taking hands off controls to note timestamps breaks match flow. Scrubbing through hours of raw gameplay recordings in post-production wastes editor hours.

OBS Marker Tool eliminates friction between capture and editing:
- **Blind Hotkey Capture**: Tap an OBS hotkey mid-fight. Timecode freezes instantly with peripheral sensory confirmation.
- **Direct NLE Import**: Generates native XML sequences and CSV files next to your recording. Drop directly onto video editor timelines with zero scrubbing.
- **Zero Window Clutter**: Lives inside OBS Studio as an ultra-compact dock. Zero third-party windows, zero system tray clutter.
- **Anti-Cheat Safe**: Uses OBS native Lua input handling. Zero dangerous OS-level global keyboard hooks that risk game bans in competitive titles like Valorant.

---

## Architecture at a Glance

The tool operates as a decoupled three-tier system:

| Layer | Component | Execution Model | Responsibility |
| :--- | :--- | :--- | :--- |
| **Presentation** | Custom Browser Dock (`src/index.html`) | OBS CEF (Chromium Embedded Framework) | Ultra-compact dock UI (22px row + 18px chips), WebSocket v5 timecode sync, preset management, undo triggers |
| **Native Integration** | Lua Service Hook (`src/marker_service.lua`) | OBS Lua Scripting Engine | Automatic daemon lifecycle management, native settings properties, anti-cheat safe hotkey registration |
| **Backend & Export** | HTTP Server Daemon (`src/server.py`) | Python Standard Library (`pythonw.exe`) | Lock-free file flag monitoring, REST API on `127.0.0.1:8765`, atomic 4-format file serialization, resilient folder purging |

---

## Documentation Index

Explore in-depth documentation across dedicated topics:

| Guide | Summary |
| :--- | :--- |
| [Architecture and Design Decisions](Architecture-and-Design-Decisions) | Deep technical breakdown of the 3-tier architecture, IPC mechanisms, ergonomics, and rationale behind core design choices. |
| [Declined Approaches and Post-Mortem](Declined-Approaches-and-Post-Mortem) | Exhaustive post-mortem of 15 failed, tested, and rejected architectures (anti-cheat keylogger hazards, heavy web frameworks, SRT hacks, in-game overlays, OCR). |
| [File Reference and API](File-Reference-and-API) | Line-by-line breakdown of every source file, REST API endpoints specification, configuration parameters, and component pros/cons. |
| [NLE Import Guide](NLE-Import-Guide) | Complete import workflows for Adobe Premiere Pro, Apple Final Cut Pro, DaVinci Resolve, and YouTube Chapters. |
| [Functionality Ideas and Roadmap](Functionality-Ideas-and-Roadmap) | Comprehensive analysis of future feature proposals, community requests, and architectural trade-offs with pros and cons. |

---

## Quick Reference Commands

- Default HTTP Server Address: `http://127.0.0.1:8765/`
- Default WebSocket Ports Checked: `4456`, `4455`
- Target Installation Path: `%APPDATA%\obs-studio\scripts\obs-marker-tool\`
- Default Marker Save Target: Same directory as active OBS recording (auto-discovered via WebSocket)
