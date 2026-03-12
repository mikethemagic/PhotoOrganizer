@echo off
REM Update cache file paths based on a new folder location, or compare archive with cache
REM This script reads all files in a specified folder and updates their paths in the cache

REM Set environment variables from setenv.bat
call "%~dp0setenv.bat"

REM Parse arguments
set "FOLDER_PATH="
set "ARCHIVE_PATH="
set "VERBOSE="
set "COMPARE="
set "TO_PERMANENT="

:parse_args
if "%1"=="" goto validate_args
if "%1"=="--folder" (
    set "FOLDER_PATH=%2"
    shift
    shift
    goto parse_args
)
if "%1"=="--archive" (
    set "ARCHIVE_PATH=%2"
    shift
    shift
    goto parse_args
)
if "%1"=="--verbose" (
    set "VERBOSE=--verbose"
    shift
    goto parse_args
)
if "%1"=="--compare" (
    set "COMPARE=--compare"
    shift
    goto parse_args
)
if "%1"=="--to-permanent" (
    set "TO_PERMANENT=--to-permanent"
    shift
    goto parse_args
)
if "%1"=="--help" goto show_help
shift
goto parse_args

:show_help
python "%PROJECT_LIB%\cache.py" --help
exit /b 0

:validate_args
REM Verify at least one action is specified
if "%FOLDER_PATH%"=="" if "%ARCHIVE_PATH%"=="" if "%TO_PERMANENT%"=="" (
    echo Error: Specify --folder, --archive with --compare, or --to-permanent
    echo Use --help for more information
    exit /b 1
)

REM Verify archive folder exists if compare is specified
if not "%ARCHIVE_PATH%"=="" (
    if not exist "%ARCHIVE_PATH%" (
        echo Error: Archive folder does not exist: %ARCHIVE_PATH%
        exit /b 1
    )
)

REM Verify folder exists if folder is specified
if not "%FOLDER_PATH%"=="" (
    if not exist "%FOLDER_PATH%" (
        echo Error: Folder does not exist: %FOLDER_PATH%
        exit /b 1
    )
)

echo.
echo ============================================================
if not "%COMPARE%"=="" (
    echo Starting cache comparison...
    echo Archive Folder: %ARCHIVE_PATH%
) else if not "%TO_PERMANENT%"=="" (
    echo Building permanent CSV cache...
) else (
    echo Starting cache update...
    echo Source Folder: %FOLDER_PATH%
)
echo Cache Directory: %PROJECT_CACHE%
echo ============================================================
echo.

REM Run the Python cache update script
if not "%COMPARE%"=="" (
    python "%PROJECT_LIB%\cache.py" --archive "%ARCHIVE_PATH%" --compare --cache-dir "%PROJECT_CACHE%" %VERBOSE%
) else if not "%TO_PERMANENT%"=="" (
    python "%PROJECT_LIB%\cache.py" --to-permanent --cache-dir "%PROJECT_CACHE%" %VERBOSE%
) else (
    python "%PROJECT_LIB%\cache.py" --folder "%FOLDER_PATH%" --cache-dir "%PROJECT_CACHE%" %VERBOSE%
)

if errorlevel 1 (
    echo.
    echo Error: Cache operation failed
    exit /b 1
) else (
    echo.
    echo Cache operation completed successfully
    exit /b 0
)
