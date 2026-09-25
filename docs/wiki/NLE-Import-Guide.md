# NLE Import Guide

Step-by-step instructions for importing OBS Marker Tool files into Adobe Premiere Pro, Apple Final Cut Pro, DaVinci Resolve, and YouTube Chapters.

---

## 1. Export Files Overview

Every marker session generates four simultaneous export files located in `Markers_YYYY-MM-DD_HH-MM-SS`:

| File Name | Primary Compatibility | Format Specification |
| :--- | :--- | :--- |
| `premiere_sequence.xml` | Adobe Premiere Pro, DaVinci Resolve, Avid | FCP 7 XML Interchange format (`<xmeml version="5">`). Automatically builds a 60fps sequence populated with native timeline markers. |
| `final_cut_pro.fcpxml` | Apple Final Cut Pro X, DaVinci Resolve | Final Cut Pro XML format (`<fcpxml version="1.9">`). Generates an event and project with exact frame-accurate markers. |
| `markers.csv` | DaVinci Resolve, Adobe Premiere Pro | Comma-separated marker list (`Marker Name`, `Description`, `In`, `Out`, `Duration`) with RFC 4180 quotes. |
| `markers.txt` | YouTube Video Descriptions, Markdown Notes | Human-readable timestamp list with an auto-prepended `00:00:00 - Intro` anchor conforming to YouTube chapter requirements. |

---

## 2. Adobe Premiere Pro Workflow

### Method A: Importing `premiere_sequence.xml` (Recommended)
1. In Premiere Pro, open your project.
2. Select **File** -> **Import...** (or press `Ctrl + I`).
3. Navigate to the marker folder and select `premiere_sequence.xml`.
4. Premiere creates a new sequence named `Markers_YYYY-MM-DD_HH-MM-SS` in your Project bin.
5. Double-click the sequence to open it in the Timeline panel. All markers appear directly on the sequence ruler with their names and timecodes.
6. Drag your recorded OBS video file into track `V1` and align it to the start of the sequence (`00:00:00:00`). Every highlight marker is now aligned with your footage.

### Method B: Importing `markers.csv` onto an Existing Timeline
1. Open your existing sequence in Premiere Pro.
2. Go to **File** -> **Import...** and select `markers.csv`.
3. In the Project panel, right-click the imported CSV file and select **Create Sequence from Clip**, or drag markers into the timeline.

---

## 3. Apple Final Cut Pro Workflow

### Importing `final_cut_pro.fcpxml`
1. Open Apple Final Cut Pro.
2. Go to **File** -> **Import** -> **XML...**.
3. Select `final_cut_pro.fcpxml` from the marker directory.
4. Final Cut Pro automatically creates a new Event and Project containing a gap clip populated with chapter markers and to-do notes.
5. Drop your video recording onto the timeline below or above the gap clip. Markers snap directly to the corresponding video frames.

---

## 4. DaVinci Resolve Workflow

### Method A: Importing via FCPXML
1. Open your project in DaVinci Resolve.
2. Go to **File** -> **Import Timeline** -> **Import XML...** (or press `Ctrl + Shift + I`).
3. Select `final_cut_pro.fcpxml` (or `premiere_sequence.xml`).
4. In the import settings dialog:
   - Ensure the timeline frame rate matches your recording (default: `60 fps`).
   - Uncheck "Automatically import source clips into media pool" if your media is already loaded.
5. Click **OK**. Resolve constructs a timeline with all markers preserved.

### Method B: Importing via `markers.csv`
1. Create or open your sequence in the **Edit** page.
2. In the Media Pool or Edit Timeline, right-click the timeline entry and choose **Timelines** -> **Import** -> **Timeline Markers from CSV...**.
3. Select `markers.csv`.
4. Resolve populates colored markers directly across the active timeline ruler.

---

## 5. YouTube Chapters Workflow

YouTube automatically converts timestamps in video descriptions into scrubbable player chapters when specific rules are met:
- The first chapter must start at exactly `00:00:00`.
- The description must contain at least 3 chapters in ascending order.
- Each chapter must be at least 10 seconds long.

### How to Apply
1. Open `markers.txt` in any text editor.
2. Copy the formatted list:
   ```text
   00:00:00 - Intro
   00:03:15 - Ace Round 4
   00:08:42 - 1v3 Clutch
   00:14:20 - Outro
   ```
3. Paste directly into your YouTube video description.
4. Save the video details. YouTube activates interactive timeline chapters immediately.

---

## 6. Troubleshooting & Alignment Tips

### Timecode Drift / Frame Rate Mismatches
- OBS Studio typically records at 60.00 fps or 59.94 fps (NTSC).
- `server.py` calculates frame positions using integer 60fps timebase (`frame_in = int(total_seconds * 60)`).
- If your NLE project is set to 24fps or 29.97fps, ensure you match your sequence frame rate to 60fps before importing the XML to prevent fractional frame drift over multi-hour recordings.

### Accidental Marker Rollback
- If an accidental keypress occurs, tap the Red Undo button in the dock within 5 seconds.
- Undoing the last marker immediately removes its record from all 4 files. If zero markers remain, the folder is completely purged from disk.
