# PhotoOrganizer Developer Guide

This guide provides detailed information for developers who want to contribute to, extend, or integrate with the PhotoOrganizer project.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Development Setup](#development-setup)
3. [Code Structure](#code-structure)
4. [Core Components](#core-components)
5. [Extending the System](#extending-the-system)
6. [Testing](#testing)
7. [Contributing Guidelines](#contributing-guidelines)
8. [Performance Optimization](#performance-optimization)
9. [Troubleshooting](#troubleshooting)

## Architecture Overview

PhotoOrganizer follows a modular architecture designed for scalability and maintainability:

```
┌─────────────────────────────────────────────────────────────┐
│                    PhotoOrganizer                           │
├─────────────────────────────────────────────────────────────┤
│  CLI Interface (main.py)                                   │
├─────────────────────────────────────────────────────────────┤
│  PhotoOrganizer Class (Core Logic)                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │   Scanner   │ │  Organizer  │ │   Cache     │           │
│  │   Module    │ │   Module    │ │   Module    │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │    EXIF     │ │     GPS     │ │   Script    │           │
│  │   Handler   │ │   Geocoder  │ │ Generator   │           │
│  │             │ │             │ │             │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
├─────────────────────────────────────────────────────────────┤
│  External Dependencies: PIL, requests, threading           │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Separation of Concerns**: Each module handles a specific aspect
2. **Thread Safety**: All shared resources use proper locking
3. **Configurable**: Extensible pattern matching and settings
4. **Caching**: Intelligent caching to avoid redundant operations
5. **Error Resilience**: Graceful handling of malformed files

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Git
- Linux/macOS/Windows with WSL

### Environment Setup

1. **Clone and Setup Environment**
```bash
git clone <repository>
cd PhotoOrganizer
source bin/setenv.sh
```

2. **Create Virtual Environment**
```bash
./bin/install_py.sh
```

3. **Activate Development Environment**
```bash
source bin/manage_interpreter.sh activate_interpreter
```

### Project Structure

```
PhotoOrganizer/
├── bin/                    # Executable scripts
│   ├── setenv.sh          # Environment setup
│   ├── organize.sh        # Main execution wrapper
│   ├── install_py.sh      # Python environment setup
│   └── manage_interpreter.sh  # Python env management
├── lib/                   # Core library code
│   ├── photo_organizer.py # Main PhotoOrganizer class
│   └── requirements.txt   # Python dependencies
├── cfg/                   # Configuration files
│   └── photo_organizer.cfg    # Pattern definitions
├── cache/                 # Cache directory (created at runtime)
├── scripts/              # Generated scripts (created at runtime)
├── data/                 # Data directory
├── Readme.md             # User documentation
├── API_REFERENCE.md      # API documentation
└── DEVELOPER_GUIDE.md    # This file
```

## Code Structure

### Main Class: PhotoOrganizer

The `PhotoOrganizer` class is the central component that orchestrates all operations:

```python
class PhotoOrganizer:
    def __init__(self, ...):
        # Configuration and setup
        
    def scan_photos(self):
        # Phase 1: Parallel file processing
        # Phase 2: Sequential geocoding
        
    def organize_photos(self, dry_run=True):
        # File organization and movement
```

### Data Flow

1. **Discovery Phase**: Scan directory tree for supported files
2. **Processing Phase**: Extract metadata in parallel
3. **Geocoding Phase**: Convert GPS to locations sequentially
4. **Grouping Phase**: Organize photos into events
5. **Execution Phase**: Move files or generate scripts

### Thread Safety

The system uses several thread-safe mechanisms:

```python
# Thread-safe caches with locks
self.location_cache_lock = threading.Lock()
self.hash_cache_lock = threading.Lock()

# Usage pattern
with self.location_cache_lock:
    self.location_cache[coords] = location_name
```

## Core Components

### 1. File Scanner

**Purpose**: Discover and validate photo/video files

**Key Methods**:
- File type detection
- Recursive directory traversal
- Extension filtering

**Extension Points**:
```python
# Add support for new file types
self.supported_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', 
                           '.mov', '.mp4', '.avi', '.vid'}
```

### 2. Metadata Extractor

**Purpose**: Extract timestamps, GPS, and other metadata

**Priority Order**:
1. EXIF data (highest priority)
2. Filename patterns
3. File modification time (fallback)

**Key Methods**:
```python
def get_best_datetime(self, filepath: Path) -> datetime
def get_exif_datetime(self, filepath: Path) -> Optional[datetime]
def get_datetime_from_filename(self, filepath: Path) -> Optional[datetime]
```

### 3. Pattern Matching System

**Purpose**: Extract dates from filenames using configurable regex patterns

**Configuration**: `cfg/photo_organizer.cfg`

**Pattern Requirements**:
- 6 groups: Year, Month, Day, Hour, Minute, Second
- 3 groups: Year, Month, Day (time defaults to 12:00:00)

**Adding New Patterns**:
```ini
[Filename_Patterns]
# Your custom pattern
my_format = (\d{4})\.(\d{2})\.(\d{2})_(\d{2})h(\d{2})m(\d{2})s
```

### 4. GPS and Geocoding

**Purpose**: Handle GPS coordinates and location resolution

**API**: OpenStreetMap Nominatim (rate-limited to 1 req/sec)

**Caching Strategy**:
- Rounds coordinates to ~100m precision
- Thread-safe cache access
- Persistent cache storage

**Key Methods**:
```python
def get_gps_coords(self, filepath: Path) -> Optional[Tuple[float, float]]
def get_location_name(self, coords: Tuple[float, float]) -> Optional[str]
def calculate_distance(self, coord1, coord2) -> float
```

### 5. Event Grouping Algorithm

**Purpose**: Group photos into meaningful events

**Criteria**:
- Temporal proximity (configurable days)
- Geographic proximity (configurable radius)
- Minimum event size (configurable count)

**Algorithm**:
```python
def group_photos_into_events(self) -> Dict[str, List[PhotoInfo]]:
    # 1. Sort photos by timestamp
    # 2. Group by temporal/spatial proximity
    # 3. Filter by minimum size
    # 4. Create folder names
```

### 6. Cache Management

**Purpose**: Avoid redundant processing in repeated runs

**Cache Structure**:
```json
{
  "metadata": {
    "created": "2025-01-15T10:30:00",
    "source_dir": "/path/to/photos",
    "total_photos": 1500
  },
  "photos": [
    {
      "filepath": "/path/to/photo.jpg",
      "datetime": "2025-01-15T14:30:25",
      "gps_coords": [52.520, 13.405],
      "location_name": "Berlin",
      "file_hash": "sha256hash...",
      "file_size": 2048576,
      "is_video": false
    }
  ],
  "location_cache": {
    "52.520,13.405": "Berlin"
  },
  "duplicates": ["hash1", "hash2"]
}
```

## Extending the System

### Adding New File Format Support

1. **Update Supported Extensions**:
```python
# In __init__ method
self.supported_extensions.add('.heic')  # Apple HEIC format
```

2. **Add Format-Specific Metadata Extraction**:
```python
def get_heic_datetime(self, filepath: Path) -> Optional[datetime]:
    # Implementation for HEIC metadata
    pass
```

3. **Update get_best_datetime() Method**:
```python
def get_best_datetime(self, filepath: Path) -> datetime:
    if filepath.suffix.lower() == '.heic':
        heic_datetime = self.get_heic_datetime(filepath)
        if heic_datetime:
            return heic_datetime
    # ... existing logic
```

### Custom Filename Patterns

1. **Add Pattern to Configuration**:
```ini
[Filename_Patterns]
# Social media timestamp format
social_media = (\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_social
```

2. **Test Pattern**:
```python
import re
pattern = r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_social'
filename = "20250315_143025_social.jpg"
match = re.search(pattern, filename)
if match:
    print(match.groups())  # ('2025', '03', '15', '14', '30', '25')
```

### Custom Event Grouping Logic

1. **Extend create_event_name() Method**:
```python
def create_event_name(self, photos: List[PhotoInfo]) -> str:
    # Custom logic for specific photo collections
    if self.is_vacation_photos(photos):
        return self.create_vacation_event_name(photos)
    
    # Default logic
    return super().create_event_name(photos)
```

2. **Add Custom Grouping Criteria**:
```python
def custom_belongs_to_event(self, photo: PhotoInfo, event_photos: List[PhotoInfo]) -> bool:
    # Implement custom grouping logic
    # e.g., based on camera model, photographer, etc.
    pass
```

### Adding New Geocoding Providers

1. **Create Provider Interface**:
```python
class GeocodingProvider:
    def reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        raise NotImplementedError
```

2. **Implement Provider**:
```python
class GoogleGeocodingProvider(GeocodingProvider):
    def reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        # Implementation using Google Maps API
        pass
```

3. **Update get_location_name() Method**:
```python
def get_location_name(self, coords: Tuple[float, float]) -> Optional[str]:
    for provider in self.geocoding_providers:
        try:
            location = provider.reverse_geocode(coords[0], coords[1])
            if location:
                return location
        except Exception as e:
            continue  # Try next provider
    return None
```

## Testing

### Unit Tests

Create test files following this pattern:

```python
# test_photo_organizer.py
import unittest
from pathlib import Path
from photo_organizer import PhotoOrganizer

class TestPhotoOrganizer(unittest.TestCase):
    def setUp(self):
        self.organizer = PhotoOrganizer(
            source_dir="/tmp/test_photos",
            target_dir="/tmp/test_output",
            use_geocoding=False  # Disable for tests
        )
    
    def test_datetime_extraction(self):
        test_file = Path("/tmp/IMG_20250315_143025.jpg")
        # Mock file creation and test
        datetime_result = self.organizer.get_datetime_from_filename(test_file)
        self.assertIsNotNone(datetime_result)
        
    def test_distance_calculation(self):
        berlin = (52.5200, 13.4050)
        munich = (48.1351, 11.5820)
        distance = self.organizer.calculate_distance(berlin, munich)
        self.assertAlmostEqual(distance, 504.2, places=1)  # ~504km
```

### Integration Tests

```python
def test_full_workflow(self):
    # Create test photo collection
    self.create_test_photos()
    
    # Run organization
    self.organizer.scan_photos()
    events = self.organizer.preview_organization()
    
    # Verify results
    self.assertGreater(len(events), 0)
    self.assertIn("2025/03-15", events)
```

### Performance Tests

```python
def test_large_collection_performance(self):
    import time
    
    start_time = time.time()
    self.organizer.scan_photos()  # 10,000 photos
    end_time = time.time()
    
    processing_time = end_time - start_time
    photos_per_second = len(self.organizer.photos) / processing_time
    
    self.assertGreater(photos_per_second, 50)  # At least 50 photos/sec
```

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_photo_organizer.py

# Run with coverage
python -m pytest --cov=photo_organizer tests/
```

## Contributing Guidelines

### Code Style

1. **Follow PEP 8**: Use `black` for formatting
```bash
black lib/photo_organizer.py
```

2. **Type Hints**: Use comprehensive type annotations
```python
def process_photo(self, filepath: Path) -> Optional[PhotoInfo]:
    pass
```

3. **Documentation**: Use docstrings for all public methods
```python
def calculate_distance(self, coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """
    Calculates distance between two GPS coordinates using Haversine formula.
    
    Args:
        coord1: First GPS coordinate as (latitude, longitude)
        coord2: Second GPS coordinate as (latitude, longitude)
        
    Returns:
        Distance in kilometers
    """
```

### Git Workflow

1. **Create Feature Branch**:
```bash
git checkout -b feature/new-file-format-support
```

2. **Make Changes with Good Commit Messages**:
```bash
git commit -m "Add HEIC file format support

- Implement HEIC metadata extraction
- Add HEIC to supported extensions
- Update tests for HEIC files
- Document HEIC support in README"
```

3. **Create Pull Request**:
- Include comprehensive description
- Add tests for new functionality
- Update documentation
- Ensure all tests pass

### Code Review Checklist

- [ ] Code follows established patterns
- [ ] New functionality has tests
- [ ] Documentation is updated
- [ ] Performance impact is considered
- [ ] Error handling is appropriate
- [ ] Thread safety is maintained

## Performance Optimization

### Profiling

1. **CPU Profiling**:
```python
import cProfile
import pstats

# Profile the scanning process
cProfile.run('organizer.scan_photos()', 'profile_stats')
stats = pstats.Stats('profile_stats')
stats.sort_stats('cumulative')
stats.print_stats(20)
```

2. **Memory Profiling**:
```python
from memory_profiler import profile

@profile
def scan_photos(self):
    # Method implementation
    pass
```

### Optimization Strategies

1. **Parallel Processing Tuning**:
```python
# Optimal worker count
import os
optimal_workers = min(32, (os.cpu_count() or 1) + 4)
```

2. **Memory Management**:
```python
# Process files in batches for large collections
def scan_photos_batched(self, batch_size: int = 1000):
    all_files = list(self.source_dir.rglob('*'))
    
    for i in range(0, len(all_files), batch_size):
        batch = all_files[i:i + batch_size]
        self.process_batch(batch)
        # Optional: garbage collection
        import gc
        gc.collect()
```

3. **I/O Optimization**:
```python
# Use memory mapping for large files
import mmap

def get_file_hash_mmap(self, filepath: Path) -> str:
    with open(filepath, 'rb') as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            return hashlib.sha256(mm).hexdigest()
```

### Caching Strategies

1. **Smart Cache Invalidation**:
```python
def is_cache_valid(self) -> bool:
    if not self.cache_file.exists():
        return False
    
    cache_mtime = self.cache_file.stat().st_mtime
    source_mtime = max(p.stat().st_mtime for p in self.source_dir.rglob('*'))
    
    return cache_mtime > source_mtime
```

2. **Hierarchical Caching**:
```python
# Directory-level caches for large collections
def create_directory_cache(self, directory: Path) -> Path:
    cache_name = f"dir_cache_{directory.name}.json"
    return self.cache_dir / cache_name
```

## Troubleshooting

### Common Issues

1. **Memory Exhaustion**:
```python
# Symptoms: Out of memory errors with large collections
# Solution: Implement batch processing or increase batch size
def scan_photos_memory_efficient(self):
    # Process files in smaller chunks
    for batch in self.get_file_batches(batch_size=500):
        self.process_batch(batch)
```

2. **Geocoding Rate Limits**:
```python
# Symptoms: HTTP 429 errors or blocked requests
# Solution: Implement exponential backoff
import time
import random

def get_location_with_backoff(self, coords: Tuple[float, float]) -> Optional[str]:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return self.get_location_name(coords)
        except requests.HTTPError as e:
            if e.response.status_code == 429:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(wait_time)
            else:
                raise
    return None
```

3. **Thread Deadlocks**:
```python
# Symptoms: Application hangs during parallel processing
# Solution: Use timeout on lock acquisition
def safe_cache_update(self, key, value):
    try:
        if self.location_cache_lock.acquire(timeout=10):
            self.location_cache[key] = value
            self.location_cache_lock.release()
        else:
            print(f"Warning: Could not acquire lock for {key}")
    except Exception as e:
        print(f"Cache update error: {e}")
```

### Debug Logging

Enable comprehensive logging for troubleshooting:

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('photo_organizer.log'),
        logging.StreamHandler()
    ]
)

# Add logging throughout the codebase
def scan_photos(self):
    logging.info(f"Starting scan of {self.source_dir}")
    logging.debug(f"Using {self.max_workers} workers")
    
    # ... implementation
    
    logging.info(f"Scan complete: {len(self.photos)} photos found")
```

### Performance Monitoring

```python
import time
from functools import wraps

def monitor_performance(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        print(f"{func.__name__} took {end_time - start_time:.2f} seconds")
        return result
    return wrapper

# Apply to key methods
@monitor_performance
def scan_photos(self):
    # Implementation
    pass
```

This developer guide provides comprehensive information for contributing to and extending PhotoOrganizer. The modular architecture makes it easy to add new features while maintaining code quality and performance.