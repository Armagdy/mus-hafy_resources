# Clean Android Build Artifacts
# This script removes ONLY generated build files that are gitignored
# Safe to run - only removes files that Gradle will regenerate
# Essential configuration files (build.gradle, etc.) are preserved

Write-Host "Cleaning Android build artifacts..." -ForegroundColor Cyan
Write-Host ""

# Only delete folders that are in .gitignore (build outputs and caches)
$foldersToDelete = @(
    "android\.gradle",
    "android\.idea", 
    "android\.kotlin",
    "android\build",
    "android\app\build",
    "android\capacitor-cordova-android-plugins\build"
)

# Don't delete local.properties - it contains your SDK path
# (Android Studio will regenerate it, but keeping it saves time)
$filesToDelete = @()

$totalSize = 0

# Calculate total size before deletion
foreach ($folder in $foldersToDelete) {
    if (Test-Path $folder) {
        $size = (Get-ChildItem $folder -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        if ($size) { $totalSize += $size }
    }
}

foreach ($file in $filesToDelete) {
    if (Test-Path $file) {
        $item = Get-Item $file -ErrorAction SilentlyContinue
        if ($item -and $item.Length) { $totalSize += $item.Length }
    }
}

$totalSizeMB = [math]::Round($totalSize / 1MB, 2)
Write-Host "Total space to be freed: $totalSizeMB MB" -ForegroundColor Yellow
Write-Host ""

# Delete folders
foreach ($folder in $foldersToDelete) {
    if (Test-Path $folder) {
        Write-Host "  Removing: $folder" -ForegroundColor Red
        Remove-Item $folder -Recurse -Force -ErrorAction Continue
    }
    else {
        Write-Host "  Already clean: $folder" -ForegroundColor Gray
    }
}

# Delete files
foreach ($file in $filesToDelete) {
    if (Test-Path $file) {
        Write-Host "  Removing: $file" -ForegroundColor Red
        Remove-Item $file -Force -ErrorAction Continue
    }
    else {
        Write-Host "  Already clean: $file" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "Android cleanup complete! Freed approximately $totalSizeMB MB" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Run: npm run cap:sync" -ForegroundColor White
Write-Host "     (This will rebuild the Android project cleanly)" -ForegroundColor Gray
Write-Host "  2. Run: npm run cap:open" -ForegroundColor White  
Write-Host "     (Optional: Open in Android Studio)" -ForegroundColor Gray
Write-Host ""
