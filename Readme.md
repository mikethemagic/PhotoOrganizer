# PhotoOrganizer - Dokumentation

Ein intelligenter Python-basierter Foto-Organizer, der Fotos automatisch nach Datum, Ort und Events sortiert.
Ich hatte einen riesigen Stapel von automatisch gesicherten Fotos, die ich im Ordner etwas thematisch und nach Jahr und Ort zusammenfassen wollte. 
Allerdings mache ich das bei mehr als 1000 Dateien nicht mehr von Hand. 
Das Python Programm unterstützt einen dabei etwas

## 🐧 Linux/Mac Dokumentation

### 🚀 Quickstart für Linux/Mac

#### Installation & Setup
**Empfohlene Methode mit Virtual Environment:**
```bash
# 1. Virtual Environment erstellen und Abhängigkeiten installieren
./bin/install_py.sh

# 2. PhotoOrganizer verwenden
./bin/organize.sh /pfad/zu/fotos /pfad/zu/ziel

# 3. Script generieren für späteren Move
./bin/organize.sh /pfad/zu/fotos /pfad/zu/ziel --generate-script

# 4. Script ausführen
bash photo_move_20250803_233045.sh
```

**Alternative manuelle Installation:**
```bash
# 1. Abhängigkeiten installieren
pip install Pillow requests

# 2. Projektumgebung einrichten (optional)
source bin/setenv.sh

# 3. Erste Analyse (nur Vorschau)
python photo_organizer.py /pfad/zu/fotos /pfad/zu/ziel

# 4. Script generieren für späteren Move
python photo_organizer.py /pfad/zu/fotos /pfad/zu/ziel --generate-script

# 5. Script ausführen
bash photo_move_20250803_233045.sh
```

### 🎯 Häufige Anwendungsfälle (Linux/Mac)

#### Smartphone-Fotos organisieren
```bash
# Mit GPS-Daten und Geocoding
./bin/organize.sh ~/Downloads/phone_backup ~/Photos --generate-script
```

#### Screenshots sortieren
```bash
# EXIF-Daten hinzufügen da meist nicht vorhanden
./bin/organize.sh ~/Screenshots ~/sorted_screenshots --addexif --generate-script
```

#### Große Foto-Sammlung (10.000+ Fotos)
```bash
# Mit Cache für wiederholte Läufe
./bin/organize.sh /nas/photos /nas/organized --generate-script --max-workers 20
```

#### Network Attached Storage (NAS)
```bash
# Fotos vom gemounteten NAS-Laufwerk organisieren
./bin/organize.sh /mnt/nas/photos /home/user/sorted_photos --generate-script
```

### 📚 Installation (Linux/Mac)

#### Systemanforderungen
- **Python 3.8+**
- **PIL/Pillow**: Für EXIF-Daten
- **requests**: Für Geocoding (optional)
- **ffprobe**: Für Video-Metadaten (optional)

#### Empfohlene Installation mit Virtual Environment
```bash
# Automatische Installation mit Virtual Environment
./bin/install_py.sh
```

#### Alternative manuelle Installation
```bash
# Abhängigkeiten installieren
pip install Pillow requests

# Projektumgebung einrichten (optional)
source bin/setenv.sh
```

#### Was die Installations-Skripte machen:
- Erstellen ein isoliertes Python Virtual Environment im `.venv` Ordner
- Installieren automatisch alle erforderlichen Abhängigkeiten aus `requirements.txt`
- Stellen sicher, dass keine Konflikte mit anderen Python-Projekten entstehen

### 💻 Kommandozeilen-Interface (Linux/Mac)

#### Grundlegende Syntax
**Empfohlene Methode (mit Skripten):**
```bash
./bin/organize.sh <quellordner> <zielordner> [optionen]
```

**Alternative direkte Ausführung:**
```bash
python photo_organizer.py <quellordner> <zielordner> [optionen]
```

### 📖 Beispiele (Linux/Mac)

#### Smartphone-Backup organisieren
```bash
# Mit allen Features
./bin/organize.sh \
    /backup/iphone_photos \
    /nas/family_photos \
    --generate-script \
    --addexif \
    --min-event-photos 8 \
    --geo-radius 5
```

#### Alte Foto-Sammlung aufräumen
```bash
# Ohne GPS, größere Events
./bin/organize.sh \
    /archive/old_photos \
    /sorted/decades \
    --no-geocoding \
    --min-event-photos 25 \
    --event-max-days 7 \
    --generate-script
```

#### Screenshots sortieren
```bash
# EXIF hinzufügen, kleine Events erlauben
./bin/organize.sh \
    ~/Screenshots \
    ~/Pictures/Screenshots_sorted \
    --addexif \
    --min-event-photos 3 \
    --same-day-hours 24 \
    --generate-script
```

#### NAS/Server Umgebung
```bash
# Große Sammlung auf Network Storage
./bin/organize.sh \
    /mnt/nas/camera_uploads \
    /mnt/nas/organized_photos \
    --generate-script \
    --max-workers 16 \
    --cache /tmp/photo_cache.json
```

### 🔧 Fehlerbehebung (Linux/Mac)

#### "PIL/Pillow nicht installiert"
```bash
pip install Pillow
```

#### "requests nicht verfügbar"
```bash
# Abhängigkeiten installieren
./bin/install_py.sh

# Oder ohne Geocoding arbeiten:
./bin/organize.sh /fotos /ziel --no-geocoding
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
```

#### Langsames Geocoding
```bash
# Geocoding deaktivieren
./bin/organize.sh /fotos /ziel --no-geocoding

# Oder weniger Threads
./bin/organize.sh /fotos /ziel --max-workers 4
```

#### Zu viele kleine Events
```bash
# Event-Mindestgröße erhöhen
./bin/organize.sh /fotos /ziel --min-event-photos 20
```

#### Zu große Events
```bash
# Engere Parameter
./bin/organize.sh /fotos /ziel --event-max-days 1 --geo-radius 2
```

### 🛠️ Erweiterte Nutzung (Linux/Mac)

#### Batch-Verarbeitung
```bash
#!/bin/bash
# Mehrere Quellen verarbeiten
for source in /media/*/DCIM /backup/phone_*; do
    if [[ -d "$source" ]]; then
        echo "Verarbeite: $source"
        ./bin/organize.sh "$source" /nas/photos --generate-script
        bash photo_move_*.sh
    fi
done
```

#### Testläufe mit verschiedenen Parametern
```bash
# Verschiedene Event-Größen testen
./bin/organize.sh /fotos /test1 --min-event-photos 5
./bin/organize.sh /fotos /test2 --min-event-photos 15
./bin/organize.sh /fotos /test3 --min-event-photos 25

# GPS-Radius variieren
./bin/organize.sh /fotos /test_5km --geo-radius 5
./bin/organize.sh /fotos /test_20km --geo-radius 20
```

#### Cache-Sharing zwischen Zielen
```bash
# Ein Cache, verschiedene Ziele (möglich da Cache nur von Quelle abhängt)
./bin/organize.sh /fotos /backup1 --generate-script
./bin/organize.sh /fotos /backup2 --generate-script  # Verwendet gleichen Cache
./bin/organize.sh /fotos /nas --generate-script      # Verwendet gleichen Cache
```

---

## 🪟 Windows Dokumentation

### 🚀 Quickstart für Windows

#### Installation & Setup
**Empfohlene Methode mit Virtual Environment:**
```cmd
REM 1. Virtual Environment erstellen und Abhängigkeiten installieren
bin\install_py.bat

REM 2. PhotoOrganizer verwenden
bin\organize.bat C:\pfad\zu\fotos C:\pfad\zu\ziel

REM 3. Script generieren für späteren Move
bin\organize.bat C:\pfad\zu\fotos C:\pfad\zu\ziel --generate-script

REM 4. Script ausführen (PowerShell)
powershell -ExecutionPolicy Bypass -File photo_move_20250803_233045.ps1
```

**Alternative manuelle Installation:**
```cmd
REM 1. Abhängigkeiten installieren
pip install Pillow requests

REM 2. Projektumgebung einrichten (optional)
bin\setenv.bat

REM 3. Erste Analyse (nur Vorschau)
python photo_organizer.py C:\pfad\zu\fotos C:\pfad\zu\ziel

REM 4. Script generieren für späteren Move
python photo_organizer.py C:\pfad\zu\fotos C:\pfad\zu\ziel --generate-script --powershell

REM 5. Script ausführen
powershell -ExecutionPolicy Bypass -File photo_move_20250803_233045.ps1
```

### 🎯 Häufige Anwendungsfälle (Windows)

#### Smartphone-Fotos organisieren
```cmd
REM Mit GPS-Daten und Geocoding
bin\organize.bat C:\Users\%USERNAME%\Downloads\phone_backup C:\Users\%USERNAME%\Pictures\Photos --generate-script
```

#### Screenshots sortieren
```cmd
REM EXIF-Daten hinzufügen da meist nicht vorhanden
bin\organize.bat C:\Users\%USERNAME%\Pictures\Screenshots C:\Users\%USERNAME%\Pictures\sorted_screenshots --addexif --generate-script
```

#### Große Foto-Sammlung (10.000+ Fotos)
```cmd
REM Mit Cache für wiederholte Läufe
bin\organize.bat D:\NAS\photos D:\NAS\organized --generate-script --max-workers 20
```

#### PowerShell-Script generieren
```cmd
REM PowerShell-Script für Windows erstellen
bin\organize.bat C:\Photos C:\Organized --generate-script --powershell
```

### 📚 Installation (Windows)

#### Systemanforderungen
- **Python 3.8+**
- **PIL/Pillow**: Für EXIF-Daten
- **requests**: Für Geocoding (optional)
- **ffprobe**: Für Video-Metadaten (optional)

#### Empfohlene Installation mit Virtual Environment
```cmd
REM Automatische Installation mit Virtual Environment
bin\install_py.bat
```

#### Alternative manuelle Installation
```cmd
REM Abhängigkeiten installieren
pip install Pillow requests

REM Projektumgebung einrichten (optional)
bin\setenv.bat
```

#### Was die Installations-Skripte machen:
- Erstellen ein isoliertes Python Virtual Environment im `.venv` Ordner
- Installieren automatisch alle erforderlichen Abhängigkeiten aus `requirements.txt`
- Stellen sicher, dass keine Konflikte mit anderen Python-Projekten entstehen

### 💻 Kommandozeilen-Interface (Windows)

#### Grundlegende Syntax
**Empfohlene Methode (mit Skripten):**
```cmd
bin\organize.bat <quellordner> <zielordner> [optionen]
```

**Alternative direkte Ausführung:**
```cmd
python photo_organizer.py <quellordner> <zielordner> [optionen]
```

### 📖 Beispiele (Windows)

#### Smartphone-Backup organisieren
```cmd
REM Mit allen Features
bin\organize.bat ^
    C:\backup\iphone_photos ^
    D:\nas\family_photos ^
    --generate-script ^
    --addexif ^
    --min-event-photos 8 ^
    --geo-radius 5
```

#### Alte Foto-Sammlung aufräumen
```cmd
REM Ohne GPS, größere Events
bin\organize.bat ^
    C:\archive\old_photos ^
    D:\sorted\decades ^
    --no-geocoding ^
    --min-event-photos 25 ^
    --event-max-days 7 ^
    --generate-script
```

#### Screenshots sortieren
```cmd
REM EXIF hinzufügen, kleine Events erlauben
bin\organize.bat ^
    C:\Users\%USERNAME%\Pictures\Screenshots ^
    C:\Users\%USERNAME%\Pictures\sorted_screenshots ^
    --addexif ^
    --min-event-photos 3 ^
    --same-day-hours 24 ^
    --generate-script
```

#### PowerShell-Script für Windows
```cmd
REM PowerShell-Script generieren und ausführen
bin\organize.bat ^
    "C:\Users\Admin\Pictures" ^
    "D:\Photos\Organized" ^
    --generate-script ^
    --powershell ^
    --max-workers 8
```

### 🔧 Fehlerbehebung (Windows)

#### "PIL/Pillow nicht installiert"
```cmd
pip install Pillow
```

#### "requests nicht verfügbar"
```cmd
REM Abhängigkeiten installieren
bin\install_py.bat

REM Oder ohne Geocoding arbeiten:
bin\organize.bat C:\fotos C:\ziel --no-geocoding
```

#### "Cache-Quelle passt nicht"
```cmd
REM Cache löschen für Neuanalyse
del /Q %PROJECT_CACHE%\photo_cache_*.json
```

#### "Script bricht ab"
```cmd
REM PowerShell Verbose
powershell -ExecutionPolicy Bypass -File script.ps1 -Verbose
```

#### Langsames Geocoding
```cmd
REM Geocoding deaktivieren
bin\organize.bat C:\fotos C:\ziel --no-geocoding

REM Oder weniger Threads
bin\organize.bat C:\fotos C:\ziel --max-workers 4
```

#### Zu viele kleine Events
```cmd
REM Event-Mindestgröße erhöhen
bin\organize.bat C:\fotos C:\ziel --min-event-photos 20
```

#### Zu große Events
```cmd
REM Engere Parameter
bin\organize.bat C:\fotos C:\ziel --event-max-days 1 --geo-radius 2
```

### 🛠️ Erweiterte Nutzung (Windows)

#### Batch-Verarbeitung
```cmd
@echo off
REM Mehrere Quellen verarbeiten
for /D %%S in (D:\Photos\*) do (
    echo Verarbeite: %%S
    bin\organize.bat "%%S" D:\Organized --generate-script
    powershell -ExecutionPolicy Bypass -File photo_move_*.ps1
)
```

#### Testläufe mit verschiedenen Parametern
```cmd
REM Verschiedene Event-Größen testen
bin\organize.bat C:\fotos C:\test1 --min-event-photos 5
bin\organize.bat C:\fotos C:\test2 --min-event-photos 15
bin\organize.bat C:\fotos C:\test3 --min-event-photos 25

REM GPS-Radius variieren
bin\organize.bat C:\fotos C:\test_5km --geo-radius 5
bin\organize.bat C:\fotos C:\test_20km --geo-radius 20
```

#### Cache-Sharing zwischen Zielen
```cmd
REM Ein Cache, verschiedene Ziele (möglich da Cache nur von Quelle abhängt)
bin\organize.bat C:\fotos C:\backup1 --generate-script
bin\organize.bat C:\fotos C:\backup2 --generate-script
bin\organize.bat C:\fotos D:\nas --generate-script
```

---

## 📚 Allgemeine Informationen

### Wichtigste Features
- ✅ **Intelligente Zeitstempel-Erkennung**: EXIF → Dateiname → Datei-Zeit
- ✅ **GPS-basierte Ortserkennung**: Automatische Ortsauflösung über OpenStreetMap
- ✅ **Event-Gruppierung**: Ähnliche Fotos werden zu Events zusammengefasst
- ✅ **Duplikat-Erkennung**: SHA-256 Hash-basierte Erkennung
- ✅ **Parallel-Verarbeitung**: Multi-Threading für große Foto-Sammlungen
- ✅ **Cache-System**: JSON-basiertes Caching für wiederholte Läufe
- ✅ **Script-Generierung**: Bash oder PowerShell Scripts für sichere Ausführung
- ✅ **EXIF-Reparatur**: Fügt fehlende EXIF-Daten basierend auf Dateinamen hinzu

### 📁 Ordnerstruktur

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

### 📚 Comprehensive Documentation
- **[API Reference](API_REFERENCE.md)** - Complete API documentation with examples
- **[Developer Guide](DEVELOPER_GUIDE.md)** - Architecture, extending, and contributing
- **[Examples & Use Cases](EXAMPLES.md)** - Real-world scenarios and code samples

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

**📖 Für vollständige API-Dokumentation siehe [API_REFERENCE.md](API_REFERENCE.md)**

## Lizenz & Support

Dieses Tool wurde entwickelt, um die Organisation großer Foto-Sammlungen zu automatisieren und dabei die Privatsphäre zu respektieren (alle Verarbeitungen erfolgen lokal, nur Geocoding verwendet externe APIs).

Für Fragen, Probleme oder Feature-Requests bitte ein Issue erstellen oder den Code entsprechend anpassen.

---

**Viel Erfolg beim Organisieren deiner Fotos! 📸🎉**
