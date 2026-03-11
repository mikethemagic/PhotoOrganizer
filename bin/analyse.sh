#!/bin/bash
# Analyze photos in data directory
# Shows metadata statistics and organization recommendations
# Usage: ./analyse.sh [data_dir] [target_dir]
#        ./analyse.sh                          (uses default PROJECT_DATA, detailed analysis)
#        ./analyse.sh ../data ../results       (with explicit paths)
#        ./analyse.sh ../data --quick          (fast mode - file statistics only)

source setenv.sh
source manage_interpreter.sh activate_interpreter
# Detailed analysis by default. Use --quick flag for fast mode
python "$PROJECT_LIB/analyze_photos.py" "$@"
manage_interpreter.sh deactivate_interpreter
