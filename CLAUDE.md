# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**PhotoOrganizer** automatically organizes photos and videos into structured folders by
date, location, and events. It derives timestamps and GPS data from EXIF metadata, video
metadata (MP4/MOV), filenames (e.g. `IMG-20240315-WA0001.jpg`) and GPS coordinates, then
groups related media via smart event detection. A permanent cache avoids reprocessing.

## Project Structure

```text
PhotoOrganiser/
├── bin/          # Batch scripts to run and manage the tool
├── lib/          # Python source code
│   ├── photo_organizer.py   # Main organizer logic
│   ├── analyze_photos.py    # Analysis / geolocation
│   ├── cache.py             # Permanent cache
│   └── utils.py             # Helpers
├── cfg/          # Configuration
├── cache/        # Permanent cache data
├── scripts/      # Generated / helper scripts
├── data/         # Input media
├── doc/          # Documentation
└── work/         # Working files
```

## Documentation

Several topic-specific docs live at the repo root, e.g.:
`ENVIRONMENT_VARIABLES.md`, `PERMANENT_CACHE_DOCUMENTATION.md`,
`ANALYZE_GEOLOCATIONS.md`, `INSTALL_FFMPEG.md`, `REFACTORING_NOTES.md`.
Start with `README.md` for the quick start.

## Dependencies

Python; see `lib/requirements.txt`. FFmpeg is required for video metadata
(see `INSTALL_FFMPEG.md`). Behaviour is configurable via environment variables
(see `ENVIRONMENT_VARIABLES.md`).
