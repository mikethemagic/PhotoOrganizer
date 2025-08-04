# PhotoOrganizer - Dokumentation

Ein intelligenter Python-basierter Foto-Organizer, der Fotos automatisch nach Datum, Ort und Events sortiert.

## 🚀 Quickstart

### Installation & Setup
```bash
# 1. Abhängigkeiten installieren
pip install Pillow requests

# 2. Projektumgebung einrichten (optional)
source setenv.sh

# 3. Erste Analyse (nur Vorschau)
python photo_organizer.py /pfad/zu/fotos /pfad/zu/ziel

# 4. Script generieren für späteren Move
python photo_organizer.py /pfad/zu/fotos /pfad/zu/ziel --generate-script

# 5. Script ausführen
bash photo_move_20250803_233045.sh
```

### Wichtigste Features
- ✅ **Intelligente Zeitstempel-Erkennung**: EXIF → Dateiname → Datei-Zeit
- ✅ **GPS-basierte Ortserkennung**: Automatische Ortsauflösung über OpenStreetMap
- ✅ **Event-Gruppierung**: Ähnliche Fotos werden zu Events zusammengefasst
- ✅ **Duplikat-Erkennung**: SHA-256 Hash-basierte Erkennung
- ✅ **Parallel-Verarbeitung**: Multi-Threading für große Foto-Sammlungen
- ✅ **Cache-System**: JSON-basiertes Caching für wiederholte Läufe
- ✅ **Script-Generierung**: Bash oder PowerShell Scripts für sichere Ausführung
- ✅ **EXIF-Reparatur**: Fügt fehlende EXIF-Daten basierend auf Dateinamen hinzu

## 📁 Ordnerstruktur

Das Programm erstellt folgende Struktur:

```
Zielordner/
├── einzelfoto1.jpg                    # Einzelne Dateien (< min-event-photos)
├── screenshot.png                     # Einzelne Dateien
├── 2025/
│   ├── 03-15-Berlin/                  # Event mit Ort
│   │   ├── IMG_001.jpg
│   │   └── IMG_002.jpg
│   ├── 03-20/                         # Event ohne Ort
│   │   ├── photo1.jpg
│   │   └── photo2.jpg
│   └── Event_2025-03-25_bis_2025-03-27-München/  # Mehrtägiges Event
│       ├── urlaub001.jpg
│       └── urlaub002.jpg
```

## 🎯 Häufige Anwendungsfälle

### Smartphone-Fotos organisieren
```bash
# Mit GPS-Daten und Geocoding
python photo_organizer.py ~/Downloads/phone_backup ~/Photos --generate-script
```

### Screenshots sortieren
```bash
# EXIF-Daten hinzufügen da meist nicht vorhanden
python photo_organizer.py ~/Screenshots ~/sorted_screenshots --addexif --generate-script
```

### Große Foto-Sammlung (10.000+ Fotos)
```bash
# Mit Cache für wiederholte Läufe
python photo_organizer.py /nas/photos /nas/organized --generate-script --max-workers 20
```

### Windows PowerShell
```bash
# PowerShell-Script für Windows
python photo_organizer.py C:\Photos C:\Organized --generate-script --powershell
```

---

## 📚 Detaillierte Dokumentation

## Installation

### Systemanforderungen
- **Python 3.8+**
- **PIL/Pillow**: Für EXIF-Daten
- **requests**: Für Geocoding (optional)
- **ffprobe**: Für Video-Metadaten (optional)

### Abhängigkeiten installieren
```bash
pip install Pillow requests
```

### Projektstruktur einrichten (optional)
```bash
# setenv.sh erstellen
export PROJECT=/pfad/zu/projekt
export PROJECT_BIN=$PROJECT/bin
export PROJECT_DATA=$PROJECT/data
export PROJECT_SCRIPTS=$PROJECT/scripts
export PROJECT_CACHE=$PROJECT/cache
export PROJECT_CFG=$PROJECT/config

mkdir -p "$PROJECT_SCRIPTS" "$PROJECT_CACHE" "$PROJECT_CFG"
export PATH="$PROJECT_BIN:$PATH"

# Environment laden
source setenv.sh
```

## Kommandozeilen-Interface

### Grundlegende Syntax
```bash
python photo_organizer.py <quellordner> <zielordner> [optionen]
```

### Hauptoptionen
| Option | Beschreibung | Standard |
|--------|--------------|----------|
| `--execute` | Führt tatsächliche Datei-Moves durch | Nur Vorschau |
| `--generate-script` | Erzeugt Ausführungs-Script | Deaktiviert |
| `--addexif` | Fügt EXIF-Daten aus Dateinamen hinzu | Deaktiviert |
| `--powershell` | Erzeugt PowerShell- statt Bash-Script | Bash |
| `--no-geocoding` | Deaktiviert GPS→Ort Auflösung | Aktiviert |

### Event-Parameter
| Option | Beschreibung | Standard |
|--------|--------------|----------|
| `--same-day-hours` | Stunden für gleichen Tag | 12 |
| `--event-max-days` | Max. Tage für Event-Zugehörigkeit | 3 |
| `--geo-radius` | GPS-Radius in km | 10.0 |
| `--min-event-photos` | Min. Fotos für Event-Ordner | 10 |

### Performance-Optionen
| Option | Beschreibung | Standard |
|--------|--------------|----------|
| `--max-workers` | Anzahl paralleler Threads | Auto (CPU+4) |
| `--cache` | Cache-Datei | Auto-generiert |
| `--script-path` | Script-Pfad | Auto-generiert |

## Intelligente Zeitstempel-Erkennung

Das Programm verwendet eine **3-stufige Priorität** für Zeitstempel:

### 1. EXIF-Daten (Höchste Priorität)
- DateTime, DateTimeOriginal, DateTimeDigitized
- Echte Aufnahmezeit von Kamera/Smartphone

### 2. Dateiname-Analyse (Mittlere Priorität)
- Konfigurierbare Regex-Pattern
- Unterstützte Formate:
  ```
  2025-03-15 14.30.25.jpg
  IMG_20250315_143025.jpg
  Screenshot_2025-03-15-14-30-25.png
  WhatsApp Image 2025-03-15 at 14.30.25.jpg
  signal-2025-03-15-143025.jpg
  ```

### 3. Datei-Zeitstempel (Fallback)
- Datei-Modifikationszeit als letzter Ausweg

## GPS-basierte Ortserkennung

### Funktionsweise
1. **GPS-Extraktion**: Aus EXIF-Daten (falls vorhanden)
2. **Reverse-Geocoding**: OpenStreetMap/Nominatim API
3. **Caching**: Vermeidet wiederholte API-Aufrufe
4. **Rate-Limiting**: Respektiert API-Limits (1 req/sec)

### Unterstützte Ortsarten
- Stadt, Gemeinde, Dorf
- Bezirk, Landkreis
- Bundesland (als Fallback)

### Beispiel-Ordnernamen
```
2025/03-15-Berlin/
2025/03-20-München/
2025/Event_2025-03-25_bis_2025-03-27-Rom/
```

## Event-Gruppierung

### Algorithmus
1. **Zeitliche Nähe**: Fotos innerhalb `--event-max-days`
2. **Geografische Nähe**: GPS-Koordinaten innerhalb `--geo-radius`
3. **Minimalgröße**: Mindestens `--min-event-photos` Fotos

### Event-Typen
- **Einzelne Dateien**: Weniger als Mindestanzahl → Zielverzeichnis
- **Tages-Events**: Fotos eines Tages → `YYYY/MM-DD/`
- **Mehrtägige Events**: → `YYYY/Event_YYYY-MM-DD_bis_YYYY-MM-DD/`
- **Orts-Events**: Mit GPS-Daten → `YYYY/MM-DD-Ortsname/`

## Cache-System

### Automatische Cache-Namen
```bash
# Basierend auf Quellverzeichnis-Namen
photo_cache_holiday_pics.json
photo_cache_smartphone_backup.json
photo_cache_downloads.json
```

### Cache-Inhalt
- **Photo-Metadaten**: EXIF, GPS, Zeitstempel, Hashes
- **Geocoding-Cache**: GPS → Ortsname Zuordnungen
- **Duplikat-Info**: Bereits erkannte Duplikate
- **Statistiken**: Anzahl Fotos, Verarbeitungszeit

### Cache-Verwaltung
```bash
# Cache-Status prüfen
jq '.metadata' $PROJECT_CACHE/photo_cache_holiday_pics.json

# Cache löschen für Neuanalyse
rm $PROJECT_CACHE/photo_cache_holiday_pics.json

# Alle Caches auflisten
ls $PROJECT_CACHE/photo_cache_*.json
```

## Parallel-Verarbeitung

### 2-Phasen-System
1. **Phase 1**: Parallele EXIF/Hash-Extraktion (Multi-Threading)
2. **Phase 2**: Sequenzielles Geocoding (Rate-Limited)

### Performance-Optimierung
- **Thread-Anzahl**: `CPU-Kerne + 4` (max. 32)
- **Thread-sichere Caches**: Vermeidet Race-Conditions
- **Progress-Tracking**: Live-Fortschritts-Anzeige

### Typische Performance
- **1.000 Fotos**: ~2-5 Minuten (erste Analyse)
- **10.000 Fotos**: ~20-45 Minuten (erste Analyse)
- **Cache-Nutzung**: ~30 Sekunden (wiederholte Läufe)

## Script-Generierung

### Bash-Scripts (.sh)
```bash
#!/bin/bash
# Arbeitet im Quellverzeichnis mit relativen Pfaden
# Verwendet move_file() Funktion für jeden Transfer
# Farbige Ausgabe und Statistiken
```

### PowerShell-Scripts (.ps1)
```powershell
# Optimiert für Windows-Umgebungen
# Move-PhotoFile Funktion mit Try-Catch
# Write-Host mit Farben
# $ErrorActionPreference = 'Stop'
```

### Ausführung
```bash
# Bash
bash photo_move_20250803_233045.sh

# PowerShell
powershell -ExecutionPolicy Bypass -File photo_move_20250803_233045.ps1
```

## EXIF-Reparatur (--addexif)

### Funktionsweise
1. **Prüfung**: Sind bereits EXIF-Daten vorhanden?
2. **Extraktion**: Zeitstempel aus Dateiname extrahieren
3. **EXIF-Schreibung**: DateTime, DateTimeOriginal, DateTimeDigitized setzen
4. **Software-Tag**: "PhotoOrganizer" als Software-Attribut

### Unterstützte Formate
- ✅ **JPEG** (.jpg, .jpeg)
- ✅ **TIFF** (.tiff, .tif)
- ❌ **PNG** (unterstützt kein EXIF)
- ❌ **Videos** (komplexere Metadaten)

### Anwendungsfälle
- Screenshots ohne EXIF-Daten
- WhatsApp-Bilder (verlieren oft EXIF)
- Gescannte alte Fotos
- Heruntergeladene Bilder

## Konfiguration

### Pattern-Konfiguration
Datei: `$PROJECT_CFG/photo_organizer.cfg`

```ini
[Filename_Patterns]
# Standard-Formate
datetime_space = (\d{4})-(\d{2})-(\d{2})\s+(\d{2})[\.-:](\d{2})[\.-:](\d{2})
datetime_underscore = (\d{4})-(\d{2})-(\d{2})_(\d{2})[\.-:](\d{2})[\.-:](\d{2})

# App-spezifische Formate
whatsapp = IMG-(\d{4})(\d{2})(\d{2})-WA\d+
signal = signal-(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})(\d{2})
screenshot = Screenshot_(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})

# Eigene Pattern hinzufügen:
# mein_format = (\d{4})\.(\d{2})\.(\d{2})_(\d{2})h(\d{2})m(\d{2})s
```

### Regex-Gruppen
- **6 Gruppen**: Jahr, Monat, Tag, Stunde, Minute, Sekunde
- **3 Gruppen**: Jahr, Monat, Tag (Zeit → 12:00:00)

## Fortgeschrittene Nutzung

### Batch-Verarbeitung
```bash
#!/bin/bash
# Mehrere Quellen verarbeiten
for source in /media/*/DCIM /backup/phone_*; do
    if [[ -d "$source" ]]; then
        echo "Verarbeite: $source"
        python photo_organizer.py "$source" /nas/photos --generate-script
        bash photo_move_*.sh
    fi
done
```

### Testläufe mit verschiedenen Parametern
```bash
# Verschiedene Event-Größen testen
python photo_organizer.py /fotos /test1 --min-event-photos 5
python photo_organizer.py /fotos /test2 --min-event-photos 15
python photo_organizer.py /fotos /test3 --min-event-photos 25

# GPS-Radius variieren
python photo_organizer.py /fotos /test_5km --geo-radius 5
python photo_organizer.py /fotos /test_20km --geo-radius 20
```

### Cache-Sharing zwischen Zielen
```bash
# Ein Cache, verschiedene Ziele (möglich da Cache nur von Quelle abhängt)
python photo_organizer.py /fotos /backup1 --generate-script
python photo_organizer.py /fotos /backup2 --generate-script  # Verwendet gleichen Cache
python photo_organizer.py /fotos /nas --generate-script      # Verwendet gleichen Cache
```

## Fehlerbehebung

### Häufige Probleme

#### "PIL/Pillow nicht installiert"
```bash
pip install Pillow
```

#### "requests nicht verfügbar"
```bash
pip install requests
# Oder ohne Geocoding arbeiten:
python photo_organizer.py /fotos /ziel --no-geocoding
```

#### "Cache-Quelle passt nicht"
```bash
# Cache löschen für Neuanalyse
rm $PROJECT_CACHE/photo_cache_*.json
```

#### "Script bricht ab"
```bash
# Debug-Modus aktivieren
bash -x photo_move_script.sh

# Oder PowerShell Verbose
powershell -ExecutionPolicy Bypass -File script.ps1 -Verbose
```

### Performance-Probleme

#### Langsames Geocoding
```bash
# Geocoding deaktivieren
python photo_organizer.py /fotos /ziel --no-geocoding

# Oder weniger Threads
python photo_organizer.py /fotos /ziel --max-workers 4
```

#### Zu viele kleine Events
```bash
# Event-Mindestgröße erhöhen
python photo_organizer.py /fotos /ziel --min-event-photos 20
```

#### Zu große Events
```bash
# Engere Parameter
python photo_organizer.py /fotos /ziel --event-max-days 1 --geo-radius 2
```

### Debug-Informationen

#### Verbose-Modus
```bash
# Mit Cache-Details
python photo_organizer.py /fotos /ziel --cache=/tmp/debug.json

# Cache-Inhalt prüfen
jq '.metadata' /tmp/debug.json
jq '.photos | length' /tmp/debug.json
jq '.location_cache | length' /tmp/debug.json
```

#### Log-Files
```bash
# Ausgabe in Datei umleiten
python photo_organizer.py /fotos /ziel 2>&1 | tee photo_organizer.log
```

## Beispiele

### Smartphone-Backup organisieren
```bash
# Mit allen Features
python photo_organizer.py \
    /backup/iphone_photos \
    /nas/family_photos \
    --generate-script \
    --addexif \
    --min-event-photos 8 \
    --geo-radius 5
```

### Alte Foto-Sammlung aufräumen
```bash
# Ohne GPS, größere Events
python photo_organizer.py \
    /archive/old_photos \
    /sorted/decades \
    --no-geocoding \
    --min-event-photos 25 \
    --event-max-days 7 \
    --generate-script
```

### Screenshots sortieren
```bash
# EXIF hinzufügen, kleine Events erlauben
python photo_organizer.py \
    ~/Screenshots \
    ~/Pictures/Screenshots_sorted \
    --addexif \
    --min-event-photos 3 \
    --same-day-hours 24 \
    --generate-script
```

### Windows-Umgebung
```bash
# PowerShell-Script für Windows
python photo_organizer.py \
    "C:\Users\Admin\Pictures" \
    "D:\Photos\Organized" \
    --generate-script \
    --powershell \
    --max-workers 8
```

## API-Referenz

Das Programm kann auch als Python-Modul verwendet werden:

```python
from photo_organizer import PhotoOrganizer

# Organizer erstellen
organizer = PhotoOrganizer(
    source_dir="/path/to/photos",
    target_dir="/path/to/organized",
    use_geocoding=True,
    min_event_photos=10
)

# Fotos scannen
organizer.scan_photos()

# Vorschau
events = organizer.preview_organization()

# Script generieren
organizer.generate_script = True
organizer.organize_photos(dry_run=True)
```

## Lizenz & Support

Dieses Tool wurde entwickelt, um die Organisation großer Foto-Sammlungen zu automatisieren und dabei die Privatsphäre zu respektieren (alle Verarbeitungen erfolgen lokal, nur Geocoding verwendet externe APIs).

Für Fragen, Probleme oder Feature-Requests bitte ein Issue erstellen oder den Code entsprechend anpassen.

---

**Viel Erfolg beim Organisieren deiner Fotos! 📸🎉**