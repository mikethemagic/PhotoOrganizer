# PhotoOrganizer API Reference

This document provides comprehensive documentation for all public APIs, functions, and components in the PhotoOrganizer project.

## Table of Contents

1. [Overview](#overview)
2. [PhotoInfo Data Structure](#photoinfo-data-structure)
3. [PhotoOrganizer Class](#photoorganizer-class)
4. [Command Line Interface](#command-line-interface)
5. [Configuration System](#configuration-system)
6. [Utility Scripts](#utility-scripts)
7. [Usage Examples](#usage-examples)
8. [Error Handling](#error-handling)
9. [Performance Considerations](#performance-considerations)

## Overview

PhotoOrganizer is an intelligent Python-based photo organization tool that automatically sorts photos by date, location, and events. It provides both a programmatic API and command-line interface for organizing large photo collections.

### Key Features

- **Intelligent timestamp detection**: EXIF → Filename → File modification time
- **GPS-based location recognition**: Automatic location resolution via OpenStreetMap
- **Event grouping**: Groups similar photos into events
- **Duplicate detection**: SHA-256 hash-based duplicate detection
- **Parallel processing**: Multi-threading for large photo collections
- **Caching system**: JSON-based caching for repeated runs
- **Script generation**: Bash/PowerShell scripts for safe execution
- **EXIF repair**: Adds missing EXIF data based on filenames

## PhotoInfo Data Structure

```python
@dataclass
class PhotoInfo:
    """Information about a photo/video file"""
    filepath: Path
    datetime: datetime
    gps_coords: Optional[Tuple[float, float]] = None  # (lat, lon)
    location_name: Optional[str] = None  # Location name from GPS
    file_hash: str = ""
    file_size: int = 0
    is_video: bool = False
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `filepath` | `Path` | Full path to the photo/video file |
| `datetime` | `datetime` | Best available timestamp (EXIF/filename/file time) |
| `gps_coords` | `Optional[Tuple[float, float]]` | GPS coordinates as (latitude, longitude) |
| `location_name` | `Optional[str]` | Human-readable location name from reverse geocoding |
| `file_hash` | `str` | SHA-256 hash for duplicate detection |
| `file_size` | `int` | File size in bytes |
| `is_video` | `bool` | True if file is a video, False for images |

## PhotoOrganizer Class

### Constructor

```python
def __init__(self, 
             source_dir: str, 
             target_dir: str,
             same_day_hours: int = 12,
             event_max_days: int = 3,
             geo_radius_km: float = 10.0,
             min_event_photos: int = 10,
             use_geocoding: bool = True,
             max_workers: int = None,
             generate_script: bool = False,
             script_path: str = None,
             cache_file: Optional[str] = None,
             add_exif: bool = False)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source_dir` | `str` | Required | Source directory containing photos |
| `target_dir` | `str` | Required | Target directory for organized photos |
| `same_day_hours` | `int` | `12` | Hours threshold for same day classification |
| `event_max_days` | `int` | `3` | Maximum days for event association |
| `geo_radius_km` | `float` | `10.0` | GPS radius in km for event grouping |
| `min_event_photos` | `int` | `10` | Minimum photos required to create event folder |
| `use_geocoding` | `bool` | `True` | Enable reverse geocoding for location names |
| `max_workers` | `int` | `None` | Number of parallel threads (None = auto) |
| `generate_script` | `bool` | `False` | Generate shell script for later execution |
| `script_path` | `str` | `None` | Path for shell script (None = auto) |
| `cache_file` | `str` | `None` | JSON cache file path (None = auto) |
| `add_exif` | `bool` | `False` | Add EXIF data based on filenames |

#### Example

```python
from photo_organizer import PhotoOrganizer

# Basic usage
organizer = PhotoOrganizer(
    source_dir="/path/to/photos",
    target_dir="/path/to/organized"
)

# Advanced configuration
organizer = PhotoOrganizer(
    source_dir="/path/to/photos",
    target_dir="/path/to/organized",
    min_event_photos=5,
    geo_radius_km=20.0,
    use_geocoding=True,
    generate_script=True,
    add_exif=True
)
```

### Public Methods

#### scan_photos()

Scans all photos in the source directory with parallel processing.

```python
def scan_photos(self) -> None
```

**Description:**
- Discovers all supported image/video files
- Extracts metadata (EXIF, GPS, timestamps)
- Calculates file hashes for duplicate detection
- Performs geocoding for GPS coordinates
- Caches results for future runs

**Example:**
```python
organizer.scan_photos()
print(f"Found {len(organizer.photos)} photos")
```

#### preview_organization()

Shows a preview of the planned organization structure.

```python
def preview_organization(self) -> Dict[str, List[PhotoInfo]]
```

**Returns:**
- Dictionary mapping event names to lists of PhotoInfo objects

**Example:**
```python
events = organizer.preview_organization()
for event_name, photos in events.items():
    print(f"Event: {event_name} - {len(photos)} photos")
```

#### organize_photos()

Organizes photos into the target directory structure.

```python
def organize_photos(self, dry_run: bool = True) -> None
```

**Parameters:**
- `dry_run` (bool): If True, only shows what would be done without moving files

**Example:**
```python
# Preview only
organizer.organize_photos(dry_run=True)

# Actually move files
organizer.organize_photos(dry_run=False)
```

#### get_file_hash()

Calculates SHA-256 hash of a file for duplicate detection.

```python
def get_file_hash(self, filepath: Path) -> str
```

**Parameters:**
- `filepath` (Path): Path to the file

**Returns:**
- SHA-256 hash as hexadecimal string

**Example:**
```python
from pathlib import Path
hash_value = organizer.get_file_hash(Path("photo.jpg"))
```

#### get_best_datetime()

Determines the best timestamp using priority order: EXIF > Filename > File time.

```python
def get_best_datetime(self, filepath: Path) -> datetime
```

**Parameters:**
- `filepath` (Path): Path to the photo/video file

**Returns:**
- Best available datetime for the file

**Example:**
```python
from pathlib import Path
timestamp = organizer.get_best_datetime(Path("IMG_20250315_143025.jpg"))
```

#### get_gps_coords()

Extracts GPS coordinates from EXIF data.

```python
def get_gps_coords(self, filepath: Path) -> Optional[Tuple[float, float]]
```

**Parameters:**
- `filepath` (Path): Path to the image file

**Returns:**
- GPS coordinates as (latitude, longitude) tuple or None

**Example:**
```python
from pathlib import Path
coords = organizer.get_gps_coords(Path("photo_with_gps.jpg"))
if coords:
    lat, lon = coords
    print(f"Location: {lat}, {lon}")
```

#### get_location_name()

Converts GPS coordinates to location names via reverse geocoding.

```python
def get_location_name(self, coords: Tuple[float, float]) -> Optional[str]
```

**Parameters:**
- `coords` (Tuple[float, float]): GPS coordinates as (latitude, longitude)

**Returns:**
- Human-readable location name or None

**Example:**
```python
location = organizer.get_location_name((52.5200, 13.4050))  # Berlin
print(f"Location: {location}")  # Output: Berlin
```

#### calculate_distance()

Calculates distance between two GPS coordinates using Haversine formula.

```python
def calculate_distance(self, coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float
```

**Parameters:**
- `coord1` (Tuple[float, float]): First GPS coordinate
- `coord2` (Tuple[float, float]): Second GPS coordinate

**Returns:**
- Distance in kilometers

**Example:**
```python
berlin = (52.5200, 13.4050)
munich = (48.1351, 11.5820)
distance = organizer.calculate_distance(berlin, munich)
print(f"Distance: {distance:.1f} km")
```

#### save_cache() / load_cache()

Save and load photo metadata to/from JSON cache.

```python
def save_cache(self) -> None
def load_cache(self) -> bool
```

**Example:**
```python
# Save current state
organizer.save_cache()

# Load from cache
if organizer.load_cache():
    print("Cache loaded successfully")
```

#### generate_shell_script()

Generates shell script for safe photo organization.

```python
def generate_shell_script(self, events: Dict[str, List[PhotoInfo]]) -> None
```

**Parameters:**
- `events` (Dict[str, List[PhotoInfo]]): Event organization structure

**Example:**
```python
events = organizer.preview_organization()
organizer.generate_shell_script(events)
```

### Properties

#### photos

List of all discovered photos as PhotoInfo objects.

```python
@property
def photos(self) -> List[PhotoInfo]
```

#### duplicates

Set of file paths identified as duplicates.

```python
@property
def duplicates(self) -> Set[str]
```

## Command Line Interface

### Basic Syntax

```bash
python photo_organizer.py <source_dir> <target_dir> [options]
```

### Required Arguments

| Argument | Description |
|----------|-------------|
| `source` | Source directory with photos |
| `target` | Target directory for organized photos |

### Options

#### Core Options

| Option | Description | Default |
|--------|-------------|---------|
| `--execute` | Actually move files (without this, only preview) | Preview only |
| `--generate-script` | Generate shell script for later execution | Disabled |
| `--addexif` | Add EXIF data based on filenames | Disabled |

#### Event Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--same-day-hours` | int | 12 | Hours threshold for same day |
| `--event-max-days` | int | 3 | Maximum days for event association |
| `--geo-radius` | float | 10.0 | GPS radius in km for grouping |
| `--min-event-photos` | int | 10 | Minimum photos for event folder |

#### Performance & Features

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--max-workers` | int | auto | Number of parallel threads |
| `--no-geocoding` | flag | False | Disable GPS location lookup |
| `--cache` | str | auto | JSON cache file path |
| `--script-path` | str | auto | Shell script output path |

### Usage Examples

#### Basic Photo Organization

```bash
# Preview organization
python photo_organizer.py /path/to/photos /path/to/organized

# Actually move files
python photo_organizer.py /path/to/photos /path/to/organized --execute
```

#### Advanced Configuration

```bash
# Custom event settings
python photo_organizer.py /photos /organized \
    --min-event-photos 5 \
    --geo-radius 20 \
    --event-max-days 7

# Generate script for later execution
python photo_organizer.py /photos /organized \
    --generate-script \
    --addexif

# High-performance batch processing
python photo_organizer.py /large_collection /organized \
    --max-workers 32 \
    --generate-script
```

#### Special Use Cases

```bash
# Organize screenshots (add EXIF, small events)
python photo_organizer.py ~/Screenshots ~/Pictures/Screenshots \
    --addexif \
    --min-event-photos 3 \
    --same-day-hours 24

# Old photo collection (no GPS, larger events)
python photo_organizer.py /archive/photos /sorted \
    --no-geocoding \
    --min-event-photos 25 \
    --event-max-days 7
```

## Configuration System

### Environment Variables

The project uses several environment variables for configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `PROJECT` | Project root directory | Current directory |
| `PROJECT_BIN` | Binary/script directory | `$PROJECT/bin` |
| `PROJECT_LIB` | Library directory | `$PROJECT/lib` |
| `PROJECT_DATA` | Data directory | `$PROJECT/data` |
| `PROJECT_SCRIPTS` | Generated scripts directory | `$PROJECT/scripts` |
| `PROJECT_CACHE` | Cache files directory | `$PROJECT/cache` |
| `PROJECT_CFG` | Configuration directory | `$PROJECT/cfg` |

### Configuration File

The system uses `photo_organizer.cfg` for filename pattern configuration:

```ini
[Filename_Patterns]
# Standard formats with date and time
datetime_space = (\d{4})-(\d{2})-(\d{2})\s+(\d{2})[\.-:](\d{2})[\.-:](\d{2})
datetime_underscore = (\d{4})-(\d{2})-(\d{2})_(\d{2})[\.-:](\d{2})[\.-:](\d{2})
compact_datetime = (\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})

# Date only (time set to 12:00:00)
date_dashes = (\d{4})-(\d{2})-(\d{2})
date_compact = (\d{4})(\d{2})(\d{2})

# Camera/app-specific formats
img_camera = IMG_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})
whatsapp = IMG-(\d{4})(\d{2})(\d{2})-WA\d+
signal = signal-(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})(\d{2})
screenshot = Screenshot_(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})
```

#### Pattern Format

Regex patterns must have either:
- **6 groups**: Year, Month, Day, Hour, Minute, Second
- **3 groups**: Year, Month, Day (time defaults to 12:00:00)

#### Adding Custom Patterns

```ini
# Custom camera format
my_camera = DSC(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})

# Social media format
instagram = (\d{4})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_UTC
```

## Utility Scripts

### setenv.sh

Sets up the project environment and directory structure.

```bash
#!/bin/bash
source setenv.sh
```

**Functions:**
- Sets `PROJECT` and related environment variables
- Creates necessary directories
- Adds project bin to PATH

### organize.sh

Main execution script that handles Python environment and runs the organizer.

```bash
#!/bin/bash
./organize.sh /path/to/photos /path/to/organized [options]
```

**Functions:**
- Activates Python virtual environment
- Runs photo_organizer.py with arguments
- Deactivates environment

### install_py.sh

Sets up Python virtual environment and installs dependencies.

```bash
#!/bin/bash
./install_py.sh
```

**Functions:**
- Creates Python virtual environment
- Installs required packages from requirements.txt
- Sets up development environment

### manage_interpreter.sh

Manages Python virtual environment activation/deactivation.

```bash
#!/bin/bash
source manage_interpreter.sh activate_interpreter
source manage_interpreter.sh deactivate_interpreter
```

**Functions:**
- `activate_interpreter`: Activates virtual environment
- `deactivate_interpreter`: Deactivates virtual environment

## Usage Examples

### Programmatic API Usage

#### Basic Organization

```python
from photo_organizer import PhotoOrganizer
from pathlib import Path

# Create organizer
organizer = PhotoOrganizer(
    source_dir="/Users/john/Photos/iPhone_Backup",
    target_dir="/Users/john/Photos/Organized"
)

# Scan and organize
organizer.scan_photos()
events = organizer.preview_organization()
organizer.organize_photos(dry_run=False)
```

#### Advanced Workflow

```python
# Custom configuration
organizer = PhotoOrganizer(
    source_dir="/media/photos",
    target_dir="/storage/organized",
    min_event_photos=5,
    geo_radius_km=15.0,
    use_geocoding=True,
    max_workers=16,
    add_exif=True
)

# Process with caching
organizer.scan_photos()

# Check statistics
print(f"Total photos: {len(organizer.photos)}")
print(f"Duplicates: {len(organizer.duplicates)}")
print(f"GPS photos: {len([p for p in organizer.photos if p.gps_coords])}")

# Generate script for safe execution
organizer.generate_script = True
events = organizer.preview_organization()
organizer.organize_photos(dry_run=True)
```

#### Custom Processing

```python
# Manual photo processing
for photo_path in Path("/photos").rglob("*.jpg"):
    # Get metadata
    datetime_info = organizer.get_best_datetime(photo_path)
    gps_coords = organizer.get_gps_coords(photo_path)
    
    if gps_coords:
        location = organizer.get_location_name(gps_coords)
        print(f"{photo_path.name}: {datetime_info} at {location}")
```

### Command Line Examples

#### Smartphone Photo Organization

```bash
# iPhone backup with GPS and EXIF repair
python photo_organizer.py \
    ~/Documents/iPhone_Backup \
    ~/Photos/iPhone_Organized \
    --generate-script \
    --addexif \
    --min-event-photos 8 \
    --geo-radius 5
```

#### Large Collection Processing

```bash
# Process 10,000+ photos with caching
python photo_organizer.py \
    /nas/photo_archive \
    /nas/organized \
    --max-workers 24 \
    --generate-script \
    --cache /tmp/large_collection_cache.json
```

#### Screenshots and Downloads

```bash
# Organize screenshots with small events
python photo_organizer.py \
    ~/Screenshots \
    ~/Pictures/Screenshots_Sorted \
    --addexif \
    --min-event-photos 3 \
    --same-day-hours 24 \
    --no-geocoding
```

#### Historical Photo Archive

```bash
# Old photos without GPS
python photo_organizer.py \
    /archive/family_photos \
    /sorted/family_photos \
    --no-geocoding \
    --min-event-photos 20 \
    --event-max-days 14 \
    --generate-script
```

### Batch Processing

```bash
#!/bin/bash
# Process multiple sources
for source in /media/*/DCIM /backup/phone_*; do
    if [[ -d "$source" ]]; then
        echo "Processing: $source"
        python photo_organizer.py "$source" /nas/photos --generate-script
        bash photo_move_*.sh
    fi
done
```

## Error Handling

### Common Exceptions

| Exception | Cause | Solution |
|-----------|-------|----------|
| `ImportError` | Missing dependencies | Run `pip install -r requirements.txt` |
| `FileNotFoundError` | Invalid source/target path | Check directory paths |
| `PermissionError` | Insufficient file permissions | Check file/directory permissions |
| `requests.RequestException` | Geocoding API error | Check internet connection, use `--no-geocoding` |

### Debug Information

#### Verbose Output

```bash
# Enable detailed logging
python photo_organizer.py /photos /organized 2>&1 | tee organizer.log
```

#### Cache Inspection

```python
import json

# Examine cache contents
with open("photo_cache_photos.json") as f:
    cache = json.load(f)

print(f"Cached photos: {len(cache['photos'])}")
print(f"Location cache: {len(cache['location_cache'])}")
```

#### Performance Debugging

```bash
# Test different worker counts
for workers in 4 8 16 32; do
    echo "Testing $workers workers"
    time python photo_organizer.py /photos /test --max-workers $workers
done
```

## Performance Considerations

### Optimization Guidelines

1. **Cache Usage**: Always use caching for repeated runs
2. **Worker Threads**: Optimal = CPU cores + 4 (max 32)
3. **Geocoding**: Major bottleneck due to API rate limits
4. **Memory Usage**: Large collections may require 64GB+ RAM
5. **Storage**: Use fast SSDs for source/target directories

### Performance Characteristics

| Collection Size | First Run | Cached Run | Memory Usage |
|----------------|-----------|------------|--------------|
| 1,000 photos | 2-5 min | 30 sec | 1-2 GB |
| 10,000 photos | 20-45 min | 2-5 min | 8-16 GB |
| 100,000 photos | 4-8 hours | 10-30 min | 32-64 GB |

### Recommendations

- **Small collections** (< 1,000): Use default settings
- **Medium collections** (1,000-10,000): Enable caching, consider `--max-workers 16`
- **Large collections** (> 10,000): Use caching, script generation, multiple passes
- **GPS-heavy collections**: Expect longer processing due to geocoding rate limits
- **Historical archives**: Use `--no-geocoding` for faster processing

This completes the comprehensive API reference for PhotoOrganizer. All public APIs, functions, and components are documented with detailed examples and usage instructions.