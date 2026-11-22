# Rename Quran_XXXX.jpg to page_XXXX.jpg in mushuf_mwdoa_images folder

$sourceFolder = "public\assets\mushuf_mwdoa_images"

Write-Host "Renaming images in $sourceFolder..." -ForegroundColor Cyan

$files = Get-ChildItem -Path $sourceFolder -Filter "Quran_*.jpg"
$totalFiles = $files.Count

Write-Host "Found $totalFiles files to rename`n" -ForegroundColor Yellow

$count = 0
foreach ($file in $files) {
    $count++
    
    # Extract the number part (e.g., "0001" from "Quran_0001.jpg")
    if ($file.Name -match 'Quran_(\d+)\.jpg') {
        $number = $matches[1]
        $newName = "page_$number.jpg"
        $newPath = Join-Path $sourceFolder $newName
        
        # Rename the file
        Rename-Item -Path $file.FullName -NewName $newName -Force
        
        # Show progress every 50 files
        if ($count % 50 -eq 0) {
            Write-Host "Progress: $count / $totalFiles files renamed..." -ForegroundColor Green
        }
    }
}

Write-Host "`n" -NoNewline
Write-Host "Successfully renamed $totalFiles files!" -ForegroundColor Green
Write-Host "All images now use format: page_XXXX.jpg" -ForegroundColor Cyan
