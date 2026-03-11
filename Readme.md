# PhotoOrganizer

**Automatic photo and video organization based on timestamps and GPS data.**

Intelligently organize thousands of photos into structured folders by date, location, and events. Never manually sort photos again!

## Why PhotoOrganizer?

I had a massive pile of automatically backed-up photos from phones, cameras, and cloud storage that needed organizing by theme, year, and location. With 1000+ files, manual sorting is impractical. This tool does it automatically using:

- **EXIF metadata** from cameras
- **Video metadata** from MP4/MOV files
- **Filenames** (IMG-20240315-WA0001.jpg)
- **GPS coordinates** for location-based grouping
- **Smart event detection** to group related photos

## Quick Start (60 seconds)

### 1. Install Dependencies

**Windows:**
```cmd
bin\install_py.bat
```

**Linux/Mac:**
```bash
bash bin/install_py.sh
```

This creates a virtual environment and installs all required packages (Pillow, requests, static-ffmpeg).

### 2. Put Photos in `data/` Folder

```cmd
# Copy all your photos to the data directory
copy C:\phone_backup\*.jpg data\
copy C:\phone_backup\*.mp4 data\
```

Or simply drag-and-drop your photos into the `data/` folder.

### 3. Analyze Your Photos

**Windows:**
```cmd
bin\analyse.bat
```

**Linux/Mac:**
```bash
bash bin/analyse.sh
```

This shows you:
- How many photos/videos found
- EXIF availability
- GPS data availability
- Date ranges
- **Cached city names** from GPS coordinates
- **Missing geolocations** that need geocoding
- Recommended organization settings

**Tip:** Add `--add-missing-geolocations` to automatically geocode coordinates:
```cmd
bin\analyse.bat --add-missing-geolocations
```

### 4. Organize Your Photos

**Preview first (recommended):**
```cmd
bin\organize.bat data results
```

**Execute the organization:**
```cmd
bin\organize.bat data results --execute
```

Your photos are now organized in `results/` by year, date, and location!

### 5. How to Redo Organization

If you want to try different settings or start over:

**Windows:**
```cmd
bin\reset2data.bat
```

**Linux/Mac:**
```bash
bash bin/reset2data.sh
```

This moves all files from `results/` back to `data/`, allowing you to re-run with different parameters.

---

## Features

### Core Features
- ✅ **Smart Date Detection**: Extracts dates from EXIF, video metadata, or filenames
- ✅ **GPS-Based Grouping**: Groups photos by location using GPS coordinates
- ✅ **Event Detection**: Automatically creates events based on time + location proximity
- ✅ **Duplicate Detection**: SHA-256 hash-based duplicate identification
- ✅ **Video Support**: Full metadata extraction from MP4, MOV, AVI files (via ffprobe)
- ✅ **Multi-format**: JPG, PNG, TIFF, MP4, MOV, AVI, and more

### Advanced Features
- 📍 **Reverse Geocoding**: GPS coordinates → City names (via Nominatim)
- 📝 **EXIF Enhancement**: Adds EXIF timestamps to files that only have dates in filenames
- 💾 **Smart Caching**: Metadata and geocoding cache for fast re-runs
- 🔄 **Parallel Processing**: Multi-threaded for fast processing of large libraries
- 📜 **Script Generation**: Creates bash/PowerShell scripts for deferred execution
- 🔍 **Preview Mode**: See what will happen before moving files

---

## Workflow

### Typical Photo Organization Workflow

```
┌─────────────────┐
│  1. Put photos  │
│   in data/      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  2. Analyze     │
│  bin\analyse    │
│                 │
│  Shows stats &  │
│  recommendations│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  3. Preview     │
│  bin\organize   │
│  (no --execute) │
└────────┬────────┘
         │
         ▼
    ┌────────┐
    │ Good?  │──No──┐
    └───┬────┘      │
        │ Yes       │
        ▼           ▼
┌─────────────┐  ┌──────────────┐
│ 4. Execute  │  │ Adjust       │
│  --execute  │  │ parameters   │
└─────────────┘  └──────┬───────┘
                        │
                        └──────┐
                               ▼
                        ┌──────────────┐
                        │ 5. Reset     │
                        │ reset2data   │
                        └──────┬───────┘
                               │
                               └─────────► Back to step 3
```

---

## Folder Structure After Organization

```
results/
├── 2023/
│   ├── 01-15/                          # Single day photos
│   │   ├── photo1.jpg
│   │   └── photo2.jpg
│   ├── Berlin_2023-03-10_bis_2023-03-12/  # Multi-day event with location
│   │   ├── photo1.jpg
│   │   ├── photo2.jpg
│   │   └── video1.mp4
│   └── Paris_2023-05-20_bis_2023-05-25/
│       └── ...
├── 2024/
│   ├── 05-10/
│   │   └── screenshot.png
│   └── New_York_2024-12-01_bis_2024-12-05/
│       └── ...
└── Duplicates/
    └── duplicate_photo.jpg
```

---

## Command Reference

### Analyze Command

**Basic analysis:**
```cmd
bin\analyse.bat [data_dir] [target_dir]
```

**Quick analysis (file stats only, faster):**
```cmd
bin\analyse.bat --quick
```

**Geocode missing locations and save to config:**
```cmd
bin\analyse.bat --add-missing-geolocations
```

**Output includes:**
- File counts and types
- Metadata availability (EXIF, GPS, datetime)
- **Cached city names** from previous geocoding
- **Coordinates without location names** that need geocoding
- Date ranges
- Organization preview
- Recommended settings

### Organize Command

**Basic syntax:**
```cmd
bin\organize.bat <source> <target> [options]
```

**Common options:**
| Option | Description |
|--------|-------------|
| `--execute` | Actually move files (default is preview only) |
| `--generate-script` | Create a bash/PowerShell script instead of moving files |
| `--addexif` | Add EXIF timestamps to files that only have dates in filenames |
| `--no-geocoding` | Skip GPS geocoding (faster) |
| `--powershell` | Generate PowerShell script instead of bash (Windows) |
| `--min-event-photos 5` | Minimum photos to create an event folder (default: 10) |
| `--same-day-hours 12` | Hours to consider as "same day" (default: 12) |
| `--event-max-days 3` | Maximum days for a single event (default: 3) |
| `--geo-radius 10` | GPS radius in km for event grouping (default: 10) |
| `--max-workers 8` | Number of parallel threads (default: auto) |

**Examples:**

Preview organization:
```cmd
bin\organize.bat data results
```

Execute with EXIF enhancement:
```cmd
bin\organize.bat data results --execute --addexif
```

Fast organization without GPS:
```cmd
bin\organize.bat data results --execute --no-geocoding
```

Generate script for later execution:
```cmd
bin\organize.bat data results --generate-script
# Review: scripts\photo_move_script_20240315_120000.bat
# Execute: scripts\photo_move_script_20240315_120000.bat
```

Custom event settings:
```cmd
bin\organize.bat data results --execute --min-event-photos 5 --event-max-days 2 --geo-radius 5
```

### Reset Command

**Move all files back to data folder:**
```cmd
bin\reset2data.bat
```

This allows you to re-organize with different settings.

---

## Configuration

### GPS Location Cache (`cfg/geo_coords.cfg`)

Pre-configured or cached GPS coordinates with city names:

```ini
[geo_locations]
52.5200,13.4050: Berlin
48.8566,2.3522: Paris
40.7128,-74.0060: New York
```

**Benefits:**
- Speeds up geocoding by avoiding API calls
- Persists location names across runs
- Can be manually edited to fix incorrect locations
- Automatically updated with `--add-missing-geolocations`

**How to populate:**
1. Run `bin\analyse.bat --add-missing-geolocations` to auto-geocode
2. Or manually add coordinates in the format above

### Environment Variables (`bin/setenv.bat` or `bin/setenv.sh`)

Configure default paths:

```bash
PROJECT_DATA=c:\path\to\your\photos     # Input folder
PROJECT_WORK=c:\path\to\results          # Output folder
PROJECT_CACHE=c:\path\to\cache           # Metadata cache
PROJECT_SCRIPTS=c:\path\to\scripts       # Generated scripts
PROJECT_CFG=c:\path\to\cfg               # Config files
```

---

## Troubleshooting

### Video Metadata Errors

**Problem:** `[WinError 2] Das System kann die angegebene Datei nicht finden` for video files

**Solution:**
```bash
pip install static-ffmpeg
```

The tool now automatically uses the bundled ffprobe from this package.

### Missing File Errors

**Problem:** `EXIF-Fehler bei file.jpg: [Errno 2] No such file or directory`

**Cause:** Stale cache or files deleted between scanning and processing

**Solution:** The tool now automatically skips missing files. Delete cache to force fresh scan:
```cmd
del cache\photo_cache_*.json
```

### Geocoding Issues

**Problem:** Geocoding is slow or fails

**Solutions:**
1. Use `--no-geocoding` to skip it:
   ```cmd
   bin\organize.bat data results --no-geocoding
   ```

2. Pre-populate `cfg/geo_coords.cfg` with known locations

3. Use `bin\analyse.bat --add-missing-geolocations` to geocode incrementally

### Too Many Small Events

**Problem:** Creating too many small event folders

**Solution:** Increase minimum event size:
```cmd
bin\organize.bat data results --min-event-photos 20
```

### Events Too Large

**Problem:** Events spanning too many days or locations

**Solution:** Use stricter parameters:
```cmd
bin\organize.bat data results --event-max-days 1 --geo-radius 2
```

---

## Supported File Formats

**Images:** `.jpg`, `.jpeg`, `.png`, `.tiff`, `.tif`

**Videos:** `.mp4`, `.mov`, `.avi`, `.vid`

---

## Installation Details

### Requirements

- **Python 3.7+**
- **Pillow** (image processing and EXIF)
- **requests** (geocoding API)
- **static-ffmpeg** (video metadata extraction)

### Manual Installation

```bash
# Install dependencies
pip install -r lib/requirements.txt

# Or install individually
pip install Pillow>=8.0.0 requests>=2.25.0 static-ffmpeg>=2.5
```

---

## Advanced Usage

### Batch Processing Multiple Folders

**Windows:**
```cmd
@echo off
for /D %%S in (D:\Photos\*) do (
    echo Processing: %%S
    bin\organize.bat "%%S" D:\Organized --execute
)
```

**Linux/Mac:**
```bash
#!/bin/bash
for source in /media/*/DCIM /backup/phone_*; do
    if [[ -d "$source" ]]; then
        echo "Processing: $source"
        bash bin/organize.sh "$source" /nas/photos --execute
    fi
done
```

### Cache Sharing

The cache is based on the source directory, so you can organize the same photos to different targets using the same cache:

```cmd
bin\organize.bat data backup1 --generate-script
bin\organize.bat data backup2 --generate-script  # Reuses cache
bin\organize.bat data nas --generate-script      # Reuses cache
```

### Testing Different Parameters

```cmd
# Test different event sizes
bin\organize.bat data test1 --min-event-photos 5
bin\organize.bat data test2 --min-event-photos 15
bin\organize.bat data test3 --min-event-photos 25

# Test different GPS radii
bin\organize.bat data test_5km --geo-radius 5
bin\organize.bat data test_20km --geo-radius 20
```

---

## Tips & Best Practices

1. **Always analyze first** - Run `bin\analyse.bat` to understand your collection
2. **Use preview mode** - Never use `--execute` on first run
3. **Keep backups** - Always keep originals safe
4. **Start small** - Test with a subset of photos first
5. **Check duplicates folder** - Review before deleting
6. **Leverage cache** - Reuse cache when trying different organization settings
7. **Manual review** - The tool is smart but not perfect - review results

---

## FAQ

**Q: Can I organize photos already in subfolders?**
A: Yes, the tool recursively scans all subfolders.

**Q: What happens to duplicates?**
A: Duplicates (same file hash) are moved to `Duplicates/` folder.

**Q: Can I undo organization?**
A: Yes, use `bin\reset2data.bat` to move all files back.

**Q: Does it modify my photos?**
A: Only if you use `--addexif`. Otherwise files are only moved, not modified.

**Q: How accurate is event detection?**
A: Adjust `--same-day-hours`, `--event-max-days`, and `--geo-radius` for your needs.

**Q: Can I run on network drives?**
A: Yes, but may be slower. Consider using `--max-workers 2` for reliability.

**Q: What if I don't have GPS data?**
A: Use `--no-geocoding` to skip GPS-based grouping. Events will be based on time only.

---

## Project Structure

```
PhotoOrganiser/
├── bin/
│   ├── analyse.bat/sh      # Analyze photos and show stats
│   ├── organize.bat/sh     # Organize photos
│   ├── reset2data.bat/sh   # Reset organization
│   ├── setenv.bat/sh       # Environment configuration
│   └── install_py.bat/sh   # Install dependencies
├── lib/
│   ├── photo_organizer.py  # Main organizer module
│   ├── analyze_photos.py   # Analysis tool
│   └── requirements.txt    # Python dependencies
├── data/                   # Your photos go here
├── results/                # Organized output
├── cache/                  # Metadata cache
├── scripts/                # Generated scripts
└── cfg/                    # Configuration
    └── geo_coords.cfg      # GPS location cache
```

---

## Contributing

Contributions welcome! Please:
- Follow existing code style
- Add tests for new features
- Update documentation

---

## License

Provided as-is for personal and educational use. All processing is done locally (except geocoding which uses Nominatim API).

---

**Happy organizing! 📸**

---

## 🐧 Erweiterte Linux/Mac Dokumentation (Deutsch)

### 🚀 Quickstart für Linux/Mac

#### Installation & Setup
**Empfohlene Methode mit Virtual Environment:**
```bash
# 1. Virtual Environment erstellen und Abhängigkeiten installieren
./bin/install_py.sh

# 2. PhotoOrganizer verwenden
./bin/organize.sh /pfad/zu/fotos /pfad/zu/ziel

# 3. Script generieren für späteren Move
./bin/organize.sh /pfad/zu/fotos /pfad/zu/ziel --generate-script

# 4. Script ausführen
bash photo_move_20250803_233045.sh
```

**Alternative manuelle Installation:**
```bash
# 1. Abhängigkeiten installieren
pip install Pillow requests

# 2. Projektumgebung einrichten (optional)
source bin/setenv.sh

# 3. Erste Analyse (nur Vorschau)
python photo_organizer.py /pfad/zu/fotos /pfad/zu/ziel

# 4. Script generieren für späteren Move
python photo_organizer.py /pfad/zu/fotos /pfad/zu/ziel --generate-script

# 5. Script ausführen
bash photo_move_20250803_233045.sh
```

### 🎯 Häufige Anwendungsfälle (Linux/Mac)

#### Smartphone-Fotos organisieren
```bash
# Mit GPS-Daten und Geocoding
./bin/organize.sh ~/Downloads/phone_backup ~/Photos --generate-script
```

#### Screenshots sortieren
```bash
# EXIF-Daten hinzufügen da meist nicht vorhanden
./bin/organize.sh ~/Screenshots ~/sorted_screenshots --addexif --generate-script
```

#### Große Foto-Sammlung (10.000+ Fotos)
```bash
# Mit Cache für wiederholte Läufe
./bin/organize.sh /nas/photos /nas/organized --generate-script --max-workers 20
```

#### Network Attached Storage (NAS)
```bash
# Fotos vom gemounteten NAS-Laufwerk organisieren
./bin/organize.sh /mnt/nas/photos /home/user/sorted_photos --generate-script
```

### 📚 Installation (Linux/Mac)

#### Systemanforderungen
- **Python 3.8+**
- **PIL/Pillow**: Für EXIF-Daten
- **requests**: Für Geocoding (optional)
- **ffprobe**: Für Video-Metadaten (optional)

#### Empfohlene Installation mit Virtual Environment
```bash
# Automatische Installation mit Virtual Environment
./bin/install_py.sh
```

#### Alternative manuelle Installation
```bash
# Abhängigkeiten installieren
pip install Pillow requests

# Projektumgebung einrichten (optional)
source bin/setenv.sh
```

#### Was die Installations-Skripte machen:
- Erstellen ein isoliertes Python Virtual Environment im `.venv` Ordner
- Installieren automatisch alle erforderlichen Abhängigkeiten aus `requirements.txt`
- Stellen sicher, dass keine Konflikte mit anderen Python-Projekten entstehen

### 💻 Kommandozeilen-Interface (Linux/Mac)

#### Grundlegende Syntax
**Empfohlene Methode (mit Skripten):**
```bash
./bin/organize.sh <quellordner> <zielordner> [optionen]
```

**Alternative direkte Ausführung:**
```bash
python photo_organizer.py <quellordner> <zielordner> [optionen]
```

### 📖 Beispiele (Linux/Mac)

#### Smartphone-Backup organisieren
```bash
# Mit allen Features
./bin/organize.sh \
    /backup/iphone_photos \
    /nas/family_photos \
    --generate-script \
    --addexif \
    --min-event-photos 8 \
    --geo-radius 5
```

#### Alte Foto-Sammlung aufräumen
```bash
# Ohne GPS, größere Events
./bin/organize.sh \
    /archive/old_photos \
    /sorted/decades \
    --no-geocoding \
    --min-event-photos 25 \
    --event-max-days 7 \
    --generate-script
```

#### Screenshots sortieren
```bash
# EXIF hinzufügen, kleine Events erlauben
./bin/organize.sh \
    ~/Screenshots \
    ~/Pictures/Screenshots_sorted \
    --addexif \
    --min-event-photos 3 \
    --same-day-hours 24 \
    --generate-script
```

#### NAS/Server Umgebung
```bash
# Große Sammlung auf Network Storage
./bin/organize.sh \
    /mnt/nas/camera_uploads \
    /mnt/nas/organized_photos \
    --generate-script \
    --max-workers 16 \
    --cache /tmp/photo_cache.json
```

### 🔧 Fehlerbehebung (Linux/Mac)

#### "PIL/Pillow nicht installiert"
```bash
pip install Pillow
```

#### "requests nicht verfügbar"
```bash
# Abhängigkeiten installieren
./bin/install_py.sh

# Oder ohne Geocoding arbeiten:
./bin/organize.sh /fotos /ziel --no-geocoding
```

#### "Cache-Quelle passt nicht"
```bash
# Cache löschen für Neuanalyse
rm $PROJECT_CACHE/photo_cache_*.json
```

#### "Script bricht ab"
```bash
# Debug-Modus aktivieren
bash -x photo_move_script.sh
```

#### Langsames Geocoding
```bash
# Geocoding deaktivieren
./bin/organize.sh /fotos /ziel --no-geocoding

# Oder weniger Threads
./bin/organize.sh /fotos /ziel --max-workers 4
```

#### Zu viele kleine Events
```bash
# Event-Mindestgröße erhöhen
./bin/organize.sh /fotos /ziel --min-event-photos 20
```

#### Zu große Events
```bash
# Engere Parameter
./bin/organize.sh /fotos /ziel --event-max-days 1 --geo-radius 2
```

### 🛠️ Erweiterte Nutzung (Linux/Mac)

#### Batch-Verarbeitung
```bash
#!/bin/bash
# Mehrere Quellen verarbeiten
for source in /media/*/DCIM /backup/phone_*; do
    if [[ -d "$source" ]]; then
        echo "Verarbeite: $source"
        ./bin/organize.sh "$source" /nas/photos --generate-script
        bash photo_move_*.sh
    fi
done
```

#### Testläufe mit verschiedenen Parametern
```bash
# Verschiedene Event-Größen testen
./bin/organize.sh /fotos /test1 --min-event-photos 5
./bin/organize.sh /fotos /test2 --min-event-photos 15
./bin/organize.sh /fotos /test3 --min-event-photos 25

# GPS-Radius variieren
./bin/organize.sh /fotos /test_5km --geo-radius 5
./bin/organize.sh /fotos /test_20km --geo-radius 20
```

#### Cache-Sharing zwischen Zielen
```bash
# Ein Cache, verschiedene Ziele (möglich da Cache nur von Quelle abhängt)
./bin/organize.sh /fotos /backup1 --generate-script
./bin/organize.sh /fotos /backup2 --generate-script  # Verwendet gleichen Cache
./bin/organize.sh /fotos /nas --generate-script      # Verwendet gleichen Cache
```

---

## 🪟 Windows Dokumentation

### 🚀 Quickstart für Windows

#### Installation & Setup
**Empfohlene Methode mit Virtual Environment:**
```cmd
REM 1. Virtual Environment erstellen und Abhängigkeiten installieren
bin\install_py.bat

REM 2. PhotoOrganizer verwenden
bin\organize.bat C:\pfad\zu\fotos C:\pfad\zu\ziel

REM 3. Script generieren für späteren Move
bin\organize.bat C:\pfad\zu\fotos C:\pfad\zu\ziel --generate-script

REM 4. Script ausführen (PowerShell)
powershell -ExecutionPolicy Bypass -File photo_move_20250803_233045.ps1
```

**Alternative manuelle Installation:**
```cmd
REM 1. Abhängigkeiten installieren
pip install Pillow requests

REM 2. Projektumgebung einrichten (optional)
bin\setenv.bat

REM 3. Erste Analyse (nur Vorschau)
python photo_organizer.py C:\pfad\zu\fotos C:\pfad\zu\ziel

REM 4. Script generieren für späteren Move
python photo_organizer.py C:\pfad\zu\fotos C:\pfad\zu\ziel --generate-script --powershell

REM 5. Script ausführen
powershell -ExecutionPolicy Bypass -File photo_move_20250803_233045.ps1
```

### 🎯 Häufige Anwendungsfälle (Windows)

#### Smartphone-Fotos organisieren
```cmd
REM Mit GPS-Daten und Geocoding
bin\organize.bat C:\Users\%USERNAME%\Downloads\phone_backup C:\Users\%USERNAME%\Pictures\Photos --generate-script
```

#### Screenshots sortieren
```cmd
REM EXIF-Daten hinzufügen da meist nicht vorhanden
bin\organize.bat C:\Users\%USERNAME%\Pictures\Screenshots C:\Users\%USERNAME%\Pictures\sorted_screenshots --addexif --generate-script
```

#### Große Foto-Sammlung (10.000+ Fotos)
```cmd
REM Mit Cache für wiederholte Läufe
bin\organize.bat D:\NAS\photos D:\NAS\organized --generate-script --max-workers 20
```

#### PowerShell-Script generieren
```cmd
REM PowerShell-Script für Windows erstellen
bin\organize.bat C:\Photos C:\Organized --generate-script --powershell
```

### 📚 Installation (Windows)

#### Systemanforderungen
- **Python 3.8+**
- **PIL/Pillow**: Für EXIF-Daten
- **requests**: Für Geocoding (optional)
- **ffprobe**: Für Video-Metadaten (optional)

#### Empfohlene Installation mit Virtual Environment
```cmd
REM Automatische Installation mit Virtual Environment
bin\install_py.bat
```

#### Alternative manuelle Installation
```cmd
REM Abhängigkeiten installieren
pip install Pillow requests

REM Projektumgebung einrichten (optional)
bin\setenv.bat
```

#### Was die Installations-Skripte machen:
- Erstellen ein isoliertes Python Virtual Environment im `.venv` Ordner
- Installieren automatisch alle erforderlichen Abhängigkeiten aus `requirements.txt`
- Stellen sicher, dass keine Konflikte mit anderen Python-Projekten entstehen

### 💻 Kommandozeilen-Interface (Windows)

#### Grundlegende Syntax
**Empfohlene Methode (mit Skripten):**
```cmd
bin\organize.bat <quellordner> <zielordner> [optionen]
```

**Alternative direkte Ausführung:**
```cmd
python photo_organizer.py <quellordner> <zielordner> [optionen]
```

### 📖 Beispiele (Windows)

#### Smartphone-Backup organisieren
```cmd
REM Mit allen Features
bin\organize.bat ^
    C:\backup\iphone_photos ^
    D:\nas\family_photos ^
    --generate-script ^
    --addexif ^
    --min-event-photos 8 ^
    --geo-radius 5
```

#### Alte Foto-Sammlung aufräumen
```cmd
REM Ohne GPS, größere Events
bin\organize.bat ^
    C:\archive\old_photos ^
    D:\sorted\decades ^
    --no-geocoding ^
    --min-event-photos 25 ^
    --event-max-days 7 ^
    --generate-script
```

#### Screenshots sortieren
```cmd
REM EXIF hinzufügen, kleine Events erlauben
bin\organize.bat ^
    C:\Users\%USERNAME%\Pictures\Screenshots ^
    C:\Users\%USERNAME%\Pictures\sorted_screenshots ^
    --addexif ^
    --min-event-photos 3 ^
    --same-day-hours 24 ^
    --generate-script
```

#### PowerShell-Script für Windows
```cmd
REM PowerShell-Script generieren und ausführen
bin\organize.bat ^
    "C:\Users\Admin\Pictures" ^
    "D:\Photos\Organized" ^
    --generate-script ^
    --powershell ^
    --max-workers 8
```

### 🔧 Fehlerbehebung (Windows)

#### "PIL/Pillow nicht installiert"
```cmd
pip install Pillow
```

#### "requests nicht verfügbar"
```cmd
REM Abhängigkeiten installieren
bin\install_py.bat

REM Oder ohne Geocoding arbeiten:
bin\organize.bat C:\fotos C:\ziel --no-geocoding
```

#### "Cache-Quelle passt nicht"
```cmd
REM Cache löschen für Neuanalyse
del /Q %PROJECT_CACHE%\photo_cache_*.json
```

#### "Script bricht ab"
```cmd
REM PowerShell Verbose
powershell -ExecutionPolicy Bypass -File script.ps1 -Verbose
```

#### Langsames Geocoding
```cmd
REM Geocoding deaktivieren
bin\organize.bat C:\fotos C:\ziel --no-geocoding

REM Oder weniger Threads
bin\organize.bat C:\fotos C:\ziel --max-workers 4
```

#### Zu viele kleine Events
```cmd
REM Event-Mindestgröße erhöhen
bin\organize.bat C:\fotos C:\ziel --min-event-photos 20
```

#### Zu große Events
```cmd
REM Engere Parameter
bin\organize.bat C:\fotos C:\ziel --event-max-days 1 --geo-radius 2
```

### 🛠️ Erweiterte Nutzung (Windows)

#### Batch-Verarbeitung
```cmd
@echo off
REM Mehrere Quellen verarbeiten
for /D %%S in (D:\Photos\*) do (
    echo Verarbeite: %%S
    bin\organize.bat "%%S" D:\Organized --generate-script
    powershell -ExecutionPolicy Bypass -File photo_move_*.ps1
)
```

#### Testläufe mit verschiedenen Parametern
```cmd
REM Verschiedene Event-Größen testen
bin\organize.bat C:\fotos C:\test1 --min-event-photos 5
bin\organize.bat C:\fotos C:\test2 --min-event-photos 15
bin\organize.bat C:\fotos C:\test3 --min-event-photos 25

REM GPS-Radius variieren
bin\organize.bat C:\fotos C:\test_5km --geo-radius 5
bin\organize.bat C:\fotos C:\test_20km --geo-radius 20
```

#### Cache-Sharing zwischen Zielen
```cmd
REM Ein Cache, verschiedene Ziele (möglich da Cache nur von Quelle abhängt)
bin\organize.bat C:\fotos C:\backup1 --generate-script
bin\organize.bat C:\fotos C:\backup2 --generate-script
bin\organize.bat C:\fotos D:\nas --generate-script
```

---

## 📚 Allgemeine Informationen

### Wichtigste Features
- ✅ **Intelligente Zeitstempel-Erkennung**: EXIF → Dateiname → Datei-Zeit
- ✅ **GPS-basierte Ortserkennung**: Automatische Ortsauflösung über OpenStreetMap
- ✅ **Event-Gruppierung**: Ähnliche Fotos werden zu Events zusammengefasst
- ✅ **Duplikat-Erkennung**: SHA-256 Hash-basierte Erkennung
- ✅ **Parallel-Verarbeitung**: Multi-Threading für große Foto-Sammlungen
- ✅ **Cache-System**: JSON-basiertes Caching für wiederholte Läufe
- ✅ **Script-Generierung**: Bash oder PowerShell Scripts für sichere Ausführung
- ✅ **EXIF-Reparatur**: Fügt fehlende EXIF-Daten basierend auf Dateinamen hinzu

### 📁 Ordnerstruktur

Das Programm erstellt folgende Struktur:

```
Zielordner/
├── einzelfoto1.jpg                    # Einzelne Dateien (< min-event-photos)
├── screenshot.png                     # Einzelne Dateien
├── 2025/
│   ├── 03-15-Berlin/                  # Event mit Ort
│   │   ├── IMG_001.jpg
│   │   └── IMG_002.jpg
│   ├── 03-20/                         # Event ohne Ort
│   │   ├── photo1.jpg
│   │   └── photo2.jpg
│   └── Event_2025-03-25_bis_2025-03-27-München/  # Mehrtägiges Event
│       ├── urlaub001.jpg
│       └── urlaub002.jpg
```

### 📚 Comprehensive Documentation
- **[API Reference](API_REFERENCE.md)** - Complete API documentation with examples
- **[Developer Guide](DEVELOPER_GUIDE.md)** - Architecture, extending, and contributing
- **[Examples & Use Cases](EXAMPLES.md)** - Real-world scenarios and code samples

### Hauptoptionen
| Option | Beschreibung | Standard |
|--------|--------------|----------|
| `--execute` | Führt tatsächliche Datei-Moves durch | Nur Vorschau |
| `--generate-script` | Erzeugt Ausführungs-Script | Deaktiviert |
| `--addexif` | Fügt EXIF-Daten aus Dateinamen hinzu | Deaktiviert |
| `--powershell` | Erzeugt PowerShell- statt Bash-Script | Bash |
| `--no-geocoding` | Deaktiviert GPS→Ort Auflösung | Aktiviert |

### Event-Parameter
| Option | Beschreibung | Standard |
|--------|--------------|----------|
| `--same-day-hours` | Stunden für gleichen Tag | 12 |
| `--event-max-days` | Max. Tage für Event-Zugehörigkeit | 3 |
| `--geo-radius` | GPS-Radius in km | 10.0 |
| `--min-event-photos` | Min. Fotos für Event-Ordner | 10 |

### Performance-Optionen
| Option | Beschreibung | Standard |
|--------|--------------|----------|
| `--max-workers` | Anzahl paralleler Threads | Auto (CPU+4) |
| `--cache` | Cache-Datei | Auto-generiert |
| `--script-path` | Script-Pfad | Auto-generiert |

## API-Referenz

Das Programm kann auch als Python-Modul verwendet werden:

```python
from photo_organizer import PhotoOrganizer

# Organizer erstellen
organizer = PhotoOrganizer(
    source_dir="/path/to/photos",
    target_dir="/path/to/organized",
    use_geocoding=True,
    min_event_photos=10
)

# Fotos scannen
organizer.scan_photos()

# Vorschau
events = organizer.preview_organization()

# Script generieren
organizer.generate_script = True
organizer.organize_photos(dry_run=True)
```

**📖 Für vollständige API-Dokumentation siehe [API_REFERENCE.md](API_REFERENCE.md)**

## Lizenz & Support

Dieses Tool wurde entwickelt, um die Organisation großer Foto-Sammlungen zu automatisieren und dabei die Privatsphäre zu respektieren (alle Verarbeitungen erfolgen lokal, nur Geocoding verwendet externe APIs).

Für Fragen, Probleme oder Feature-Requests bitte ein Issue erstellen oder den Code entsprechend anpassen.

---

**Viel Erfolg beim Organisieren deiner Fotos! 📸🎉**
