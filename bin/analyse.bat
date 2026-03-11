@echo off
REM Analyze photos in data directory
REM Shows metadata statistics and organization recommendations
REM Usage: analyse.bat [data_dir] [target_dir]
REM         analyse.bat                          (uses default PROJECT_DATA, detailed analysis)
REM         analyse.bat ..\data ..\results       (with explicit paths)
REM         analyse.bat ..\data --quick          (fast mode - file statistics only)

call setenv.bat
call manage_interpreter.bat activate_interpreter
REM Detailed analysis by default. Use --quick flag for fast mode
python "%PROJECT_LIB%\analyze_photos.py" %*
call manage_interpreter.bat deactivate_interpreter
