param([string]$Root='C:\ProgramData\PolitiTrack', [switch]$Apply)
$ErrorActionPreference = 'Stop'
$install = Join-Path $env:LOCALAPPDATA 'Programs\PolitiTrack'
$path = Join-Path $install 'PolitiTrack.exe'
if (Get-Process PolitiTrack -ErrorAction SilentlyContinue) { throw 'Close the desktop launcher before updating its address.' }
Add-Type -Path "$Root\tools\mono-cecil\lib\net40\Mono.Cecil.dll"
$assembly = [Mono.Cecil.AssemblyDefinition]::ReadAssembly($path)
function Get-AllTypes($types) {
    foreach ($type in $types) { $type; Get-AllTypes $type.NestedTypes }
}
$old = 'https://polititrack-web-s6icmprjvq-uc.a.run.app'
$new = 'http://127.0.0.1:8765'
$changes = 0
foreach ($type in (Get-AllTypes $assembly.MainModule.Types)) {
    foreach ($field in $type.Fields) {
        if ($field.HasConstant -and $field.Constant -is [string] -and $field.Constant.Contains($old)) {
            $field.Constant = $field.Constant.Replace($old, $new); $changes++
        }
    }
    foreach ($method in $type.Methods) {
        if (-not $method.HasBody) { continue }
        foreach ($instruction in $method.Body.Instructions) {
            if ($instruction.OpCode.Name -eq 'ldstr' -and ([string]$instruction.Operand).Contains($old)) {
                $instruction.Operand = ([string]$instruction.Operand).Replace($old, $new); $changes++
            }
        }
    }
}
if ($changes -ne 4) { $assembly.Dispose(); throw "Unexpected launcher layout: $changes URL references. No file changed." }
Write-Output "Prepared $changes URL substitutions, preserving existing tray, icon, startup and notification code."
if (-not $Apply) { $assembly.Dispose(); exit 0 }
if ((Invoke-WebRequest -UseBasicParsing "$new/readyz").StatusCode -ne 200) { throw 'Local dashboard is not ready.' }
$backup = Join-Path $Root 'backups\desktop-before-local'
if (Test-Path $backup) { throw 'Desktop backup already exists; inspect the previous attempt before retrying.' }
New-Item -ItemType Directory $backup | Out-Null
Copy-Item "$install\*" $backup -Recurse
$temporary = Join-Path $install 'PolitiTrack.local.exe'
$assembly.Write($temporary)
$assembly.Dispose()
$check = [Mono.Cecil.AssemblyDefinition]::ReadAssembly($temporary)
$check.Dispose()
Move-Item $temporary $path -Force
$releasePath = Join-Path $install 'release.json'
if (Test-Path $releasePath) {
    $release = Get-Content $releasePath -Raw | ConvertFrom-Json
    $release.live_url = "$new/#overview"
    $release | ConvertTo-Json -Depth 10 | Set-Content $releasePath
}
Get-FileHash $path -Algorithm SHA256 | Select-Object Algorithm, Hash |
    ConvertTo-Json | Set-Content "$Root\backups\desktop-local-hash.json"
Write-Output 'Existing desktop launcher now points to the verified local dashboard.'
