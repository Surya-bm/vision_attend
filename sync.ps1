# sync.ps1 - Automated 3-Tier Git Promotion Pipeline
param (
    [Parameter(Mandatory=$true)]
    [string]$msg
)

Write-Host "`n[START] Automated Git Promotion Pipeline Starting..." -ForegroundColor Cyan

# 1. WORKING BRANCH
Write-Host "`n[1/4] Committing and Pushing on 'working' branch..." -ForegroundColor Yellow
git checkout working
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] Failed to checkout working" -ForegroundColor Red; exit }

git add .
git commit -m "$msg"
git push origin working
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] Failed to push to working" -ForegroundColor Red; exit }
Write-Host "[OK] 'working' branch updated successfully!" -ForegroundColor Green

# 2. DEV BRANCH
Write-Host "`n[2/4] Merging 'working' into 'dev'..." -ForegroundColor Yellow
git checkout dev
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] Failed to checkout dev" -ForegroundColor Red; exit }

git pull origin dev
git merge working
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] Merge conflict on dev! Please resolve." -ForegroundColor Red; exit }

git push origin dev
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] Failed to push to dev" -ForegroundColor Red; exit }
Write-Host "[OK] 'dev' branch updated successfully!" -ForegroundColor Green

# 3. MAIN BRANCH (PRODUCTION)
Write-Host "`n[3/4] Merging 'dev' into 'main' (Production)..." -ForegroundColor Yellow
git checkout main
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] Failed to checkout main" -ForegroundColor Red; exit }

git pull origin main
git merge dev
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] Merge conflict on main! Please resolve." -ForegroundColor Red; exit }

git push origin main
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] Failed to push to main" -ForegroundColor Red; exit }
Write-Host "[OK] 'main' branch updated successfully!" -ForegroundColor Green

# 4. RETURN TO WORKING BRANCH
Write-Host "`n[4/4] Returning to 'working' branch for your next task..." -ForegroundColor Yellow
git checkout working
Write-Host "`n[SUCCESS] All 3 branches (working -> dev -> main) synced cleanly!" -ForegroundColor Cyan
Write-Host "[INFO] You are now safely back on 'working' branch.`n" -ForegroundColor Green
