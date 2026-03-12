"""
Cache management library for updating file paths in cached metadata.
"""

import json
import os
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


class CacheManager:
    """Manages cache files and updates file paths."""

    def __init__(self, cache_dir: str):
        """
        Initialize cache manager.

        Args:
            cache_dir: Path to the cache directory
        """
        self.cache_dir = Path(cache_dir)
        self.cache_files = self._find_cache_files()

    def _find_cache_files(self) -> List[Path]:
        """Find all JSON cache files in the cache directory."""
        if not self.cache_dir.exists():
            raise ValueError(f"Cache directory does not exist: {self.cache_dir}")

        cache_files = list(self.cache_dir.glob("*.json"))
        if not cache_files:
            raise ValueError(f"No JSON cache files found in {self.cache_dir}")

        return cache_files

    def scan_folder(self, folder_path: str) -> Dict[str, Path]:
        """
        Scan a folder and return all files with their paths.

        Args:
            folder_path: Path to the folder to scan

        Returns:
            Dictionary with filename as key and full path as value
        """
        folder = Path(folder_path)
        if not folder.exists():
            raise ValueError(f"Folder does not exist: {folder_path}")

        files = {}
        for file_path in folder.rglob("*"):
            if file_path.is_file():
                files[file_path.name] = file_path

        return files

    def _is_video(self, file_path: Path) -> bool:
        """Check if file is a video based on extension."""
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v'}
        return file_path.suffix.lower() in video_extensions

    def _get_file_hash(self, file_path: Path, algorithm: str = 'sha256') -> str:
        """
        Calculate file hash.

        Args:
            file_path: Path to the file
            algorithm: Hash algorithm to use (default: sha256)

        Returns:
            Hex string of the file hash
        """
        hasher = hashlib.new(algorithm)
        try:
            with open(file_path, 'rb') as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            if False:  # Set to True for verbose output
                print(f"Warning: Could not hash {file_path}: {e}")
            return ""

    def _hash_file_worker(self, file_path: Path) -> Tuple[Path, str]:
        """Worker function for parallel hashing."""
        return file_path, self._get_file_hash(file_path)

    def _get_file_metadata(self, file_path: Path, file_hash: str = "") -> dict:
        """
        Extract metadata from a file.

        Args:
            file_path: Path to the file
            file_hash: Pre-computed file hash (optional)

        Returns:
            Dictionary with file metadata
        """
        try:
            stat = file_path.stat()
            # Try to get modification time, fall back to creation time
            mtime = datetime.fromtimestamp(stat.st_mtime).isoformat()

            return {
                "filepath": str(file_path),
                "datetime": mtime,
                "file_hash": file_hash,
                "file_size": stat.st_size,
                "is_video": self._is_video(file_path)
            }
        except Exception as e:
            print(f"Warning: Could not extract metadata for {file_path}: {e}")
            return None

    def _compute_file_hashes_parallel(self, file_paths: List[Path], max_workers: int = 4) -> Dict[Path, str]:
        """
        Compute file hashes in parallel.

        Args:
            file_paths: List of file paths to hash
            max_workers: Maximum number of parallel workers

        Returns:
            Dictionary mapping file path to hash
        """
        hashes = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self._hash_file_worker, fp): fp for fp in file_paths}
            for future in as_completed(futures):
                try:
                    file_path, file_hash = future.result()
                    hashes[file_path] = file_hash
                except Exception as e:
                    print(f"Warning: Error hashing file: {e}")
        return hashes

    def update_cache(self, new_folder: str, verbose: bool = False) -> Dict[str, any]:
        """
        Update cache files with new file paths from the specified folder.
        Also adds new files found in the folder to the cache.

        Args:
            new_folder: Path to the new folder containing files
            verbose: Print detailed information about updates

        Returns:
            Dictionary with update statistics
        """
        # Scan the new folder for files
        new_files = self.scan_folder(new_folder)
        stats = {
            "total_files_found": len(new_files),
            "total_cache_entries": 0,
            "paths_updated": 0,
            "new_files_added": 0,
            "files_not_found": [],
            "updated_cache_files": [],
            "files_added": []
        }

        # Track which files are in the cache
        cached_filenames = set()

        # Process each cache file
        for cache_file in self.cache_files:
            try:
                # Try UTF-8 first, fall back to UTF-8 with error handling
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                except UnicodeDecodeError:
                    # Fall back to UTF-8 with replace errors
                    with open(cache_file, 'r', encoding='utf-8', errors='replace') as f:
                        cache_data = json.load(f)

                if verbose:
                    print(f"\nProcessing cache file: {cache_file.name}")

                # Check if this cache has a 'photos' key (array of entries)
                if isinstance(cache_data, dict) and 'photos' in cache_data:
                    entries = cache_data['photos']
                    stats["total_cache_entries"] += len(entries)

                    # Update each entry and track filenames
                    for entry in entries:
                        if 'filepath' in entry:
                            old_path = Path(entry['filepath'])
                            filename = old_path.name
                            cached_filenames.add(filename)

                            # Search for the file in the new folder
                            if filename in new_files:
                                new_path = new_files[filename]
                                if entry['filepath'] != str(new_path):
                                    if verbose:
                                        print(f"  Updated: {filename}")
                                        print(f"    Old: {entry['filepath']}")
                                        print(f"    New: {new_path}")
                                    entry['filepath'] = str(new_path)
                                    stats["paths_updated"] += 1
                            else:
                                # File not found in new folder
                                stats["files_not_found"].append({
                                    "filename": filename,
                                    "old_path": entry['filepath']
                                })

                    # Find all new files (not in cache)
                    new_file_paths = []
                    new_file_mapping = {}  # Maps Path to filename
                    for filename, file_path in new_files.items():
                        if filename not in cached_filenames:
                            new_file_paths.append(file_path)
                            new_file_mapping[file_path] = filename

                    # Compute hashes in parallel for new files
                    if new_file_paths:
                        if verbose:
                            print(f"  Computing hashes for {len(new_file_paths)} new files in parallel...")
                        file_hashes = self._compute_file_hashes_parallel(new_file_paths)

                        # Add new files with their computed hashes
                        for file_path, file_hash in file_hashes.items():
                            filename = new_file_mapping[file_path]
                            metadata = self._get_file_metadata(file_path, file_hash=file_hash)
                            if metadata:
                                entries.append(metadata)
                                stats["new_files_added"] += 1
                                stats["files_added"].append(filename)
                                if verbose:
                                    print(f"  Added: {filename}")
                                    print(f"    Path: {file_path}")

                    # Update metadata if it exists
                    if 'metadata' in cache_data:
                        cache_data['metadata']['last_updated'] = datetime.now().isoformat()

                    # Save the updated cache file
                    self._save_cache_file(cache_file, cache_data)
                    stats["updated_cache_files"].append(cache_file.name)

                    if verbose:
                        print(f"  Saved: {cache_file.name}")

            except json.JSONDecodeError as e:
                print(f"Warning: Invalid JSON in {cache_file.name}: {e}")
                print(f"  Skipping {cache_file.name}")
            except Exception as e:
                print(f"Warning: Error processing {cache_file.name}: {e}")
                print(f"  Skipping {cache_file.name}")

        return stats

    def _save_cache_file(self, cache_file: Path, data: dict) -> None:
        """
        Save cache data to a JSON file.

        Args:
            cache_file: Path to the cache file
            data: Dictionary containing cache data
        """
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def print_stats(self, stats: Dict) -> None:
        """Print update statistics in a readable format."""
        print("\n" + "="*60)
        print("CACHE UPDATE SUMMARY")
        print("="*60)
        print(f"Files found in new folder: {stats['total_files_found']}")
        print(f"Total cache entries (before): {stats['total_cache_entries']}")
        print(f"Paths updated: {stats['paths_updated']}")
        print(f"New files added: {stats['new_files_added']}")
        print(f"Files not found in new location: {len(stats['files_not_found'])}")
        print(f"Cache files updated: {', '.join(stats['updated_cache_files'])}")

        if stats['files_not_found']:
            print("\nFiles no longer in new folder:")
            for entry in stats['files_not_found'][:10]:  # Show first 10
                print(f"  - {entry['filename']}")
            if len(stats['files_not_found']) > 10:
                print(f"  ... and {len(stats['files_not_found']) - 10} more")

        if stats['files_added']:
            print("\nNew files added to cache:")
            for filename in stats['files_added'][:10]:  # Show first 10
                print(f"  + {filename}")
            if len(stats['files_added']) > 10:
                print(f"  ... and {len(stats['files_added']) - 10} more")

    def build_permanent_cache(self) -> bool:
        """
        Build a permanent CSV cache from all JSON cache files.

        Combines metadata and photo entries from all cache files into a single CSV file.
        Filename format: photo_cache_permanent_YYYYMMDD_HHMMSS.csv

        Returns:
            True if successful, False otherwise
        """
        import csv

        if not self.cache_files:
            print("No cache files found")
            return False

        try:
            # Collect all data
            all_rows = []
            headers = set()

            # Process each cache file
            for cache_file in self.cache_files:
                try:
                    # Load cache file
                    try:
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                    except UnicodeDecodeError:
                        with open(cache_file, 'r', encoding='utf-8', errors='replace') as f:
                            cache_data = json.load(f)

                    if not isinstance(cache_data, dict):
                        continue

                    # Extract metadata
                    metadata = cache_data.get('metadata', {})
                    photos = cache_data.get('photos', [])

                    print(f"  Processing {cache_file.name}: {len(photos)} photos")

                    # Combine metadata with each photo entry
                    for photo in photos:
                        if not isinstance(photo, dict):
                            continue

                        # Create row with metadata + photo data
                        row = {
                            'created': metadata.get('created', ''),
                            'source_dir': metadata.get('source_dir', ''),
                            'target_dir': metadata.get('target_dir', ''),
                            'total_photos': metadata.get('total_photos', ''),
                            'duplicates_count': metadata.get('duplicates_count', ''),
                            'last_updated': metadata.get('last_updated', ''),
                            'filepath': photo.get('filepath', ''),
                            'datetime': photo.get('datetime', ''),
                            'file_hash': photo.get('file_hash', ''),
                            'file_size': photo.get('file_size', ''),
                            'is_video': photo.get('is_video', ''),
                        }

                        all_rows.append(row)
                        headers.update(row.keys())

                except json.JSONDecodeError as e:
                    print(f"  Warning: Invalid JSON in {cache_file.name}: {e}")
                except Exception as e:
                    print(f"  Warning: Error processing {cache_file.name}: {e}")

            if not all_rows:
                print("No photo entries found to export")
                return False

            # Define column order
            column_order = [
                'created',
                'source_dir',
                'target_dir',
                'total_photos',
                'duplicates_count',
                'last_updated',
                'filepath',
                'datetime',
                'file_hash',
                'file_size',
                'is_video',
            ]

            # Create output filename with timestamp
            now = datetime.now()
            timestamp = now.strftime('%Y%m%d_%H%M%S')
            output_file = self.cache_dir / f"photo_cache_permanent_{timestamp}.csv"

            # Write CSV file
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=column_order, delimiter=';')
                writer.writeheader()
                writer.writerows(all_rows)

            print(f"\n[SUCCESS] Permanent cache created: {output_file}")
            print(f"   Total entries: {len(all_rows)}")
            print(f"   Columns: {len(column_order)}")

            return True

        except Exception as e:
            print(f"[ERROR] Error creating permanent cache: {e}")
            return False


def main():
    """Main entry point for the cache update script."""
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description='Update cache file paths based on a new folder location, or build permanent cache'
    )
    parser.add_argument(
        '--folder',
        help='Path to the folder containing files to update in cache'
    )
    parser.add_argument(
        '--cache-dir',
        help='Path to the cache directory (default: PROJECT_CACHE env var)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print detailed information about updates'
    )
    parser.add_argument(
        '--to-permanent',
        action='store_true',
        help='Build permanent CSV cache from all JSON cache files'
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.folder and not args.to_permanent:
        parser.print_help()
        print("\nError: Either --folder or --to-permanent must be specified")
        sys.exit(1)

    # Get cache directory
    cache_dir = args.cache_dir or os.environ.get('PROJECT_CACHE')
    if not cache_dir:
        print("Error: Cache directory not specified. Use --cache-dir or set PROJECT_CACHE")
        sys.exit(1)

    try:
        manager = CacheManager(cache_dir)

        if args.to_permanent:
            # Build permanent CSV cache
            print("="*60)
            print("Building Permanent CSV Cache")
            print("="*60)
            success = manager.build_permanent_cache()
            sys.exit(0 if success else 1)

        else:
            # Update cache with new folder
            stats = manager.update_cache(args.folder, verbose=args.verbose)
            manager.print_stats(stats)

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
