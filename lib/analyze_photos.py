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

def analyze_photos_quick(data_dir=None):
    """Quick analysis of photo files without detailed EXIF processing"""

    # Use environment variable as default
    if data_dir is None:
        data_dir = os.environ.get('PROJECT_DATA', './data')

    data_path = Path(data_dir).resolve()

    print("\n" + "=" * 100)
    print("QUICK PHOTO ANALYSIS")
    print("=" * 100)

    if not data_path.exists():
        print(f"Error: Data directory not found: {data_path}")
        return

    print(f"\nScanning: {data_path}\n")

    # File statistics
    stats = {
        'total_files': 0,
        'by_extension': defaultdict(int),
        'total_size_mb': 0,
        'photos': 0,
        'videos': 0,
        'with_datetime_pattern': 0,
        'sample_files': []
    }

    # Supported extensions
    photo_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.raw', '.heic'}
    video_exts = {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v', '.webm'}

    # Scan files
    for filepath in sorted(data_path.rglob('*')):
        # Validate: is_file() checks during scan, exists() prevents race conditions
        if not filepath.is_file() or not filepath.exists():
            continue

        ext = filepath.suffix.lower()
        if ext not in photo_exts and ext not in video_exts:
            continue

        stats['total_files'] += 1
        stats['by_extension'][ext] += 1
        stats['total_size_mb'] += filepath.stat().st_size / (1024 * 1024)

        if ext in photo_exts:
            stats['photos'] += 1
        elif ext in video_exts:
            stats['videos'] += 1

        # Check for datetime pattern in filename
        name = filepath.stem
        if any(c.isdigit() for c in name):
            stats['with_datetime_pattern'] += 1

        # Keep first few samples
        if len(stats['sample_files']) < 5:
            stats['sample_files'].append(filepath.name)

    # Display results
    print(f"Total files found: {stats['total_files']}")
    print(f"Total size: {stats['total_size_mb']:.2f} MB\n")

    print("File types:")
    for ext in sorted(stats['by_extension'].keys()):
        count = stats['by_extension'][ext]
        pct = 100 * count / stats['total_files'] if stats['total_files'] > 0 else 0
        print(f"  {ext}: {count} ({pct:.1f}%)")

    print(f"\nBreakdown:")
    print(f"  Photos: {stats['photos']} ({100*stats['photos']/stats['total_files']:.1f}%)" if stats['total_files'] > 0 else "  Photos: 0")
    print(f"  Videos: {stats['videos']} ({100*stats['videos']/stats['total_files']:.1f}%)" if stats['total_files'] > 0 else "  Videos: 0")

    print(f"\nMetadata:")
    pct_datetime = 100 * stats['with_datetime_pattern'] / stats['total_files'] if stats['total_files'] > 0 else 0
    print(f"  Files with datetime pattern in name: {stats['with_datetime_pattern']} ({pct_datetime:.1f}%)")

    if stats['sample_files']:
        print(f"\nSample filenames:")
        for name in stats['sample_files']:
            print(f"  - {name}")

    print("\n" + "=" * 100)
    print("RECOMMENDATIONS")
    print("=" * 100)

    recommendations = []
    if pct_datetime > 90:
        recommendations.append("High datetime pattern in filenames - good for organization")
    elif pct_datetime > 50:
        recommendations.append("Most files have datetime in filename - this will help with sorting")
    else:
        recommendations.append("WARNING: Less than 50% of files have datetime info in filename")

    if stats['videos'] > stats['photos'] * 0.1:
        recommendations.append(f"Many videos detected ({stats['videos']}) - might need video metadata extraction")

    print("\nAnalysis:")
    for rec in recommendations:
        print(f"  - {rec}")

    print("\n" + "-" * 100)
    print("SUGGESTED COMMAND FOR ORGANIZATION")
    print("-" * 100)

    try:
        rel_path = data_path.relative_to(data_path.parent.parent)
        cmd_path = str(rel_path).replace('\\', '/').strip('.')
    except:
        cmd_path = str(data_path)

    cmd_switches = []
    if stats['videos'] > 0:
        cmd_switches.append("--addexif")

    if cmd_switches:
        cmd = f"organize.bat {cmd_path} results {' '.join(cmd_switches)}"
    else:
        cmd = f"organize.bat {cmd_path} results"

    print(f"\n{cmd}\n")
    print("Options:")
    print("  - Add --execute to actually move files")
    print("  - Add --generate-script to create a .bat/.sh for later execution")
    print("  - Add --no-geocoding if you don't have GPS data or want faster processing")

    print("\n" + "=" * 100 + "\n")


def analyze_photos(data_dir=None, target_dir=None, add_missing_geolocations=False):
    """Detailed analysis with full EXIF/metadata processing"""

    # Use environment variables as defaults
    if data_dir is None:
        data_dir = os.environ.get('PROJECT_DATA', './data')
    if target_dir is None:
        target_dir = os.environ.get('PROJECT_WORK', './results')

    data_path = Path(data_dir).resolve()
    target_path = Path(target_dir).resolve()

    print("\n" + "=" * 100)
    print("PHOTO ANALYSIS REPORT (DETAILED)")
    print("=" * 100)

    if not data_path.exists():
        print(f"Error: Data directory not found: {data_path}")
        return

    # Create organizer with fast scanning (max 4 workers for faster analysis)
    # Enable geocoding if --add-missing-geolocations is set
    try:
        organizer = PhotoOrganizer(
            source_dir=str(data_path),
            target_dir=str(target_path),
            use_geocoding=add_missing_geolocations,  # Enable only if needed
            max_workers=4
        )
    except Exception as e:
        print(f"Error creating organizer: {e}")
        return

    # Scan all photos
    print(f"\nScanning photos in: {data_path}")
    if add_missing_geolocations:
        print("(Geocoding enabled for missing location lookup)\n")
    else:
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

    # Display location cache information
    city_coords = {}  # Initialize for later use in outlier analysis

    if organizer.location_cache:
        print("\n" + "-" * 100)
        print("CACHED LOCATION INFORMATION")
        print("-" * 100)

        # Filter out None values (unsuccessful geocoding)
        cached_locations = [(coords, city) for coords, city in organizer.location_cache.items() if city is not None]

        # Group coordinates by city
        for (lat, lon), city in cached_locations:
            if city not in city_coords:
                city_coords[city] = []
            city_coords[city].append((lat, lon))

        print(f"\nCached city names ({len(cached_locations)}) - Min/Max coordinates:")
        for city in sorted(city_coords.keys()):
            coords_list = city_coords[city]
            lats = [c[0] for c in coords_list]
            lons = [c[1] for c in coords_list]

            min_lat, max_lat = min(lats), max(lats)
            min_lon, max_lon = min(lons), max(lons)

            print(f"  {city:30} Lat: {min_lat:.4f} - {max_lat:.4f}, Lon: {min_lon:.4f} - {max_lon:.4f}")

    # Find coordinates without location names
    coords_without_names = set()
    for photo in organizer.photos:
        if photo.gps_coords and not photo.location_name:
            coords_without_names.add(photo.gps_coords)

    if coords_without_names:
        print("\n" + "-" * 100)
        print("COORDINATES WITHOUT LOCATION NAMES")
        print("-" * 100)
        print(f"\nFound {len(coords_without_names)} unique coordinates without location names:")
        for lat, lon in sorted(coords_without_names)[:20]:  # Show first 20
            print(f"  ({lat:.4f}, {lon:.4f})")
        if len(coords_without_names) > 20:
            print(f"  ... and {len(coords_without_names) - 20} more")

        if not add_missing_geolocations:
            print("\nTip: Use --add-missing-geolocations to geocode these coordinates")
        else:
            print("\n🌍 Geocoding missing locations...")

            # Import requests for geocoding
            try:
                import requests
                import time
            except ImportError:
                print("❌ Error: 'requests' library required for geocoding")
                print("Install with: pip install requests")
            else:
                geocoded_count = 0
                failed_count = 0

                for lat, lon in sorted(coords_without_names):
                    # Round coords to match cache format (100m accuracy)
                    rounded_coords = (round(lat, 3), round(lon, 3))

                    # Check if already in cache
                    if rounded_coords in organizer.location_cache:
                        continue

                    # Geocode using organizer's method
                    location_name = organizer.get_location_name((lat, lon))

                    if location_name and location_name != "Unknown":
                        geocoded_count += 1
                        print(f"  ✅ ({lat:.4f}, {lon:.4f}) -> {location_name}")
                    else:
                        failed_count += 1
                        print(f"  ❌ ({lat:.4f}, {lon:.4f}) -> Failed to geocode")

                print(f"\n✅ Geocoded: {geocoded_count}")
                print(f"❌ Failed: {failed_count}")

                # Save to config file
                if geocoded_count > 0:
                    organizer.save_geo_locations_to_config()
                    print(f"\n💾 Saved {len(organizer.location_cache)} locations to cfg/geo_coords.cfg")

    # Analyze coordinate outliers per location using DBSCAN
    if city_coords:
        print("\n" + "-" * 100)
        print("COORDINATE OUTLIERS ANALYSIS (DBSCAN Clustering)")
        print("-" * 100)

        try:
            from sklearn.cluster import DBSCAN
            import numpy as np

            outliers_found = False

            for city in sorted(city_coords.keys()):
                coords_list = city_coords[city]

                # Skip if too few coordinates
                if len(coords_list) < 3:
                    continue

                # Convert to numpy array for DBSCAN
                coords_array = np.array(coords_list)

                # DBSCAN with eps in degrees (~1.1 km per degree at equator)
                # eps=0.01 degrees ≈ 1.1 km
                clustering = DBSCAN(eps=0.01, min_samples=2).fit(coords_array)
                labels = clustering.labels_

                # Find outliers (label == -1)
                outlier_indices = np.where(labels == -1)[0]

                if len(outlier_indices) > 0:
                    outliers_found = True
                    print(f"\n  {city}:")

                    # Calculate center of main cluster
                    main_cluster_mask = labels >= 0
                    if main_cluster_mask.any():
                        main_cluster_coords = coords_array[main_cluster_mask]
                        center_lat = np.mean(main_cluster_coords[:, 0])
                        center_lon = np.mean(main_cluster_coords[:, 1])
                    else:
                        center_lat = np.mean(coords_array[:, 0])
                        center_lon = np.mean(coords_array[:, 1])

                    for idx in outlier_indices:
                        lat, lon = coords_list[idx]
                        # Calculate distance from center in km (rough approximation)
                        lat_diff = (lat - center_lat) * 111.0  # 1 degree ≈ 111 km
                        lon_diff = (lon - center_lon) * 111.0 * np.cos(np.radians(center_lat))
                        distance_km = np.sqrt(lat_diff ** 2 + lon_diff ** 2)

                        print(f"    ⚠️  Outlier: ({lat:.4f}, {lon:.4f}) - {distance_km:.1f} km from center")

            if not outliers_found:
                print("\n  No significant outliers found - all coordinates are well-clustered per location")

        except ImportError:
            print("\n  Note: scikit-learn required for DBSCAN analysis.")
            print("  Install with: pip install scikit-learn")

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
    parser.add_argument("data_dir", nargs="?", help="Data directory to analyze (default: PROJECT_DATA env var or ./data)")
    parser.add_argument("target_dir", nargs="?", help="Target directory for organization (default: PROJECT_WORK env var or ./results)")
    parser.add_argument("--quick", action="store_true", help="Quick analysis (files only, no EXIF processing)")
    parser.add_argument("--add-missing-geolocations", action="store_true",
                        help="Geocode coordinates without location names and save to cfg/geo_coords.cfg")

    args = parser.parse_args()

    if args.quick:
        analyze_photos_quick(args.data_dir)
    else:
        analyze_photos(args.data_dir, args.target_dir, args.add_missing_geolocations)
