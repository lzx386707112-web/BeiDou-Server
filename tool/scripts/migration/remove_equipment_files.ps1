param(
    [Parameter(Mandatory = $true)][string]$ClientRoot,
    [string]$ServerRoot,
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'removed-equipment-files.json') -Raw | ConvertFrom-Json
$approvedIds = @{}
foreach ($id in $manifest.delete_ids) { $approvedIds[[string]$id] = $true }
$protectedIds = @{}
foreach ($id in $manifest.keep_ids) { $protectedIds[[string]$id] = $true }
if ($approvedIds.Count -ne 315 -or $protectedIds.Count -ne 39 -or $manifest.files.Count -ne 630) {
    throw 'Unexpected deletion manifest.'
}

$pending = @()
foreach ($entry in $manifest.files) {
    if ($entry.path -notmatch '^(clien/Data/Character|gms-server/wz/Character.wz)/(Weapon|Shoes)/0([0-9]{7})\.img(\.xml)?$') {
        throw "Invalid resource path: $($entry.path)"
    }
    $itemId = $Matches[3]
    if (-not $approvedIds.ContainsKey($itemId) -or $protectedIds.ContainsKey($itemId)) {
        throw "Unapproved ID: $itemId"
    }
    if ($entry.path.StartsWith('clien/')) {
        if ($entry.path.EndsWith('.xml')) { throw 'Client XML path is invalid.' }
        $root = (Resolve-Path -LiteralPath $ClientRoot).Path
        $relative = $entry.path.Substring(6)
    } else {
        if (-not $entry.path.EndsWith('.xml')) { throw 'Server IMG path is invalid.' }
        if (-not $ServerRoot) { continue }
        $root = (Resolve-Path -LiteralPath $ServerRoot).Path
        $relative = $entry.path.Substring(11)
    }
    $target = Join-Path $root $relative
    if (Test-Path -LiteralPath $target -PathType Leaf) {
        $hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($hash -ne $entry.sha256) { throw "Resource differs from reviewed baseline: $target" }
        $pending += $target
    }
}

foreach ($target in $pending) {
    if ($Execute) { Remove-Item -LiteralPath $target }
    Write-Output $target
}
if ($Execute) {
    Write-Output "Deleted $($pending.Count) approved files. Restore from backup to recover."
} else {
    Write-Output "Preview: $($pending.Count) files. Add -Execute to delete after backing up."
}
