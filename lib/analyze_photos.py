#!/usr/bin/env python3
"""
Analyze photos in data directory and provide statistics
Shows metadata availability and recommends organization settings
"""

import sys
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add lib directory to path for imports
lib_dir = Path(__file__).parent
sys.path.insert(0, str(lib_dir))

from photo_organizer import PhotoOrganizer, PILLOW_AVAILABLE

def analyze_photos(data_dir="./data", target_dir="./results"):
    """Analyze all photos and provide statistics"""

    data_path = Path(data_dir).resolve()
    target_path = Path(target_dir).resolve()

    print("\n" + "=" * 100)
    print("PHOTO ANALYSIS REPORT")
    print("=" * 100)

    if not data_path.exists():
        print(f"Error: Data directory not found: {data_path}")
        return

    # Create organizer with fast scanning (max 4 workers for faster analysis)
    try:
        organizer = PhotoOrganizer(
            source_dir=str(data_path),
            target_dir=str(target_path),
            use_geocoding=False,  # Skip geocoding for faster analysis
            max_workers=4
        )
    except Exception as e:
        print(f"Error creating organizer: {e}")
        return

    # Scan all photos
    print(f"\nScanning photos in: {data_path}")
    print("(Geocoding disabled for faster analysis)\n")
    organizer.scan_photos()

    if not organizer.photos:
        print("No photos found in data directory")
        return

    # Statistics collection
    stats = {
        'total_photos': len(organizer.photos),
        'total_videos': 0,
        'with_gps': 0,
        'with_exif_datetime': 0,
        'with_filename_datetime': 0,
        'with_gps_and_exif': 0,
        'duplicates': 0,
        'total_size_mb': 0,
        'extensions': defaultdict(int),
        'date_range': {'earliest': None, 'latest': None},
    }

    print(f"Total items found: {stats['total_photos']}")

    # Analyze each photo
    for photo in organizer.photos:
        # Count extension
        ext = photo.filepath.suffix.lower()
        stats['extensions'][ext] += 1

        # Count videos
        if photo.is_video:
            stats['total_videos'] += 1

        # Size
        stats['total_size_mb'] += photo.file_size / (1024 * 1024)

        # Metadata tracking
        has_gps = photo.gps_coords is not None
        has_exif_dt = False
        has_filename_dt = False

        # Check if datetime came from EXIF or filename
        if photo.datetime:
            # Try to get EXIF datetime (mimics get_exif_datetime)
            exif_dt = organizer.get_exif_datetime(photo.filepath)
            if exif_dt:
                has_exif_dt = True

            # Check if filename has datetime
            filename_dt = organizer.get_datetime_from_filename(photo.filepath)
            if filename_dt:
                has_filename_dt = True

            # If no EXIF but filename has datetime, it came from filename
            if not has_exif_dt and has_filename_dt:
                has_filename_dt = True
                has_exif_dt = False
            elif has_exif_dt and not has_filename_dt:
                has_filename_dt = False
                has_exif_dt = True
            elif has_exif_dt and has_filename_dt:
                # Both exist, EXIF takes priority
                has_exif_dt = True
                has_filename_dt = False

        if has_gps:
            stats['with_gps'] += 1
        if has_exif_dt:
            stats['with_exif_datetime'] += 1
        if has_filename_dt:
            stats['with_filename_datetime'] += 1
        if has_gps and has_exif_dt:
            stats['with_gps_and_exif'] += 1

        # Track date range
        if photo.datetime:
            if stats['date_range']['earliest'] is None or photo.datetime < stats['date_range']['earliest']:
                stats['date_range']['earliest'] = photo.datetime
            if stats['date_range']['latest'] is None or photo.datetime > stats['date_range']['latest']:
                stats['date_range']['latest'] = photo.datetime

    # Count duplicates
    stats['duplicates'] = len(organizer.duplicates)

    # Print metadata statistics
    print("\n" + "-" * 100)
    print("METADATA STATISTICS")
    print("-" * 100)

    print(f"\nTotal size: {stats['total_size_mb']:.2f} MB")
    print(f"Photos: {stats['total_photos'] - stats['total_videos']}")
    print(f"Videos: {stats['total_videos']}")
    print(f"Duplicates found: {stats['duplicates']}")

    if stats['date_range']['earliest']:
        print(f"\nDate range:")
        print(f"  Earliest: {stats['date_range']['earliest'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Latest: {stats['date_range']['latest'].strftime('%Y-%m-%d %H:%M:%S')}")
        span = stats['date_range']['latest'] - stats['date_range']['earliest']
        print(f"  Span: {span.days} days")

    # File types
    print(f"\nFile types:")
    for ext, count in sorted(stats['extensions'].items(), key=lambda x: -x[1]):
        pct = 100 * count / stats['total_photos']
        print(f"  {ext}: {count} ({pct:.1f}%)")

    # Metadata availability
    print(f"\nMetadata availability:")

    gps_pct = 100 * stats['with_gps'] / stats['total_photos'] if stats['total_photos'] > 0 else 0
    exif_pct = 100 * stats['with_exif_datetime'] / stats['total_photos'] if stats['total_photos'] > 0 else 0
    filename_pct = 100 * stats['with_filename_datetime'] / stats['total_photos'] if stats['total_photos'] > 0 else 0

    print(f"  Files with GPS coordinates: {stats['with_gps']} ({gps_pct:.1f}%)")
    print(f"  Files with EXIF datetime: {stats['with_exif_datetime']} ({exif_pct:.1f}%)")
    print(f"  Files with datetime in filename: {stats['with_filename_datetime']} ({filename_pct:.1f}%)")
    print(f"  Files with GPS + EXIF datetime: {stats['with_gps_and_exif']} ({100*stats['with_gps_and_exif']/stats['total_photos']:.1f}%)")

    # Preview organization with default settings
    print("\n" + "-" * 100)
    print("ORGANIZATION PREVIEW (Default Settings)")
    print("-" * 100)
    print("Settings: same_day_hours=12, event_max_days=3, geo_radius_km=10.0")

    try:
        events = organizer.group_photos_into_events()

        single_photos = len(events.get(".", []))
        event_groups = {k: v for k, v in events.items() if k != "."}

        print(f"\nWould create:")
        print(f"  {len(event_groups)} event groups")
        print(f"  {single_photos} single photos (not part of any event)")

        # Analyze locations in events
        locations = set()
        for event_name, photos in event_groups.items():
            for photo in photos:
                if photo.location_name:
                    locations.add(photo.location_name)

        if locations:
            print(f"\nLocations found ({len(locations)}):")
            for loc in sorted(locations)[:20]:  # Show first 20
                print(f"  - {loc}")
            if len(locations) > 20:
                print(f"  ... and {len(locations) - 20} more")
        else:
            print(f"\nNo location data available (GPS geocoding disabled or no GPS data)")

        # Show sample events
        print(f"\nSample event groups (first 5):")
        for i, (event_name, photos) in enumerate(list(event_groups.items())[:5]):
            if event_name == ".":
                continue
            min_date = min(p.datetime for p in photos).strftime("%Y-%m-%d")
            max_date = max(p.datetime for p in photos).strftime("%Y-%m-%d")
            print(f"  {event_name}: {len(photos)} photos ({min_date} to {max_date})")

    except Exception as e:
        print(f"Error previewing organization: {e}")
        events = {}

    # Recommendations
    print("\n" + "=" * 100)
    print("RECOMMENDATIONS")
    print("=" * 100)

    recommendations = []

    # GPS recommendation
    if stats['with_gps'] == 0:
        recommendations.append("--no-geocoding (No GPS data found - skip geocoding)")
    elif gps_pct < 20:
        recommendations.append("--no-geocoding (Only {:.1f}% have GPS - geocoding may be slow)".format(gps_pct))
    else:
        recommendations.append("(GPS geocoding will be used for location-based grouping)")

    # EXIF recommendation
    if stats['with_exif_datetime'] < 50:
        recommendations.append("--addexif (Only {:.1f}% have EXIF datetime)".format(exif_pct))

    # Event settings based on photo count and date span
    if events:
        event_count = len([k for k in events.keys() if k != "."])
        avg_photos_per_event = (stats['total_photos'] - single_photos) / event_count if event_count > 0 else 0

        if avg_photos_per_event < 3:
            recommendations.append("--min-event-photos 3 (Small events detected)")
        elif avg_photos_per_event > 50:
            recommendations.append("--min-event-photos 20 (Large events detected)")

    print("\nSuggested switches:")
    for rec in recommendations:
        print(f"  {rec}")

    # Generate command line
    print("\n" + "-" * 100)
    print("SUGGESTED COMMAND")
    print("-" * 100)

    cmd_switches = []
    if stats['with_gps'] == 0 or gps_pct < 20:
        cmd_switches.append("--no-geocoding")
    if stats['with_exif_datetime'] < 50:
        cmd_switches.append("--addexif")
    if event_count > 0 and single_photos > 0:
        min_photos = max(3, int(stats['total_photos'] / (event_count + 5)))
        if min_photos != 3:
            cmd_switches.append(f"--min-event-photos {min_photos}")

    cmd_base = f"organize.bat {data_dir} {target_dir}"
    if cmd_switches:
        cmd_line = cmd_base + " " + " ".join(cmd_switches)
    else:
        cmd_line = cmd_base + " (using default settings)"

    print(f"\n{cmd_line}")

    print("\nWithout --execute flag, this will show a preview first.")
    print("Add --execute to actually move files.")
    print("Add --generate-script to create a .sh/.bat script for later execution.")

    print("\n" + "=" * 100 + "\n")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analyze photos in data directory")
    parser.add_argument("data_dir", nargs="?", default="./data", help="Data directory to analyze")
    parser.add_argument("target_dir", nargs="?", default="./results", help="Target directory for organization")

    args = parser.parse_args()

    analyze_photos(args.data_dir, args.target_dir)
