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
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import shutil
import subprocess

PORT = 8765
SCRIPT_DIR = Path(__file__).parent.resolve()
DESKTOP_DIR = Path(os.path.expanduser("~")) / "Desktop"
CONFIG_FILE = SCRIPT_DIR / "config.json"
FLAG_FILE = SCRIPT_DIR / "freeze_trigger.flag"

class MarkerSession:
    def __init__(self):
        self.session_id = None
        self.files_created = False
        self.folder_path = None
        self.txt_path = None
        self.csv_path = None
        self.xml_path = None
        self.fcpxml_path = None
        self.markers = []
        self.recording_dir = None
        self.custom_output_dir = None
        self.last_freeze_time = 0.0
        self.load_config()

    def load_config(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    val = data.get("custom_output_dir", "")
                    self.custom_output_dir = val.strip() if val and val.strip() else None
            except Exception:
                pass

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
            self.folder_path = base_dir / folder_name
            self.txt_path = self.folder_path / "markers.txt"
            self.csv_path = self.folder_path / "markers.csv"
            self.xml_path = self.folder_path / "premiere_sequence.xml"
            self.fcpxml_path = self.folder_path / "final_cut_pro.fcpxml"
            self.files_created = False
            self.markers = []

    def add_marker(self, timecode, name):
        self.start_new_session_if_needed()
        display_name = name.strip() if name and name.strip() else f"Marker {len(self.markers) + 1}"

        try:
            parts = timecode.split(":")
            if len(parts) == 3:
                h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
            elif len(parts) == 2:
                h, m, s = 0, int(parts[0]), float(parts[1])
            else:
                h, m, s = 0, 0, float(parts[0])
            total_seconds = h * 3600 + m * 60 + s
            frame_in = int(total_seconds * 60)
        except Exception:
            total_seconds = 0
            frame_in = 0

        marker_entry = {
            "timecode": timecode,
            "seconds": total_seconds,
            "name": display_name,
            "frame_in": frame_in,
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

        with open(self.txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(txt_content) + "\n")

        # 2. Premiere Pro CSV Export
        csv_rows = ["Marker Name,Description,In,Out,Duration"]
        for m in self.markers:
            tc = m['timecode']
            if len(tc.split(":")) == 2:
                tc = "00:" + tc
            tc_frames = f"{tc}:00"
            safe_name = m['name'].replace('"', '""')
            csv_rows.append(f'"{safe_name}","{safe_name}",{tc_frames},{tc_frames},00:00:00:00')

        with open(self.csv_path, "w", encoding="utf-8") as f:
            f.write("\n".join(csv_rows) + "\n")

        # 3. Premiere Pro / FCP 7 Sequence XML Export
        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE xmeml>',
            '<xmeml version="5">',
            '  <sequence>',
            f'    <name>Markers_{self.session_id}</name>',
            '    <rate>',
            '      <timebase>60</timebase>',
            '      <ntsc>FALSE</ntsc>',
            '    </rate>',
            '    <media>',
            '      <video>',
            '        <track>'
        ]

        for m in self.markers:
            xml_lines.extend([
                '          <marker>',
                f'            <name>{m["name"]}</name>',
                f'            <comment>{m["timecode"]}</comment>',
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

        with open(self.xml_path, "w", encoding="utf-8") as f:
            f.write("\n".join(xml_lines) + "\n")

        # 4. Final Cut Pro FCPXML Export
        fcpxml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE fcpxml>',
            '<fcpxml version="1.9">',
            '  <resources>',
            '    <format id="r1" name="FFVideoFormat1080p60" frameDuration="1/60s" width="1920" height="1080"/>',
            '  </resources>',
            '  <library>',
            f'    <event name="Event_{self.session_id}">',
            f'      <project name="Markers_{self.session_id}">',
            '        <sequence format="r1">',
            '          <spine>'
        ]

        max_sec = max([m['seconds'] for m in self.markers], default=60) + 10
        total_fcpxml_frames = int(max_sec * 60)

        fcpxml_lines.extend([
            f'            <gap name="Timeline" offset="0s" duration="{total_fcpxml_frames}/60s" start="0s">'
        ])

        for m in self.markers:
            fcpxml_lines.append(
                f'              <marker start="{m["frame_in"]}/60s" duration="1/60s" value="{m["name"]}"/>'
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

        with open(self.fcpxml_path, "w", encoding="utf-8") as f:
            f.write("\n".join(fcpxml_lines) + "\n")

        self.files_created = True

    def cleanup_session_files(self):
        """Completely delete the 4 export files and the session folder."""
        folder = self.folder_path
        files_to_remove = [self.txt_path, self.csv_path, self.xml_path, self.fcpxml_path]

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
        self.markers = []

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
                "freeze_event": session.last_freeze_time
            }
            self.send_json(data)
        elif parsed.path == "/api/config":
            self.send_json({
                "custom_output_dir": session.custom_output_dir,
                "recording_dir": session.recording_dir,
                "base_dir": str(session.get_base_dir())
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
                marker = session.add_marker(timecode, name)
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
                if "recording_dir" in payload and payload["recording_dir"]:
                    session.recording_dir = payload["recording_dir"]
                if "custom_output_dir" in payload:
                    val = payload["custom_output_dir"].strip()
                    session.custom_output_dir = val if val else None
                    try:
                        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                            json.dump({"custom_output_dir": session.custom_output_dir or ""}, f)
                    except Exception:
                        pass
                self.send_json({
                    "success": True,
                    "recording_dir": session.recording_dir,
                    "custom_output_dir": session.custom_output_dir,
                    "base_dir": str(session.get_base_dir())
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

class ResilientHTTPServer(HTTPServer):
    allow_reuse_address = True

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
