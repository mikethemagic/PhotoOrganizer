#!/bin/bash
# Analyze photos in data directory and provide statistics
# Usage: ./analyse.sh [data_dir] [target_dir]
#        ./analyse.sh                          (uses default ./data and ./results)
#        ./analyse.sh ../data ../results       (uses relative paths)

source setenv.sh
source manage_interpreter.sh activate_interpreter
python "$PROJECT_LIB/analyze_photos.py" "$@"
manage_interpreter.sh deactivate_interpreter
