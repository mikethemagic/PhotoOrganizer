@echo off
REM Reset PDFs - Move all jpg files from ergebnisse back to data folder
REM This allows reprocessing of the last run

setlocal enabledelayedexpansion

echo ====================================
echo jpg RESET TOOL
echo ====================================
echo.

REM Load environment variables
call "%~dp0\bin\setenv.bat"

if not defined PROJECT_DATA (
    echo ERROR: Environment variables not set. Please run setenv.bat first.
    pause
    exit /b 1
)

echo Source folder: %PROJECT_WORK%
echo Target folder: %PROJECT_DATA%
echo.

REM Check if directories exist
if not exist "%PROJECT_WORK%" (
    echo ERROR: Results folder not found: %PROJECT_WORK%
    pause
    exit /b 1
)

if not exist "%PROJECT_DATA%" (
    echo Creating data folder: %PROJECT_DATA%
    mkdir "%PROJECT_DATA%"
)

REM Count PDFs to be moved
set /a count=0
for /r "%PROJECT_WORK%" %%f in (*.jpg) do (
    set /a count+=1
)

if %count%==0 (
    echo No jpg files found in work folder.
    echo Nothing to reset.
    pause
    exit /b 0
)

echo Found %count% jpg files to move back to data folder.
echo.
echo WARNING: This will move all jpg files from customer folders back to the data folder.
echo Any existing PDFs in the data folder may be overwritten.
echo.
set /p confirm="Continue? (y/N): "

if /i not "%confirm%"=="y" (
    echo Operation cancelled.
    pause
    exit /b 0
)

echo.
echo Moving jpg files...
echo.

REM Move all PDFs back to data folder
set /a moved=0
for /r "%PROJECT_WORK%" %%f in (*.jpg) do (
    echo Moving: %%~nxf
    move "%%f" "%PROJECT_DATA%\" >nul 2>&1
    if !errorlevel! equ 0 (
        set /a moved+=1
    ) else (
        echo ERROR: Failed to move %%~nxf
    )
)

echo.
echo ====================================
echo RESET COMPLETE
echo ====================================
echo Moved %moved% jpg files back to data folder.
echo You can now run the organizer again.
echo.

pause
