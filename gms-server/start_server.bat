@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ========================================
echo   BeiDou Server
echo ========================================
echo  dir: %CD%
echo.

if not exist "%~dp0start_server.ps1" (
  echo [ERROR] missing start_server.ps1
  echo Put start_server.bat and start_server.ps1 next to BeiDou.jar
  echo.
  pause
  exit /b 1
)

set "BEIDOU_BACKGROUND=0"
set "BEIDOU_JAR="
set "BEIDOU_CONFIG="
set "BEIDOU_APP_ARGS="

:parse_args
if "%~1"=="" goto parse_done
if /i "%~1"=="-h" goto show_help
if /i "%~1"=="--help" goto show_help
if /i "%~1"=="--background" (
  set "BEIDOU_BACKGROUND=1"
  shift
  goto parse_args
)
if /i "%~1"=="--jar" (
  if "%~2"=="" (
    echo [ERROR] --jar needs a path
    pause
    exit /b 2
  )
  set "BEIDOU_JAR=%~2"
  shift
  shift
  goto parse_args
)
if /i "%~1"=="--config" (
  if "%~2"=="" (
    echo [ERROR] --config needs a path
    pause
    exit /b 2
  )
  set "BEIDOU_CONFIG=%~2"
  shift
  shift
  goto parse_args
)
if /i "%~1"=="--" (
  shift
  goto collect_app_args
)
echo [ERROR] unknown arg: %~1
echo Use start_server.bat --help
pause
exit /b 2

:collect_app_args
if "%~1"=="" goto parse_done
set "BEIDOU_APP_ARGS=!BEIDOU_APP_ARGS! %~1"
shift
goto collect_app_args

:show_help
echo Usage:
echo   start_server.bat
echo   start_server.bat --background
echo   start_server.bat --config application.yml
echo   start_server.bat -- --server.port=8687
echo.
echo Put this file next to BeiDou.jar. It checks JDK 21 and MySQL/MariaDB,
echo installs them into runtime\ if missing, then starts the server.
echo.
echo Options:
echo   --jar PATH       jar path, default BeiDou.jar then target\BeiDou.jar
echo   --config PATH    external application.yml
echo   --background     start minimized, write BeiDou.pid
echo   --help           show help
echo.
echo Args after -- are passed to Spring Boot.
echo JAVA_HOME_21 can point to JDK 21 if auto-detect fails.
echo.
pause
exit /b 0

:parse_done

set "PSBIN="
where powershell.exe >nul 2>&1 && set "PSBIN=powershell.exe"
if not defined PSBIN (
  where pwsh.exe >nul 2>&1 && set "PSBIN=pwsh.exe"
)
if not defined PSBIN (
  echo [ERROR] powershell.exe not found
  echo Windows PowerShell 5.1 or PowerShell 7 is required.
  echo.
  pause
  exit /b 1
)

echo using: %PSBIN%
echo.

"%PSBIN%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_server.ps1"
set "ERR=%ERRORLEVEL%"

if not "%ERR%"=="0" (
  echo.
  echo [ERROR] exit code %ERR%
  echo.
  pause
)
exit /b %ERR%
