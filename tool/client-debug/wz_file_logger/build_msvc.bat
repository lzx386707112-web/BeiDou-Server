@echo off
setlocal

rem Run from "x86 Native Tools Command Prompt for VS".
rem BeiDou.exe is 32-bit, so both EXE and DLL here must be 32-bit.

cd /d "%~dp0"

cl /nologo /W4 /EHsc /LD WzFileLogger.cpp user32.lib /Fe:WzFileLogger.dll
if errorlevel 1 exit /b 1

copy /Y WzFileLogger.dll ..\..\..\clien\WzFileLogger.dll
if errorlevel 1 exit /b 1

cl /nologo /W4 /EHsc BeiDouLogLauncher.cpp /Fe:BeiDouLogLauncher.exe
if errorlevel 1 exit /b 1

echo Built WzFileLogger.dll and BeiDouLogLauncher.exe
