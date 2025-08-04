# PhotoOrganizer Examples & Use Cases

This document provides comprehensive examples and real-world use cases for PhotoOrganizer, covering both command-line usage and programmatic API usage.

## Table of Contents

1. [Quick Start Examples](#quick-start-examples)
2. [Real-World Scenarios](#real-world-scenarios)
3. [Advanced Use Cases](#advanced-use-cases)
4. [Programmatic API Examples](#programmatic-api-examples)
5. [Batch Processing](#batch-processing)
6. [Troubleshooting Examples](#troubleshooting-examples)
7. [Integration Examples](#integration-examples)

## Quick Start Examples

### Basic Photo Organization

```bash
# Preview what would happen (safe, no files moved)
python photo_organizer.py ~/Pictures/Camera_Roll ~/Pictures/Organized

# Actually organize the photos
python photo_organizer.py ~/Pictures/Camera_Roll ~/Pictures/Organized --execute
```

### Generate Script for Later Execution

```bash
# Create a shell script instead of moving files immediately
python photo_organizer.py ~/Pictures/Camera_Roll ~/Pictures/Organized --generate-script

# Execute the generated script
bash photo_move_20250315_143025.sh
```

## Real-World Scenarios

### 1. Smartphone Photo Backup

**Scenario**: You've backed up 5,000 photos from your iPhone and want to organize them by date and location.

```bash
# Command with GPS geocoding and EXIF repair
python photo_organizer.py \
    ~/Documents/iPhone_Backup \
    ~/Photos/iPhone_Organized \
    --generate-script \
    --addexif \
    --min-event-photos 8 \
    --geo-radius 5 \
    --same-day-hours 18
```

**Result Structure**:
```
iPhone_Organized/
├── single_photo_1.jpg
├── single_photo_2.jpg
├── 2024/
│   ├── 12-25-Berlin/          # Christmas in Berlin
│   │   ├── IMG_001.jpg
│   │   └── IMG_002.jpg
│   └── 12-31-Muenchen/        # New Year in Munich
│       ├── party_001.jpg
│       └── party_002.jpg
└── 2025/
    ├── 01-15-Berlin/          # Daily photos
    │   ├── coffee_morning.jpg
    │   └── work_lunch.jpg
    └── Event_2025-02-10_bis_2025-02-17-Rom/  # Week in Rome
        ├── colosseum.jpg
        ├── vatican.jpg
        └── trevi_fountain.jpg
```

### 2. Family Photo Archive

**Scenario**: Organizing 20 years of family photos (15,000+ files) without GPS data.

```bash
# Large collection without geocoding, bigger events
python photo_organizer.py \
    /nas/family_archive \
    /nas/family_organized \
    --no-geocoding \
    --min-event-photos 25 \
    --event-max-days 14 \
    --max-workers 16 \
    --generate-script
```

**Optimizations Used**:
- `--no-geocoding`: Faster processing without GPS lookup
- `--min-event-photos 25`: Larger events for family gatherings
- `--event-max-days 14`: Longer events for vacations
- `--max-workers 16`: More parallel processing

### 3. Screenshot Organization

**Scenario**: Organize 2,000 screenshots that lack EXIF data.

```bash
# Add EXIF, small events, 24-hour grouping
python photo_organizer.py \
    ~/Screenshots \
    ~/Pictures/Screenshots_Organized \
    --addexif \
    --min-event-photos 3 \
    --same-day-hours 24 \
    --no-geocoding \
    --generate-script
```

**Features Used**:
- `--addexif`: Adds EXIF data from filename timestamps
- `--min-event-photos 3`: Small events (project screenshots)
- `--same-day-hours 24`: Full day grouping
- `--no-geocoding`: Screenshots don't have GPS

### 4. Professional Photography Workflow

**Scenario**: Wedding photographer organizing shoots from multiple events.

```bash
# Tight grouping for individual shoots
python photo_organizer.py \
    /storage/raw_shoots \
    /storage/organized_by_date \
    --min-event-photos 50 \
    --event-max-days 1 \
    --geo-radius 2 \
    --same-day-hours 6 \
    --generate-script
```

**Professional Settings**:
- `--min-event-photos 50`: Substantial shoots only
- `--event-max-days 1`: Same-day events only
- `--geo-radius 2`: Tight geographic grouping
- `--same-day-hours 6`: Separate morning/evening shoots

### 5. Travel Photo Organization

**Scenario**: Organizing photos from a 3-month world tour.

```bash
# Location-focused organization
python photo_organizer.py \
    ~/Travel/WorldTour2024 \
    ~/Photos/WorldTour_Organized \
    --min-event-photos 15 \
    --geo-radius 25 \
    --event-max-days 5 \
    --generate-script
```

**Travel-Optimized Settings**:
- `--geo-radius 25`: City-level grouping
- `--event-max-days 5`: Multi-day city visits
- Location names will create folders like "2024/03-15-Tokyo"

## Advanced Use Cases

### 1. Multi-Source Photo Consolidation

**Scenario**: Combine photos from multiple devices and sources.

```bash
#!/bin/bash
# Process multiple photo sources

# iPhone backup
python photo_organizer.py \
    ~/Backups/iPhone \
    ~/Photos/Consolidated \
    --generate-script --script-path ~/Scripts/iphone.sh

# Android backup  
python photo_organizer.py \
    ~/Backups/Android \
    ~/Photos/Consolidated \
    --generate-script --script-path ~/Scripts/android.sh

# Camera SD card
python photo_organizer.py \
    /media/sd_card/DCIM \
    ~/Photos/Consolidated \
    --generate-script --script-path ~/Scripts/camera.sh

# Execute all moves
bash ~/Scripts/iphone.sh
bash ~/Scripts/android.sh
bash ~/Scripts/camera.sh
```

### 2. Incremental Photo Processing

**Scenario**: Daily processing of new photos with persistent cache.

```bash
#!/bin/bash
# Daily photo processing script

# Set up environment
source ~/PhotoOrganizer/bin/setenv.sh

# Process new photos (cache makes this fast)
python photo_organizer.py \
    ~/Dropbox/Camera_Uploads \
    ~/Photos/Auto_Organized \
    --execute \
    --cache ~/Photos/.photo_cache.json \
    --min-event-photos 5

# Clean up processed photos from Dropbox
# (only after successful organization)
if [ $? -eq 0 ]; then
    echo "Organization successful, cleaning up Dropbox"
    rm -rf ~/Dropbox/Camera_Uploads/*
fi
```

### 3. Quality-Based Organization

**Scenario**: Organize photos but separate high-quality originals from compressed versions.

**Custom Implementation**:
```python
from photo_organizer import PhotoOrganizer
from pathlib import Path

class QualityAwareOrganizer(PhotoOrganizer):
    def __init__(self, *args, **kwargs):
        self.high_quality_dir = kwargs.pop('high_quality_dir', None)
        super().__init__(*args, **kwargs)
    
    def organize_photos(self, dry_run=True):
        # Group photos first
        events = self.group_photos_into_events()
        
        for event_name, photos in events.items():
            for photo in photos:
                # Determine quality based on file size and resolution
                if self.is_high_quality(photo):
                    target_dir = Path(self.high_quality_dir) / event_name
                else:
                    target_dir = self.target_dir / event_name
                
                if not dry_run:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    # Move file logic here
    
    def is_high_quality(self, photo):
        # Custom quality detection logic
        return photo.file_size > 5_000_000  # > 5MB

# Usage
organizer = QualityAwareOrganizer(
    source_dir="/photos/mixed_quality",
    target_dir="/photos/organized",
    high_quality_dir="/photos/high_quality"
)
```

### 4. Duplicate Analysis and Cleanup

**Scenario**: Find and handle duplicates across multiple photo collections.

```python
from photo_organizer import PhotoOrganizer
from pathlib import Path
import shutil

def find_duplicates_across_collections(collections):
    """Find duplicates across multiple photo collections."""
    all_hashes = {}
    duplicates = {}
    
    for collection_name, collection_path in collections.items():
        organizer = PhotoOrganizer(
            source_dir=collection_path,
            target_dir="/tmp/dummy",  # Not used
            use_geocoding=False  # Faster processing
        )
        
        organizer.scan_photos()
        
        for photo in organizer.photos:
            file_hash = photo.file_hash
            if file_hash in all_hashes:
                # Duplicate found
                if file_hash not in duplicates:
                    duplicates[file_hash] = {
                        'original': all_hashes[file_hash],
                        'duplicates': []
                    }
                duplicates[file_hash]['duplicates'].append({
                    'collection': collection_name,
                    'path': photo.filepath
                })
            else:
                all_hashes[file_hash] = {
                    'collection': collection_name,
                    'path': photo.filepath
                }
    
    return duplicates

# Usage
collections = {
    'iPhone_Backup': '/backups/iphone',
    'Android_Backup': '/backups/android',
    'Old_Computer': '/archive/old_photos'
}

duplicates = find_duplicates_across_collections(collections)

# Report duplicates
for file_hash, info in duplicates.items():
    original = info['original']
    print(f"\nDuplicate group (hash: {file_hash[:8]}...):")
    print(f"  Original: {original['collection']}: {original['path']}")
    for dup in info['duplicates']:
        print(f"  Duplicate: {dup['collection']}: {dup['path']}")
```

## Programmatic API Examples

### 1. Basic API Usage

```python
from photo_organizer import PhotoOrganizer
from pathlib import Path

# Create organizer instance
organizer = PhotoOrganizer(
    source_dir="/Users/john/Downloads/photos",
    target_dir="/Users/john/Photos/Organized",
    min_event_photos=5,
    use_geocoding=True
)

# Scan photos
print("Scanning photos...")
organizer.scan_photos()

# Show statistics
print(f"Found {len(organizer.photos)} photos")
print(f"Found {len(organizer.duplicates)} duplicates")
gps_photos = [p for p in organizer.photos if p.gps_coords]
print(f"Photos with GPS: {len(gps_photos)}")

# Preview organization
events = organizer.preview_organization()
print(f"Will create {len(events)} event groups")

# Organize (dry run first)
organizer.organize_photos(dry_run=True)

# If satisfied, do it for real
# organizer.organize_photos(dry_run=False)
```

### 2. Custom Photo Processing

```python
from photo_organizer import PhotoOrganizer, PhotoInfo
from pathlib import Path
from datetime import datetime
import json

def analyze_photo_collection(source_dir):
    """Analyze a photo collection and generate detailed report."""
    
    organizer = PhotoOrganizer(
        source_dir=source_dir,
        target_dir="/tmp/dummy",  # Not used for analysis
        use_geocoding=True
    )
    
    organizer.scan_photos()
    
    # Analysis
    analysis = {
        'total_photos': len(organizer.photos),
        'date_range': {
            'earliest': min(p.datetime for p in organizer.photos).isoformat(),
            'latest': max(p.datetime for p in organizer.photos).isoformat()
        },
        'locations': {},
        'cameras': {},
        'file_types': {},
        'size_stats': {
            'total_size': sum(p.file_size for p in organizer.photos),
            'avg_size': sum(p.file_size for p in organizer.photos) / len(organizer.photos),
            'largest': max(p.file_size for p in organizer.photos),
            'smallest': min(p.file_size for p in organizer.photos)
        }
    }
    
    # Location analysis
    for photo in organizer.photos:
        if photo.location_name:
            analysis['locations'][photo.location_name] = \
                analysis['locations'].get(photo.location_name, 0) + 1
    
    # File type analysis
    for photo in organizer.photos:
        ext = photo.filepath.suffix.lower()
        analysis['file_types'][ext] = \
            analysis['file_types'].get(ext, 0) + 1
    
    return analysis

# Usage
analysis = analyze_photo_collection("/path/to/photos")
print(json.dumps(analysis, indent=2))
```

### 3. Event-Based Photo Export

```python
from photo_organizer import PhotoOrganizer
import shutil
from pathlib import Path

def export_event_highlights(source_dir, export_dir, photos_per_event=5):
    """Export a few representative photos from each event."""
    
    organizer = PhotoOrganizer(
        source_dir=source_dir,
        target_dir="/tmp/dummy",
        min_event_photos=10  # Only process substantial events
    )
    
    organizer.scan_photos()
    events = organizer.group_photos_into_events()
    
    export_path = Path(export_dir)
    export_path.mkdir(parents=True, exist_ok=True)
    
    for event_name, photos in events.items():
        if event_name == ".":  # Skip single files
            continue
            
        # Select representative photos (evenly spaced)
        total_photos = len(photos)
        if total_photos <= photos_per_event:
            selected = photos
        else:
            step = total_photos // photos_per_event
            selected = [photos[i * step] for i in range(photos_per_event)]
        
        # Create event directory
        event_dir = export_path / event_name.replace("/", "_")
        event_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy selected photos
        for i, photo in enumerate(selected, 1):
            dest_name = f"{i:02d}_{photo.filepath.name}"
            dest_path = event_dir / dest_name
            shutil.copy2(photo.filepath, dest_path)
            print(f"Exported: {dest_path}")

# Usage
export_event_highlights(
    source_dir="/large/photo/collection",
    export_dir="/exports/highlights",
    photos_per_event=3
)
```

## Batch Processing

### 1. Process Multiple Directories

```bash
#!/bin/bash
# Process multiple photo directories

SOURCES=(
    "/media/sdcard1/DCIM"
    "/media/sdcard2/DCIM" 
    "/backups/phone_2023"
    "/backups/phone_2024"
)

TARGET="/storage/all_photos_organized"

for source in "${SOURCES[@]}"; do
    if [[ -d "$source" ]]; then
        echo "Processing: $source"
        
        # Generate unique script for each source
        timestamp=$(date +%Y%m%d_%H%M%S)
        script_name="organize_${timestamp}.sh"
        
        python photo_organizer.py \
            "$source" \
            "$TARGET" \
            --generate-script \
            --script-path "$script_name"
        
        # Execute the script
        if [[ -f "$script_name" ]]; then
            echo "Executing: $script_name"
            bash "$script_name"
            
            # Move script to archive
            mkdir -p scripts_archive
            mv "$script_name" scripts_archive/
        fi
    else
        echo "Directory not found: $source"
    fi
done

echo "Batch processing complete!"
```

### 2. Automated Daily Processing

```bash
#!/bin/bash
# Daily photo processing with error handling

set -e  # Exit on any error

# Configuration
SOURCE_DIR="$HOME/Dropbox/Camera_Uploads"
TARGET_DIR="$HOME/Photos/Auto_Organized"
CACHE_FILE="$HOME/.photo_organizer_cache.json"
LOG_FILE="$HOME/logs/photo_organizer.log"

# Create log directory
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    echo "$1"
}

# Check if source directory has new files
if [[ ! -d "$SOURCE_DIR" ]] || [[ -z "$(ls -A "$SOURCE_DIR")" ]]; then
    log "No new photos to process"
    exit 0
fi

log "Starting photo processing..."

# Count files before processing
file_count=$(find "$SOURCE_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \) | wc -l)
log "Found $file_count photos to process"

# Run photo organizer
if python photo_organizer.py \
    "$SOURCE_DIR" \
    "$TARGET_DIR" \
    --execute \
    --cache "$CACHE_FILE" \
    --min-event-photos 3 \
    --addexif \
    2>&1 >> "$LOG_FILE"; then
    
    log "Photo organization successful"
    
    # Archive processed photos instead of deleting
    archive_dir="$HOME/Photos/Processed_Archive/$(date +%Y%m%d)"
    mkdir -p "$archive_dir"
    mv "$SOURCE_DIR"/* "$archive_dir"/ 2>/dev/null || true
    
    log "Moved $file_count photos to archive: $archive_dir"
else
    log "ERROR: Photo organization failed!"
    exit 1
fi
```

### 3. Cloud Storage Integration

```python
#!/usr/bin/env python3
"""
Cloud storage integration example with Google Drive
"""

import os
import shutil
from pathlib import Path
from photo_organizer import PhotoOrganizer

def sync_and_organize(drive_folder, local_organized, temp_dir="/tmp/photo_sync"):
    """Download from cloud, organize, and upload organized photos."""
    
    temp_path = Path(temp_dir)
    temp_path.mkdir(exist_ok=True)
    
    try:
        # 1. Download from cloud storage (example with rclone)
        print("Downloading from cloud storage...")
        os.system(f"rclone copy 'drive:{drive_folder}' '{temp_path}'")
        
        # 2. Organize photos
        print("Organizing photos...")
        organizer = PhotoOrganizer(
            source_dir=str(temp_path),
            target_dir=local_organized,
            min_event_photos=5,
            generate_script=True
        )
        
        organizer.scan_photos()
        organizer.organize_photos(dry_run=False)
        
        # 3. Upload organized photos back to cloud
        print("Uploading organized photos...")
        os.system(f"rclone copy '{local_organized}' 'drive:{drive_folder}_organized'")
        
        # 4. Cleanup
        shutil.rmtree(temp_path)
        
        print("Cloud sync and organization complete!")
        
    except Exception as e:
        print(f"Error during sync: {e}")
        # Cleanup on error
        if temp_path.exists():
            shutil.rmtree(temp_path)
        raise

# Usage
if __name__ == "__main__":
    sync_and_organize(
        drive_folder="Photos/Unorganized",
        local_organized="/local/storage/photos"
    )
```

## Troubleshooting Examples

### 1. Handling Large Collections

```bash
# Problem: Out of memory with 50,000+ photos
# Solution: Process in smaller batches

#!/bin/bash
SOURCE="/huge/photo/collection"
TARGET="/organized/photos"
BATCH_SIZE=5000

# Create temporary directories for batches
for i in {1..10}; do
    batch_dir="/tmp/batch_$i"
    mkdir -p "$batch_dir"
    
    # Move files to batch directory (first 5000 files)
    find "$SOURCE" -type f \( -name "*.jpg" -o -name "*.jpeg" \) \
        | head -n $BATCH_SIZE \
        | xargs -I {} mv {} "$batch_dir"
    
    # Process batch
    if [[ -n "$(ls -A "$batch_dir")" ]]; then
        echo "Processing batch $i..."
        python photo_organizer.py \
            "$batch_dir" \
            "$TARGET" \
            --execute \
            --max-workers 8
    fi
    
    # Cleanup
    rm -rf "$batch_dir"
done
```

### 2. Recovering from Failed Organization

```python
#!/usr/bin/env python3
"""
Recovery script for failed photo organization
"""

import json
from pathlib import Path
from photo_organizer import PhotoOrganizer

def recover_from_cache(cache_file, target_dir):
    """Recreate organization structure from cache file."""
    
    with open(cache_file) as f:
        cache_data = json.load(f)
    
    # Recreate PhotoInfo objects
    photos = []
    for photo_data in cache_data['photos']:
        # Check if original file still exists
        original_path = Path(photo_data['filepath'])
        if original_path.exists():
            photos.append(photo_data)
        else:
            print(f"Warning: Original file missing: {original_path}")
    
    print(f"Found {len(photos)} recoverable photos from cache")
    
    # Create minimal organizer for grouping logic
    organizer = PhotoOrganizer(
        source_dir="/dummy",  # Not used
        target_dir=target_dir,
        use_geocoding=False  # Use cached location data
    )
    
    # Restore photos list (simplified)
    organizer.photos = photos
    
    # Perform organization
    events = organizer.group_photos_into_events()
    organizer.organize_photos(dry_run=False)

# Usage
if __name__ == "__main__":
    recover_from_cache(
        cache_file="/path/to/photo_cache.json",
        target_dir="/recovered/photos"
    )
```

### 3. Debugging Geocoding Issues

```python
#!/usr/bin/env python3
"""
Debug geocoding problems
"""

from photo_organizer import PhotoOrganizer
import time

def debug_geocoding(source_dir):
    """Debug geocoding issues step by step."""
    
    organizer = PhotoOrganizer(
        source_dir=source_dir,
        target_dir="/tmp/debug",
        use_geocoding=True,
        max_workers=1  # Single threaded for debugging
    )
    
    # Find photos with GPS
    organizer.scan_photos()
    gps_photos = [p for p in organizer.photos if p.gps_coords]
    
    print(f"Found {len(gps_photos)} photos with GPS coordinates")
    
    # Test geocoding for first few photos
    for i, photo in enumerate(gps_photos[:5]):
        print(f"\nTesting photo {i+1}: {photo.filepath.name}")
        print(f"GPS coordinates: {photo.gps_coords}")
        
        try:
            # Manual geocoding test
            location = organizer.get_location_name(photo.gps_coords)
            print(f"Location result: {location}")
            
            # Test rate limiting
            time.sleep(1.5)  # Extra delay for safety
            
        except Exception as e:
            print(f"Geocoding error: {e}")
            
    # Check cache status
    print(f"\nLocation cache entries: {len(organizer.location_cache)}")
    for coords, location in list(organizer.location_cache.items())[:5]:
        print(f"  {coords} -> {location}")

# Usage
if __name__ == "__main__":
    debug_geocoding("/path/to/test/photos")
```

## Integration Examples

### 1. Integration with Photo Management Software

```python
#!/usr/bin/env python3
"""
Export organized structure to Lightroom-compatible format
"""

import csv
from pathlib import Path
from photo_organizer import PhotoOrganizer

def export_for_lightroom(source_dir, target_dir, csv_output):
    """Export organization data for Lightroom import."""
    
    organizer = PhotoOrganizer(
        source_dir=source_dir,
        target_dir=target_dir
    )
    
    organizer.scan_photos()
    events = organizer.group_photos_into_events()
    
    # Create CSV for Lightroom
    with open(csv_output, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Filename', 'Event', 'Date', 'Location', 'GPS_Lat', 'GPS_Lon'])
        
        for event_name, photos in events.items():
            for photo in photos:
                writer.writerow([
                    photo.filepath.name,
                    event_name,
                    photo.datetime.isoformat(),
                    photo.location_name or '',
                    photo.gps_coords[0] if photo.gps_coords else '',
                    photo.gps_coords[1] if photo.gps_coords else ''
                ])
    
    print(f"Lightroom import data exported to: {csv_output}")

# Usage
export_for_lightroom(
    source_dir="/photos/raw",
    target_dir="/photos/organized",
    csv_output="/exports/lightroom_import.csv"
)
```

### 2. Web Dashboard Integration

```python
#!/usr/bin/env python3
"""
Flask web interface for PhotoOrganizer
"""

from flask import Flask, render_template, request, jsonify
from photo_organizer import PhotoOrganizer
import json
from pathlib import Path

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scan', methods=['POST'])
def scan_photos():
    data = request.json
    source_dir = data.get('source_dir')
    target_dir = data.get('target_dir')
    
    if not source_dir or not target_dir:
        return jsonify({'error': 'Missing directories'}), 400
    
    try:
        organizer = PhotoOrganizer(
            source_dir=source_dir,
            target_dir=target_dir
        )
        
        organizer.scan_photos()
        
        return jsonify({
            'total_photos': len(organizer.photos),
            'duplicates': len(organizer.duplicates),
            'gps_photos': len([p for p in organizer.photos if p.gps_coords])
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/preview', methods=['POST'])
def preview_organization():
    data = request.json
    source_dir = data.get('source_dir')
    target_dir = data.get('target_dir')
    
    organizer = PhotoOrganizer(
        source_dir=source_dir,
        target_dir=target_dir
    )
    
    organizer.scan_photos()
    events = organizer.preview_organization()
    
    # Convert to JSON-serializable format
    events_data = {}
    for event_name, photos in events.items():
        events_data[event_name] = {
            'count': len(photos),
            'date_range': {
                'start': min(p.datetime for p in photos).isoformat(),
                'end': max(p.datetime for p in photos).isoformat()
            },
            'locations': list(set(p.location_name for p in photos if p.location_name))
        }
    
    return jsonify(events_data)

if __name__ == '__main__':
    app.run(debug=True)
```

This comprehensive examples document provides practical, real-world usage scenarios for PhotoOrganizer, covering everything from basic organization to advanced integrations and troubleshooting.