@echo off
title Mario Kart Wii AP Client
cd /d "%~dp0"
echo Starting Mario Kart Wii AP Client...
echo.

REM Try Archipelago's bundled Python first (frozen install)
if exist "..\pythonw.exe" (
    "..\python.exe" mkwii_client.py %*
    goto :end
)
if exist "..\python.exe" (
    "..\python.exe" mkwii_client.py %*
    goto :end
)

REM Try Archipelago's lib Python (some installs)
if exist "..\lib\python.exe" (
    "..\lib\python.exe" mkwii_client.py %*
    goto :end
)

REM Fall back to system Python
python mkwii_client.py %*

:end
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Client exited with an error. Check the output above.
    pause
)
