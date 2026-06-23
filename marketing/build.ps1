# Rebuild the Shoe Shopper promo MP4 from promo.html
# Usage:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$ffmpeg = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
if (-not (Test-Path $ffmpeg)) { $ffmpeg = "ffmpeg" }   # fall back to PATH

Write-Host "1/2  Capturing frames from promo.html ..."
node render.js

Write-Host "2/2  Encoding MP4 ..."
& $ffmpeg -y -framerate 30 -i frames/f%05d.png -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -movflags +faststart ShoeShopper_Promo.mp4

Remove-Item -Recurse -Force frames
Write-Host "Done -> ShoeShopper_Promo.mp4"
