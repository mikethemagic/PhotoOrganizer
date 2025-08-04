@echo off

if "%1"=="activate_interpreter" goto activate_interpreter
if "%1"=="deactivate_interpreter" goto deactivate_interpreter
goto usage

:activate_interpreter
if exist "%PROJECT%\.venv\Scripts\activate.bat" (
    call "%PROJECT%\.venv\Scripts\activate.bat"
) else (
    echo Virtual environment not found. Run install_py.bat first.
    exit /b 1
)
goto end

:deactivate_interpreter
if defined VIRTUAL_ENV (
    call "%PROJECT%\.venv\Scripts\deactivate.bat"
)
goto end

:usage
echo Usage: %0 {activate_interpreter^|deactivate_interpreter}
exit /b 1

:end