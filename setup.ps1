param(
    [Parameter(Mandatory = $true)][string]$GamePath,
    [string]$DataPath = (Join-Path $env:USERPROFILE ".probablysage"),
    [string]$Python = "python",
    [string]$Ilspy = ""
)
$ErrorActionPreference = "Stop"
$projectPath = $PSScriptRoot
$pythonPath = Join-Path $projectPath ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    & $Python -m venv (Join-Path $projectPath ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Could not create Python environment. Install Python 3.10+." }
}
& $pythonPath -m pip install --index-url https://pypi.org/simple -e $projectPath
if ($LASTEXITCODE -ne 0) { throw "Could not install dependencies." }
$setupArguments = @("-m", "probablysage", "--data", $DataPath, "setup", "--game", $GamePath)
if ($Ilspy) { $setupArguments += @("--ilspy", $Ilspy) }
& $pythonPath @setupArguments
if ($LASTEXITCODE -ne 0) { throw "Index build failed. Previous index, if any, was retained." }
& $pythonPath -m probablysage --data $DataPath doctor
if ($LASTEXITCODE -ne 0) { throw "Index is not ready." }
