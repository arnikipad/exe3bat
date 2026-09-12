@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 exe3bat.py
    goto :done
)
where python >nul 2>nul
if not errorlevel 1 (
    python exe3bat.py
    goto :done
)
echo Python 3 was not found.
echo Install Python 3 and try again.
:done
endlocal
