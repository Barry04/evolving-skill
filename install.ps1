param(
    [string]$RepoRoot = $PSScriptRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRootFull = (Resolve-Path $RepoRoot).Path
$sourceSkillDir = Join-Path $repoRootFull "skill"

if (-not (Test-Path $sourceSkillDir)) {
    throw "Skill directory not found: $sourceSkillDir (run this script from the bundle or repo root)"
}

$skillDirs = @(Get-ChildItem -Path $sourceSkillDir -Directory | Sort-Object Name)
if ($skillDirs.Count -eq 0) {
    throw "No skills found under $sourceSkillDir"
}

foreach ($skill in $skillDirs) {
    $skillFile = Join-Path $skill.FullName "SKILL.md"
    if (-not (Test-Path $skillFile)) {
        throw "Missing SKILL.md: $($skill.FullName)"
    }
}

$homeDir = [Environment]::GetFolderPath("UserProfile")
$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $homeDir ".codex" }
$toolDirs = @(
    (Join-Path $codexHome "skills"),
    (Join-Path $homeDir ".claude\skills"),
    (Join-Path $homeDir ".cursor\skills")
)

foreach ($toolDir in $toolDirs) {
    if (-not (Test-Path $toolDir)) {
        New-Item -ItemType Directory -Path $toolDir -Force | Out-Null
    }
}

$totalInstalled = 0
foreach ($skill in $skillDirs) {
    $skillName = $skill.Name
    foreach ($toolDir in $toolDirs) {
        $targetSkillDir = Join-Path $toolDir $skillName
        if (Test-Path $targetSkillDir) {
            Remove-Item -Path $targetSkillDir -Recurse -Force
        }
        Copy-Item -Path $skill.FullName -Destination $targetSkillDir -Recurse -Force
    }
    $totalInstalled++
    Write-Host "  installed: $skillName"
}

Write-Host "`nDone. Installed $totalInstalled skill(s) to: $($toolDirs -join ', ')"
Write-Host "Source: $sourceSkillDir"
