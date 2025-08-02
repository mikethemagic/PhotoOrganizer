#!/bin/bash

activate_interpreter() {
    if [ -f "$PROJECT/.venv/bin/activate" ]; then
        source "$PROJECT/.venv/bin/activate"
    else
        echo "Virtual environment not found. Run install_py.sh first."
        exit 1
    fi
}

deactivate_interpreter() {
    if [ -n "$VIRTUAL_ENV" ]; then
        deactivate
    fi
}

# Call function based on argument
case "$1" in
    activate_interpreter)
        activate_interpreter
        ;;
    deactivate_interpreter)
        deactivate_interpreter
        ;;
    *)
        echo "Usage: $0 {activate_interpreter|deactivate_interpreter}"
        exit 1
        ;;
esac
