"""
Cache management library for updating file paths in cached metadata.
"""

import json
import os
import hashlib
import csv
from pathlib import Path
from typing import Dict, List, Tuple, Set
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import utilities
from utils import get_file_hash, write_json_file


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

    def _build_file_inventory(self, folder_path: str, verbose: bool = False) -> Dict[str, list]:
        """
        Build a complete recursive file inventory of a folder.

        Unlike scan_folder, this handles duplicate filenames by storing all occurrences.

        Args:
            folder_path: Path to the folder to scan
            verbose: Print detailed information about files found

        Returns:
            Dictionary with filename as key and list of Path objects as values
        """
        folder = Path(folder_path)
        if not folder.exists():
            raise ValueError(f"Folder does not exist: {folder_path}")

        file_inventory = {}
        total_files = 0

        for file_path in folder.rglob("*"):
            if file_path.is_file():
                filename = file_path.name

                # Store as list to handle duplicate filenames
                if filename not in file_inventory:
                    file_inventory[filename] = []

                file_inventory[filename].append(file_path)
                total_files += 1

                if verbose:
                    rel_path = file_path.relative_to(folder)
                    print(f"    Found: {rel_path}")

        if verbose:
            print(f"\n  Total files found: {total_files}")
            duplicate_count = sum(1 for paths in file_inventory.values() if len(paths) > 1)
            if duplicate_count > 0:
                print(f"  Files with duplicate names: {duplicate_count}")
                for filename, paths in file_inventory.items():
                    if len(paths) > 1:
                        print(f"    - {filename}: {len(paths)} occurrences")

        return file_inventory

    def _is_video(self, file_path: Path) -> bool:
        """Check if file is a video based on extension."""
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v'}
        return file_path.suffix.lower() in video_extensions

    def _hash_file_worker(self, file_path: Path) -> Tuple[Path, str]:
        """Worker function for parallel hashing."""
        return file_path, get_file_hash(file_path)

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
        # Build complete file inventory (handles duplicate filenames)
        if verbose:
            print("\nBuilding file inventory from new folder...")
        file_inventory = self._build_file_inventory(new_folder, verbose=verbose)

        # Also scan for backward compatibility (single file per name)
        new_files = self.scan_folder(new_folder)

        # Count total unique files (accounting for duplicates)
        total_files_count = sum(len(paths) for paths in file_inventory.values())

        stats = {
            "total_files_found": total_files_count,
            "total_unique_filenames": len(file_inventory),
            "total_cache_entries": 0,
            "paths_updated": 0,
            "new_files_added": 0,
            "files_not_found": [],
            "files_with_duplicates_in_target": [],
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
                            if filename in file_inventory:
                                matching_paths = file_inventory[filename]

                                # If multiple files with same name, use the first match
                                # or try to match by file size as a heuristic
                                new_path = matching_paths[0]

                                if len(matching_paths) > 1:
                                    if 'file_size' in entry:
                                        # Try to find matching file by size
                                        for candidate_path in matching_paths:
                                            try:
                                                if candidate_path.stat().st_size == entry['file_size']:
                                                    new_path = candidate_path
                                                    break
                                            except Exception:
                                                pass

                                    # Report duplicate detection
                                    if filename not in [f['filename'] for f in stats["files_with_duplicates_in_target"]]:
                                        stats["files_with_duplicates_in_target"].append({
                                            "filename": filename,
                                            "count": len(matching_paths)
                                        })

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
                    write_json_file(cache_file, cache_data)
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


    def print_stats(self, stats: Dict) -> None:
        """Print update statistics in a readable format."""
        print("\n" + "="*60)
        print("CACHE UPDATE SUMMARY")
        print("="*60)
        print(f"Files found in new folder: {stats['total_files_found']}")
        print(f"Unique filenames: {stats['total_unique_filenames']}")
        print(f"Total cache entries (before): {stats['total_cache_entries']}")
        print(f"Paths updated: {stats['paths_updated']}")
        print(f"New files added: {stats['new_files_added']}")
        print(f"Files not found in new location: {len(stats['files_not_found'])}")
        print(f"Cache files updated: {', '.join(stats['updated_cache_files'])}")

        if stats['files_with_duplicates_in_target']:
            print(f"\nFiles with duplicate names in target folder: {len(stats['files_with_duplicates_in_target'])}")
            for entry in stats['files_with_duplicates_in_target'][:5]:  # Show first 5
                print(f"  - {entry['filename']}: {entry['count']} occurrences")
            if len(stats['files_with_duplicates_in_target']) > 5:
                print(f"  ... and {len(stats['files_with_duplicates_in_target']) - 5} more")

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

    def _read_archive_folders_from_config(self, config_path: str) -> List[str]:
        """Read archive_folder section paths from config file."""
        import configparser
        config = configparser.ConfigParser()
        config.read(config_path, encoding='utf-8')
        folders = []
        if 'archive_folder' in config:
            for key, value in config['archive_folder'].items():
                folders.append(value.strip())
        return folders

    def check_and_promote_to_permanent(
        self,
        config_path: str,
        data_dir: str = None,
        few_files_threshold: int = 20,
        verbose: bool = False,
        dry_run: bool = False
    ) -> bool:
        """
        Check if all JSON cache entries are confirmed in archive folders, then
        promote them to the permanent CSV and archive the JSON file.

        Steps:
        1. Optionally check data_dir file count as a precondition indicator.
        2. Load all JSON cache entries.
        3. Read archive_folder paths from the config file.
        4. Categorise entries: confirmed in archive / path matches but file missing / not in archive.
        5. Promote only if every entry resolves to an archive path.
        6. Append confirmed entries to the most recent permanent CSV (or create a new one).
        7. Rename the processed JSON to *.json.promoted so it is no longer re-loaded.

        Args:
            config_path:          Path to photo_organizer.cfg.
            data_dir:             Source/data directory (optional – used for file-count info).
            few_files_threshold:  Warn if data_dir has more files than this (default 20).
            verbose:              Print individual problem files.
            dry_run:              Report only, make no changes.

        Returns:
            True if promotion happened (or would happen in dry_run), False otherwise.
        """
        print("\n" + "=" * 60)
        print("CACHE-PRÜFUNG & PROMOTE -> PERMANENT CSV")
        print("=" * 60)

        # --- optional: data_dir file count --------------------------------
        if data_dir:
            data_path = Path(data_dir)
            if data_path.exists():
                data_files = [f for f in data_path.iterdir() if f.is_file()]
                n = len(data_files)
                tag = "[OK]" if n <= few_files_threshold else "[WARN]"
                print(f"\n{tag} Quelldateien im data-Ordner: {n} (Schwellwert: {few_files_threshold})")
            else:
                print(f"\n[WARN] Quellordner nicht gefunden: {data_dir}")

        # --- load JSON cache entries ---------------------------------------
        json_files = [f for f in self.cache_files if f.suffix == '.json']
        if not json_files:
            print("\n[ERROR] Keine JSON-Cache-Dateien gefunden.")
            return False

        all_entries: List[tuple] = []   # (entry_dict, json_path)
        for json_file in sorted(json_files):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                photos = cache_data.get('photos', [])
                print(f"\n  [FILE] {json_file.name}: {len(photos)} Eintraege")
                for photo in photos:
                    all_entries.append((photo, json_file))
            except Exception as e:
                print(f"  [WARN] Fehler beim Laden von {json_file.name}: {e}")

        if not all_entries:
            print("\n[ERROR] Keine Eintraege in JSON-Cache.")
            return False
        print(f"\n  Gesamt: {len(all_entries)} Eintraege in JSON-Cache")

        # --- read archive folders from config ----------------------------
        archive_folders = self._read_archive_folders_from_config(config_path)
        if not archive_folders:
            print(f"\n[ERROR] Keine [archive_folder]-Sektion in Config gefunden: {config_path}")
            return False

        print(f"\n  Archiv-Ordner:")
        for af in archive_folders:
            tag = "[OK]" if Path(af).exists() else "[MISSING]"
            print(f"    {tag}  {af}")

        # Normalise separators for prefix comparison
        archive_prefixes = [af.replace('/', '\\').rstrip('\\') + '\\' for af in archive_folders]

        # --- categorise entries -------------------------------------------
        confirmed: List[tuple] = []    # in archive path AND file exists
        missing: List[tuple] = []      # in archive path BUT file missing on disk
        not_archived: List[tuple] = [] # filepath NOT under any archive folder

        for entry, json_file in all_entries:
            filepath = entry.get('filepath', '')
            if not filepath:
                continue
            fp_norm = filepath.replace('/', '\\')
            in_archive = any(
                fp_norm.lower().startswith(prefix.lower())
                for prefix in archive_prefixes
            )
            if in_archive:
                if Path(filepath).exists():
                    confirmed.append((entry, json_file))
                else:
                    missing.append((entry, json_file))
            else:
                not_archived.append((entry, json_file))

        print(f"\n{'=' * 60}")
        print("ERGEBNIS")
        print(f"{'=' * 60}")
        print(f"  [OK]      Im Archiv vorhanden:     {len(confirmed)}")
        print(f"  [MISSING] Im Archiv-Pfad, fehlt:   {len(missing)}")
        print(f"  [OUT]     Nicht im Archiv-Pfad:    {len(not_archived)}")

        if verbose:
            if missing:
                print("\n  Dateien im Archiv-Pfad aber nicht (mehr) vorhanden:")
                for entry, _ in missing[:10]:
                    print(f"    - {entry['filepath']}")
                if len(missing) > 10:
                    print(f"    ... und {len(missing) - 10} weitere")
            if not_archived:
                print("\n  Dateien ausserhalb der Archiv-Ordner:")
                for entry, _ in not_archived[:10]:
                    print(f"    - {entry['filepath']}")
                if len(not_archived) > 10:
                    print(f"    ... und {len(not_archived) - 10} weitere")

        # --- decide whether to promote ------------------------------------
        if not_archived:
            print(f"\n[WARN] {len(not_archived)} Eintraege sind noch nicht im Archiv-Pfad.")
            print("   Fuehre zuerst photo_organizer.py --execute aus und aktualisiere die")
            print("   Cache-Pfade mit cache.py --folder <archiv>.")
            return False

        promotable = confirmed + missing
        if not promotable:
            print("\n[ERROR] Keine Eintraege zum Promoten gefunden.")
            return False

        print(f"\n  {len(promotable)} Eintraege werden in permanenten Cache uebertragen...")
        if dry_run:
            print("   [DRY-RUN] Keine Aenderungen vorgenommen.")
            return True

        # --- write to permanent CSV --------------------------------------
        column_order = [
            'created', 'source_dir', 'target_dir', 'total_photos',
            'duplicates_count', 'last_updated', 'filepath', 'datetime',
            'file_hash', 'file_size', 'is_video',
        ]
        now = datetime.now()
        rows = []
        for entry, _ in promotable:
            rows.append({
                'created': now.isoformat(),
                'source_dir': '',
                'target_dir': '',
                'total_photos': '',
                'duplicates_count': '',
                'last_updated': now.isoformat(),
                'filepath': entry.get('filepath', ''),
                'datetime': entry.get('datetime', ''),
                'file_hash': entry.get('file_hash', ''),
                'file_size': entry.get('file_size', ''),
                'is_video': entry.get('is_video', ''),
            })

        permanent_files = self._find_permanent_cache_files()
        if permanent_files:
            target_csv = permanent_files[0]
            print(f"  -> Fuege hinzu zu: {target_csv.name}")
            try:
                with open(target_csv, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=column_order, delimiter=';')
                    writer.writerows(rows)
                print(f"  [OK] {len(rows)} Eintraege hinzugefuegt.")
            except Exception as e:
                print(f"  [ERROR] Fehler beim Schreiben: {e}")
                return False
        else:
            timestamp = now.strftime('%Y%m%d_%H%M%S')
            output_file = self.cache_dir / f"photo_cache_permanent_{timestamp}.csv"
            print(f"  -> Erstelle: {output_file.name}")
            try:
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=column_order, delimiter=';')
                    writer.writeheader()
                    writer.writerows(rows)
                print(f"  [OK] Erstellt mit {len(rows)} Eintraegen.")
            except Exception as e:
                print(f"  [ERROR] Fehler beim Erstellen: {e}")
                return False

        # --- archive the JSON file(s) ------------------------------------
        promoted_json_files: Set[Path] = {jf for _, jf in promotable}
        for json_path in promoted_json_files:
            archived_name = json_path.with_name(json_path.name + '.promoted')
            try:
                json_path.rename(archived_name)
                print(f"  [ARCHIVED] {json_path.name} -> {archived_name.name}")
            except Exception as e:
                print(f"  [WARN] Konnte JSON nicht umbenennen ({json_path.name}): {e}")

        print(f"\n[SUCCESS] Promote abgeschlossen: {len(rows)} Eintraege uebertragen.")
        return True

    def _find_permanent_cache_files(self) -> List[Path]:
        """Find all permanent CSV cache files in the cache directory."""
        if not self.cache_dir.exists():
            return []
        cache_files = list(self.cache_dir.glob("photo_cache_permanent_*.csv"))
        return sorted(cache_files, reverse=True)  # Most recent first

    def _load_permanent_cache_data(self) -> Dict[str, dict]:
        """
        Load all data from permanent CSV cache files.

        Returns:
            Dictionary with filepath as key and metadata dict as value
        """
        permanent_files = self._find_permanent_cache_files()
        if not permanent_files:
            print("No permanent cache files found")
            return {}

        cache_data = {}
        for cache_file in permanent_files:
            print(f"Loading: {cache_file.name}")
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    for row in reader:
                        filepath = row.get('filepath', '')
                        if filepath:
                            cache_data[filepath] = row
            except Exception as e:
                print(f"Warning: Error reading {cache_file.name}: {e}")

        return cache_data

    def compare_archive_with_cache(self, archive_folder: str, verbose: bool = False) -> Dict[str, any]:
        """
        Compare archive folder with permanent cache files.

        Identifies files in archive that are not in the cache.

        Args:
            archive_folder: Path to the archive folder to compare
            verbose: Print detailed information

        Returns:
            Dictionary with comparison statistics
        """
        print("\n" + "="*60)
        print("ARCHIVE vs CACHE COMPARISON")
        print("="*60)

        # Load permanent cache data
        print("\nLoading permanent cache data...")
        cache_data = self._load_permanent_cache_data()
        print(f"Loaded {len(cache_data)} entries from cache")

        # Build file inventory from archive
        print("\nScanning archive folder...")
        file_inventory = self._build_file_inventory(archive_folder, verbose=False)
        archive_files_list = []
        for filename, paths in file_inventory.items():
            for path in paths:
                archive_files_list.append(path)

        print(f"Found {len(archive_files_list)} files in archive")

        # Compare: which files are in archive but not in cache
        archive_filepaths = {str(p) for p in archive_files_list}
        cache_filepaths = set(cache_data.keys())

        missing_in_cache = []
        for archive_file in archive_files_list:
            archive_file_str = str(archive_file)
            if archive_file_str not in cache_filepaths:
                # Also check if file exists with different path but same name and size
                filename = archive_file.name
                file_size = archive_file.stat().st_size
                found_in_cache = False

                for cached_path, cached_data in cache_data.items():
                    cached_filename = Path(cached_path).name
                    cached_size = cached_data.get('file_size', '')
                    if cached_filename == filename and str(cached_size) == str(file_size):
                        found_in_cache = True
                        break

                if not found_in_cache:
                    missing_in_cache.append(archive_file)

        stats = {
            "archive_files_count": len(archive_files_list),
            "cache_entries_count": len(cache_data),
            "missing_in_cache": missing_in_cache,
            "missing_count": len(missing_in_cache)
        }

        # Print comparison results
        print(f"\n{'='*60}")
        print(f"Files in archive: {len(archive_files_list)}")
        print(f"Files in cache: {len(cache_data)}")
        print(f"Files in archive but NOT in cache: {len(missing_in_cache)}")

        if missing_in_cache:
            print(f"\nMissing files (first 20):")
            for file_path in missing_in_cache[:20]:
                print(f"  - {file_path.name}")
            if len(missing_in_cache) > 20:
                print(f"  ... and {len(missing_in_cache) - 20} more")

        return stats

    def add_missing_files_to_cache(self, missing_files: List[Path], verbose: bool = False) -> str:
        """
        Add missing files to permanent cache by computing hashes.

        Args:
            missing_files: List of file paths to add
            verbose: Print detailed information

        Returns:
            Path to the created permanent cache file
        """
        if not missing_files:
            print("No files to add")
            return None

        print(f"\n{'='*60}")
        print(f"Computing hashes for {len(missing_files)} missing files...")
        print(f"{'='*60}")

        # Compute hashes in parallel
        file_hashes = self._compute_file_hashes_parallel(missing_files)

        # Prepare new entries
        new_entries = []
        for file_path, file_hash in file_hashes.items():
            metadata = self._get_file_metadata(file_path, file_hash=file_hash)
            if metadata:
                new_entries.append(metadata)
                if verbose:
                    print(f"  Processed: {file_path.name}")

        # Create new permanent cache CSV
        now = datetime.now()
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        output_file = self.cache_dir / f"photo_cache_permanent_added_{timestamp}.csv"

        # Prepare CSV rows
        rows = []
        for entry in new_entries:
            row = {
                'created': now.isoformat(),
                'source_dir': '',
                'target_dir': '',
                'total_photos': '',
                'duplicates_count': '',
                'last_updated': now.isoformat(),
                'filepath': entry.get('filepath', ''),
                'datetime': entry.get('datetime', ''),
                'file_hash': entry.get('file_hash', ''),
                'file_size': entry.get('file_size', ''),
                'is_video': entry.get('is_video', ''),
            }
            rows.append(row)

        # Write CSV file
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

        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=column_order, delimiter=';')
                writer.writeheader()
                writer.writerows(rows)

            print(f"\n[SUCCESS] New permanent cache created: {output_file}")
            print(f"   Entries added: {len(rows)}")
            return str(output_file)

        except Exception as e:
            print(f"[ERROR] Error creating permanent cache: {e}")
            return None

    def build_permanent_cache(self) -> bool:
        """
        Build a permanent CSV cache from all JSON cache files.

        Combines metadata and photo entries from all cache files into a single CSV file.
        Filename format: photo_cache_permanent_YYYYMMDD_HHMMSS.csv

        Returns:
            True if successful, False otherwise
        """
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

    # Usage examples
    examples = """
EXAMPLES:

  1. Update cache paths after moving files to new location:
     python lib/cache.py --folder D:\\Archive\\Photos 

  2. Update cache with verbose output:
     python lib/cache.py --folder /nas/organized_photos  --verbose

  3. Build permanent CSV cache from JSON cache files:
     python lib/cache.py --to-permanent 

  4. Compare archive folder with permanent cache:
     python lib/cache.py --archive D:\\MyPhotos --compare 

  5. Compare with verbose output and optional hash computation:
     python lib/cache.py --archive /backup/photos --compare  --verbose

  6. Prüfe ob JSON-Einträge im Archiv sind und übertrage sie in permanente CSV:
     python lib/cache.py --promote --config cfg/photo_organizer.cfg

  7. Promote mit Quellordner-Anzeige und Dry-Run:
     python lib/cache.py --promote --config cfg/photo_organizer.cfg --data-dir data --dry-run --verbose

TYPICAL WORKFLOW:

  Step 1: Organize and cache photos
    python lib/photo_organizer.py --execute

  Step 2: Update cache paths to archive location
    python lib/cache.py --folder C:\\Users\\...\\Nextcloud\\Photos

  Step 3: Check that archived files are confirmed, then promote JSON -> permanent CSV
    python lib/cache.py --promote --config cfg/photo_organizer.cfg --data-dir data

  Step 4: Compare archive with cache (find any new files not yet in cache)
    python lib/cache.py --archive /archive/photos --compare

FEATURES:

  --folder:        Update cache with new file paths (fast, no hash recalculation)
  --to-permanent:  Build permanent CSV from JSON cache (one-time operation)
  --compare:       Compare archive folder with permanent cache (identify missing files)
  --promote:       Prüft JSON-Einträge gegen archive_folder und überträgt sie in permanente CSV
  --dry-run:       Zeigt Aktionen an ohne Änderungen durchzuführen (mit --promote)
  --verbose:       Show detailed progress during operations
  --cache-dir:     Specify custom cache directory (default: PROJECT_CACHE env var)
"""

    parser = argparse.ArgumentParser(
        description='Update cache file paths, build permanent cache, or compare archive with cache',
        epilog=examples,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--folder',
        help='Path to the folder containing files to update in cache'
    )
    parser.add_argument(
        '--archive',
        help='Path to archive folder for comparison (use with --compare)'
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
    parser.add_argument(
        '--compare',
        action='store_true',
        help='Compare archive folder with permanent cache (requires --archive)'
    )
    parser.add_argument(
        '--promote',
        action='store_true',
        help='Prüft ob JSON-Cache-Einträge im Archiv vorhanden sind und überträgt sie in die permanente CSV'
    )
    parser.add_argument(
        '--config',
        help='Pfad zur photo_organizer.cfg (für archive_folder-Pfade, erforderlich bei --promote)'
    )
    parser.add_argument(
        '--data-dir',
        help='Pfad zum Quellordner (optional, für Dateianzahl-Anzeige bei --promote)'
    )
    parser.add_argument(
        '--few-files',
        type=int,
        default=20,
        help='Schwellwert für "wenig Quelldateien" (Standard: 20, nur bei --promote)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Zeigt Aktionen an, führt aber keine Änderungen durch'
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.folder and not args.to_permanent and not args.compare and not args.promote:
        parser.print_help()
        print("\nError: Specify --folder, --to-permanent, --compare, or --promote")
        sys.exit(1)

    if args.compare and not args.archive:
        parser.print_help()
        print("\nError: --compare requires --archive argument")
        sys.exit(1)

    # Validate folder path exists if specified
    if args.folder:
        folder_path = Path(args.folder)
        if not folder_path.exists():
            print(f"Error: Folder does not exist: {args.folder}")
            sys.exit(1)
        if not folder_path.is_dir():
            print(f"Error: Path is not a directory: {args.folder}")
            sys.exit(1)

    # Validate archive path exists if specified
    if args.archive:
        archive_path = Path(args.archive)
        if not archive_path.exists():
            print(f"Error: Archive folder does not exist: {args.archive}")
            sys.exit(1)
        if not archive_path.is_dir():
            print(f"Error: Archive path is not a directory: {args.archive}")
            sys.exit(1)

    # Get cache directory
    cache_dir = args.cache_dir or os.environ.get('PROJECT_CACHE')
    if not cache_dir:
        print("Error: Cache directory not specified. Use --cache-dir or set PROJECT_CACHE")
        sys.exit(1)

    if args.promote and not args.config:
        print("Error: --promote requires --config (Pfad zur photo_organizer.cfg)")
        sys.exit(1)

    try:
        manager = CacheManager(cache_dir)

        if args.promote:
            success = manager.check_and_promote_to_permanent(
                config_path=args.config,
                data_dir=getattr(args, 'data_dir', None),
                few_files_threshold=args.few_files,
                verbose=args.verbose,
                dry_run=args.dry_run,
            )
            sys.exit(0 if success else 1)

        elif args.compare:
            # Compare archive with cache
            stats = manager.compare_archive_with_cache(args.archive, verbose=args.verbose)

            if stats['missing_count'] > 0:
                print(f"\n{'='*60}")
                response = input(f"Found {stats['missing_count']} missing files. Update cache? (y/n): ")
                if response.lower() == 'y':
                    result = manager.add_missing_files_to_cache(stats['missing_in_cache'], verbose=args.verbose)
                    if result:
                        print(f"\nCache updated successfully: {result}")
                    sys.exit(0)
                else:
                    print("Cache update skipped")
                    sys.exit(0)
            else:
                print(f"\n{'='*60}")
                print("All files in archive are already in cache!")
                sys.exit(0)

        elif args.to_permanent:
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
