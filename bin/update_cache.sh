#!/bin/bash
#
# Update cache file paths based on a new folder location, or compare archive with cache
# This script reads all files in a specified folder and updates their paths in the cache
#

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source the environment setup script
if [ -f "$SCRIPT_DIR/setenv.sh" ]; then
    source "$SCRIPT_DIR/setenv.sh"
else
    # Try to construct paths manually if setenv.sh doesn't exist
    PROJECT="${SCRIPT_DIR%/bin}"
    PROJECT_BIN="$PROJECT/bin"
    PROJECT_CFG="$PROJECT/cfg"
    PROJECT_DATA="$PROJECT/data"
    PROJECT_SCRIPTS="$PROJECT/scripts"
    PROJECT_CACHE="$PROJECT/cache"
    PROJECT_WORK="$PROJECT/work"
    PROJECT_LIB="$PROJECT/lib"
fi

# Parse arguments
FOLDER_PATH=""
ARCHIVE_PATH=""
VERBOSE=""
COMPARE=""
TO_PERMANENT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --folder)
            FOLDER_PATH="$2"
            shift 2
            ;;
        --archive)
            ARCHIVE_PATH="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE="--verbose"
            shift
            ;;
        --compare)
            COMPARE="--compare"
            shift
            ;;
        --to-permanent)
            TO_PERMANENT="--to-permanent"
            shift
            ;;
        --help|-h)
            python3 "$PROJECT_LIB/cache.py" --help
            exit 0
            ;;
        *)
            echo "Error: Unknown option: $1"
            echo "Use --help for more information"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [ -z "$FOLDER_PATH" ] && [ -z "$ARCHIVE_PATH" ] && [ -z "$TO_PERMANENT" ]; then
    echo "Error: Specify --folder, --archive with --compare, or --to-permanent"
    echo "Use --help for more information"
    exit 1
fi

# Check if archive folder exists if compare is specified
if [ -n "$ARCHIVE_PATH" ]; then
    if [ ! -d "$ARCHIVE_PATH" ]; then
        echo "Error: Archive folder does not exist: $ARCHIVE_PATH"
        exit 1
    fi
fi

# Check if folder exists if folder is specified
if [ -n "$FOLDER_PATH" ]; then
    if [ ! -d "$FOLDER_PATH" ]; then
        echo "Error: Folder does not exist: $FOLDER_PATH"
        exit 1
    fi
fi

# Check if cache directory exists
if [ ! -d "$PROJECT_CACHE" ]; then
    echo "Error: Cache directory does not exist: $PROJECT_CACHE"
    exit 1
fi

# Check if cache.py exists
if [ ! -f "$PROJECT_LIB/cache.py" ]; then
    echo "Error: Cache script not found: $PROJECT_LIB/cache.py"
    exit 1
fi

# Display header
echo ""
echo "============================================================"
if [ -n "$COMPARE" ]; then
    echo "Starting cache comparison..."
    echo "Archive Folder: $ARCHIVE_PATH"
elif [ -n "$TO_PERMANENT" ]; then
    echo "Building permanent CSV cache..."
else
    echo "Starting cache update..."
    echo "Source Folder: $FOLDER_PATH"
fi
echo "Cache Directory: $PROJECT_CACHE"
echo "============================================================"
echo ""

# Run the Python cache update script
if [ -n "$COMPARE" ]; then
    python3 "$PROJECT_LIB/cache.py" --archive "$ARCHIVE_PATH" --compare --cache-dir "$PROJECT_CACHE" $VERBOSE
elif [ -n "$TO_PERMANENT" ]; then
    python3 "$PROJECT_LIB/cache.py" --to-permanent --cache-dir "$PROJECT_CACHE" $VERBOSE
else
    python3 "$PROJECT_LIB/cache.py" --folder "$FOLDER_PATH" --cache-dir "$PROJECT_CACHE" $VERBOSE
fi

# Check exit status
if [ $? -eq 0 ]; then
    echo ""
    echo "Cache operation completed successfully"
    exit 0
else
    echo ""
    echo "Error: Cache operation failed"
    exit 1
fi
