"""
Synchronize docs/wiki/ markdown files directly to GitHub's Wiki repository.
Reads credentials from Windows Credential Manager and pushes to obs-marker-tool.wiki.git.
"""
import ctypes
from ctypes import wintypes
import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
DOCS_WIKI_DIR = REPO_ROOT / "docs" / "wiki"
GIT_EXE = r"C:\Users\mudxiej\AppData\Local\GitHubDesktop\app-3.6.6\resources\app\git\cmd\git.exe"

class CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR)
    ]

def get_github_token():
    target = "GitHub - https://api.github.com/Mudxiej"
    pcred = ctypes.POINTER(CREDENTIAL)()
    res = ctypes.windll.advapi32.CredReadW(target, 1, 0, ctypes.byref(pcred))
    if not res:
        raise RuntimeError("Failed to read GitHub token from Windows Credential Manager")
    token = ctypes.string_at(pcred.contents.CredentialBlob, pcred.contents.CredentialBlobSize).decode("utf-8")
    username = pcred.contents.UserName
    ctypes.windll.advapi32.CredFree(pcred)
    return username, token

def sync_wiki():
    if not DOCS_WIKI_DIR.exists():
        print(f"Error: {DOCS_WIKI_DIR} does not exist.")
        return False

    username, token = get_github_token()
    wiki_url = f"https://{username}:{token}@github.com/{username}/obs-marker-tool.wiki.git"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        print(f"[*] Copying wiki files from {DOCS_WIKI_DIR} to temp git directory...")
        for item in DOCS_WIKI_DIR.iterdir():
            if item.is_file():
                shutil.copy2(item, tmp_path / item.name)

        print("[*] Initializing local git repository...")
        subprocess.run([GIT_EXE, "init", "-b", "master"], cwd=tmp_path, check=True)
        subprocess.run([GIT_EXE, "config", "user.name", username], cwd=tmp_path, check=True)
        subprocess.run([GIT_EXE, "config", "user.email", "oskar@mudziejewski.pl"], cwd=tmp_path, check=True)
        subprocess.run([GIT_EXE, "add", "-A"], cwd=tmp_path, check=True)
        subprocess.run([GIT_EXE, "commit", "-m", "docs: update wiki documentation"], cwd=tmp_path, check=True)

        print("[*] Attempting push to GitHub Wiki remote...")
        res = subprocess.run([GIT_EXE, "push", "--force", wiki_url, "master"], cwd=tmp_path, capture_output=True, text=True)
        if res.returncode == 0:
            print("[SUCCESS] Wiki pages synchronized successfully to GitHub Wiki!")
            return True
        else:
            print("[NOTICE] GitHub Wiki repository not yet allocated by GitHub:")
            sanitized_err = res.stderr.replace(token, "***").strip()
            print(sanitized_err)
            print("\nNote: GitHub requires clicking 'Create the first page' once in the web UI")
            print("at https://github.com/Mudxiej/obs-marker-tool/wiki before the git backend is initialized.")
            print("Once clicked, running this script pushes all docs/wiki/ pages automatically.")
            return False

if __name__ == "__main__":
    success = sync_wiki()
    sys.exit(0 if success else 1)
