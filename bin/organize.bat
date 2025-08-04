@echo off
call setenv.bat
call manage_interpreter.bat activate_interpreter
python "%PROJECT_LIB%\photo_organizer.py" %*
call manage_interpreter.bat deactivate_interpreter