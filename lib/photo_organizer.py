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

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
except ImportError:
    print("PIL/Pillow nicht installiert. Installiere mit: pip install Pillow")
    exit(1)

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
                 use_geocoding: bool = True):
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
        """
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        self.same_day_hours = same_day_hours
        self.event_max_days = event_max_days
        self.geo_radius_km = geo_radius_km
        self.min_event_photos = min_event_photos
        self.use_geocoding = use_geocoding and GEOCODING_AVAILABLE
        
        self.supported_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.mov', '.mp4', '.avi', '.vid'}
        self.video_extensions = {'.mov', '.mp4', '.avi', '.vid'}
        
        self.photos: List[PhotoInfo] = []
        self.duplicates: Set[str] = set()
        self.location_cache: Dict[Tuple[float, float], str] = {}  # GPS -> Ortsname Cache
        
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
        """Extrahiert Datum/Zeit aus Dateinamen (verschiedene Formate)"""
        import re
        
        filename = filepath.stem  # Dateiname ohne Erweiterung
        
        # Verschiedene Dateinamen-Muster (häufigste zuerst)
        patterns = [
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
        
        for pattern in patterns:
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
        """Konvertiert GPS-Koordinaten zu Ortsnamen via Reverse-Geocoding"""
        if not self.use_geocoding:
            return None
            
        # Cache prüfen (gerundet auf ~100m Genauigkeit)
        rounded_coords = (round(coords[0], 3), round(coords[1], 3))
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
            
            # Rate-Limiting respektieren
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
                        self.location_cache[rounded_coords] = clean_location
                        return clean_location
            
        except requests.RequestException as e:
            print(f"Geocoding-Fehler für {coords}: {e}")
        except Exception as e:
            print(f"Unerwarteter Geocoding-Fehler für {coords}: {e}")
        
        # Fallback: Cache leeren Eintrag setzen
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
    
    def scan_photos(self) -> None:
        """Scannt alle Fotos im Quellverzeichnis"""
        print(f"Scanne Fotos in: {self.source_dir}")
        
        file_hashes = {}
        
        for filepath in self.source_dir.rglob('*'):
            if filepath.is_file() and filepath.suffix.lower() in self.supported_extensions:
                print(f"Verarbeite: {filepath.name}")
                
                # Hash für Duplikat-Erkennung
                file_hash = self.get_file_hash(filepath)
                if file_hash in file_hashes:
                    print(f"Duplikat gefunden: {filepath.name} -> {file_hashes[file_hash]}")
                    self.duplicates.add(str(filepath))
                    continue
                file_hashes[file_hash] = str(filepath)
                
                # Zeitstempel extrahieren (Priorität: EXIF > Dateiname > Datei-Zeit)
                photo_datetime = self.get_best_datetime(filepath)
                
                # GPS-Koordinaten extrahieren
                gps_coords = self.get_gps_coords(filepath)
                location_name = None
                if gps_coords:
                    print(f"  GPS: {gps_coords[0]:.6f}, {gps_coords[1]:.6f}")
                    if self.use_geocoding:
                        location_name = self.get_location_name(gps_coords)
                        if location_name:
                            print(f"  Ort: {location_name}")
                
                photo_info = PhotoInfo(
                    filepath=filepath,
                    datetime=photo_datetime,
                    gps_coords=gps_coords,
                    location_name=location_name,
                    file_hash=file_hash,
                    file_size=filepath.stat().st_size,
                    is_video=filepath.suffix.lower() in self.video_extensions
                )
                
                self.photos.append(photo_info)
        
        print(f"Gefunden: {len(self.photos)} Fotos/Videos, {len(self.duplicates)} Duplikate")
    
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
                    if len(current_event_photos) >= self.min_event_photos:
                        event_name = self.create_event_name(current_event_photos)
                        events[event_name] = current_event_photos.copy()
                    else:
                        # Zu kleine Events zu Einzeltagen hinzufügen
                        for p in current_event_photos:
                            day_name = p.datetime.strftime('%Y/%m-%d')
                            if day_name not in events:
                                events[day_name] = []
                            events[day_name].append(p)
                    
                    # Neues Event starten
                    current_event_photos = [photo]
                    current_event_start = photo.datetime
        
        # Letztes Event verarbeiten
        if current_event_photos:
            if len(current_event_photos) >= self.min_event_photos:
                event_name = self.create_event_name(current_event_photos)
                events[event_name] = current_event_photos
            else:
                for p in current_event_photos:
                    day_name = p.datetime.strftime('%Y/%m-%d')
                    if day_name not in events:
                        events[day_name] = []
                    events[day_name].append(p)
        
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
        print(f"Insgesamt {len(self.photos)} Fotos in {len(events)} Ordnern:")
        
        for event_name, photos in events.items():
            photo_count = len([p for p in photos if not p.is_video])
            video_count = len([p for p in photos if p.is_video])
            
            start_date = min(p.datetime for p in photos)
            end_date = max(p.datetime for p in photos)
            
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
        
        if dry_run:
            print("\n=== DRY RUN - Keine Dateien werden verschoben ===")
        else:
            print("\n=== DATEIEN WERDEN VERSCHOBEN ===")
            self.target_dir.mkdir(parents=True, exist_ok=True)
        
        moved_count = 0
        error_count = 0
        
        for event_name, photos in events.items():
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
                        print(f"  würde verschieben: {photo.filepath.name} -> {target_path}")
                    else:
                        shutil.move(str(photo.filepath), str(target_path))
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
    
    args = parser.parse_args()
    
    organizer = PhotoOrganizer(
        source_dir=args.source,
        target_dir=args.target,
        same_day_hours=args.same_day_hours,
        event_max_days=args.event_max_days,
        geo_radius_km=args.geo_radius,
        min_event_photos=args.min_event_photos,
        use_geocoding=not args.no_geocoding
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
    
    if not args.execute:
        print("\n💡 Verwende --execute um die Dateien tatsächlich zu verschieben")

if __name__ == "__main__":
    main()