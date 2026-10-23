@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem --- find a Python that has tkinter ---
set "PYW="
for %%D in ("%LOCALAPPDATA%\Programs\Python\Python314"
            "%LOCALAPPDATA%\Programs\Python\Python313"
            "%LOCALAPPDATA%\Programs\Python\Python312"
            "%LOCALAPPDATA%\Programs\Python\Python311"
            "%LOCALAPPDATA%\Programs\Python\Python310"
            "%ProgramFiles%\Python314"
            "%ProgramFiles%\Python313"
            "%ProgramFiles%\Python312") do (
  if not defined PYW if exist "%%~D\pythonw.exe" set "PYW=%%~D\pythonw.exe"
)

if not defined PYW (
  for /f "delims=" %%P in ('where pythonw 2^>nul') do (
    if not defined PYW set "PYW=%%P"
  )
)

if not defined PYW (
  echo Python not found. Install Python 3.8+ and tick "Add to PATH".
  echo If it is already installed, edit this file and set PYW to its pythonw.exe.
  pause
  exit /b 1
)

start "" "%PYW%" "%~dp0gui.py"
exit /b 0
