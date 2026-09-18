# Prompts (hidden input) for each owner-held credential and stores it as a GitHub Actions secret.
# Usage:  powershell -File scripts/set_secrets.ps1
# Requires: gh CLI logged in (gh auth status).
$repo = "abdullahprobal/StoryVocabs-social"
$names = @("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "GEMINI_API_KEY", "META_PAGE_ID", "META_PAGE_TOKEN", "META_IG_USER_ID")
foreach ($n in $names) {
    $sec = Read-Host -AsSecureString "Paste $n (Enter to skip)"
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    $val = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    if ([string]::IsNullOrWhiteSpace($val)) { Write-Host "  skipped $n"; continue }
    $val | gh secret set $n -R $repo
    if ($LASTEXITCODE -eq 0) { Write-Host "  set $n" } else { Write-Host "  FAILED $n" }
}
gh secret list -R $repo
