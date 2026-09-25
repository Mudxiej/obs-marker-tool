## Description
<!-- Provide a brief, dense summary of the purpose of this PR and what problem it resolves. -->

## Changes Introduced
<!-- Bulleted list detailing every changed file and specific logic modified. -->
- 

## Components Modified
- [ ] `src/server.py` (HTTP daemon, file exports, session state, directory cleanup)
- [ ] `src/marker_service.lua` (OBS frontend scripting, hotkey registration, process hooks)
- [ ] `src/index.html` (OBS Custom Browser Dock UI, styles, WebSocket v5 client)
- [ ] `src/install.bat` / `src/run_silent.vbs` / scripts (Installation and process lifecycle)
- [ ] `docs/` / Wiki / Readme (Documentation and guides)

## Verification & Testing Performed
<!-- Describe the specific tests executed on your local machine. -->
- [ ] Tested live inside OBS Studio with active recording enabled
- [ ] Verified global hotkey trigger and Electric Cyan visual feedback
- [ ] Verified timeline marker import in target NLE (Premiere Pro / Resolve / Final Cut Pro)
- [ ] Verified atomic Undo rolls back markers and cleans up disk if count reaches 0
- [ ] Confirmed zero new external Python dependencies added (Python standard library only)
- [ ] Verified server cleanly terminates on OBS exit without orphaned `pythonw.exe` processes

## Related Issue(s)
<!-- Fixes #(issue_number) or Closes #(issue_number) -->
Fixes #
