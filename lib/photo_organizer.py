#!/usr/bin/env python3
"""
Automatische Foto-Organisation basierend auf Zeitstempel und GPS-Daten
Organisiert Fotos in Ordnerstrukturen: YYYY/MM-DD/ oder YYYY/Event_YYYY-MM-DD_bis_YYYY-MM-DD/
"""

import os
import shutil
import json
import re
import configparser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from collections import defaultdict, Counter
import math
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import utilities
from utils import (
    normalize_path, validate_file, ensure_directory_exists,
    clean_filename, clean_location_name as clean_location_name_util,
    get_file_hash, escape_bash_path, escape_powershell_path,
    get_timestamp as get_timestamp_util, get_most_common_items,
    write_json_file, read_json_file, write_text_file,
    is_video_file
)

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    from PIL.ExifTags import Base as ExifBase
    PILLOW_AVAILABLE = True
except ImportError:
    print("PIL/Pillow nicht installiert. Installiere mit: pip install Pillow")
    PILLOW_AVAILABLE = False

try:
    import subprocess
    from static_ffmpeg import run
    # Get paths to bundled ffmpeg/ffprobe binaries
    ffmpeg_path, ffprobe_path = run.get_or_fetch_platform_executables_else_raise()
    FFPROBE_AVAILABLE = True
    FFPROBE_PATH = ffprobe_path
except ImportError:
    FFPROBE_AVAILABLE = False
    FFPROBE_PATH = 'ffprobe'  # Fallback to system ffprobe
    print("Warnung: static-ffmpeg nicht verfügbar. Versuche System-ffprobe zu verwenden.")

try:
    import requests
    import time
    GEOCODING_AVAILABLE = True
except ImportError:
    GEOCODING_AVAILABLE = False
    print("Warnung: requests nicht verfügbar. Installiere mit: pip install requests")

@dataclass
class PhotoInfo:
    """Informationen über ein Foto/Video"""
    filepath: Path
    datetime: datetime
    gps_coords: Optional[Tuple[float, float]] = None  # (lat, lon)
    location_name: Optional[str] = None  # Ortsname aus GPS
    file_hash: str = ""
    file_size: int = 0
    is_video: bool = False

class PhotoOrganizer:
    def __init__(self, 
                 source_dir: str,
                 target_dir: str,
                 same_day_hours: int = 12,
                 event_max_days: int = 3,
                 geo_radius_km: float = 10.0,
                 use_geocoding: bool = True,
                 max_workers: int = None,
                 generate_script: bool = False,
                 script_path: str = None,
                 cache_file: Optional[str] = None,
                 add_exif: bool = False,
                 powershell: bool = False,
                 compare_with_cache: bool = True):
        """
        Initialisiert den Photo Organizer

        Args:
            source_dir: Quellverzeichnis mit Fotos
            target_dir: Zielverzeichnis für organisierte Fotos
            same_day_hours: Stunden-Schwelle für gleichen Tag
            event_max_days: Maximale Tage für Event-Zusammengehörigkeit
            geo_radius_km: GPS-Radius in km für Event-Zugehörigkeit
            use_geocoding: Aktiviert Reverse-Geocoding für Ortsnamen
            max_workers: Anzahl paralleler Threads (None = auto)
            generate_script: Erzeugt Shell-Script für spätere Ausführung
            script_path: Pfad für das Shell-Script (None = auto mit PROJECT_SCRIPTS)
            cache_file: JSON-Cache-Datei für Photo-Daten und Geocoding (None = auto mit PROJECT_CACHE)
            add_exif: Fügt EXIF-Daten basierend auf Dateinamen hinzu
            powershell: Erzeugt PowerShell-Script (.ps1) statt Bash-Script (.sh)
            compare_with_cache: Vergleicht mit permanenter CSV (default: True)
        """
        self.source_dir = Path(source_dir).resolve()
        self.target_dir = Path(target_dir).resolve()
        self.same_day_hours = same_day_hours
        self.event_max_days = event_max_days
        self.geo_radius_km = geo_radius_km
        self.use_geocoding = use_geocoding and GEOCODING_AVAILABLE
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        self.generate_script = generate_script
        self.add_exif = add_exif and PILLOW_AVAILABLE
        self.powershell = powershell
        
        if add_exif and not PILLOW_AVAILABLE:
            print("⚠️  --addexif erfordert PIL/Pillow. Feature deaktiviert.")
        
        # Auto-generiere Script-Pfad falls nicht angegeben
        if script_path is None:
            script_path = self.generate_script_path()
        self.script_path = Path(script_path)
        
        # Auto-generiere Cache-Dateinamen falls nicht angegeben
        if cache_file is None:
            cache_file = self.generate_cache_filename()
        self.cache_file = Path(cache_file) if cache_file else None
        
        self.supported_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.mov', '.mp4', '.avi', '.vid'}
        self.video_extensions = {'.mov', '.mp4', '.avi', '.vid'}
        self.exif_writable_extensions = {'.jpg', '.jpeg', '.tiff', '.tif'}  # Formate die EXIF unterstützen
        
        self.photos: List[PhotoInfo] = []
        self.duplicates: Set[str] = set()
        self.cached: Set[str] = set()  # Dateien die bereits in der Sammlung sind

        # Thread-sichere Caches
        self.location_cache: Dict[Tuple[float, float], str] = {}
        self.location_cache_lock = threading.Lock()
        self.hash_cache: Dict[str, str] = {}
        self.hash_cache_lock = threading.Lock()

        # Permanenter Cache aus CSV für Duplikat-Erkennung
        self.compare_with_cache = compare_with_cache
        self.cached_hash_dict: Dict[str, str] = {}  # hash -> filepath aus permanenter CSV
        if compare_with_cache:
            self.load_permanent_cache()
        
        # Shell-Script Sammlung
        self.move_commands: List[Tuple[Path, Path]] = []  # (source, target)
        
        # Lade Dateinamen-Pattern aus Konfiguration
        self.filename_patterns = self.load_filename_patterns()
        # Lade default Geokoordinaten aus Konfiguration
        self.location_cache = self.load_geo_cords()
        # Lade Zielordner-Benennungsmuster aus Konfiguration
        self.foldernames_config = self.load_foldernames_config()
        
        # EXIF-Statistiken
        self.exif_added_count = 0
        self.exif_skipped_count = 0
        self.exif_error_count = 0
        
        print(f"Initialisiert mit {self.max_workers} parallelen Threads")
        if self.cache_file:
            print(f"Cache-Datei: {self.cache_file}")
        if self.generate_script:
            script_type = "PowerShell" if self.powershell else "Bash"
            print(f"{script_type}-Script: {self.script_path}")
        if self.add_exif:
            print(f"EXIF-Hinzufügung: Aktiviert")

    def load_permanent_cache(self) -> bool:
        """
        Lädt die neueste permanente CSV-Cache-Datei.
        Speichert alle Hashes für Duplikat-Erkennung.

        Returns:
            True wenn erfolgreich, False sonst
        """
        import csv

        try:
            project_cache = os.environ.get('PROJECT_CACHE')
            if not project_cache:
                print("⚠️  PROJECT_CACHE nicht gesetzt. Permanenter Cache wird ignoriert.")
                return False

            cache_dir = Path(project_cache)
            if not cache_dir.exists():
                print(f"⚠️  Cache-Verzeichnis existiert nicht: {cache_dir}")
                return False

            # Finde die neueste permanente CSV-Datei
            permanent_files = list(cache_dir.glob('photo_cache_permanent_*.csv'))

            # Fallback: Prüfe auch auf "permanent.csv" (Legacy-Name)
            if not permanent_files:
                legacy_file = cache_dir / 'permanent.csv'
                if legacy_file.exists():
                    permanent_files = [legacy_file]
                    print(f"Lade Legacy-Cache: {legacy_file.name}")

            if not permanent_files:
                print("⚠️  Keine permanente CSV-Datei gefunden")
                return False

            # Sortiere nach Dateinamen (enthält Timestamp) - wenn mehrere neueste Datei nehmen
            if len(permanent_files) > 1:
                permanent_files.sort()
                permanent_file = permanent_files[-1]  # Neueste Datei
            else:
                permanent_file = permanent_files[0]

            print(f"Lade permanenten Cache: {permanent_file.name}")

            # Lade die CSV und fülle cached_hash_dict
            with open(permanent_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                hash_count = 0

                for row in reader:
                    file_hash = row.get('file_hash', '').strip()
                    filepath = row.get('filepath', '').strip()

                    if file_hash and filepath:
                        self.cached_hash_dict[file_hash] = filepath
                        hash_count += 1

            print(f"  Geladen: {hash_count} Hashes aus permanenter Cache")
            return True

        except Exception as e:
            print(f"⚠️  Fehler beim Laden permanenter Cache: {e}")
            return False

    def load_geo_cords(self) -> Dict[Tuple[float, float], str]:
        """Lädt Geokoordinaten aus Konfigurationsdatei"""
       
        default_patterns = {
            (47.269,8.846): "Duernten",
            (48.341,10.906): "Augsburg",
            (48.147,11.561): "Muenchen",
            (48.151,11.462): "Muenchen",
        }
        project_cfg = os.environ.get('PROJECT_CFG')
        if not project_cfg:
            print("🔧 PROJECT_CFG nicht gesetzt, verwende Default-Pattern")
            return default_patterns
        
        config_dir = Path(project_cfg)
        geoconfig_file = config_dir / "geo_coords.cfg"

        
        if not geoconfig_file.exists():
            # Erstelle Standard-Konfigurationsdatei
            config_content = """# PhotoOrganizer geo Koordinaten Konfigurationsdatei
#
# Diese Datei enthält zu den Angaben von Länge und Breite den entsprechenden Ort

[geo_locations]
# Bekannte Orte mit Koordinaten
47.269,8.846 = Duernten
48.341,10.906 = Augsburg
48.147,11.561 = Muenchen
48.151,11.462 = Muenchen

[unknown]
# GPS-Koordinaten, die nicht reverse-geocodiert werden konnten
# Diese werden bei --no-geocoding Flag gespeichert
# Format: latitude,longitude = unknown
"""
            self.create_default_config(geoconfig_file, config_content)
            print(f"🔧 Standard-Config erstellt: {geoconfig_file}")
        
        try:
            config = configparser.ConfigParser()
            config.read(geoconfig_file, encoding='utf-8')

            # Load known locations from [geo_locations]
            if 'geo_locations' in config:
                for key, location_name in config['geo_locations'].items():
                    try:
                        # Parse Koordinaten aus dem Key "lat,lon"
                        lat_str, lon_str = key.split(',')
                        lat = float(lat_str.strip())
                        lon = float(lon_str.strip())

                        # Füge zum Cache hinzu
                        default_patterns[(lat, lon)] = location_name.strip()

                    except ValueError as e:
                        print(f"⚠️  Ungültiges Koordinatenformat in [geo_locations]: '{key}' -> {e}")
                        continue

            # Load unknown coordinates from [unknown] section
            # These won't be re-queried via API
            if 'unknown' in config:
                unknown_count = 0
                for key in config['unknown'].keys():
                    try:
                        # Parse Koordinaten aus dem Key "lat,lon"
                        lat_str, lon_str = key.split(',')
                        lat = float(lat_str.strip())
                        lon = float(lon_str.strip())

                        # Store as None to avoid re-querying
                        default_patterns[(lat, lon)] = None
                        unknown_count += 1

                    except ValueError as e:
                        print(f"⚠️  Ungültiges Koordinatenformat in [unknown]: '{key}' -> {e}")
                        continue

                if unknown_count > 0 and default_patterns:
                    print(f"🔧 {len(default_patterns)} Pattern aus Config geladen ({unknown_count} unbekannt): {geoconfig_file}")
                    return default_patterns
                elif default_patterns:
                    print(f"🔧 {len(default_patterns)} Pattern aus Config geladen: {geoconfig_file}")
                    return default_patterns

        except Exception as e:
            print(f"⚠️  Fehler beim Laden der Config: {e}")
            print("🔧 Verwende Default-Pattern")
            return default_patterns

    def save_geo_locations_to_config(self) -> None:
        """
        Save geolocation data to geo_coords.cfg using configparser.

        Known locations (with names) go to [geo_locations].
        Unknown locations (with None value) go to [unknown].
        Preserves existing sections and entries.
        """
        import configparser

        project_cfg = os.environ.get('PROJECT_CFG')
        config_dir = Path(project_cfg)
        geoconfig_file = config_dir / "geo_coords.cfg"

        try:
            # Load existing config to preserve other sections
            config = configparser.ConfigParser()
            if config_dir.exists() and geoconfig_file.exists():
                config.read(geoconfig_file, encoding='utf-8')

            # Ensure sections exist
            if 'geo_locations' not in config:
                config['geo_locations'] = {}
            if 'unknown' not in config:
                config['unknown'] = {}

            # Separate known and unknown locations
            known_count = 0
            unknown_count = 0

            for (lat, lon), location_name in sorted(self.location_cache.items()):
                key = f"{lat},{lon}"

                if location_name is None or location_name == "unknown":
                    # Store in [unknown] section only if value is None
                    # (not an empty string, actual None)
                    if location_name is None:
                        config['unknown'][key] = "unknown"
                        unknown_count += 1
                else:
                    # Store in [geo_locations] section
                    config['geo_locations'][key] = location_name
                    known_count += 1

            # Remove [unknown] section if it's empty (all entries were geocoded)
            if 'unknown' in config:
                if len(config['unknown']) == 0:
                    config.remove_section('unknown')

            # Save to file
            os.makedirs(config_dir, exist_ok=True)
            with open(geoconfig_file, 'w', encoding='utf-8') as f:
                config.write(f)

            total = known_count + unknown_count
            print(f"✅ Geo-Locations gespeichert: {geoconfig_file}")
            print(f"   Bekannte Orte [geo_locations]: {known_count}")
            if unknown_count > 0:
                print(f"   Unbekannte Koordinaten [unknown]: {unknown_count}")
            else:
                print(f"   [unknown] section wurde entfernt (alle Koordinaten geocodiert)")

        except Exception as e:
            print(f"❌ Fehler beim Speichern: {e}")

    def load_foldernames_config(self) -> Dict[str, str]:
        """Lädt Zielordner-Benennungsmuster aus Konfigurationsdatei"""
        # Default-Muster falls Config nicht verfügbar
        default_config = {
            'single_day': '{year}/{start_date}',
            'multi_day': '{year}/{start_date}_bis_{end_date}',
            'single_files': '{year}/einzeldateien',
        }

        project_cfg = os.environ.get('PROJECT_CFG')
        if not project_cfg:
            print("🔧 PROJECT_CFG nicht gesetzt, verwende Standard-Muster")
            return default_config

        config_dir = Path(project_cfg)
        config_file = config_dir / "photo_organizer.cfg"

        if not config_file.exists():
            return default_config

        try:
            config = configparser.ConfigParser()
            config.read(config_file, encoding='utf-8')

            if 'foldernames_target' in config:
                loaded_config = {}
                for key, value in config['foldernames_target'].items():
                    if value.strip():  # Überspringe leere Werte
                        loaded_config[key.strip()] = value.strip()

                if loaded_config:
                    print(f"🔧 Zielordner-Muster aus Config geladen: {config_file}")
                    # Merge mit Default-Config für fehlende Keys
                    result = default_config.copy()
                    result.update(loaded_config)
                    return result

        except Exception as e:
            print(f"⚠️  Fehler beim Laden der Folder-Konfiguration: {e}")

        return default_config

    def load_filename_patterns(self) -> List[str]:
        """Lädt Dateinamen-Pattern aus Konfigurationsdatei"""
        # Default-Pattern falls Config nicht verfügbar
        default_patterns = [
            # YYYY-MM-DD HH.MM.SS oder YYYY-MM-DD HH-MM-SS
            r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2})[\.\-:](\d{2})[\.\-:](\d{2})',
            # YYYY-MM-DD_HH.MM.SS oder YYYY-MM-DD_HH-MM-SS
            r'(\d{4})-(\d{2})-(\d{2})_(\d{2})[\.\-:](\d{2})[\.\-:](\d{2})',
            # YYYYMMDD_HHMMSS
            r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})',
            # YYYY-MM-DD (nur Datum, Zeit wird auf 12:00:00 gesetzt)
            r'(\d{4})-(\d{2})-(\d{2})',
            # YYYYMMDD (nur Datum)
            r'(\d{4})(\d{2})(\d{2})',
            # IMG_YYYYMMDD_HHMMSS (typisch für Kameras)
            r'IMG_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})',
            # WhatsApp Format: IMG-YYYYMMDD-WAXXXX
            r'IMG-(\d{4})(\d{2})(\d{2})-WA\d+',
            # Signal Format: signal-YYYY-MM-DD-HHMMSS
            r'signal-(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})(\d{2})',
            # Screenshot Format: Screenshot_YYYY-MM-DD-HH-MM-SS
            r'Screenshot_(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})',
            # Allgemeines Muster: beliebiger Text + YYYYMMDD
            r'.*(\d{4})(\d{2})(\d{2}).*',
        ]
        
        project_cfg = os.environ.get('PROJECT_CFG')
        if not project_cfg:
            print("🔧 PROJECT_CFG nicht gesetzt, verwende Default-Pattern")
            return default_patterns
        
        config_dir = Path(project_cfg)
        config_file = config_dir / "photo_organizer.cfg"
        
        if not config_file.exists():
            # Erstelle Standard-Konfigurationsdatei
            config_content = """# PhotoOrganizer Konfigurationsdatei
# 
# Diese Datei enthält Regex-Pattern für die Erkennung von Datum/Zeit in Dateinamen
# Format: pattern_name = regex_pattern
# 
# Regex-Gruppen:
# - 6 Gruppen: Jahr, Monat, Tag, Stunde, Minute, Sekunde
# - 3 Gruppen: Jahr, Monat, Tag (Zeit wird auf 12:00:00 gesetzt)

[Filename_Patterns]

# Standard-Formate mit Datum und Zeit
datetime_space = (\\d{4})-(\\d{2})-(\\d{2})\\s+(\\d{2})[\\.-:](\\d{2})[\\.-:](\\d{2})
datetime_underscore = (\\d{4})-(\\d{2})-(\\d{2})_(\\d{2})[\\.-:](\\d{2})[\\.-:](\\d{2})
compact_datetime = (\\d{4})(\\d{2})(\\d{2})_(\\d{2})(\\d{2})(\\d{2})

# Nur Datum (Zeit wird auf 12:00:00 gesetzt)
date_dashes = (\\d{4})-(\\d{2})-(\\d{2})
date_compact = (\\d{4})(\\d{2})(\\d{2})

# Kamera-/App-spezifische Formate
img_camera = IMG_(\\d{4})(\\d{2})(\\d{2})_(\\d{2})(\\d{2})(\\d{2})
whatsapp = IMG-(\\d{4})(\\d{2})(\\d{2})-WA\\d+
signal = signal-(\\d{4})-(\\d{2})-(\\d{2})-(\\d{2})(\\d{2})(\\d{2})
screenshot = Screenshot_(\\d{4})-(\\d{2})-(\\d{2})-(\\d{2})-(\\d{2})-(\\d{2})

# Fallback: beliebiger Text + Datum
fallback_date = .*(\\d{4})(\\d{2})(\\d{2}).*

# Eigene Pattern können hier hinzugefügt werden:
# mein_format = (\\d{4})\\.(\\d{2})\\.(\\d{2})_(\\d{2})h(\\d{2})m(\\d{2})s
"""
            self.create_default_config(config_file, config_content)
            print(f"🔧 Standard-Config erstellt: {config_file}")
        
        try:
            config = configparser.ConfigParser()
            config.read(config_file, encoding='utf-8')
            
            if 'Filename_Patterns' in config:
                patterns = []
                for key, pattern in config['Filename_Patterns'].items():
                    if pattern.strip():  # Überspringe leere Pattern
                        patterns.append(pattern.strip())
                
                if patterns:
                    print(f"🔧 {len(patterns)} Pattern aus Config geladen: {config_file}")
                    return patterns
                    
        except Exception as e:
            print(f"⚠️  Fehler beim Laden der Config: {e}")
            print("🔧 Verwende Default-Pattern")
            return default_patterns
    
    def create_default_config(self, config_file: Path, config_content) -> None:
        """Erstellt Standard-Konfigurationsdatei"""
        config_dir = config_file.parent
        config_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(config_content)
        except Exception as e:
            print(f"❌ Fehler beim Erstellen der Config: {e}")
    
    def generate_script_path(self) -> str:
        """Generiert automatischen Script-Pfad mit PROJECT_SCRIPTS falls verfügbar"""
        # Prüfe PROJECT_SCRIPTS Umgebungsvariable
        project_scripts = os.environ.get('PROJECT_SCRIPTS')
        
        if project_scripts:
            scripts_dir = Path(project_scripts)
            # Erstelle Verzeichnis falls es nicht existiert
            scripts_dir.mkdir(parents=True, exist_ok=True)
            
            # Bestimme Dateiendung basierend auf Script-Typ
            extension = ".ps1" if self.powershell else ".sh"
            script_filename = f"photo_move_{get_timestamp_util()}{extension}"
            script_path = scripts_dir / script_filename
            print(f"🔧 Verwende PROJECT_SCRIPTS: {script_path}")
            return str(script_path)
        else:
            # Fallback auf aktuelles Verzeichnis
            print(f"🔧 PROJECT_SCRIPTS nicht gesetzt, verwende aktuelles Verzeichnis")
            extension = ".ps1" if self.powershell else ".sh"
            return f"photo_move_script{extension}"
    
    def generate_cache_filename(self) -> str:
        """Generiert automatischen Cache-Dateinamen mit PROJECT_CACHE falls verfügbar"""
        # Prüfe PROJECT_CACHE Umgebungsvariable
        project_cache = os.environ.get('PROJECT_CACHE')
        
        # Verwende nur den Namen des Quellverzeichnisses
        source_abs = self.source_dir.resolve()
        source_name = source_abs.name or "root"
        source_clean = clean_filename(source_name)
        
        cache_filename = f"photo_cache_{source_clean}.json"
        
        if project_cache:
            cache_dir = Path(project_cache)
            # Erstelle Verzeichnis falls es nicht existiert
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = cache_dir / cache_filename
            print(f"🔧 Verwende PROJECT_CACHE: {cache_path}")
            return str(cache_path)
        else:
            # Fallback auf aktuelles Verzeichnis
            print(f"🔧 PROJECT_CACHE nicht gesetzt, verwende aktuelles Verzeichnis")
            print(f"🔧 Auto-Cache-Name: {cache_filename}")
            return cache_filename
    

    
    def get_datetime_from_filename(self, filepath: Path) -> Optional[datetime]:
        """Extrahiert Datum/Zeit aus Dateinamen (Pattern aus Konfiguration)"""
        import re
        
        filename = filepath.stem  # Dateiname ohne Erweiterung
        
        # Verwende Pattern aus Konfiguration
        for pattern in self.filename_patterns:
            match = re.search(pattern, filename)
            if match:
                groups = match.groups()
                try:
                    if len(groups) == 6:  # Vollständiges Datum + Zeit
                        year, month, day, hour, minute, second = map(int, groups)
                        return datetime(year, month, day, hour, minute, second)
                    elif len(groups) == 3:  # Nur Datum
                        year, month, day = map(int, groups)
                        return datetime(year, month, day, 12, 0, 0)  # Mittag als Standard
                    elif len(groups) == 2:  # Spezielle Formate
                        continue
                except ValueError as e:
                    print(f"  Ungültiges Datum im Dateinamen {filename}: {e}")
                    continue
        
        return None
    
    def add_exif_to_file(self, filepath: Path, datetime_from_filename: datetime) -> bool:
        """Fügt EXIF-Daten aus Dateinamen zu Bilddatei hinzu"""
        if not self.add_exif:
            return False
            
        # Nur für unterstützte Bildformate
        if filepath.suffix.lower() not in self.exif_writable_extensions:
            return False
            
        try:
            # Prüfe ob bereits EXIF-Datum vorhanden
            existing_exif_date = self.get_exif_datetime(filepath)
            if existing_exif_date:
                print(f"  ⏭️  EXIF bereits vorhanden: {filepath.name}")
                self.exif_skipped_count += 1
                return False
            
            # Lade Bild - explicitly convert Path to string to handle special characters
            with Image.open(str(filepath)) as img:
                # Hole existierende EXIF-Daten oder erstelle neue
                exif_dict = img.getexif()
                
                # Konvertiere datetime zu EXIF-Format (YYYY:MM:DD HH:MM:SS)
                exif_datetime_str = datetime_from_filename.strftime('%Y:%m:%d %H:%M:%S')
                
                # Setze EXIF-Tags für Datum/Zeit
                # 306 = DateTime (Image creation date)
                # 36867 = DateTimeOriginal (Original image date)  
                # 36868 = DateTimeDigitized (Digitization date)
                exif_dict[306] = exif_datetime_str      # DateTime
                exif_dict[36867] = exif_datetime_str    # DateTimeOriginal
                exif_dict[36868] = exif_datetime_str    # DateTimeDigitized
                
                # Optional: Software-Tag setzen
                exif_dict[305] = "PhotoOrganizer"       # Software
                
                # Erstelle Backup des Original (optional)
                # backup_path = filepath.with_suffix(filepath.suffix + '.backup')
                # shutil.copy2(filepath, backup_path)
                
                # Speichere Bild mit neuen EXIF-Daten
                img.save(filepath, exif=exif_dict, quality=95, optimize=True)
                
                print(f"  ✅ EXIF hinzugefügt: {filepath.name} -> {exif_datetime_str}")
                self.exif_added_count += 1
                return True
                
        except Exception as e:
            print(f"  ❌ EXIF-Fehler bei {filepath.name}: {e}")
            self.exif_error_count += 1
            return False
    
    def escape_shell_path(self, path: Path) -> str:
        """Escapet Pfade für sichere Shell-Verwendung"""
        shell = 'powershell' if self.powershell else 'bash'
        return escape_shell_path(str(path), shell=shell)
    
    def generate_shell_script(self, events: Dict[str, List[PhotoInfo]]) -> None:
        """Erzeugt Shell-Script für die Foto-Organisation"""
        if self.powershell:
            self.generate_powershell_script(events)
        else:
            self.generate_bash_script(events)
    
    def generate_bash_script(self, events: Dict[str, List[PhotoInfo]]) -> None:
        """Erzeugt Bash-Script für die Foto-Organisation"""
        script_content = []
        
        # Script-Header
        script_content.append("#!/bin/bash")
        script_content.append("# Automatisch generiertes Bash-Script für Foto-Organisation")
        script_content.append(f"# Erstellt am: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        script_content.append(f"# Quelle: {self.source_dir}")
        script_content.append(f"# Ziel: {self.target_dir}")
        script_content.append("")
        script_content.append("set -e  # Stoppe bei Fehlern")
        script_content.append("set -u  # Stoppe bei undefinierten Variablen")
        script_content.append("")
        script_content.append("# Farben für Output")
        script_content.append('GREEN="\\033[0;32m"')
        script_content.append('RED="\\033[0;31m"')
        script_content.append('BLUE="\\033[0;34m"')
        script_content.append('YELLOW="\\033[0;33m"')
        script_content.append('NC="\\033[0m"  # No Color')
        script_content.append("")
        script_content.append("# Statistiken")
        script_content.append("moved_count=0")
        script_content.append("error_count=0")
        script_content.append("")
        
        # Funktion für Datei-Moves
        script_content.append("# Funktion zum Verschieben einer einzelnen Datei")
        script_content.append("move_file() {")
        script_content.append("    local source_file=\"$1\"")
        script_content.append("    local target_path=\"$2\"")
        script_content.append("    ")
        script_content.append("    if [[ -f \"$source_file\" ]]; then")
        script_content.append("        if mv \"$source_file\" \"$target_path\"; then")
        script_content.append("            echo -e \"  ${GREEN}✅ $(basename \"$source_file\")${NC}\"")
        script_content.append("            moved_count=$((moved_count + 1))")
        script_content.append("        else")
        script_content.append("            echo -e \"  ${RED}❌ Fehler: $(basename \"$source_file\")${NC}\"")
        script_content.append("            error_count=$((error_count + 1))")
        script_content.append("        fi")
        script_content.append("    else")
        script_content.append("        echo -e \"  ${RED}❌ Nicht gefunden: $(basename \"$source_file\")${NC}\"")
        script_content.append("        error_count=$((error_count + 1))")
        script_content.append("    fi")
        script_content.append("}")
        script_content.append("")
        
        script_content.append("echo -e \"${BLUE}🚀 Starte Foto-Organisation...${NC}\"")
        script_content.append("echo")
        script_content.append("")
        
        # Wechsle ins Quellverzeichnis
        script_content.append("# Wechsle ins Quellverzeichnis")
        source_escaped = self.escape_shell_path(self.source_dir)
        script_content.append(f"cd {source_escaped}")
        script_content.append(f"echo -e \"${{YELLOW}}📁 Arbeitsverzeichnis: $(pwd)${{NC}}\"")
        script_content.append("echo")
        script_content.append("")
        
        # Sammle alle Move-Kommandos
        all_moves = []
        
        for event_name, photos in events.items():
            if event_name == "einzeldateien" or event_name.endswith("/einzeldateien"):
                # Einzeldateien in Jahresordnern
                if "/" in event_name:
                    year = event_name.split("/")[0]
                    target_folder = self.target_dir / year / "einzeldateien" 
                    script_content.append(f"# 📄 Einzeldateien {year} ({len(photos)} Dateien)")
                    script_content.append(f"echo -e \"${{BLUE}}📄 Einzeldateien {year} ({len(photos)} Dateien)${{NC}}\"")
                else:
                    target_folder = self.target_dir / "einzeldateien"
                    script_content.append(f"# 📄 Einzeldateien ({len(photos)} Dateien)")
                    script_content.append(f"echo -e \"${{BLUE}}📄 Einzeldateien ({len(photos)} Dateien)${{NC}}\"")
                
                # Erstelle Zielordner
                target_escaped = self.escape_shell_path(target_folder)
                script_content.append(f"mkdir -p {target_escaped}")
            elif event_name == ".":
                # Fallback: Einzelne Dateien direkt ins Zielverzeichnis (sollte nicht mehr vorkommen)
                target_folder = self.target_dir
                script_content.append(f"# 📄 Einzelne Dateien -> Zielverzeichnis ({len(photos)} Dateien)")
                script_content.append(f"echo -e \"${{BLUE}}📄 Einzelne Dateien -> Zielverzeichnis ({len(photos)} Dateien)${{NC}}\"")
            else:
                # Event-Ordner
                target_folder = self.target_dir / event_name
                script_content.append(f"# 📁 {event_name}/ ({len(photos)} Dateien)")
                script_content.append(f"echo -e \"${{BLUE}}📁 {event_name}/ ({len(photos)} Dateien)${{NC}}\"")
                
                # Erstelle Zielordner
                target_escaped = self.escape_shell_path(target_folder)
                script_content.append(f"mkdir -p {target_escaped}")
            
            # Move-Kommandos für diese Gruppe
            for photo in photos:
                target_path = target_folder / photo.filepath.name
                
                # Sammle für Statistiken
                all_moves.append((photo.filepath, target_path))
                
                # Relative Pfade für einfachere Kommandos
                rel_source = photo.filepath.relative_to(self.source_dir)
                rel_source_escaped = self.escape_shell_path(rel_source)
                target_escaped = self.escape_shell_path(target_path)
                
                # Funktionsaufruf
                script_content.append(f"move_file {rel_source_escaped} {target_escaped}")
            
            script_content.append("echo")
        
        # Script-Footer mit Statistiken
        script_content.append("")
        script_content.append("# Zusammenfassung")
        script_content.append("echo")
        script_content.append("echo -e \"${BLUE}=== ZUSAMMENFASSUNG ===${NC}\"")
        script_content.append("echo -e \"${GREEN}✅ $moved_count Dateien erfolgreich verschoben${NC}\"")
        script_content.append("if [[ $error_count -gt 0 ]]; then")
        script_content.append("    echo -e \"${RED}❌ $error_count Fehler aufgetreten${NC}\"")
        script_content.append("    exit 1")
        script_content.append("else")
        script_content.append("    echo -e \"${GREEN}🎉 Alle Dateien erfolgreich organisiert!${NC}\"")
        script_content.append("fi")
        
        # Speichere alle Move-Kommandos für interne Verwendung
        self.move_commands = all_moves
        
        # Script in Datei schreiben
        self.write_script_to_file(script_content)
    
    def generate_powershell_script(self, events: Dict[str, List[PhotoInfo]]) -> None:
        """Erzeugt PowerShell-Script für die Foto-Organisation"""
        script_content = []
        
        # Script-Header
        script_content.append("# Automatisch generiertes PowerShell-Script für Foto-Organisation")
        script_content.append(f"# Erstellt am: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        script_content.append(f"# Quelle: {self.source_dir}")
        script_content.append(f"# Ziel: {self.target_dir}")
        script_content.append("")
        script_content.append("# Fehlerbehandlung")
        script_content.append("$ErrorActionPreference = 'Stop'")
        script_content.append("")
        script_content.append("# Statistiken")
        script_content.append("$movedCount = 0")
        script_content.append("$errorCount = 0")
        script_content.append("")
        
        # Funktion für Datei-Moves
        script_content.append("# Funktion zum Verschieben einer einzelnen Datei")
        script_content.append("function Move-PhotoFile {")
        script_content.append("    param(")
        script_content.append("        [string]$SourceFile,")
        script_content.append("        [string]$TargetPath")
        script_content.append("    )")
        script_content.append("    ")
        script_content.append("    if (Test-Path $SourceFile) {")
        script_content.append("        try {")
        script_content.append("            Move-Item -Path $SourceFile -Destination $TargetPath -Force")
        script_content.append('            Write-Host "   $(Split-Path $SourceFile -Leaf)" -ForegroundColor Green')
        script_content.append("            $script:movedCount++")
        script_content.append("        }")
        script_content.append("        catch {")
        script_content.append('            Write-Host "[NOT OK] Fehler: $(Split-Path $SourceFile -Leaf)" -ForegroundColor Red')
        script_content.append("            $script:errorCount++")
        script_content.append("        }")
        script_content.append("    }")
        script_content.append("    else {")
        script_content.append('        Write-Host "[NOT OK] Nicht gefunden: $(Split-Path $SourceFile -Leaf)" -ForegroundColor Red')
        script_content.append("        $script:errorCount++")
        script_content.append("    }")
        script_content.append("}")
        script_content.append("")
        
        script_content.append('Write-Host "Starte Foto-Organisation..." -ForegroundColor Blue')
        script_content.append('Write-Host ""')
        script_content.append("")
        
        # Wechsle ins Quellverzeichnis
        script_content.append("# Wechsle ins Quellverzeichnis")
        source_escaped = self._escape_powershell_string(str(self.source_dir))
        script_content.append(f"Set-Location {source_escaped}")
        script_content.append('Write-Host "Arbeitsverzeichnis: $(Get-Location)" -ForegroundColor Yellow')
        script_content.append('Write-Host ""')
        script_content.append("")
        
        # Sammle alle Move-Kommandos
        all_moves = []
        
        for event_name, photos in events.items():
            if event_name == ".":
                # Einzelne Dateien direkt ins Zielverzeichnis
                target_folder = self.target_dir
                safe_header = self._escape_powershell_string(f"📄 Einzelne Dateien -> Zielverzeichnis -{len(photos)} Dateien")
                script_content.append(f"# 📄 Einzelne Dateien -> Zielverzeichnis -{len(photos)} Dateien")
                script_content.append(f"Write-Host {safe_header} -ForegroundColor Blue")
            else:
                # Event-Ordner
                target_folder = self.target_dir / event_name
                safe_header = self._escape_powershell_string(f"{event_name}/ - {len(photos)} Dateien")
                script_content.append(f"# {event_name.replace('/', '_')}/ - {len(photos)} Dateien")
                script_content.append(f"Write-Host {safe_header} -ForegroundColor Blue")
                
                # Erstelle Zielordner
                target_escaped = self._escape_powershell_string(str(target_folder))
                script_content.append(f"New-Item -Path {target_escaped} -ItemType Directory -Force | Out-Null")
            
            # Move-Kommandos für diese Gruppe
            for photo in photos:
                target_path = target_folder / photo.filepath.name
                
                # Sammle für Statistiken
                all_moves.append((photo.filepath, target_path))
                
                # Relative Pfade für einfachere Kommandos
                rel_source = photo.filepath.relative_to(self.source_dir)
                rel_source_escaped = self._escape_powershell_string(str(rel_source))
                target_escaped = self._escape_powershell_string(str(target_path))
                
                # Funktionsaufruf
                script_content.append(f"Move-PhotoFile {rel_source_escaped} {target_escaped}")
            
            script_content.append('Write-Host ""')
        
        # Script-Footer mit Statistiken
        script_content.append("")
        script_content.append("# Zusammenfassung")
        script_content.append('Write-Host ""')
        script_content.append('Write-Host "=== ZUSAMMENFASSUNG ===" -ForegroundColor Blue')
        script_content.append('Write-Host "$movedCount Dateien erfolgreich verschoben" -ForegroundColor Green')
        script_content.append("if ($errorCount -gt 0) {")
        script_content.append('    Write-Host "$errorCount Fehler aufgetreten" -ForegroundColor Red')
        script_content.append("    exit 1")
        script_content.append("}")
        script_content.append("else {")
        script_content.append('    Write-Host "Alle Dateien erfolgreich organisiert!" -ForegroundColor Green')
        script_content.append("}")
        
        # Speichere alle Move-Kommandos für interne Verwendung
        self.move_commands = all_moves
        
        # Script in Datei schreiben
        self.write_script_to_file(script_content)

    def _escape_powershell_string(self, text: str) -> str:
        """
        Escaped einen String für PowerShell korrekt.
        Verwendet einfache Anführungszeichen für bessere Kompatibilität mit Unicode.
        """
        # Ersetze einfache Anführungszeichen durch doppelte einfache Anführungszeichen
        escaped = text.replace("'", "''")
        return f"'{escaped}'"

    def write_script_to_file(self, script_content: List[str]) -> None:
        """Schreibt Script-Inhalt in Datei"""
        try:
            with open(self.script_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(script_content))
            
            # Script ausführbar machen (nur bei Bash)
            if not self.powershell:
                import stat
                self.script_path.chmod(self.script_path.stat().st_mode | stat.S_IEXEC)
            
            script_type = "PowerShell" if self.powershell else "Bash"
            execution_cmd = f"powershell -ExecutionPolicy Bypass -File {self.script_path}" if self.powershell else f"bash {self.script_path}"
            
            print(f"\n🎯 {script_type}-Script erstellt: {self.script_path}")
            print(f"   🔧 Ausführung mit: {execution_cmd}")
            print(f"   ⚠️  Das Script verschiebt die Dateien tatsächlich!")
            
        except Exception as e:
            print(f"❌ Fehler beim Erstellen des Shell-Scripts: {e}")
    
    def get_exif_datetime(self, filepath: Path) -> Optional[datetime]:
        """Extrahiert Datum/Zeit aus EXIF-Daten"""
        try:
            if filepath.suffix.lower() in self.video_extensions:
                return self.get_video_datetime(filepath)

            # Explicitly convert Path to string to handle special characters properly
            with Image.open(str(filepath)) as img:
                exif = img._getexif()
                if exif:
                    for tag_id, value in exif.items():
                        tag = TAGS.get(tag_id, tag_id)
                        if tag in ['DateTime', 'DateTimeOriginal', 'DateTimeDigitized']:
                            try:
                                return datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                            except ValueError:
                                continue
        except Exception as e:
            print(f"EXIF-Fehler bei {filepath}: {e}")
        return None
    
    def get_best_datetime(self, filepath: Path) -> datetime:
        """Bestimmt den besten Zeitstempel in der Prioritätsreihenfolge: EXIF > Dateiname > Datei-Zeit"""
        # 1. Priorität: EXIF-Daten
        exif_datetime = self.get_exif_datetime(filepath)
        if exif_datetime:
            print(f"  ✅ EXIF-Datum: {exif_datetime}")
            return exif_datetime
        
        # 2. Priorität: Dateiname
        filename_datetime = self.get_datetime_from_filename(filepath)
        if filename_datetime:
            print(f"  📝 Dateiname-Datum: {filename_datetime}")
            
            # EXIF hinzufügen falls gewünscht und möglich
            if self.add_exif:
                self.add_exif_to_file(filepath, filename_datetime)
            
            return filename_datetime
        
        # 3. Priorität: Datei-Modifikationszeit
        file_datetime = datetime.fromtimestamp(filepath.stat().st_mtime)
        print(f"  📁 Datei-Zeit: {file_datetime}")
        return file_datetime
    
    def get_video_datetime(self, filepath: Path) -> Optional[datetime]:
        """Extrahiert Datum/Zeit aus Video-Metadaten mit ffprobe"""
        if not FFPROBE_AVAILABLE:
            return None

        try:
            cmd = [FFPROBE_PATH, '-v', 'quiet', '-print_format', 'json', '-show_format', str(filepath)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                creation_time = data.get('format', {}).get('tags', {}).get('creation_time')
                if creation_time:
                    # Verschiedene Zeitformat-Varianten probieren
                    formats = ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S']
                    for fmt in formats:
                        try:
                            return datetime.strptime(creation_time, fmt)
                        except ValueError:
                            continue
        except Exception as e:
            print(f"Video-Metadaten-Fehler bei {filepath}: {e}")
        return None
    
    def get_gps_coords(self, filepath: Path) -> Optional[Tuple[float, float]]:
        """Extrahiert GPS-Koordinaten aus EXIF-Daten"""
        try:
            if filepath.suffix.lower() in self.video_extensions:
                return None  # GPS aus Videos ist komplexer

            # Explicitly convert Path to string to handle special characters properly
            with Image.open(str(filepath)) as img:
                exif = img._getexif()
                if exif:
                    gps_info = exif.get(34853)  # GPS IFD
                    if gps_info:
                        gps_data = {}
                        for key, value in gps_info.items():
                            decoded = GPSTAGS.get(key, key)
                            gps_data[decoded] = value
                        
                        if 'GPSLatitude' in gps_data and 'GPSLongitude' in gps_data:
                            lat = self.convert_gps_coord(gps_data['GPSLatitude'], gps_data.get('GPSLatitudeRef', 'N'))
                            lon = self.convert_gps_coord(gps_data['GPSLongitude'], gps_data.get('GPSLongitudeRef', 'E'))
                            return (lat, lon)
        except Exception as e:
            print(f"GPS-Fehler bei {filepath}: {e}")
        return None
    
    def convert_gps_coord(self, coord_tuple, ref) -> float:
        """Konvertiert GPS-Koordinaten von DMS zu Dezimalgrad"""
        degrees, minutes, seconds = coord_tuple
        decimal = float(degrees) + float(minutes)/60 + float(seconds)/3600
        if ref in ['S', 'W']:
            decimal = -decimal
        return decimal
    
    def calculate_distance(self, coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """Berechnet Entfernung zwischen zwei GPS-Koordinaten in km (Haversine-Formel)"""
        lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
        lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371  # Erdradius in km
        
        return c * r
    
    def get_location_name(self, coords: Tuple[float, float]) -> Optional[str]:
        """Konvertiert GPS-Koordinaten zu Ortsnamen via Reverse-Geocoding (Thread-sicher)"""
        if not self.use_geocoding:
            return None
            
        # Cache prüfen (gerundet auf ~100m Genauigkeit)
        rounded_coords = (round(coords[0], 3), round(coords[1], 3))
        
        # Thread-sicherer Cache-Zugriff
        with self.location_cache_lock:
            if rounded_coords in self.location_cache:
                return self.location_cache[rounded_coords]
        
        try:
            # Nominatim (OpenStreetMap) API - kostenlos, aber mit Rate-Limiting
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                'lat': coords[0],
                'lon': coords[1],
                'format': 'json',
                'addressdetails': 1,
                'zoom': 10,  # Stadt-Level
                'extratags': 1
            }
            headers = {
                'User-Agent': 'PhotoOrganizer/1.0 (Python Script)'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Rate-Limiting respektieren (thread-sicher)
            time.sleep(1.1)  # Nominatim: max 1 request/second
            
            if 'address' in data:
                address = data['address']
                
                # Priorisierte Ortsnamen (vom spezifischsten zum allgemeinsten)
                location_candidates = [
                    address.get('city'),
                    address.get('town'),
                    address.get('village'),
                    address.get('municipality'),
                    address.get('county'),
                    address.get('state_district'),
                    address.get('state')
                ]
                
                # Ersten verfügbaren Ortsnamen nehmen
                for location in location_candidates:
                    if location:
                        # Sonderzeichen für Dateinamen bereinigen
                        clean_location = clean_location_name_util(location)

                        # Thread-sicher in Cache speichern
                        with self.location_cache_lock:
                            self.location_cache[rounded_coords] = clean_location
                        return clean_location
            
        except requests.RequestException as e:
            print(f"Geocoding-Fehler für {coords}: {e}")
        except Exception as e:
            print(f"Unerwarteter Geocoding-Fehler für {coords}: {e}")
        
        # Fallback: Cache leeren Eintrag setzen (thread-sicher)
        with self.location_cache_lock:
            self.location_cache[rounded_coords] = None
        return None
    
    
    def save_cache(self) -> None:
        """Speichert Photo-Daten in JSON-Cache"""
        if not self.cache_file:
            return
            
        cache_data = {
            'metadata': {
                'created': datetime.now().isoformat(),
                'source_dir': str(self.source_dir),
                'target_dir': str(self.target_dir),
                'total_photos': len(self.photos),
                'duplicates_count': len(self.duplicates),
                'cached_count': len(self.cached)
            },
            'photos': [],
            'duplicates': list(self.duplicates),
            'cached': list(self.cached),  # Dateien bereits in der Sammlung
            'location_cache': {}
        }
        
        # Photo-Daten serialisieren
        for photo in self.photos:
            photo_data = {
                'filepath': str(photo.filepath),
                'datetime': photo.datetime.isoformat(),
                'gps_coords': photo.gps_coords,
                'location_name': photo.location_name,
                'file_hash': photo.file_hash,
                'file_size': photo.file_size,
                'is_video': photo.is_video
            }
            cache_data['photos'].append(photo_data)
        
        # Location-Cache serialisieren
        with self.location_cache_lock:
            for coords, location in self.location_cache.items():
                key = f"{coords[0]:.3f},{coords[1]:.3f}"
                cache_data['location_cache'][key] = location
        
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            print(f"💾 Cache gespeichert: {self.cache_file}")
        except Exception as e:
            print(f"❌ Fehler beim Speichern des Caches: {e}")
    
    def load_cache(self) -> bool:
        """Lädt Photo-Daten aus JSON-Cache"""
        if not self.cache_file or not self.cache_file.exists():
            if self.cache_file:
                print(f"📂 Cache-Datei nicht gefunden: {self.cache_file}")
            return False
            
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            print(f"📂 Lade Cache: {self.cache_file}")
            
            # Metadata prüfen
            metadata = cache_data.get('metadata', {})
            cached_source = metadata.get('source_dir')
            cached_target = metadata.get('target_dir')
            
            # Validiere Cache-Kompatibilität
            if cached_source != str(self.source_dir):
                print(f"⚠️  Cache-Warnung: Quellverzeichnis unterschiedlich")
                print(f"   Cache: {cached_source}")
                print(f"   Aktuell: {self.source_dir}")
                print(f"   Cache wird trotzdem verwendet (nur bei identischen Inhalten sinnvoll)")
            
            # Zielverzeichnis wird nicht validiert (irrelevant für Cache)
            
            # Photo-Daten laden
            self.photos = []
            skipped_files = 0
            for photo_data in cache_data.get('photos', []):
                try:
                    filepath = Path(photo_data['filepath'])

                    # Skip files that no longer exist
                    if not filepath.exists():
                        skipped_files += 1
                        continue

                    photo = PhotoInfo(
                        filepath=filepath,
                        datetime=datetime.fromisoformat(photo_data['datetime']),
                        gps_coords=tuple(photo_data['gps_coords']) if photo_data['gps_coords'] else None,
                        location_name=photo_data.get('location_name'),
                        file_hash=photo_data['file_hash'],
                        file_size=photo_data['file_size'],
                        is_video=photo_data['is_video']
                    )
                    self.photos.append(photo)
                except Exception as e:
                    print(f"⚠️  Fehler beim Laden von Photo-Daten: {e}")
            
            # Duplikate laden
            self.duplicates = set(cache_data.get('duplicates', []))

            # Cached-Einträge laden (Dateien bereits in der Sammlung)
            self.cached = set(cache_data.get('cached', []))

            # Location-Cache laden
            location_cache_data = cache_data.get('location_cache', {})
            with self.location_cache_lock:
                self.location_cache = {}
                for coord_str, location in location_cache_data.items():
                    try:
                        lat_str, lon_str = coord_str.split(',')
                        coords = (float(lat_str), float(lon_str))
                        self.location_cache[coords] = location
                    except Exception as e:
                        print(f"⚠️  Fehler beim Laden von GPS-Cache: {e}")
            
            cache_created = metadata.get('created', 'unbekannt')
            print(f"✅ Cache geladen (erstellt: {cache_created}):")
            print(f"  📸 {len(self.photos)} Fotos/Videos")
            if skipped_files > 0:
                print(f"  ⚠️  {skipped_files} Dateien aus Cache übersprungen (nicht mehr vorhanden)")
            print(f"  🗑️  {len(self.duplicates)} Duplikate")
            print(f"  🗺️  {len(self.location_cache)} Orte im GPS-Cache")
            return True
            
        except Exception as e:
            print(f"❌ Fehler beim Laden des Caches: {e}")
            return False
    
    def post_process_geocoding(self) -> None:
        """Führt Geocoding als separaten, sequenziellen Schritt durch"""
        if not self.use_geocoding:
            return

        # Lade aktuelle Geokoordinaten aus geo_coords.cfg nochmals
        # (für den Fall, dass die Datei zwischen Läufen aktualisiert wurde)
        print("🔄 Aktualisiere Geokoordinaten aus geo_coords.cfg...")
        updated_cache = self.load_geo_cords()
        with self.location_cache_lock:
            # Merge: neue Einträge hinzufügen, bestehende behalten
            for coords, location in updated_cache.items():
                if coords not in self.location_cache:
                    self.location_cache[coords] = location

        # Sammle alle eindeutigen GPS-Koordinaten ohne Ortsname
        coords_to_process = []
        for photo in self.photos:
            if photo.gps_coords and not photo.location_name:
                rounded_coords = (round(photo.gps_coords[0], 3), round(photo.gps_coords[1], 3))
                if rounded_coords not in coords_to_process:
                    coords_to_process.append(rounded_coords)

        if not coords_to_process:
            print("🌍 Alle GPS-Koordinaten haben bereits Ortsnamen")
            return

        print(f"\n🌍 Starte sequenzielles Geocoding für {len(coords_to_process)} Orte...")

        processed_count = 0
        for coords in coords_to_process:
            processed_count += 1
            print(f"📍 Geocoding {processed_count}/{len(coords_to_process)}: {coords[0]:.3f}, {coords[1]:.3f}")

            # Überspringe wenn bereits im Cache
            with self.location_cache_lock:
                if coords in self.location_cache:
                    location = self.location_cache[coords]
                    if location is None:
                        print(f"   ❌ Bereits als nicht-verfügbar markiert")
                    else:
                        print(f"   ✅ Aus Cache: {location}")
                    continue
            
            # Geocoding durchführen
            location_name = self.get_location_name(coords)
            if location_name:
                print(f"   ✅ Gefunden: {location_name}")
                
                # Aktualisiere alle Fotos mit diesen Koordinaten
                for photo in self.photos:
                    if photo.gps_coords:
                        photo_rounded = (round(photo.gps_coords[0], 3), round(photo.gps_coords[1], 3))
                        if photo_rounded == coords:
                            photo.location_name = location_name
            else:
                print(f"   ❌ Kein Ortsname gefunden")
        
        print(f"✅ Geocoding abgeschlossen")
        
        # Cache aktualisieren falls vorhanden
        if self.cache_file:
            self.save_cache()
            self.save_geo_locations_to_config()
    
    def process_single_file(self, filepath: Path) -> Optional[PhotoInfo]:
        """Verarbeitet eine einzelne Datei (für parallele Ausführung) - OHNE Geocoding"""
        try:
            # Hash für Duplikat-Erkennung
            file_hash = get_file_hash(filepath)

            # Prüfe ob bereits in permanenter Cache vorhanden (wenn aktiviert)
            if self.compare_with_cache and file_hash in self.cached_hash_dict:
                # Datei ist bereits in der Sammlung gespeichert
                self.cached.add(str(filepath))
                return None

            # Thread-sicherer Hash-Cache-Zugriff
            with self.hash_cache_lock:
                if file_hash in self.hash_cache:
                    # Duplikat gefunden (in dieser Verarbeitung)
                    return None
                self.hash_cache[file_hash] = str(filepath)

            # Zeitstempel extrahieren (Priorität: EXIF > Dateiname > Datei-Zeit)
            photo_datetime = self.get_best_datetime(filepath)

            # GPS-Koordinaten extrahieren (OHNE API-Geocoding)
            gps_coords = self.get_gps_coords(filepath)

            # Prüfe ob GPS-Koordinate bereits in geo_coords.cfg vorhanden ist
            location_name = None
            if gps_coords:
                rounded_coords = (round(gps_coords[0], 3), round(gps_coords[1], 3))
                with self.location_cache_lock:
                    if rounded_coords in self.location_cache:
                        location_name = self.location_cache[rounded_coords]

            return PhotoInfo(
                filepath=filepath,
                datetime=photo_datetime,
                gps_coords=gps_coords,
                location_name=location_name,  # Aus geo_coords.cfg oder None (wird später geocodiert)
                file_hash=file_hash,
                file_size=filepath.stat().st_size,
                is_video=filepath.suffix.lower() in self.video_extensions
            )

        except Exception as e:
            print(f"❌ Fehler bei der Verarbeitung von {filepath}: {e}")
            return None
    
    def scan_photos(self) -> None:
        """Scannt alle Fotos im Quellverzeichnis mit paralleler Verarbeitung"""
        
        # Versuche Cache zu laden
        if self.cache_file and self.load_cache():
            print("📂 Verwende Daten aus Cache")
            return
        
        print(f"🔍 Scanne Fotos in: {self.source_dir}")
        
        # Sammle alle zu verarbeitenden Dateien
        all_files = []
        for filepath in self.source_dir.rglob('*'):
            # Validate: is_file() checks during scan, exists() prevents race conditions
            if filepath.is_file() and filepath.exists() and filepath.suffix.lower() in self.supported_extensions:
                all_files.append(filepath)
        
        print(f"📁 Gefunden: {len(all_files)} Dateien zum Verarbeiten")
        print(f"🚀 Starte parallele Verarbeitung mit {self.max_workers} Threads...")
        print("⚠️  Geocoding wird später sequenziell durchgeführt")
        
        # Progress tracking
        processed_count = 0
        duplicates_count = 0
        
        # Parallele Verarbeitung mit ThreadPoolExecutor (OHNE Geocoding)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Alle Tasks starten
            future_to_filepath = {
                executor.submit(self.process_single_file, filepath): filepath 
                for filepath in all_files
            }
            
            # Ergebnisse sammeln
            for future in as_completed(future_to_filepath):
                filepath = future_to_filepath[future]
                processed_count += 1
                
                # Progress anzeigen (alle 100 Dateien)
                if processed_count % 100 == 0 or processed_count == len(all_files):
                    progress = (processed_count / len(all_files)) * 100
                    print(f"📊 Progress: {processed_count}/{len(all_files)} ({progress:.1f}%)")
                
                try:
                    photo_info = future.result()
                    if photo_info is None:
                        # Duplikat
                        duplicates_count += 1
                        self.duplicates.add(str(filepath))
                    else:
                        self.photos.append(photo_info)
                        
                except Exception as e:
                    print(f"❌ Fehler bei {filepath}: {e}")
        
        print(f"\n✅ Parallel-Verarbeitung abgeschlossen:")
        print(f"  📸 {len(self.photos)} Fotos/Videos erfolgreich verarbeitet")
        print(f"  🗑️  {duplicates_count} Duplikate gefunden")
        if self.compare_with_cache and self.cached:
            print(f"  💾 {len(self.cached)} Dateien bereits in Sammlung (Cache)")
        print(f"  🌍 {len([p for p in self.photos if p.gps_coords])} Fotos mit GPS-Daten")
        
        # EXIF-Statistiken anzeigen
        if self.add_exif:
            print(f"\n📋 EXIF-Hinzufügung:")
            print(f"  ✅ {self.exif_added_count} EXIF-Daten hinzugefügt")
            print(f"  ⏭️  {self.exif_skipped_count} bereits vorhanden")
            print(f"  ❌ {self.exif_error_count} Fehler")
        
        # Cache speichern (vor Geocoding)
        if self.cache_file:
            self.save_cache()
        
        # Geocoding als separater sequenzieller Schritt
        self.post_process_geocoding()
        
        # Cache erneut speichern (nach Geocoding)
        if self.cache_file:
            self.save_cache()
        
        print(f"  📍 {len([p for p in self.photos if p.location_name])} Fotos mit Ortsinformation")
    
    def group_photos_into_events(self) -> Dict[str, List[PhotoInfo]]:
        """Gruppiert Fotos in Events basierend auf Zeit und Ort"""
        if not self.photos:
            return {}
        
        # Sortiere Fotos nach Datum
        sorted_photos = sorted(self.photos, key=lambda p: p.datetime)
        
        events = {}
        current_event_photos = []
        current_event_start = None
        
        for photo in sorted_photos:
            if not current_event_photos:
                # Erstes Foto eines neuen Events
                current_event_photos = [photo]
                current_event_start = photo.datetime
            else:
                # Prüfe ob Foto zum aktuellen Event gehört
                time_diff = photo.datetime - current_event_start
                belongs_to_event = False
                
                # Zeitkriterium
                if time_diff.days <= self.event_max_days:
                    belongs_to_event = True
                    
                    # Zusätzliche GPS-Prüfung wenn verfügbar
                    if photo.gps_coords:
                        # Prüfe GPS-Nähe zu anderen Fotos im Event
                        for event_photo in current_event_photos:
                            if event_photo.gps_coords:
                                distance = self.calculate_distance(photo.gps_coords, event_photo.gps_coords)
                                if distance <= self.geo_radius_km:
                                    belongs_to_event = True
                                    break
                        else:
                            # Kein Foto im Event hat GPS oder alle sind zu weit weg
                            if any(p.gps_coords for p in current_event_photos):
                                belongs_to_event = False
                
                if belongs_to_event:
                    current_event_photos.append(photo)
                else:
                    # Event abschließen wenn es groß genug ist
                    self.event_name_from_number(events, current_event_photos)
                    
                    # Neues Event starten
                    current_event_photos = [photo]
                    current_event_start = photo.datetime
        
        # Letztes Event verarbeiten
        if current_event_photos:
            self.event_name_from_number(events, current_event_photos)
        
        return events

    def event_name_from_number(self, events, current_event_photos):
        if len(current_event_photos) == 1:
            # Einzelnes Foto: direkt im Zielverzeichnis
            event_name = self.create_event_name(current_event_photos)
            year = event_name.split("/")[0]
            events[year+"/einzeldateien"] = current_event_photos
        else:
            # Gruppe von Fotos: Event-Ordner klassisch benennen
            event_name = self.create_event_name(current_event_photos) 
            events[event_name] = current_event_photos
    
    def create_event_name(self, photos: List[PhotoInfo]) -> str:
        """
        Erstellt Event-Namen basierend auf Zeitraum und optional Ort.
        Verwendet konfigurierbare Muster aus [foldernames_target].
        """
        start_date = min(p.datetime for p in photos)
        end_date = max(p.datetime for p in photos)

        # Bestimme dominanten Ort falls GPS-Daten vorhanden
        location_name = self.get_dominant_location(photos)

        # Formatiere die Daten
        year = start_date.strftime('%Y')
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

        # Wähle das passende Muster aus der Konfiguration
        if (end_date - start_date).days == 0:
            # Eintägiges Event - nutze 'single_day' Muster
            pattern = self.foldernames_config.get('single_day', '{year}/{start_date}')
        else:
            # Mehrtägiges Event - nutze 'multi_day' Muster
            pattern = self.foldernames_config.get('multi_day', '{year}/{start_date}_bis_{end_date}')

        # Ersetze Variablen im Muster
        event_name = pattern.format(
            year=year,
            yyyy=year,  # Alias
            start_date=start_date_str,
            end_date=end_date_str,
            location=location_name if location_name else ''
        )

        # Entferne trailing Bindestriche falls kein Ort vorhanden
        if not location_name and event_name.endswith('-'):
            event_name = event_name[:-1]

        return event_name
    
    def get_dominant_location(self, photos: List[PhotoInfo]) -> Optional[str]:
        """Bestimmt den dominanten Ort einer Foto-Gruppe"""
        if not self.use_geocoding:
            return None
            
        # Sammle alle Ortsnamen
        locations = [p.location_name for p in photos if p.location_name]
        
        if not locations:
            return None
        
        # Häufigster Ortsname
        from collections import Counter
        location_counts = Counter(locations)
        most_common = location_counts.most_common(1)
        
        if most_common:
            dominant_location, count = most_common[0]
            # Nur verwenden wenn mindestens 30% der Fotos diesen Ort haben
            if count >= max(1, len(photos) * 0.3):
                return dominant_location
        
        return None
    
    def preview_organization(self) -> Dict[str, List[PhotoInfo]]:
        """Zeigt Vorschau der geplanten Organisation"""
        events = self.group_photos_into_events()
        
        print("\n=== VORSCHAU DER ORGANISATION ===")
        
        # Separate Zählung für Events und einzelne Dateien
        event_count = len([k for k in events.keys() if k != "." and not k.endswith("/einzeldateien")])
        single_files_count = sum(len(photos) for event_name, photos in events.items() 
                                if event_name == "." or event_name.endswith("/einzeldateien"))
        
        print(f"Insgesamt {len(self.photos)} Fotos:")
        if event_count > 0:
            print(f"  📁 {event_count} Event-Ordner")
        if single_files_count > 0:
            print(f"  📄 {single_files_count} einzelne Dateien (in Jahresordnern)")
        
        for event_name, photos in events.items():
            photo_count = len([p for p in photos if not p.is_video])
            video_count = len([p for p in photos if p.is_video])
            
            start_date = min(p.datetime for p in photos)
            end_date = max(p.datetime for p in photos)
            
            if event_name == "." or event_name.endswith("/einzeldateien"):
                if "/" in event_name:
                    year = event_name.split("/")[0]
                    print(f"\n📄 Einzeldateien {year}/:")
                else:
                    print(f"\n📄 Einzeldateien:")
                print(f"   📊 {photo_count} Fotos, {video_count} Videos")
                print(f"   📅 Zeitraum: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}")
            else:
                print(f"\n📁 {event_name}/")
                print(f"   📊 {photo_count} Fotos, {video_count} Videos")
                print(f"   📅 {start_date.strftime('%d.%m.%Y %H:%M')} - {end_date.strftime('%d.%m.%Y %H:%M')}")
            
            # GPS-Info falls verfügbar
            gps_photos = [p for p in photos if p.gps_coords]
            if gps_photos:
                print(f"   🌍 {len(gps_photos)} Fotos mit GPS-Daten")
                
                # Zeige Ortsinformationen
                locations = [p.location_name for p in photos if p.location_name]
                if locations:
                    from collections import Counter
                    location_counts = Counter(locations)
                    most_common_locations = location_counts.most_common(3)
                    location_str = ", ".join([f"{loc} ({count})" for loc, count in most_common_locations])
                    print(f"   📍 Orte: {location_str}")
        
        if self.duplicates:
            print(f"\n🗑️  {len(self.duplicates)} Duplikate werden übersprungen")
        
        return events
    
    def organize_photos(self, dry_run: bool = True) -> None:
        """Organisiert die Fotos in die Zielstruktur"""
        events = self.group_photos_into_events()
        
        # Shell-Script generieren falls gewünscht (am Ende!)
        if self.generate_script:
            self.generate_shell_script(events)
            if dry_run:
                print(f"\n💡 Dry-Run abgeschlossen.")
                return
        
        if dry_run:
            print("\n=== DRY RUN - Keine Dateien werden verschoben ===")
        else:
            print("\n=== DATEIEN WERDEN VERSCHOBEN ===")
            self.target_dir.mkdir(parents=True, exist_ok=True)
        
        moved_count = 0
        error_count = 0
        
        for event_name, photos in events.items():
            if event_name == ".":
                # Einzelne Dateien direkt ins Zielverzeichnis
                target_folder = self.target_dir
                print(f"\n📄 Einzelne Dateien (Zielverzeichnis) - {len(photos)} Dateien")
            else:
                # Event-Ordner
                target_folder = self.target_dir / event_name
                if not dry_run:
                    target_folder.mkdir(parents=True, exist_ok=True)
                print(f"\n📁 {event_name}/ ({len(photos)} Dateien)")
            
            for photo in photos:
                target_path = target_folder / photo.filepath.name
                
                # Handle Namenskonflikte
                counter = 1
                original_target = target_path
                while target_path.exists() and not dry_run:
                    stem = original_target.stem
                    suffix = original_target.suffix
                    target_path = target_folder / f"{stem}_{counter}{suffix}"
                    counter += 1
                
                try:
                    if dry_run:
                        if event_name == "." or event_name.endswith("/einzeldateien"):
                            folder_name = f"einzeldateien" if "/" not in event_name else event_name
                            print(f"  würde verschieben: {photo.filepath.name} -> {folder_name}/{target_path.name}")
                        else:
                            print(f"  würde verschieben: {photo.filepath.name} -> {target_path}")
                    else:
                        shutil.move(str(photo.filepath), str(target_path))
                        if event_name == "." or event_name.endswith("/einzeldateien"):
                            folder_name = f"einzeldateien" if "/" not in event_name else event_name
                            print(f"  ✅ {photo.filepath.name} -> {folder_name}/{target_path.name}")
                        else:
                            print(f"  ✅ {photo.filepath.name} -> {target_path.name}")
                    moved_count += 1
                except Exception as e:
                    print(f"  ❌ Fehler bei {photo.filepath.name}: {e}")
                    error_count += 1
        
        print(f"\n=== ZUSAMMENFASSUNG ===")
        print(f"✅ {moved_count} Dateien {'würden verschoben werden' if dry_run else 'verschoben'}")
        if error_count > 0:
            print(f"❌ {error_count} Fehler")
        if self.duplicates:
            print(f"🗑️  {len(self.duplicates)} Duplikate übersprungen")

    def _load_cache_hashes(self) -> Optional[Dict[str, str]]:
        """
        Lädt alle bekannten Hashes aus CSV- und JSON-Cache-Dateien.

        Returns:
            Dict hash -> filepath, oder None wenn kein Cache verfügbar.
        """
        import csv

        print("🔍 Lade Cache-Hashes...")

        project_cache = os.environ.get('PROJECT_CACHE')
        if not project_cache:
            print("⚠️  PROJECT_CACHE nicht gesetzt. Kein Cache verfügbar.")
            return None

        cache_dir = Path(project_cache)
        if not cache_dir.exists():
            print(f"⚠️  Cache-Verzeichnis nicht gefunden: {cache_dir}")
            return None

        cache_hash_map: Dict[str, str] = {}

        for csv_file in sorted(cache_dir.glob('photo_cache_permanent_*.csv')):
            print(f"  📄 Lade CSV: {csv_file.name}")
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    count = 0
                    for row in reader:
                        file_hash = row.get('file_hash', '').strip()
                        filepath = row.get('filepath', '').strip()
                        if file_hash and filepath:
                            cache_hash_map[file_hash] = filepath
                            count += 1
                print(f"     {count} Hashes geladen")
            except Exception as e:
                print(f"⚠️  Fehler beim Lesen von {csv_file.name}: {e}")

        for json_file in sorted(cache_dir.glob('photo_cache_*.json')):
            print(f"  📄 Lade JSON: {json_file.name}")
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                count = 0
                for photo in cache_data.get('photos', []):
                    file_hash = photo.get('file_hash', '').strip()
                    filepath = photo.get('filepath', '').strip()
                    if file_hash and filepath and file_hash not in cache_hash_map:
                        cache_hash_map[file_hash] = filepath
                        count += 1
                print(f"     {count} neue Hashes geladen")
            except Exception as e:
                print(f"⚠️  Fehler beim Lesen von {json_file.name}: {e}")

        if not cache_hash_map:
            print("⚠️  Keine Hashes in Cache gefunden.")
            return None

        print(f"✅ {len(cache_hash_map)} Hashes aus Cache geladen")
        return cache_hash_map

    def _find_duplicates_in_source(self, cache_hash_map: Dict[str, str]) -> Tuple[List[Tuple[Path, str]], int, int]:
        """
        Scannt das Quellverzeichnis und findet Dateien, deren Hash im Cache bekannt ist.

        Args:
            cache_hash_map: Dict hash -> filepath aus dem Cache.

        Returns:
            (duplicates, unique_count, error_count)
            duplicates: List of (source_path, cached_path)
        """
        print(f"\n🔍 Scanne Quelldateien in: {self.source_dir}")

        all_files = [
            f for f in self.source_dir.rglob('*')
            if f.is_file() and f.suffix.lower() in self.supported_extensions
        ]

        print(f"📁 {len(all_files)} Dateien zum Prüfen gefunden")
        print(f"🚀 Berechne Hashes mit {self.max_workers} Threads...")

        duplicates_found = []
        unique_count = 0
        error_count = 0

        def hash_and_check(filepath: Path):
            file_hash = get_file_hash(filepath)
            if not file_hash:
                return filepath, None, None
            cached_path = cache_hash_map.get(file_hash)
            return filepath, cached_path, file_hash

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {executor.submit(hash_and_check, f): f for f in all_files}
            processed = 0
            for future in as_completed(future_to_file):
                processed += 1
                if processed % 100 == 0 or processed == len(all_files):
                    print(f"  📊 Progress: {processed}/{len(all_files)}")
                try:
                    filepath, cached_path, file_hash = future.result()
                    if file_hash is None:
                        error_count += 1
                    elif cached_path:
                        duplicates_found.append((filepath, cached_path))
                    else:
                        unique_count += 1
                except Exception as e:
                    print(f"❌ Fehler: {e}")
                    error_count += 1

        duplicates_found.sort(key=lambda x: str(x[0]))
        return duplicates_found, unique_count, error_count

    def _print_duplicates_report(self, duplicates: List[Tuple[Path, str]], total_files: int, unique_count: int, error_count: int) -> None:
        """Gibt den Duplikat-Bericht auf der Konsole aus."""
        print(f"\n{'='*70}")
        print(f"DUPLIKAT-BERICHT")
        print(f"{'='*70}")
        print(f"Geprüfte Dateien: {total_files}")
        print(f"Duplikate:        {len(duplicates)}")
        print(f"Einzigartig:      {unique_count}")
        if error_count:
            print(f"Fehler:           {error_count}")

        if duplicates:
            print(f"\n{'='*70}")
            print(f"DUPLIKATE IM QUELLVERZEICHNIS:")
            print(f"{'='*70}")
            for src_file, cached_path in duplicates:
                try:
                    rel_src = src_file.relative_to(self.source_dir)
                except ValueError:
                    rel_src = src_file
                print(f"\n  QUELLE:  {rel_src}")
                print(f"  BEREITS: {cached_path}")
        else:
            print("\n✅ Keine Duplikate gefunden.")

    def show_duplicates_from_cache(self) -> None:
        """Zeigt Duplikate im Quellverzeichnis verglichen mit Cache-Dateien."""
        cache_hash_map = self._load_cache_hashes()
        if cache_hash_map is None:
            return

        duplicates, unique_count, error_count = self._find_duplicates_in_source(cache_hash_map)
        total = len(duplicates) + unique_count + error_count
        self._print_duplicates_report(duplicates, total, unique_count, error_count)

    def remove_duplicates_from_source(self) -> None:
        """
        Entfernt Duplikate aus dem Quellverzeichnis.
        Dateien, deren Hash im Cache bekannt ist, werden gelöscht.
        Gibt zuerst den Bericht aus, dann werden die Dateien entfernt.
        """
        cache_hash_map = self._load_cache_hashes()
        if cache_hash_map is None:
            return

        duplicates, unique_count, error_count = self._find_duplicates_in_source(cache_hash_map)
        total = len(duplicates) + unique_count + error_count
        self._print_duplicates_report(duplicates, total, unique_count, error_count)

        if not duplicates:
            return

        print(f"\n{'='*70}")
        print(f"ENTFERNE {len(duplicates)} DUPLIKATE AUS QUELLVERZEICHNIS...")
        print(f"{'='*70}")

        removed = 0
        remove_errors = 0
        for src_file, cached_path in duplicates:
            try:
                src_file.unlink()
                try:
                    rel_src = src_file.relative_to(self.source_dir)
                except ValueError:
                    rel_src = src_file
                print(f"  🗑️  Gelöscht: {rel_src}")
                removed += 1
            except Exception as e:
                print(f"  ❌ Fehler beim Löschen von {src_file.name}: {e}")
                remove_errors += 1

        print(f"\n✅ {removed} Duplikate entfernt")
        if remove_errors:
            print(f"❌ {remove_errors} Fehler beim Löschen")


def main():
    """Hauptfunktion mit Beispiel-Verwendung"""
    import argparse

    # Get defaults from environment variables
    default_source = os.environ.get('PROJECT_DATA', './data')
    default_target = os.environ.get('PROJECT_WORK', './results')

    examples = """
EXAMPLES:

  1. Dry-run: Vorschau der Organisation (keine Dateien werden verschoben):
     python lib/photo_organizer.py

  2. Mit benutzerdefinierten Verzeichnissen (Vorschau):
     python lib/photo_organizer.py D:\\Fotos D:\\OrganisierteFotos

  3. Dateien tatsächlich verschieben:
     python lib/photo_organizer.py --execute

  4. Mit benutzerdefinierten Verzeichnissen und Ausführung:
     python lib/photo_organizer.py D:\\Fotos D:\\OrganisierteFotos --execute

  5. Mit EXIF-Ergänzung aus Dateinamen:
     python lib/photo_organizer.py --addexif --execute

  6. Ohne Geocoding (schneller, wenn GPS-Daten nicht benötigt):
     python lib/photo_organizer.py --no-geocoding --execute

  7. Shell-Script generieren für spätere Ausführung:
     python lib/photo_organizer.py --generate-script

  8. PowerShell-Script statt Bash-Script:
     python lib/photo_organizer.py --generate-script --powershell

  9. Mit benutzerdefinierten Event-Einstellungen:
     python lib/photo_organizer.py --event-max-days 5 --geo-radius 20.0 --execute

 10. Mit allen Optimierungen:
     python lib/photo_organizer.py --addexif --no-compare-with-cache --max-workers 8 --execute

TYPICAL WORKFLOW:

  Step 1: Analysiere Fotos und erhalte Empfehlungen
    python lib/analyze_photos.py --quick
    python lib/analyze_photos.py

    Output: Empfehlungen für Flags (--no-geocoding, --addexif, etc.)

  Step 2: Vorschau der Organisation (kein --execute)
    python lib/photo_organizer.py

    Output: Zeigt geplante Ordnerstruktur ohne Dateien zu verschieben

  Step 3: Führe mit empfohlenen Flags aus
    python lib/photo_organizer.py --no-geocoding --addexif --execute

  Step 4: Cache und Dateitypen aktualisieren (optional)
    python lib/cache.py --to-permanent
    python lib/cache.py --folder D:\\OrganisierteFotos

OPTIMIZATION:

  Schnelle Verarbeitung:
    python lib/photo_organizer.py --no-geocoding --max-workers 8 --execute

  Detaillierte Metadaten:
    python lib/photo_organizer.py --addexif --execute

  Script-Generierung für Batch-Verarbeitung:
    python lib/photo_organizer.py --generate-script --powershell
    powershell -ExecutionPolicy Bypass -File scripts\\photo_move_*.ps1

FEATURES:

  --execute:                  Dateien tatsächlich verschieben (sonst Vorschau)
  --addexif:                  EXIF-Daten aus Dateinamen hinzufügen
  --no-geocoding:             Ortsnamen-Geocoding deaktivieren (schneller)
  --generate-script:          Shell/PowerShell-Script für spätere Ausführung
  --powershell:               PowerShell-Script (.ps1) statt Bash (.sh)
  --event-max-days:           Maximale Tage für Event-Zusammenfassung
  --geo-radius:               GPS-Radius in km für räumliche Gruppierung
  --same-day-hours:           Stunden-Schwelle für "gleicher Tag"
  --max-workers:              Parallele Threads (default: auto)
  --cache:                    JSON-Cache-Datei (default: auto)
  --compare-with-cache:       Duplikate mit permanenter CSV prüfen (default: ja)

COMMON OPTIONS:

  Schnell (keine GPS/Geocoding):
    --no-geocoding

  Detailliert (mit Dateimetadaten):
    --addexif

  Für große Foto-Sammlungen:
    --max-workers 16 --no-geocoding --execute

  Mit Script-Generierung:
    --generate-script --powershell
"""

    parser = argparse.ArgumentParser(
        description='Automatische Foto-Organisation basierend auf Datum, GPS und Dateinamen',
        epilog=examples,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('source', nargs='?', default=default_source, help=f'Quellverzeichnis mit Fotos (default: {default_source})')
    parser.add_argument('target', nargs='?', default=default_target, help=f'Zielverzeichnis für organisierte Fotos (default: {default_target})')
    parser.add_argument('--execute', action='store_true', help='Dateien tatsächlich verschieben (ohne --execute nur Vorschau)')
    parser.add_argument('--same-day-hours', type=int, default=12, help='Stunden für gleichen Tag (default: 12)')
    parser.add_argument('--event-max-days', type=int, default=3, help='Max. Tage für Event (default: 3)')
    parser.add_argument('--geo-radius', type=float, default=10.0, help='GPS-Radius in km (default: 10.0)')
    parser.add_argument('--min-event-photos', type=int, default=10, help='Min. Fotos für Event (default: 10)')
    parser.add_argument('--no-geocoding', action='store_true', help='Deaktiviert Reverse-Geocoding für Ortsnamen')
    parser.add_argument('--max-workers', type=int, default=None, help='Anzahl paralleler Threads (default: auto)')
    parser.add_argument('--generate-script', action='store_true', help='Erzeugt Shell-Script für spätere Ausführung')
    parser.add_argument('--script-path', default=None, help='Pfad für Shell-Script (default: auto mit PROJECT_SCRIPTS)')
    parser.add_argument('--cache', help='JSON-Cache-Datei für Photo-Daten (default: auto mit PROJECT_CACHE)')
    parser.add_argument('--addexif', action='store_true', help='Fügt EXIF-Daten basierend auf Dateinamen zu Originaldateien hinzu')
    parser.add_argument('--powershell', action='store_true', help='Erzeugt PowerShell-Script (.ps1) statt Bash-Script (.sh)')
    parser.add_argument('--compare-with-cache', action='store_true', default=True, help='Vergleicht mit permanenter CSV (default: True)')
    parser.add_argument('--no-compare-with-cache', action='store_false', dest='compare_with_cache', help='Deaktiviert Vergleich mit permanenter Cache')
    parser.add_argument('--show-duplicates', action='store_true', help='Zeigt Duplikate im Quellverzeichnis verglichen mit JSON/CSV-Cache-Dateien')
    parser.add_argument('--remove-duplicates', action='store_true', help='Entfernt Duplikate aus dem Quellverzeichnis (Dateien, die bereits im Cache bekannt sind)')

    args = parser.parse_args()

    organizer = PhotoOrganizer(
        source_dir=args.source,
        target_dir=args.target,
        same_day_hours=args.same_day_hours,
        event_max_days=args.event_max_days,
        geo_radius_km=args.geo_radius,
        use_geocoding=not args.no_geocoding,
        max_workers=args.max_workers,
        generate_script=args.generate_script,
        script_path=args.script_path,
        cache_file=args.cache,
        add_exif=args.addexif,
        powershell=args.powershell,
        compare_with_cache=args.compare_with_cache
    )

    if args.show_duplicates:
        organizer.show_duplicates_from_cache()
        return

    if args.remove_duplicates:
        organizer.remove_duplicates_from_source()
        return

    # Fotos scannen
    organizer.scan_photos()
    
    if not organizer.photos:
        print("Keine Fotos gefunden!")
        return
    
    # Vorschau anzeigen
    organizer.preview_organization()
    
    # Organisation durchführen
    organizer.organize_photos(dry_run=not args.execute)
    
    if not args.execute and not args.generate_script:
        print("\n💡 Verwende --execute um die Dateien tatsächlich zu verschieben")
        print("💡 Verwende --generate-script um ein Shell-Script zu erstellen")

if __name__ == "__main__":
    main()
