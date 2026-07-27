# Rebuild a Shoe Shopper promo MP4 from its source HTML animation.
# Usage:  powershell -ExecutionPolicy Bypass -File build.ps1                # consumer promo
#         powershell -ExecutionPolicy Bypass -File build.ps1 promo_pitch.html ShoeShopper_Pitch.mp4
param(
    [string]$Html = "promo.html",
    [string]$Out = "ShoeShopper_Promo.mp4"
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$ffmpeg = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
if (-not (Test-Path $ffmpeg)) { $ffmpeg = "ffmpeg" }   # fall back to PATH

# PowerShell 5.1's $ErrorActionPreference does not stop on native-command
# failure, so every node/ffmpeg step needs an explicit exit-code check.
Write-Host "1/3  Inlining image assets into $Html ..."
node inline-assets.js $Html
if ($LASTEXITCODE -ne 0) { throw "Asset inlining failed (exit $LASTEXITCODE) - not rendering stale HTML." }

Write-Host "2/3  Capturing frames from $Html ..."
node render.js $Html
if ($LASTEXITCODE -ne 0) { throw "Frame capture failed (exit $LASTEXITCODE) - not encoding a partial video." }

Write-Host "3/3  Encoding MP4 ..."
& $ffmpeg -y -framerate 30 -i frames/f%05d.png -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -movflags +faststart $Out
if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed (exit $LASTEXITCODE)." }

Remove-Item -Recurse -Force frames
Write-Host "Done -> $Out"
