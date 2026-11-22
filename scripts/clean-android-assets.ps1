# Script to remove mushaf images from Android assets after cap sync
# These images should be downloaded on-demand from GitHub, not bundled in APK

$assetsPath = Join-Path $PSScriptRoot "..\android\app\src\main\assets\public\assets"

Write-Host "Cleaning Android assets..." -ForegroundColor Cyan

$dirsToRemove = @(
    "mushaf_madinah_images",
    "mushaf_tashel_pages",
    "mushuf_mwdoa_images"
)

foreach ($dir in $dirsToRemove) {
    $fullPath = Join-Path $assetsPath $dir
    if (Test-Path $fullPath) {
        Remove-Item $fullPath -Recurse -Force
        Write-Host "✓ Removed $dir" -ForegroundColor Green
    } else {
        Write-Host "✓ $dir already removed" -ForegroundColor Gray
    }
}

Write-Host "`nAndroid assets cleaned successfully!" -ForegroundColor Green
Write-Host "Mushaf images will be downloaded on-demand from GitHub." -ForegroundColor Yellow
