@echo off

set PROJECT=C:\10-Develop\gitrepos\PhotoOrganiser
set PROJECT_BIN=%PROJECT%\bin
set PROJECT_DATA=%PROJECT%\data
set PROJECT_SCRIPTS=%PROJECT%\scripts
set PROJECT_CACHE=%PROJECT%\cache
set PROJECT_WORK=%PROJECT%\work
set PROJECT_LIB=%PROJECT%\lib

REM Create directories if they don't exist
if not exist "%PROJECT%\scripts" mkdir "%PROJECT%\scripts"
if not exist "%PROJECT%\data" mkdir "%PROJECT%\data"
if not exist "%PROJECT%\cache" mkdir "%PROJECT%\cache"

REM Add project bin to PATH
set PATH=%PROJECT_BIN%;%PATH%
