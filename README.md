> The whole project was vibe coded with Cursor and Grok 4.7 xhigh.

# S3 Viewer

Beta **0.1.0**. This software is in development.

<p>
  <img alt="Beta 0.1.0" src="https://img.shields.io/badge/beta-0.1.0-f59e0b?style=for-the-badge">
  <img alt="In development" src="https://img.shields.io/badge/status-in%20development-eab308?style=for-the-badge">
  <img alt="Linux, macOS, and Windows" src="https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-0f766e?style=for-the-badge">
  <img alt="Python 3.12 or newer" src="https://img.shields.io/badge/Python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="German and English" src="https://img.shields.io/badge/languages-Deutsch%20%7C%20English-1f2937?style=for-the-badge">
  <img alt="MIT license" src="https://img.shields.io/badge/license-MIT-16a34a?style=for-the-badge">
</p>

A desktop app for browsing OpenStack and other S3 buckets. Open files, change them, and move them between your machine and the bucket.

<img src="misc/Forest%20segmentation%20storage%20and%20YAML%20preview.png" alt="Browsing a bucket and previewing a YAML file" width="100%">

<img src="misc/Dark%20and%20light%20mode%20comparison.png" alt="Dark and light mode" width="72%">

## Features

- 💾 Save connections
- 🗂️ Double-click through folders
- 🔎 Filter by name
- ✏️ Open and edit files right there — txt, yaml, xml, json, csv, and tiff
- ⬆️⬇️🗑️ Upload, download, and delete files and folders
- 🌙☀️ Light and dark mode

## Run it

Python 3.12 or newer is required. The first launch creates a virtual environment in `.venv` and installs the dependencies.

### Linux

```bash
./start.sh
```

You can also start it from the application menu, or double-click `S3 Viewer.desktop`, after that file points at this folder.

### macOS

Double-click `start.command`. Terminal opens and starts the app. Or, in Terminal:

```bash
./start.command
```

### Windows

Double-click `start.bat`. The first run installs the dependencies in a console window, then the app opens without a console.

## Where connections are stored

Saved connections, including the secret key, and the last connection form are kept outside the repository:

| System | Folder |
| --- | --- |
| Linux | `~/.config/s3-viewer/` |
| macOS | `~/Library/Application Support/s3-viewer/` |
| Windows | `%AppData%\s3-viewer\` |

`connections.json` holds named connections and credentials. `settings.ini` remembers the endpoint, access key, region, and window options. The secret key is written only when you save a named connection. An older Linux store in `~/.s3-viewer` is copied over once.
