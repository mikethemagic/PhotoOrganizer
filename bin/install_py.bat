@echo off
call setenv.bat

if not exist "%PROJECT%\.venv" (
    echo Initialisiere Python virtual environment...
    python -m venv "%PROJECT%\.venv" --upgrade-deps
    echo Erfolgreich.
    
    call "%PROJECT%\.venv\Scripts\activate.bat"
    echo Installiere erforderliche Python Packages...
    pip install -r "%PROJECT_LIB%\requirements.txt" -q
    echo Erfolgreich
    call "%PROJECT%\.venv\Scripts\deactivate.bat"
) else (
    echo Erforderliche Python Packages bereits installiert!
)