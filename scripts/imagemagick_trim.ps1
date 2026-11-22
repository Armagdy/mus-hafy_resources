# ImageMagick Border Removal Script
# Usage: .\imagemagick_trim.ps1 <input_directory> <fuzz_percentage>
# fuzz_percentage: 0-100, higher = more aggressive (default: 10)

param(
    [Parameter(Mandatory=$true)]
    [string]$InputDir,
    
    [Parameter(Mandatory=$false)]
    [int]$Fuzz = 10
)

if (-not (Test-Path $InputDir)) {
    Write-Error "Directory not found: $InputDir"
    exit 1
}

# Get all JPG files
$images = Get-ChildItem -Path $InputDir -Filter "*.jpg" | Sort-Object Name

if ($images.Count -eq 0) {
    Write-Error "No JPG files found in directory"
    exit 1
}

Write-Host "Found $($images.Count) images to process" -ForegroundColor Green
Write-Host "Fuzz tolerance: $Fuzz%" -ForegroundColor Yellow
Write-Host ""

$processedCount = 0
$errorCount = 0

foreach ($image in $images) {
    $processedCount++
    $inputPath = $image.FullName
    
    try {
        # Get original dimensions
        $origInfo = magick identify -format "%wx%h" $inputPath
        
        # Trim the image with fuzz tolerance
        # -fuzz: color tolerance (higher = more aggressive)
        # -trim: remove edges that are the same color as corner pixels
        # +repage: reset page geometry
        magick $inputPath -fuzz "$Fuzz%" -trim +repage $inputPath
        
        # Get new dimensions
        $newInfo = magick identify -format "%wx%h" $inputPath
        
        # Calculate removed pixels
        if ($origInfo -match '(\d+)x(\d+)' -and $newInfo -match '(\d+)x(\d+)') {
            $origWidth = [int]$matches[1]
            $origHeight = [int]$matches[2]
            $origInfo -match '(\d+)x(\d+)' | Out-Null
            $origWidth = [int]$matches[1]
            $origHeight = [int]$matches[2]
            $newInfo -match '(\d+)x(\d+)' | Out-Null
            $newWidth = [int]$matches[1]
            $newHeight = [int]$matches[2]
            
            $removedWidth = $origWidth - $newWidth
            $removedHeight = $origHeight - $newHeight
            
            $status = if ($removedWidth -gt 0 -or $removedHeight -gt 0) { "TRIMMED" } else { "NO CHANGE" }
            Write-Host "[$processedCount/$($images.Count)] $($image.Name): $origInfo → $newInfo (removed ${removedWidth}px width, ${removedHeight}px height) [$status]" -ForegroundColor $(if ($status -eq "TRIMMED") { "Cyan" } else { "Gray" })
        }
    }
    catch {
        $errorCount++
        Write-Host "[$processedCount/$($images.Count)] ERROR: $($image.Name) - $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Processing complete!" -ForegroundColor Green
Write-Host "Processed: $processedCount images" -ForegroundColor Cyan
Write-Host "Errors: $errorCount images" -ForegroundColor $(if ($errorCount -gt 0) { "Red" } else { "Green" })
