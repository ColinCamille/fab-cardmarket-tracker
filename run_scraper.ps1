$repoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoDir

$logFile = Join-Path $repoDir "run_scraper.log"
"" | Out-File -FilePath $logFile -Append
"===== Run $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') =====" | Out-File -FilePath $logFile -Append

$env:LOCALAPPDATA = "C:\Users\Camille\AppData\Local"
$env:APPDATA = "C:\Users\Camille\AppData\Roaming"
$env:USERPROFILE = "C:\Users\Camille"

"whoami: $(whoami)" | Out-File -FilePath $logFile -Append
"env:LOCALAPPDATA = $env:LOCALAPPDATA" | Out-File -FilePath $logFile -Append
$probePath = "C:\Users\Camille\AppData\Local\ms-playwright\chromium_headless_shell-1228\chrome-headless-shell-win64\chrome-headless-shell.exe"
"Test-Path probe: $(Test-Path $probePath)" | Out-File -FilePath $logFile -Append
$msPlaywrightList = Get-ChildItem 'C:\Users\Camille\AppData\Local\ms-playwright' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name
"Get-ChildItem ms-playwright: $($msPlaywrightList -join ', ')" | Out-File -FilePath $logFile -Append

$python = "C:\Users\Camille\AppData\Local\Programs\Python\Python312\python.exe"

if (-not (Test-Path $probePath)) {
    "Navigateur Playwright introuvable dans ce contexte, installation..." | Out-File -FilePath $logFile -Append
    & $python -m playwright install chromium *>> $logFile
}

& $python scraper.py *>> $logFile
$scraperExit = $LASTEXITCODE
"Code de sortie du scraper (cards.json): $scraperExit" | Out-File -FilePath $logFile -Append

& $python scrape_catalog.py *>> $logFile
$catalogExit = $LASTEXITCODE
"Code de sortie du scraper (catalog.json): $catalogExit" | Out-File -FilePath $logFile -Append

if ($scraperExit -ne 0 -and $catalogExit -ne 0) {
    "Les deux scrapers ont echoue, on ne commit pas." | Out-File -FilePath $logFile -Append
    exit 1
}

git add prices.json catalog_state.json *>> $logFile
git diff --cached --quiet
$hasChanges = $LASTEXITCODE -ne 0
if ($hasChanges) {
    git commit -m "Mise a jour des prix ($(Get-Date -Format 'yyyy-MM-dd HH:mm'))" *>> $logFile
    git push *>> $logFile
    "Commit et push effectues." | Out-File -FilePath $logFile -Append
} else {
    "Aucun changement a pousser." | Out-File -FilePath $logFile -Append
}
