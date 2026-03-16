"""
Utility functions for PhotoOrganizer
Shared utilities used across multiple modules
"""

import os
import re
import json
import hashlib
import shlex
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List


# ============================================================================
# ENVIRONMENT VARIABLE MANAGEMENT
# ============================================================================

# UNUSED: get_env_var
# def get_env_var(var_name: str, default: str = None) -> str:
#     """
#     Get environment variable with optional default value.
#
#     Args:
#         var_name: Environment variable name
#         default: Default value if not set
#
#     Returns:
#         Environment variable value or default
#     """
#     return os.environ.get(var_name, default)


def get_project_path(var_name: str, default: str = None) -> Optional[Path]:
    """
    Get project path from environment variable.

    Resolves PROJECT_* environment variables (PROJECT_DATA, PROJECT_CACHE, etc.)
    to absolute paths.

    Args:
        var_name: Environment variable name (e.g., 'PROJECT_DATA')
        default: Default path if not set

    Returns:
        Resolved Path object or None if not set and no default
    """
    path_str = os.environ.get(var_name, default)
    if not path_str:
        return None

    return normalize_path(path_str)


# UNUSED: require_project_path
# def require_project_path(var_name: str) -> Path:
#     """
#     Get project path from environment variable or raise exception.
#
#     Args:
#         var_name: Environment variable name (e.g., 'PROJECT_CACHE')
#
#     Returns:
#         Resolved Path object
#
#     Raises:
#         ValueError: If environment variable is not set
#     """
#     path = get_project_path(var_name)
#     if not path:
#         raise ValueError(f"{var_name} environment variable not set")
#
#     return path


# ============================================================================
# FILE EXTENSION DEFINITIONS
# ============================================================================

# Common video file extensions
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v'}

# Common photo file extensions
PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.raw', '.heic'}

# All media file extensions
MEDIA_EXTENSIONS = PHOTO_EXTENSIONS | VIDEO_EXTENSIONS


def is_video_file(filepath: Path) -> bool:
    """
    Check if file is a video based on extension.

    Args:
        filepath: Path to file

    Returns:
        True if file has a video extension
    """
    return filepath.suffix.lower() in VIDEO_EXTENSIONS


# UNUSED: is_photo_file
# def is_photo_file(filepath: Path) -> bool:
#     """
#     Check if file is a photo based on extension.
#
#     Args:
#         filepath: Path to file
#
#     Returns:
#         True if file has a photo extension
#     """
#     return filepath.suffix.lower() in PHOTO_EXTENSIONS


# UNUSED: is_media_file
# def is_media_file(filepath: Path) -> bool:
#     """
#     Check if file is a photo or video based on extension.
#
#     Args:
#         filepath: Path to file
#
#     Returns:
#         True if file has a media extension
#     """
#     return filepath.suffix.lower() in MEDIA_EXTENSIONS


# ============================================================================
# PATH UTILITIES
# ============================================================================

def normalize_path(path_str: str) -> Path:
    """
    Normalize and resolve a path to absolute.

    Args:
        path_str: Path as string or Path object

    Returns:
        Resolved Path object
    """
    return Path(path_str).resolve()


def validate_file(filepath: Path) -> bool:
    """
    Validate that a file exists and is a regular file.
    Prevents race conditions where file is deleted between scan and processing.

    Args:
        filepath: Path to file to validate

    Returns:
        True if file exists and is a regular file
    """
    try:
        return filepath.is_file() and filepath.exists()
    except (OSError, ValueError):
        return False


# UNUSED: validate_directory (used by unused function get_files_by_extensions)
# def validate_directory(dirpath: Path) -> bool:
#     """
#     Validate that a directory exists.
#
#     Args:
#         dirpath: Path to directory to validate
#
#     Returns:
#         True if directory exists
#     """
#     try:
#         return dirpath.is_dir() and dirpath.exists()
#     except (OSError, ValueError):
#         return False


def ensure_directory_exists(dirpath: Path) -> Path:
    """
    Create directory if it doesn't exist.

    Args:
        dirpath: Path to directory

    Returns:
        The directory path
    """
    dirpath = normalize_path(dirpath)
    dirpath.mkdir(parents=True, exist_ok=True)
    return dirpath


# ============================================================================
# STRING SANITIZATION
# ============================================================================

# UNUSED: clean_string (replaced by clean_location_name)
# def clean_string(text: str, max_length: int = None, replace_special: bool = True) -> str:
#     """
#     Clean a string by removing/replacing special characters.
#
#     Args:
#         text: Input string
#         max_length: Maximum length (None for no limit)
#         replace_special: If True, replace umlauts with ae/oe/ue
#
#     Returns:
#         Cleaned string
#     """
#     if not text:
#         return ""
#
#     # Replace German umlauts and special characters
#     if replace_special:
#         replacements = {
#             'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
#             'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue'
#         }
#         for old, new in replacements.items():
#             text = text.replace(old, new)
#
#     # Remove special characters, keep alphanumeric, hyphen, underscore, space
#     text = re.sub(r'[^\w\-_\s]', '', text)
#
#     # Replace multiple spaces with underscore and collapse underscores
#     text = re.sub(r'\s+', '_', text.strip())
#     text = re.sub(r'_+', '_', text)
#
#     # Truncate if needed
#     if max_length:
#         text = text[:max_length]
#
#     return text


def clean_filename(name: str, max_length: int = 20) -> str:
    """
    Clean a filename string for use in folder/file names.

    Args:
        name: Original name
        max_length: Maximum length of cleaned name (default 20)

    Returns:
        Cleaned filename safe for file system
    """
    if not name:
        return "unnamed"

    # Keep numbers, letters, hyphen, underscore
    cleaned = re.sub(r'[^\w\-_]', '_', name)
    # Collapse multiple underscores
    cleaned = re.sub(r'_+', '_', cleaned)
    # Strip underscores from edges
    cleaned = cleaned.strip('_')
    # Truncate
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]

    return cleaned or "unnamed"


def clean_location_name(location: str, max_length: int = 30) -> str:
    """
    Clean a location/city name for use in folder names.
    Handles German umlauts and special characters.

    Args:
        location: Original location name
        max_length: Maximum length (default 30)

    Returns:
        Cleaned location name
    """
    if not location:
        return ""

    # Replace German umlauts and special characters
    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
        'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue'
    }
    for old, new in replacements.items():
        location = location.replace(old, new)

    # Remove special characters, keep alphanumeric, hyphen, underscore, space
    location = re.sub(r'[^\w\-_\s]', '', location)

    # Replace multiple spaces with underscore and collapse underscores
    location = re.sub(r'\s+', '_', location.strip())
    location = re.sub(r'_+', '_', location)

    # Truncate if needed
    if max_length:
        location = location[:max_length]

    return location


# ============================================================================
# FILE I/O UTILITIES
# ============================================================================

def write_text_file(filepath: Path, content: str, encoding: str = 'utf-8') -> bool:
    """
    Write text to file with consistent encoding.

    Args:
        filepath: Path to file
        content: Text content to write
        encoding: File encoding (default UTF-8)

    Returns:
        True if successful
    """
    try:
        filepath = normalize_path(filepath)
        ensure_directory_exists(filepath.parent)
        with open(filepath, 'w', encoding=encoding) as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"❌ Error writing file {filepath}: {e}")
        return False


# UNUSED: read_text_file
# def read_text_file(filepath: Path, encoding: str = 'utf-8') -> Optional[str]:
#     """
#     Read text from file with consistent encoding.
#
#     Args:
#         filepath: Path to file
#         encoding: File encoding (default UTF-8)
#
#     Returns:
#         File content or None if error
#     """
#     try:
#         filepath = normalize_path(filepath)
#         with open(filepath, 'r', encoding=encoding) as f:
#             return f.read()
#     except Exception as e:
#         print(f"❌ Error reading file {filepath}: {e}")
#         return None


def write_json_file(filepath: Path, data: Any, indent: int = 2) -> bool:
    """
    Write data to JSON file with consistent formatting.

    Args:
        filepath: Path to JSON file
        data: Data to serialize
        indent: JSON indentation level

    Returns:
        True if successful
    """
    try:
        content = json.dumps(data, indent=indent, ensure_ascii=False)
        return write_text_file(filepath, content, encoding='utf-8')
    except Exception as e:
        print(f"❌ Error writing JSON {filepath}: {e}")
        return False


def read_json_file(filepath: Path) -> Optional[Dict]:
    """
    Read data from JSON file.

    Args:
        filepath: Path to JSON file

    Returns:
        Parsed JSON data or None if error
    """
    try:
        filepath = normalize_path(filepath)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        if content:
            return json.loads(content)
    except Exception as e:
        print(f"❌ Error reading JSON {filepath}: {e}")
    return None


# ============================================================================
# CONFIGURATION FILE UTILITIES
# ============================================================================

# UNUSED: load_config_section
# def load_config_section(config_file: Path, section: str, default_factory=None) -> Dict:
#     """
#     Load a section from INI config file.
#
#     Args:
#         config_file: Path to config file
#         section: Section name in config
#         default_factory: Function to call if file/section not found
#
#     Returns:
#         Dictionary of section values or empty dict
#     """
#     try:
#         if not validate_file(config_file):
#             if default_factory:
#                 return default_factory()
#             return {}
#
#         config = configparser.ConfigParser()
#         config.read(config_file, encoding='utf-8')
#
#         if section in config:
#             return dict(config[section])
#
#         if default_factory:
#             return default_factory()
#         return {}
#
#     except Exception as e:
#         print(f"⚠️  Error loading config {config_file}: {e}")
#         if default_factory:
#             return default_factory()
#         return {}


# UNUSED: save_config_section
# def save_config_section(config_file: Path, section: str, data: Dict[str, str]) -> bool:
#     """
#     Save a section to INI config file.
#
#     Args:
#         config_file: Path to config file
#         section: Section name
#         data: Dictionary of key-value pairs
#
#     Returns:
#         True if successful
#     """
#     try:
#         config = configparser.ConfigParser()
#
#         # Load existing config if it exists
#         if validate_file(config_file):
#             config.read(config_file, encoding='utf-8')
#
#         # Update or create section
#         if not config.has_section(section):
#             config.add_section(section)
#
#         for key, value in data.items():
#             config.set(section, key, str(value))
#
#         # Ensure directory exists
#         ensure_directory_exists(config_file.parent)
#
#         with open(config_file, 'w', encoding='utf-8') as f:
#             config.write(f)
#
#         return True
#
#     except Exception as e:
#         print(f"❌ Error saving config {config_file}: {e}")
#         return False


# ============================================================================
# FILE METADATA EXTRACTION
# ============================================================================

def get_file_metadata(filepath: Path,
                     include_hash: bool = False,
                     hash_algorithm: str = 'sha256') -> Optional[Dict]:
    """
    Extract file metadata (size, timestamps, optional hash).

    Args:
        filepath: Path to file
        include_hash: Compute file hash (default: False)
        hash_algorithm: Hash algorithm if include_hash=True (default: sha256)

    Returns:
        Dict with metadata: {
            'filepath': str,
            'file_size': int,
            'mtime_iso': str,  # Modification time in ISO format
            'mtime_timestamp': float,  # Modification time as timestamp
            'is_video': bool,
            'file_hash': str (if include_hash)
        }
        or None if file doesn't exist or error occurs
    """
    try:
        if not validate_file(filepath):
            return None

        filepath = normalize_path(filepath)
        stat = filepath.stat()

        metadata = {
            'filepath': str(filepath),
            'file_size': stat.st_size,
            'mtime_iso': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'mtime_timestamp': stat.st_mtime,
            'is_video': is_video_file(filepath),
        }

        if include_hash:
            metadata['file_hash'] = get_file_hash(filepath, algorithm=hash_algorithm)

        return metadata

    except Exception as e:
        print(f"❌ Error extracting metadata for {filepath}: {e}")
        return None


# ============================================================================
# FILE HASHING
# ============================================================================

def get_file_hash(filepath: Path, algorithm: str = 'sha256') -> str:
    """
    Compute hash of a file for duplicate detection.

    Args:
        filepath: Path to file
        algorithm: Hash algorithm ('sha256', 'md5', etc.)

    Returns:
        Hex digest of file hash
    """
    try:
        hash_obj = hashlib.new(algorithm)
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
    except Exception as e:
        print(f"❌ Error computing hash for {filepath}: {e}")
        return ""


# ============================================================================
# SHELL/SCRIPT UTILITIES
# ============================================================================

# UNUSED: escape_shell_path (direct bash/powershell functions are used instead)
# def escape_shell_path(path: str, shell: str = 'bash') -> str:
#     """
#     Escape path for safe use in shell scripts.
#
#     Args:
#         path: File path to escape
#         shell: Shell type ('bash' or 'powershell')
#
#     Returns:
#         Escaped path safe for shell use
#     """
#     if shell.lower() == 'powershell':
#         return escape_powershell_path(path)
#     else:
#         return escape_bash_path(path)


def escape_bash_path(path: str) -> str:
    """
    Escape path for bash shell scripts.

    Args:
        path: File path to escape

    Returns:
        Escaped path for bash
    """
    return shlex.quote(path)


def escape_powershell_path(path: str) -> str:
    """
    Escape path for PowerShell scripts.

    Args:
        path: File path to escape

    Returns:
        Escaped path for PowerShell
    """
    # PowerShell: wrap in quotes and escape backticks
    escaped = path.replace('`', '``')
    escaped = escaped.replace('$', '`$')
    return f'"{escaped}"'


# ============================================================================
# FILE LISTING UTILITIES
# ============================================================================

# UNUSED: get_files_by_extensions
# def get_files_by_extensions(directory: Path,
#                             extensions: set = None,
#                             recursive: bool = True) -> List[Path]:
#     """
#     Get all files with specified extensions from directory.
#
#     Args:
#         directory: Directory to scan
#         extensions: Set of file extensions (e.g., {'.jpg', '.png'})
#                    If None, returns all files
#         recursive: Use rglob if True, else glob
#
#     Returns:
#         List of validated file paths
#     """
#     directory = normalize_path(directory)
#     if not validate_directory(directory):
#         return []
#
#     files = []
#
#     if extensions is None:
#         # Get all files
#         pattern = "**/*" if recursive else "*"
#         glob_func = directory.rglob if recursive else directory.glob
#         for item in glob_func("*" if recursive else "*"):
#             if validate_file(item):
#                 files.append(item)
#     else:
#         # Get files with specific extensions
#         pattern = "**/*" if recursive else "*"
#         glob_func = directory.rglob if recursive else directory.glob
#
#         for item in glob_func("*" if recursive else "*"):
#             if validate_file(item) and item.suffix.lower() in extensions:
#                 files.append(item)
#
#     return sorted(files)


# UNUSED: get_file_list
# def get_file_list(directory: Path, recursive: bool = True) -> List[Path]:
#     """
#     Get all files in directory (convenience wrapper).
#
#     Args:
#         directory: Directory to scan
#         recursive: Use rglob if True, else glob
#
#     Returns:
#         Sorted list of file paths
#     """
#     return get_files_by_extensions(directory, extensions=None, recursive=recursive)


# ============================================================================
# DATETIME UTILITIES
# ============================================================================

def get_timestamp(format_str: str = '%Y%m%d_%H%M%S') -> str:
    """
    Generate a timestamp string.

    Args:
        format_str: strftime format string

    Returns:
        Formatted timestamp
    """
    return datetime.now().strftime(format_str)


# UNUSED: get_iso_timestamp
# def get_iso_timestamp() -> str:
#     """Get ISO format timestamp (for config files)."""
#     return datetime.now().isoformat()


# UNUSED: format_datetime_for_exif
# def format_datetime_for_exif(dt: datetime) -> str:
#     """
#     Format datetime for EXIF tags (YYYY:MM:DD HH:MM:SS).
#
#     Args:
#         dt: Datetime object
#
#     Returns:
#         EXIF-formatted datetime string
#     """
#     return dt.strftime('%Y:%m:%d %H:%M:%S')


# UNUSED: parse_exif_datetime
# def parse_exif_datetime(exif_str: str) -> Optional[datetime]:
#     """
#     Parse EXIF datetime string to datetime object.
#
#     Args:
#         exif_str: EXIF datetime string
#
#     Returns:
#         Parsed datetime or None if parsing fails
#     """
#     formats = [
#         '%Y:%m:%d %H:%M:%S',      # Standard EXIF format
#         '%Y-%m-%dT%H:%M:%S.%fZ',  # ISO with microseconds
#         '%Y-%m-%dT%H:%M:%SZ',     # ISO without microseconds
#         '%Y-%m-%d %H:%M:%S'       # Fallback format
#     ]
#
#     for fmt in formats:
#         try:
#             return datetime.strptime(exif_str, fmt)
#         except ValueError:
#             continue
#
#     return None


# ============================================================================
# DATA STRUCTURE UTILITIES
# ============================================================================

def get_most_common_items(items: List, n: int = 1, key_func=None) -> List:
    """
    Get the most common items from a list.

    Args:
        items: List of items
        n: Number of top items to return
        key_func: Optional function to transform items before counting

    Returns:
        List of (item, count) tuples for top n items
    """
    from collections import Counter

    if key_func:
        items = [key_func(item) for item in items]

    counter = Counter(items)
    return counter.most_common(n)


# UNUSED: group_by_key
# def group_by_key(items: List, key_func) -> Dict:
#     """
#     Group list items by a key function.
#
#     Args:
#         items: List of items
#         key_func: Function to extract grouping key from item
#
#     Returns:
#         Dictionary mapping keys to lists of items
#     """
#     groups = {}
#     for item in items:
#         key = key_func(item)
#         if key not in groups:
#             groups[key] = []
#         groups[key].append(item)
#     return groups


# ============================================================================
# FORMATTING UTILITIES
# ============================================================================

# UNUSED: format_file_size
# def format_file_size(bytes_size: float) -> str:
#     """
#     Format file size for human reading.
#
#     Args:
#         bytes_size: Size in bytes
#
#     Returns:
#         Formatted size string (e.g., "123.45 MB")
#     """
#     for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
#         if bytes_size < 1024:
#             return f"{bytes_size:.2f} {unit}"
#         bytes_size /= 1024
#     return f"{bytes_size:.2f} PB"


# UNUSED: format_date_range
# def format_date_range(start_date, end_date) -> str:
#     """
#     Format a date range for display.
#
#     Args:
#         start_date: Start datetime
#         end_date: End datetime
#
#     Returns:
#         Formatted date range (e.g., "2024-01-15 to 2024-03-20")
#     """
#     if not start_date or not end_date:
#         return "Unknown"
#
#     if start_date.date() == end_date.date():
#         return start_date.strftime('%Y-%m-%d')
#
#     return f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"


# UNUSED: format_percentage
# def format_percentage(value: float, total: float) -> str:
#     """
#     Format value as percentage of total.
#
#     Args:
#         value: Value to convert
#         total: Total value
#
#     Returns:
#         Percentage string (e.g., "45.5%")
#     """
#     if total == 0:
#         return "0.0%"
#     return f"{(value / total) * 100:.1f}%"
