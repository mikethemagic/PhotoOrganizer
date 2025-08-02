#!/bin/bash
. setenv.sh
manage_interpreter.sh activate_interpreter
python3 $PROJECT_LIB/photo_organizer.py "$@"
manage_interpreter.sh deactivate_interpreter
