@echo off
cd /d "%~dp0"
python storetrack.py
if errorlevel 1 (
  echo.
  echo StoreTrack could not start. Check that Python 3 is installed and available on PATH.
  pause
)
