@echo off
REM Analyze photos in data directory and provide statistics
REM Usage: analyse.bat [data_dir] [target_dir]
REM         analyse.bat                          (uses default ./data and ./results)
REM         analyse.bat ..\data ..\results       (uses relative paths)

call setenv.bat
call manage_interpreter.bat activate_interpreter
python "%PROJECT_LIB%\analyze_photos.py" %*
call manage_interpreter.bat deactivate_interpreter
