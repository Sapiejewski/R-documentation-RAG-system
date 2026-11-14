# First setup on Windows: in PowerShell, in this folder:   .\init.ps1
# (If scripts are blocked: powershell -ExecutionPolicy Bypass -File init.ps1)
#
# This script only makes sure R is there -- offering to install it, never without asking.
# Everything else (httr2, Docker, which R libraries to index, starting the services) is
# done in R by src/client/setup.R, the same on every system. Flow: docs/setup.md.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Rscript.exe: on PATH, or where the R installer puts it (it does not add R to PATH).
function Find-Rscript {
    $onPath = Get-Command Rscript -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    $folders = @("$env:ProgramFiles\R", "$env:LOCALAPPDATA\Programs\R")
    $found = foreach ($folder in $folders) {
        Get-ChildItem "$folder\R-*\bin\Rscript.exe" -ErrorAction SilentlyContinue
    }
    # Newest version first (R-4.10.0 after R-4.9.0: compare as versions, not as text).
    $newest = $found | Sort-Object { [version]($_.Directory.Parent.Name -replace '^R-', '') } -Descending |
        Select-Object -First 1
    if ($newest) { return $newest.FullName }
    return $null
}

$rscript = Find-Rscript
if (-not $rscript) {
    Write-Host "R was not found."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        $answer = Read-Host "Install it now with:  winget install --exact --id RProject.R  ? [y/N]"
        if ($answer -match '^(y|yes|t|tak)$') {
            winget install --exact --id RProject.R
            $rscript = Find-Rscript
        }
    }
    if (-not $rscript) {
        Write-Host "Install R from https://cloud.r-project.org/bin/windows/ and run .\init.ps1 again."
        Write-Host "Without R you can still use Docker mode: see README.md."
        exit 1
    }
}

& $rscript src/client/main.R init
exit $LASTEXITCODE
