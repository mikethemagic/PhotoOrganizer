#!/usr/bin/env python3
"""
Automatische Foto-Organisation basierend auf Zeitstempel und GPS-Daten
Organisiert Fotos in Ordnerstrukturen: YYYY/MM-DD/ oder YYYY/Event_YYYY-MM-DD_bis_YYYY-MM-DD/
"""

import os
import shutil
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from collections import defaultdict
import math
import threading
import configparser
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    FFPROBE_AVAILABLE = True
except ImportError:
    FFPROBE_AVAILABLE = False
    print("Warnung: ffprobe nicht verfügbar. Video-Metadaten werden nicht extrahiert.")

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
                 min_event_photos: int = 10,
                 use_geocoding: bool = True,
                 max_workers: int = None,
                 generate_script: bool = False,
                 script_path: str = None,
                 cache_file: Optional[str] = None,
                 add_exif: bool = False,
                 powershell: bool = False):
        """
        Initialisiert den Photo Organizer
        
        Args:
            source_dir: Quellverzeichnis mit Fotos
            target_dir: Zielverzeichnis für organisierte Fotos
            same_day_hours: Stunden-Schwelle für gleichen Tag
            event_max_days: Maximale Tage für Event-Zusammengehörigkeit
            geo_radius_km: GPS-Radius in km für Event-Zugehörigkeit
            min_event_photos: Mindestanzahl Fotos für Event-Erstellung
            use_geocoding: Aktiviert Reverse-Geocoding für Ortsnamen
            max_workers: Anzahl paralleler Threads (None = auto)
            generate_script: Erzeugt Shell-Script für spätere Ausführung
            script_path: Pfad für das Shell-Script (None = auto mit PROJECT_SCRIPTS)
            cache_file: JSON-Cache-Datei für Photo-Daten und Geocoding (None = auto mit PROJECT_CACHE)
            add_exif: Fügt EXIF-Daten basierend auf Dateinamen hinzu
            powershell: Erzeugt PowerShell-Script (.ps1) statt Bash-Script (.sh)
        """
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        self.same_day_hours = same_day_hours
        self.event_max_days = event_max_days
        self.geo_radius_km = geo_radius_km
        self.min_event_photos = min_event_photos
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
        
        # Thread-sichere Caches
        self.location_cache: Dict[Tuple[float, float], str] = {}
        self.location_cache_lock = threading.Lock()
        self.hash_cache: Dict[str, str] = {}
        self.hash_cache_lock = threading.Lock()
        
        # Shell-Script Sammlung
        self.move_commands: List[Tuple[Path, Path]] = []  # (source, target)
        
        # Lade Dateinamen-Pattern aus Konfiguration
        self.filename_patterns = self.load_filename_patterns()
        
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
            self.create_default_config(config_file)
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
    
    def create_default_config(self, config_file: Path) -> None:
        """Erstellt Standard-Konfigurationsdatei"""
        config_dir = config_file.parent
        config_dir.mkdir(parents=True, exist_ok=True)
        
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
            script_filename = f"photo_move_{self.get_timestamp()}{extension}"
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
        source_clean = self.clean_filename(source_name)
        
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
    
    def get_timestamp(self) -> str:
        """Generiert Zeitstempel für eindeutige Script-Namen"""
        return datetime.now().strftime('%Y%m%d_%H%M%S')
    
    def clean_filename(self, name: str) -> str:
        """Bereinigt String für Verwendung in Dateinamen"""
        import re
        # Nur alphanumerische Zeichen, Unterstriche und Bindestriche
        cleaned = re.sub(r'[^\w\-_]', '_', name)
        # Mehrfache Unterstriche reduzieren
        cleaned = re.sub(r'_+', '_', cleaned)
        # Auf sinnvolle Länge kürzen
        return cleaned[:20]
        
    def get_file_hash(self, filepath: Path) -> str:
        """Berechnet SHA-256 Hash einer Datei für Duplikat-Erkennung"""
        hash_sha256 = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            print(f"Fehler beim Hash-Berechnen für {filepath}: {e}")
            return ""
    
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
            
            # Lade Bild
            with Image.open(filepath) as img:
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
        return f"'{str(path).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'"
    
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
        self.write_script_to_file(script_content, all_moves)
    
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
        script_content.append("            Write-Host \"  ✅ $(Split-Path $SourceFile -Leaf)\" -ForegroundColor Green")
        script_content.append("            $script:movedCount++")
        script_content.append("        }")
        script_content.append("        catch {")
        script_content.append("            Write-Host \"  ❌ Fehler: $(Split-Path $SourceFile -Leaf)\" -ForegroundColor Red")
        script_content.append("            $script:errorCount++")
        script_content.append("        }")
        script_content.append("    }")
        script_content.append("    else {")
        script_content.append("        Write-Host \"  ❌ Nicht gefunden: $(Split-Path $SourceFile -Leaf)\" -ForegroundColor Red")
        script_content.append("        $script:errorCount++")
        script_content.append("    }")
        script_content.append("}")
        script_content.append("")
        
        script_content.append("Write-Host \"🚀 Starte Foto-Organisation...\" -ForegroundColor Blue")
        script_content.append("Write-Host \"\"")
        script_content.append("")
        
        # Wechsle ins Quellverzeichnis
        script_content.append("# Wechsle ins Quellverzeichnis")
        source_escaped = str(self.source_dir).replace("'", "''")
        script_content.append(f"Set-Location '{source_escaped}'")
        script_content.append("Write-Host \"📁 Arbeitsverzeichnis: $(Get-Location)\" -ForegroundColor Yellow")
        script_content.append("Write-Host \"\"")
        script_content.append("")
        
        # Sammle alle Move-Kommandos
        all_moves = []
        
        for event_name, photos in events.items():
            if event_name == ".":
                # Einzelne Dateien direkt ins Zielverzeichnis
                target_folder = self.target_dir
                script_content.append(f"# 📄 Einzelne Dateien -> Zielverzeichnis ({len(photos)} Dateien)")
                script_content.append(f"Write-Host \"📄 Einzelne Dateien -> Zielverzeichnis ({len(photos)} Dateien)\" -ForegroundColor Blue")
            else:
                # Event-Ordner
                target_folder = self.target_dir / event_name
                script_content.append(f"# 📁 {event_name}/ ({len(photos)} Dateien)")
                script_content.append(f"Write-Host \"📁 {event_name}/ ({len(photos)} Dateien)\" -ForegroundColor Blue")
                
                # Erstelle Zielordner
                target_escaped = str(target_folder).replace("'", "''")
                script_content.append(f"New-Item -Path '{target_escaped}' -ItemType Directory -Force | Out-Null")
            
            # Move-Kommandos für diese Gruppe
            for photo in photos:
                target_path = target_folder / photo.filepath.name
                
                # Sammle für Statistiken
                all_moves.append((photo.filepath, target_path))
                
                # Relative Pfade für einfachere Kommandos
                rel_source = photo.filepath.relative_to(self.source_dir)
                rel_source_escaped = str(rel_source).replace("'", "''")
                target_escaped = str(target_path).replace("'", "''")
                
                # Funktionsaufruf
                script_content.append(f"Move-PhotoFile '{rel_source_escaped}' '{target_escaped}'")
            
            script_content.append("Write-Host \"\"")
        
        # Script-Footer mit Statistiken
        script_content.append("")
        script_content.append("# Zusammenfassung")
        script_content.append("Write-Host \"\"")
        script_content.append("Write-Host \"=== ZUSAMMENFASSUNG ===\" -ForegroundColor Blue")
        script_content.append("Write-Host \"✅ $movedCount Dateien erfolgreich verschoben\" -ForegroundColor Green")
        script_content.append("if ($errorCount -gt 0) {")
        script_content.append("    Write-Host \"❌ $errorCount Fehler aufgetreten\" -ForegroundColor Red")
        script_content.append("    exit 1")
        script_content.append("}")
        script_content.append("else {")
        script_content.append("    Write-Host \"🎉 Alle Dateien erfolgreich organisiert!\" -ForegroundColor Green")
        script_content.append("}")
        
        # Speichere alle Move-Kommandos für interne Verwendung
        self.move_commands = all_moves
        
        # Script in Datei schreiben
        self.write_script_to_file(script_content, all_moves)
    
    def write_script_to_file(self, script_content: List[str], all_moves: List[Tuple[Path, Path]]) -> None:
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
            print(f"   📊 {len(all_moves)} Move-Operationen geplant")
            print(f"   🔧 Ausführung mit: {execution_cmd}")
            print(f"   ⚠️  Das Script verschiebt die Dateien tatsächlich!")
            
        except Exception as e:
            print(f"❌ Fehler beim Erstellen des Shell-Scripts: {e}")
    
    def get_exif_datetime(self, filepath: Path) -> Optional[datetime]:
        """Extrahiert Datum/Zeit aus EXIF-Daten"""
        try:
            if filepath.suffix.lower() in self.video_extensions:
                return self.get_video_datetime(filepath)
            
            with Image.open(filepath) as img:
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
            cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', str(filepath)]
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
                
            with Image.open(filepath) as img:
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
                        clean_location = self.clean_location_name(location)
                        
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
    
    def clean_location_name(self, location: str) -> str:
        """Bereinigt Ortsnamen für Verwendung in Dateinamen"""
        # Entferne/ersetze problematische Zeichen für Dateinamen
        import re
        
        # Umlaute und Sonderzeichen normalisieren
        replacements = {
            'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
            'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue'
        }
        
        for old, new in replacements.items():
            location = location.replace(old, new)
        
        # Nur alphanumerische Zeichen, Bindestriche und Unterstriche
        location = re.sub(r'[^\w\-_\s]', '', location)
        # Leerzeichen durch Unterstriche ersetzen
        location = re.sub(r'\s+', '_', location.strip())
        # Mehrfache Unterstriche reduzieren
        location = re.sub(r'_+', '_', location)
        
        return location[:30]  # Max. 30 Zeichen für Ordnernamen
    
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
                'duplicates_count': len(self.duplicates)
            },
            'photos': [],
            'duplicates': list(self.duplicates),
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
            for photo_data in cache_data.get('photos', []):
                try:
                    photo = PhotoInfo(
                        filepath=Path(photo_data['filepath']),
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
                    if location:
                        print(f"   ✅ Aus Cache: {location}")
                    else:
                        print(f"   ❌ Bereits als nicht-verfügbar markiert")
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
    
    def process_single_file(self, filepath: Path) -> Optional[PhotoInfo]:
        """Verarbeitet eine einzelne Datei (für parallele Ausführung) - OHNE Geocoding"""
        try:
            # Hash für Duplikat-Erkennung
            file_hash = self.get_file_hash(filepath)
            
            # Thread-sicherer Hash-Cache-Zugriff
            with self.hash_cache_lock:
                if file_hash in self.hash_cache:
                    # Duplikat gefunden
                    return None
                self.hash_cache[file_hash] = str(filepath)
            
            # Zeitstempel extrahieren (Priorität: EXIF > Dateiname > Datei-Zeit)
            photo_datetime = self.get_best_datetime(filepath)
            
            # GPS-Koordinaten extrahieren (OHNE Geocoding)
            gps_coords = self.get_gps_coords(filepath)
            
            return PhotoInfo(
                filepath=filepath,
                datetime=photo_datetime,
                gps_coords=gps_coords,
                location_name=None,  # Wird später in post_process_geocoding() gesetzt
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
            if filepath.is_file() and filepath.suffix.lower() in self.supported_extensions:
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
        single_files = []  # Sammlung für einzelne Dateien
        
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
                    if len(current_event_photos) >= self.min_event_photos:
                        event_name = self.create_event_name(current_event_photos)
                        events[event_name] = current_event_photos.copy()
                    else:
                        # Zu kleine Events: sammle einzelne Dateien
                        single_files.extend(current_event_photos)
                    
                    # Neues Event starten
                    current_event_photos = [photo]
                    current_event_start = photo.datetime
        
        # Letztes Event verarbeiten
        if current_event_photos:
            if len(current_event_photos) >= self.min_event_photos:
                event_name = self.create_event_name(current_event_photos)
                events[event_name] = current_event_photos
            else:
                # Zu kleine Events: sammle einzelne Dateien
                single_files.extend(current_event_photos)
        
        # Einzelne Dateien direkt im Zielverzeichnis (ohne Unterordner)
        if single_files:
            events["."] = single_files  # "." bedeutet aktuelles/Hauptverzeichnis
        
        return events
    
    def create_event_name(self, photos: List[PhotoInfo]) -> str:
        """Erstellt Event-Namen basierend auf Zeitraum und optional Ort"""
        start_date = min(p.datetime for p in photos)
        end_date = max(p.datetime for p in photos)
        
        # Bestimme dominanten Ort falls GPS-Daten vorhanden
        location_name = self.get_dominant_location(photos)
        
        if (end_date - start_date).days == 0:
            # Eintägiges Event
            base_name = start_date.strftime('%Y/%m-%d')
            if location_name:
                return f"{base_name}-{location_name}"
            return base_name
        else:
            # Mehrtägiges Event
            base_name = f"{start_date.strftime('%Y')}/Event_{start_date.strftime('%Y-%m-%d')}_bis_{end_date.strftime('%Y-%m-%d')}"
            if location_name:
                return f"{base_name}-{location_name}"
            return base_name
    
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
                print(f"\n💡 Dry-Run abgeschlossen. Verwende das generierte Script:")
                print(f"   bash {self.script_path}")
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

def main():
    """Hauptfunktion mit Beispiel-Verwendung"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Automatische Foto-Organisation')
    parser.add_argument('source', help='Quellverzeichnis mit Fotos')
    parser.add_argument('target', help='Zielverzeichnis für organisierte Fotos')
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
    
    args = parser.parse_args()
    
    organizer = PhotoOrganizer(
        source_dir=args.source,
        target_dir=args.target,
        same_day_hours=args.same_day_hours,
        event_max_days=args.event_max_days,
        geo_radius_km=args.geo_radius,
        min_event_photos=args.min_event_photos,
        use_geocoding=not args.no_geocoding,
        max_workers=args.max_workers,
        generate_script=args.generate_script,
        script_path=args.script_path,
        cache_file=args.cache,
        add_exif=args.addexif,
        powershell=args.powershell
    )
    
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
