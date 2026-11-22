# Finalize Optimized Images
# Replaces original images with their optimized versions

$folders = @(
    'public\assets\mushuf_mwdoa_images',
    'public\assets\mushaf_tashel_pages',
    'public\assets\mushaf_madinah_images'
)

$totalProcessed = 0
$totalFailed = 0

Write-Host "`n╔═══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     Finalize Optimized Images - Replace Originals    ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

foreach ($folder in $folders) {
    if (-not (Test-Path $folder)) {
        Write-Host "⚠️  Folder not found: $folder" -ForegroundColor Yellow
        continue
    }

    $folderName = Split-Path $folder -Leaf
    Write-Host "`n📖 Processing: $folderName" -ForegroundColor Green
    
    # Find all optimized files
    $optimizedFiles = Get-ChildItem $folder -Filter "*_optimized.webp"
    
    if ($optimizedFiles.Count -eq 0) {
        Write-Host "   ✅ No optimized files found - already finalized" -ForegroundColor Green
        continue
    }
    
    Write-Host "   Found $($optimizedFiles.Count) optimized files to finalize" -ForegroundColor Cyan
    
    $processed = 0
    $failed = 0
    
    foreach ($optimizedFile in $optimizedFiles) {
        # Get the original filename (remove _optimized suffix)
        $originalName = $optimizedFile.Name -replace '_optimized\.webp$', '.webp'
        $originalPath = Join-Path $folder $originalName
        $optimizedPath = $optimizedFile.FullName
        
        try {
            # Delete original if it exists
            if (Test-Path $originalPath) {
                Remove-Item $originalPath -Force
            }
            
            # Rename optimized to original name
            Rename-Item $optimizedPath $originalName -Force
            
            $processed++
            
            if ($processed % 100 -eq 0) {
                Write-Host "   Progress: $processed/$($optimizedFiles.Count) files..." -ForegroundColor Gray
            }
        }
        catch {
            Write-Host "   ❌ Failed: $originalName - $($_.Exception.Message)" -ForegroundColor Red
            $failed++
        }
    }
    
    Write-Host "   ✅ Finalized: $processed files" -ForegroundColor Green
    if ($failed -gt 0) {
        Write-Host "   ❌ Failed: $failed files" -ForegroundColor Red
    }
    
    $totalProcessed += $processed
    $totalFailed += $failed
}

Write-Host "`n════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "                        Summary                         " -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ Successfully finalized: $totalProcessed images" -ForegroundColor Green

if ($totalFailed -gt 0) {
    Write-Host "  ❌ Failed: $totalFailed images" -ForegroundColor Red
}

Write-Host "`n✅ Done! Original images have been replaced with optimized versions." -ForegroundColor Green
Write-Host "   You can now build and sync to Android." -ForegroundColor Cyan
