#!/bin/bash
source setenv.sh

if [ ! -d "$PROJECT/.venv" ]; then
    echo "Initialisiere Python virtual environment..."
    python3 -m venv "$PROJECT/.venv" --upgrade-deps
    echo "Erfolgreich."
    
    source "$PROJECT/.venv/bin/activate"
    echo "Installiere erforderliche Python Packages..."
    pip install -r "$PROJECT_LIB/requirements.txt" -q
    echo "Erfolgreich"
    deactivate
else
    echo "Erforderliche Python Packages bereits installiert!"
fi
