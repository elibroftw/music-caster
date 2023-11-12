@echo off
set args=%1
shift
:start
if [%1] == [] goto done
set args=%args% %1
shift
goto start
:done
python -m venv .venv 2>NUL
".venv/Scripts/python.exe" build.py %args%
