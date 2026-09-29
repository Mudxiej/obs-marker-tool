import os
import sys

# Windows pythonw / silent process protection: stdout and stderr may be None
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import json
import time
import gc
import stat
import threading
from datetime import datetime
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from xml.sax.saxutils import escape as xml_escape
import urllib.parse
import shutil
import subprocess
import tempfile

PORT = 8765
SCRIPT_DIR = Path(__file__).parent.resolve()


def _resolve_desktop_dir():
    home = Path(os.path.expanduser("~"))
    candidates = [
        home / "Desktop",
        home / "OneDrive" / "Desktop",
        home / "Videos",
        home,
    ]
    for c in candidates:
        try:
            if c.is_dir():
                return c
        except Exception:
            continue
    return home


DESKTOP_DIR = _resolve_desktop_dir()
CONFIG_FILE = SCRIPT_DIR / "config.json"
FLAG_FILE = SCRIPT_DIR / "freeze_trigger.flag"


def valid_fps(num, den):
    """Validate an OBS fps ratio (e.g. 60/1, 60000/1001).

    OBS reports NTSC rates as full ratios, so the numerator alone can be
    60000. Validate the calculated rate instead of the raw numerator.
    """
    try:
        num_i, den_i = int(num), int(den)
    except Exception:
        return False
    if not (1 <= den_i <= 10000 and num_i >= 1):
        return False
    try:
        fps = num_i / den_i
    except Exception:
        return False
    return 1 <= fps <= 240


def atomic_write_text(path, content):
    """Crash-safe write: temp file in same dir + fsync + os.replace.

    Keeps the previous good file if the process dies mid-write.
    Same filesystem is guaranteed because tmp lives next to target.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(target.parent), prefix=target.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        # Windows: Search indexer / AV can briefly lock the .tmp on close.
        # Retry the rename a few times before giving up.
        last_err = None
        for attempt in range(3):
            try:
                os.replace(tmp_name, target)
                last_err = None
                break
            except PermissionError as e:
                last_err = e
                time.sleep(0.025)
            except OSError as e:
                # WinError 32/5 surface as PermissionError on py3.8+,
                # but be tolerant of any transient lock error.
                last_err = e
                time.sleep(0.025)
        if last_err is not None:
            raise last_err
        try:
            # Sync directory entry so the rename survives power loss
            dir_fd = os.open(str(target.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except Exception:
            pass
    except Exception:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except Exception:
            pass
        raise

class MarkerSession:
    def __init__(self):
        self.session_id = None
        self.files_created = False
        self.folder_path = None
        self.txt_path = None
        self.csv_path = None
        self.xml_path = None
        self.fcpxml_path = None
        self.json_path = None
        self.markers = []
        self.recording_dir = None
        self.custom_output_dir = None
        self.last_freeze_time = 0.0
        self.fps_num = 60
        self.fps_den = 1
        self.paused = False
        self.folder_naming = "timestamp"
        self.recording_filename = None
        self.load_config()

    def load_config(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    val = data.get("custom_output_dir", "")
                    self.custom_output_dir = val.strip() if val and val.strip() else None
                    try:
                        num = int(data.get("fps_num", 60))
                        den = int(data.get("fps_den", 1))
                        if valid_fps(num, den):
                            self.fps_num, self.fps_den = num, den
                    except Exception:
                        pass
                    naming = data.get("folder_naming", "timestamp")
                    if isinstance(naming, str) and naming.strip().lower() == "video":
                        self.folder_naming = "video"
                    else:
                        self.folder_naming = "timestamp"
            except Exception:
                pass

    def save_config(self):
        try:
            data = {}
            if CONFIG_FILE.exists():
                try:
                    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if not isinstance(data, dict):
                            data = {}
                except Exception:
                    data = {}
            data["custom_output_dir"] = self.custom_output_dir or ""
            data["fps_num"] = self.fps_num
            data["fps_den"] = self.fps_den
            data["folder_naming"] = self.folder_naming or "timestamp"
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    @staticmethod
    def sanitize_stem(stem):
        """Sanitize a video basename for use in a folder name.

        Strips directories, extension must already be removed by caller,
        removes illegal Windows chars, trims trailing dots/spaces, caps length.
        Returns "" if nothing usable remains (caller falls back to timestamp).
        """
        try:
            s = (stem or "").strip()
            # Drop any directory components that slipped in
            s = s.replace("/", "\\").split("\\")[-1]
            for ch in '<>:"|?*':
                s = s.replace(ch, "")
            s = s.strip().rstrip(". ")
            if len(s) > 80:
                s = s[:80].rstrip(". ")
            return s
        except Exception:
            return ""

    def get_fps_float(self):
        try:
            return self.fps_num / self.fps_den
        except Exception:
            return 60.0

    def get_timebase(self):
        return int(round(self.get_fps_float()))

    def is_ntsc(self):
        # NTSC drop-frame family uses 1001 denominator (60000/1001, 30000/1001)
        return self.fps_den == 1001

    def get_base_dir(self):
        self.load_config()
        # 1. Custom directory takes highest precedence if set
        if self.custom_output_dir:
            try:
                p = Path(self.custom_output_dir)
                if p.exists() or p.parent.exists():
                    return p
            except Exception:
                pass

        # 2. Recording directory (same as OBS recordings) is the default target
        if self.recording_dir:
            try:
                p = Path(self.recording_dir)
                if p.is_dir():
                    return p
            except Exception:
                pass

        # 3. Fallback to Desktop
        return DESKTOP_DIR

    def check_freeze_flag(self):
        if FLAG_FILE.exists():
            try:
                self.last_freeze_time = time.time()
                FLAG_FILE.unlink(missing_ok=True)
            except Exception:
                pass

    def start_new_session_if_needed(self):
        if not self.session_id:
            now_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.session_id = now_str
            folder_name = f"Markers_{now_str}"
            base_dir = self.get_base_dir()
            # Avoid folder collision when two sessions start within the same second
            candidate = base_dir / folder_name
            suffix = 1
            while candidate.exists():
                suffix += 1
                candidate = base_dir / f"{folder_name}_{suffix}"
                if suffix > 100:
                    break
            self.folder_path = candidate
            self.txt_path = self.folder_path / "markers.txt"
            self.csv_path = self.folder_path / "markers.csv"
            self.xml_path = self.folder_path / "premiere_sequence.xml"
            self.fcpxml_path = self.folder_path / "final_cut_pro.fcpxml"
            self.json_path = self.folder_path / "markers.json"
            self.files_created = False
            self.markers = []

    @staticmethod
    def parse_timecode(timecode, fps=60.0):
        """Parse HH:MM:SS[.ms], MM:SS[.ms], SS[.ms] and HH:MM:SS:FF.

        Returns (total_seconds: float, frame_in: int at given fps).
        Raises ValueError on unparseable input.
        """
        try:
            fps_f = float(fps)
            if not (1 <= fps_f <= 240):
                fps_f = 60.0
        except Exception:
            fps_f = 60.0
        tc = (timecode or "").strip()
        if not tc:
            raise ValueError("empty timecode")
        parts = tc.split(":")
        if len(parts) == 4:
            # HH:MM:SS:FF — frames at given fps
            h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
            f = int(float(parts[3]))
            total_seconds = h * 3600 + m * 60 + s + f / fps_f
        elif len(parts) == 3:
            h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
            total_seconds = h * 3600 + m * 60 + s
        elif len(parts) == 2:
            h, m, s = 0, int(parts[0]), float(parts[1])
            total_seconds = h * 3600 + m * 60 + s
        elif len(parts) == 1:
            total_seconds = float(parts[0])
        else:
            raise ValueError(f"unsupported timecode: {timecode!r}")
        frame_in = int(round(total_seconds * fps_f))
        return total_seconds, frame_in

    def add_marker(self, timecode, name, paused=False):
        self.start_new_session_if_needed()
        display_name = name.strip() if name and name.strip() else f"Marker {len(self.markers) + 1}"

        try:
            total_seconds, frame_in = self.parse_timecode(timecode, self.get_fps_float())
        except Exception:
            total_seconds = 0
            frame_in = 0

        marker_entry = {
            "id": len(self.markers) + 1,
            "timecode": timecode,
            "seconds": total_seconds,
            "name": display_name,
            "frame_in": frame_in,
            "paused": bool(paused),
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        self.markers.append(marker_entry)
        self.flush_files()
        return marker_entry

    def undo_last_marker(self):
        if not self.markers:
            return None
        removed = self.markers.pop()
        if len(self.markers) > 0:
            self.flush_files()
        else:
            self.cleanup_session_files()
        return removed

    def flush_files(self):
        if not self.folder_path.exists():
            self.folder_path.mkdir(parents=True, exist_ok=True)

        fps_f = self.get_fps_float()
        timebase = self.get_timebase()
        ntsc_str = "TRUE" if self.is_ntsc() else "FALSE"

        # 1. Human TXT Export (YouTube Chapters compliant: auto-prepends 00:00:00 - Intro)
        txt_content = [
            f"# OBS Recording Markers - {self.session_id}",
            ""
        ]
        if self.markers:
            if self.markers[0].get("seconds", 0) > 0:
                txt_content.append("00:00:00 - Intro")
            for m in self.markers:
                txt_content.append(f"{m['timecode']} - {m['name']}")

        atomic_write_text(self.txt_path, "\n".join(txt_content) + "\n")

        # 2. Premiere Pro CSV Export (HH:MM:SS:FF at detected fps)
        # Derived from stored total frames so sub-second fractions roll over
        # correctly (00:01:23.999 @60fps -> 00:01:24:00, not 00:01:23:00).
        csv_rows = ["Marker Name,Description,In,Out,Duration"]
        tb = max(timebase, 1)
        for m in self.markers:
            try:
                total_frames = int(m.get("frame_in", 0))
                ff = total_frames % tb
                total_sec = total_frames // tb
                ss = total_sec % 60
                mm = (total_sec // 60) % 60
                hh = total_sec // 3600
                tc_frames = f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"
            except Exception:
                tc_frames = "00:00:00:00"
            safe_name = m['name'].replace('"', '""')
            csv_rows.append(f'"{safe_name}","{safe_name}",{tc_frames},{tc_frames},00:00:00:00')

        atomic_write_text(self.csv_path, "\n".join(csv_rows) + "\n")

        # 3. Premiere Pro / FCP 7 Sequence XML Export
        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE xmeml>',
            '<xmeml version="5">',
            '  <sequence>',
            f'    <name>Markers_{self.session_id}</name>',
            '    <rate>',
            f'      <timebase>{timebase}</timebase>',
            f'      <ntsc>{ntsc_str}</ntsc>',
            '    </rate>',
            '    <media>',
            '      <video>',
            '        <track>'
        ]

        for m in self.markers:
            safe_name = xml_escape(m["name"])
            safe_tc = xml_escape(m["timecode"])
            xml_lines.extend([
                '          <marker>',
                f'            <name>{safe_name}</name>',
                f'            <comment>{safe_tc}</comment>',
                f'            <in>{m["frame_in"]}</in>',
                f'            <out>{m["frame_in"]}</out>',
                '          </marker>'
            ])

        xml_lines.extend([
            '        </track>',
            '      </video>',
            '    </media>',
            '  </sequence>',
            '</xmeml>'
        ])

        atomic_write_text(self.xml_path, "\n".join(xml_lines) + "\n")

        # 4. Final Cut Pro FCPXML Export
        # All time values use the format's rational timescale (num/den) so
        # every start/duration is an exact multiple of frameDuration
        # (FCPXML DTD v1.9 frame-boundary rule). E.g. 59.94fps marker 3596
        # becomes 3596*1001/60000s, not 3596/60s.
        fps_label = f"{fps_f:.2f}".rstrip("0").rstrip(".")
        fcpxml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE fcpxml>',
            '<fcpxml version="1.9">',
            '  <resources>',
            f'    <format id="r1" name="FFVideoFormat{fps_label}p" frameDuration="{self.fps_den}/{self.fps_num}s" width="1920" height="1080"/>',
            '  </resources>',
            '  <library>',
            f'    <event name="Event_{self.session_id}">',
            f'      <project name="Markers_{self.session_id}">',
            '        <sequence format="r1">',
            '          <spine>'
        ]

        max_sec = max([m['seconds'] for m in self.markers], default=60) + 10
        total_fcpxml_frames = int(round(max_sec * fps_f))

        fcpxml_lines.extend([
            f'            <gap name="Timeline" offset="0s" duration="{total_fcpxml_frames * self.fps_den}/{self.fps_num}s" start="0s">'
        ])

        for m in self.markers:
            safe_attr = xml_escape(m["name"], {'"': '&quot;'})
            fcpxml_lines.append(
                f'              <marker start="{m["frame_in"] * self.fps_den}/{self.fps_num}s" duration="{self.fps_den}/{self.fps_num}s" value="{safe_attr}"/>'
            )

        fcpxml_lines.extend([
            '            </gap>',
            '          </spine>',
            '        </sequence>',
            '      </project>',
            '    </event>',
            '  </library>',
            '</fcpxml>'
        ])

        atomic_write_text(self.fcpxml_path, "\n".join(fcpxml_lines) + "\n")

        # 5. Programmatic JSON timeline export (MoviePy / Resolve API / bots).
        # name + label aliases plus stable id so consumers don't care which
        # key they look up. ensure_ascii=False keeps i18n/emoji readable.
        json_markers = []
        for i, m in enumerate(self.markers):
            json_markers.append({
                "id": m.get("id", i + 1),
                "timecode": m.get("timecode"),
                "seconds": m.get("seconds"),
                "frame": m.get("frame_in"),
                "name": m.get("name"),
                "label": m.get("name"),
                "paused": bool(m.get("paused", False)),
            })
        json_doc = {
            "recording_session": self.session_id,
            "fps": fps_f,
            "fps_num": self.fps_num,
            "fps_den": self.fps_den,
            "markers": json_markers,
        }
        atomic_write_text(self.json_path, json.dumps(json_doc, indent=2, ensure_ascii=False) + "\n")

        self.files_created = True

    def cleanup_session_files(self):
        """Completely delete the 5 export files and the session folder."""
        folder = self.folder_path
        files_to_remove = [self.txt_path, self.csv_path, self.xml_path, self.fcpxml_path, self.json_path]

        # Force Python garbage collection to release any latent Windows file handles
        gc.collect()

        # 1. Unlink specific marker files with permission overrides
        for file_path in files_to_remove:
            if file_path:
                p = Path(file_path)
                for _ in range(8):
                    if not p.exists():
                        break
                    try:
                        p.chmod(stat.S_IWRITE | stat.S_IREAD)
                        p.unlink(missing_ok=True)
                        break
                    except Exception:
                        time.sleep(0.05)

        # 2. Forcefully clean any remaining files in the session folder
        if folder and folder.exists():
            for _ in range(8):
                try:
                    for child in folder.glob("*"):
                        try:
                            child.chmod(stat.S_IWRITE | stat.S_IREAD)
                            if child.is_file():
                                child.unlink(missing_ok=True)
                            elif child.is_dir():
                                shutil.rmtree(child, ignore_errors=True)
                        except Exception:
                            pass
                    folder.rmdir()
                    break
                except Exception:
                    time.sleep(0.05)

            # 3. Fallback shutil.rmtree if directory still exists
            if folder.exists():
                def _handle_remove_readonly(func, path, exc_info):
                    try:
                        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                        func(path)
                    except Exception:
                        pass
                for _ in range(5):
                    try:
                        shutil.rmtree(folder, onerror=_handle_remove_readonly)
                        if not folder.exists():
                            break
                    except Exception:
                        pass
                    time.sleep(0.05)

            # 4. Decisive Windows command fallback if folder somehow still exists
            if folder.exists():
                try:
                    subprocess.run(["cmd.exe", "/c", "rmdir", "/s", "/q", str(folder)], capture_output=True, timeout=3)
                except Exception:
                    pass

        # 5. Completely reset session state
        self.reset_session()

    def reset_session(self):
        if self.folder_path and self.folder_path.exists() and len(self.markers) == 0:
            try:
                self.folder_path.rmdir()
            except Exception:
                try:
                    subprocess.run(["cmd.exe", "/c", "rmdir", "/s", "/q", str(self.folder_path)], capture_output=True, timeout=3)
                except Exception:
                    pass
        self.session_id = None
        self.files_created = False
        self.folder_path = None
        self.txt_path = None
        self.csv_path = None
        self.xml_path = None
        self.fcpxml_path = None
        self.json_path = None
        self.markers = []
        self.paused = False
        self.recording_filename = None

    def finalize_session(self, output_path):
        """Rename the timestamp folder to a video-stem folder on recording stop.

        Active sessions always write to Markers_<timestamp>/ so a mid-stream
        crash loses nothing. When OBS reports outputPath on STOPPED and
        folder_naming == "video", rename to Markers_<stem> with collision
        suffix. Failures keep the timestamp folder intact.
        Returns (renamed: bool, folder: str|None, reason: str).
        """
        self.load_config()
        if self.folder_naming != "video":
            return False, str(self.folder_path) if self.folder_path else None, "timestamp mode"
        if not self.folder_path or not self.folder_path.exists():
            return False, None, "no session folder"
        try:
            base = (output_path or "").replace("/", "\\").split("\\")[-1].strip()
        except Exception:
            base = ""
        if not base:
            return False, str(self.folder_path), "empty output path"
        stem = base
        if "." in base:
            stem = base.rsplit(".", 1)[0]
        stem = self.sanitize_stem(stem)
        if not stem:
            return False, str(self.folder_path), "unusable stem"
        self.recording_filename = base
        target = self.folder_path.parent / f"Markers_{stem}"
        if target.resolve() == self.folder_path.resolve():
            return False, str(self.folder_path), "already named"
        suffix = 1
        candidate = target
        while candidate.exists():
            suffix += 1
            candidate = self.folder_path.parent / f"Markers_{stem}_{suffix}"
            if suffix > 100:
                return False, str(self.folder_path), "collision overflow"
        for attempt in range(3):
            try:
                os.rename(str(self.folder_path), str(candidate))
                break
            except PermissionError:
                time.sleep(0.05)
            except OSError:
                time.sleep(0.05)
        else:
            return False, str(self.folder_path), "rename failed"
        if not candidate.exists():
            return False, str(self.folder_path), "rename failed"
        self.folder_path = candidate
        self.txt_path = candidate / "markers.txt"
        self.csv_path = candidate / "markers.csv"
        self.xml_path = candidate / "premiere_sequence.xml"
        self.fcpxml_path = candidate / "final_cut_pro.fcpxml"
        self.json_path = candidate / "markers.json"
        return True, str(candidate), "renamed"

session = MarkerSession()

def flag_watcher():
    """High-frequency watcher for Lua hotkey trigger flag."""
    while True:
        try:
            if FLAG_FILE.exists():
                session.last_freeze_time = time.time()
                try:
                    FLAG_FILE.unlink(missing_ok=True)
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(0.04)

threading.Thread(target=flag_watcher, daemon=True).start()

class RequestHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, content, status=200):
        if isinstance(content, str):
            content = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        session.check_freeze_flag()
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ["/", "/index.html"]:
            index_file = Path(__file__).parent / "index.html"
            if index_file.exists():
                with open(index_file, "rb") as f:
                    content = f.read()
                self.send_html(content)
            else:
                self.send_error(404, "index.html not found")
        elif parsed.path == "/api/status":
            data = {
                "active_session": session.session_id,
                "markers_count": len(session.markers),
                "files_created": session.files_created,
                "folder": str(session.folder_path) if session.folder_path else None,
                "base_dir": str(session.get_base_dir()),
                "recording_dir": str(session.recording_dir) if session.recording_dir else None,
                "custom_output_dir": str(session.custom_output_dir) if session.custom_output_dir else None,
                "freeze_event": session.last_freeze_time,
                "fps_num": session.fps_num,
                "fps_den": session.fps_den,
                "fps": session.get_fps_float(),
                "paused": session.paused,
                "folder_naming": session.folder_naming,
                "recording_filename": session.recording_filename
            }
            self.send_json(data)
        elif parsed.path == "/api/config":
            self.send_json({
                "custom_output_dir": session.custom_output_dir,
                "recording_dir": session.recording_dir,
                "base_dir": str(session.get_base_dir()),
                "fps_num": session.fps_num,
                "fps_den": session.fps_den,
                "fps": session.get_fps_float(),
                "paused": session.paused,
                "folder_naming": session.folder_naming,
                "recording_filename": session.recording_filename
            })
        elif parsed.path == "/api/open_folder":
            target = session.folder_path if (session.folder_path and session.folder_path.exists()) else session.get_base_dir()
            try:
                target.mkdir(parents=True, exist_ok=True)
                os.startfile(str(target))
                self.send_json({"success": True, "opened": str(target)})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, status=500)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        if parsed.path == "/api/save_marker":
            try:
                payload = json.loads(body.decode("utf-8"))
                timecode = payload.get("timecode", "00:00:00")
                name = payload.get("name", "")
                paused = payload.get("paused", session.paused)
                marker = session.add_marker(timecode, name, paused=bool(paused))
                self.send_json({
                    "success": True, 
                    "marker": marker,
                    "count": len(session.markers),
                    "folder": str(session.folder_path)
                })
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, status=500)

        elif parsed.path == "/api/undo_marker":
            try:
                removed = session.undo_last_marker()
                self.send_json({
                    "success": True, 
                    "removed": removed,
                    "count": len(session.markers)
                })
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, status=500)

        elif parsed.path == "/api/reset_session":
            session.reset_session()
            self.send_json({"success": True})

        elif parsed.path == "/api/freeze":
            session.last_freeze_time = time.time()
            self.send_json({"success": True, "freeze_time": session.last_freeze_time})

        elif parsed.path == "/api/config":
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
                if "recording_dir" in payload:
                    rec = payload["recording_dir"]
                    if isinstance(rec, str):
                        rec = rec.strip()
                        session.recording_dir = rec if rec else None
                    elif rec is None:
                        session.recording_dir = None
                if "custom_output_dir" in payload:
                    raw = payload["custom_output_dir"]
                    val = raw.strip() if isinstance(raw, str) else ""
                    session.custom_output_dir = val if val else None
                    session.save_config()
                if "fps_num" in payload or "fps_den" in payload:
                    try:
                        num = int(payload.get("fps_num", session.fps_num))
                        den = int(payload.get("fps_den", session.fps_den))
                        if valid_fps(num, den):
                            session.fps_num, session.fps_den = num, den
                            session.save_config()
                    except Exception:
                        pass
                if "paused" in payload:
                    session.paused = bool(payload["paused"])
                if "folder_naming" in payload:
                    naming = payload["folder_naming"]
                    session.folder_naming = "video" if isinstance(naming, str) and naming.strip().lower() == "video" else "timestamp"
                    session.save_config()
                if "recording_filename" in payload:
                    rec_fn = payload["recording_filename"]
                    if rec_fn is None:
                        session.recording_filename = None
                    elif isinstance(rec_fn, str):
                        rec_fn = rec_fn.replace("/", "\\").split("\\")[-1].strip()
                        session.recording_filename = rec_fn[:120] if rec_fn else None
                self.send_json({
                    "success": True,
                    "recording_dir": session.recording_dir,
                    "custom_output_dir": session.custom_output_dir,
                    "base_dir": str(session.get_base_dir()),
                    "fps_num": session.fps_num,
                    "fps_den": session.fps_den,
                    "fps": session.get_fps_float(),
                    "paused": session.paused,
                    "folder_naming": session.folder_naming,
                    "recording_filename": session.recording_filename
                })
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, status=500)

        elif parsed.path == "/api/finalize_session":
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
                output_path = payload.get("output_path", "")
                if not isinstance(output_path, str):
                    output_path = ""
                renamed, folder, reason = session.finalize_session(output_path)
                self.send_json({
                    "success": True,
                    "renamed": renamed,
                    "folder": folder,
                    "reason": reason,
                    "markers_count": len(session.markers)
                })
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, status=500)

        elif parsed.path == "/api/open_folder":
            target = session.folder_path if (session.folder_path and session.folder_path.exists()) else session.get_base_dir()
            try:
                target.mkdir(parents=True, exist_ok=True)
                os.startfile(str(target))
                self.send_json({"success": True, "opened": str(target)})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, status=500)

        else:
            self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        return

    def log_error(self, format, *args):
        try:
            with open(SCRIPT_DIR / "crash.log", "a", encoding="utf-8") as f:
                f.write(f"[HTTP Error] {format % args}\n")
        except Exception:
            pass

class ResilientHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def handle_error(self, request, client_address):
        import traceback
        try:
            with open(SCRIPT_DIR / "crash.log", "a", encoding="utf-8") as f:
                f.write(f"[Server Error from {client_address}]:\n{traceback.format_exc()}\n")
        except Exception:
            pass

def run():
    server_address = ('127.0.0.1', PORT)
    httpd = None
    for _ in range(25):
        try:
            httpd = ResilientHTTPServer(server_address, RequestHandler)
            break
        except OSError:
            time.sleep(0.5)
    if not httpd:
        with open(SCRIPT_DIR / "crash.log", "a", encoding="utf-8") as f:
            f.write("Failed to bind port 8765 after 25 retries.\n")
        return
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    except Exception:
        import traceback
        try:
            with open(SCRIPT_DIR / "crash.log", "a", encoding="utf-8") as f:
                f.write(f"[serve_forever died]:\n{traceback.format_exc()}\n")
        except Exception:
            pass
    finally:
        try:
            httpd.server_close()
        except Exception:
            pass

if __name__ == "__main__":
    try:
        run()
    except Exception:
        import traceback
        try:
            with open(Path(__file__).parent / "crash.log", "a", encoding="utf-8") as f:
                f.write(traceback.format_exc() + "\n")
        except Exception:
            pass
