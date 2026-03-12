@echo off
REM Update cache file paths based on a new folder location
REM This script reads all files in a specified folder and updates their paths in the cache

REM Set environment variables from setenv.bat
call "%~dp0setenv.bat"

REM Parse arguments
set "FOLDER_PATH="
set "VERBOSE="

:parse_args
if "%1"=="" goto validate_args
if "%1"=="--folder" (
    set "FOLDER_PATH=%2"
    shift
    shift
    goto parse_args
)
if "%1"=="--verbose" (
    set "VERBOSE=--verbose"
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
REM Verify folder argument was provided
if "%FOLDER_PATH%"=="" (
    echo Error: --folder argument is required
    echo Use --help for more information
    exit /b 1
)

REM Verify folder exists
if not exist "%FOLDER_PATH%" (
    echo Error: Folder does not exist: %FOLDER_PATH%
    exit /b 1
)

echo.
echo ============================================================
echo Starting cache update...
echo Cache Directory: %PROJECT_CACHE%
echo Source Folder: %FOLDER_PATH%
echo ============================================================
echo.

REM Run the Python cache update script
python "%PROJECT_LIB%\cache.py" --folder "%FOLDER_PATH%" --cache-dir "%PROJECT_CACHE%" %VERBOSE%

if errorlevel 1 (
    echo.
    echo Error: Cache update failed
    exit /b 1
) else (
    echo.
    echo Cache update completed successfully
    exit /b 0
)
