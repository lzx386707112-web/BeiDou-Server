$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$build = Join-Path $root 'build'

cmake -S $root -B $build -A Win32
cmake --build $build --config Release --target BeiDouWeatherCompat

$dll = Join-Path $build 'Release\BeiDouWeatherCompat.dll'
if (-not (Test-Path $dll)) { throw "Missing build output: $dll" }
Write-Host "Built $dll"
