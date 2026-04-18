Set-Location "C:\Users\DELL\.antigravity\StoryVocabs-social"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  StoryVocabs Social Media Generator v3" -ForegroundColor Cyan
Write-Host "  4 Posts/Day - OpenRouter (Qwen 80B)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Starting generation..." -ForegroundColor Yellow
Write-Host ""

python generate.py

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  DONE! Check output folder for results." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to close"
