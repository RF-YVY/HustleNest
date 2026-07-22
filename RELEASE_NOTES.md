# HustleNest v4.2.1

**Release date:** July 22, 2026

HustleNest v4.2.1 is a lifecycle maintenance release for the Windows application.

## Highlights

- Closing the final HustleNest browser workspace now shuts down the local Python backend and embedded web server.
- The launcher cleans up its Node.js child process before exiting, preventing HustleNest from remaining in Windows Processes.
- Ordinary browser refreshes and multiple open HustleNest tabs are handled without prematurely stopping the application.
- A heartbeat fallback closes orphaned processes after an abrupt browser termination.

## Fixes

- Fixed the packaged launcher continuing to run after its browser window was closed.
- Fixed the command prompt and embedded web-server process remaining alive after the user finished using HustleNest.

## Install or upgrade

1. Download `HustleNestSetup.exe` from this release.
2. Run the installer and follow the prompts.
3. Launch HustleNest from the Start menu or desktop shortcut.

Existing databases and saved preferences remain in `%LOCALAPPDATA%\HustleNest`. Backing up before a major-version upgrade is recommended.

**System requirements:** 64-bit Windows 10 or later, 4 GB RAM minimum, and a modern browser. The installer includes the browser runtime needed by HustleNest.

## Installer verification

`HustleNestSetup.exe` SHA-256: `DAA567006F9A12713DECDB2A9FD9A4512462E3FFD47965FE98C42BAF3558C3B2`
