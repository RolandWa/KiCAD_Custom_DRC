# Security scan run by the PostToolUse hook after every file edit.
# Checks staged area for absolute Windows paths, company names, or forbidden files.
# Exit 0 = OK, Exit 2 = blocking error (agent will halt).

$errorMessage = $null

# Check 1: Absolute Windows paths or company name in staged diff
$staged = git diff --cached 2>$null
if ($staged) {
    $pathLeak = $staged | Select-String -Pattern 'C:\\Users\\(?!<YourUsername>)[A-Za-z]|OneDrive - (?!<)' -Quiet
    if ($pathLeak) {
        $errorMessage = "SECURITY: Staged diff contains an absolute Windows path or company name. Replace with placeholder (e.g. C:\Users\<YourUsername>\) before committing."
    }
}

# Check 2: Gitignored sensitive files accidentally staged
$stagedFiles = git diff --cached --name-only 2>$null
if ($stagedFiles) {
    $sensitiveFile = $stagedFiles | Select-String -Pattern 'sync_to_kicad\.ps1$|test_config\.py$' -Quiet
    if ($sensitiveFile) {
        $errorMessage = "SECURITY: Staged files include sync_to_kicad.ps1 or test_config.py — these are gitignored locals and must NOT be committed."
    }
}

if ($errorMessage) {
    # Output JSON systemMessage so the agent surfaces it, then block with exit 2
    $json = [ordered]@{
        systemMessage = $errorMessage
    } | ConvertTo-Json -Compress
    Write-Output $json
    exit 2
}

exit 0
