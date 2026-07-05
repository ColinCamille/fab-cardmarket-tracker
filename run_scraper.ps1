$ErrorActionPreference = "Stop"
$repoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoDir

python scraper.py

git add prices.json
$changes = git diff --cached --quiet; $hasChanges = $LASTEXITCODE -ne 0
if ($hasChanges) {
    git commit -m "Mise a jour des prix ($(Get-Date -Format 'yyyy-MM-dd HH:mm'))"
    git push
} else {
    Write-Host "Aucun changement a pousser."
}
