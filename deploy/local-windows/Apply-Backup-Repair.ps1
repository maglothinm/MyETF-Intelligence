param(
    [string]$Root = 'C:\ProgramData\PolitiTrack',
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$Revision
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Approve Windows administrator elevation to restart the existing scheduler.'
}
$app = Join-Path $Root 'app'
$python = Join-Path $Root 'venv\Scripts\python.exe'
$git = 'C:\Program Files\Git\cmd\git.exe'
$service = Get-CimInstance Win32_Service -Filter "Name='PolitiTrackScheduler'"
if ($service.PathName.Trim('"') -ne "$Root\services\PolitiTrackScheduler.exe") {
    throw 'Unexpected scheduler installation; no changes made.'
}
$remote = & $git -C $app remote get-url origin
if ($remote -ne 'https://github.com/maglothinm/MyETF-Intelligence.git') { throw 'Wrong repository.' }
& $git -C $app diff --quiet HEAD --
if ($LASTEXITCODE -ne 0) { throw 'Tracked local edits must be reconciled before deployment.' }
& $git -C $app fetch origin main
if ($LASTEXITCODE -ne 0) { throw 'Cannot verify canonical main.' }
& $git -C $app merge-base --is-ancestor $Revision origin/main
if ($LASTEXITCODE -ne 0) { throw 'Requested revision is not on canonical main.' }
$oldRevision = (& $git -C $app rev-parse HEAD).Trim()
$configPath = Join-Path $Root 'config\runtime.json'
$configBefore = [IO.File]::ReadAllText($configPath)
Start-Transcript -Path (Join-Path $Root 'logs\backup-repair-install.log') -Append | Out-Null
try {
    Stop-Service PolitiTrackScheduler
    (Get-Service PolitiTrackScheduler).WaitForStatus('Stopped', [TimeSpan]::FromSeconds(90))
    & $git -C $app checkout --detach $Revision
    if ($LASTEXITCODE -ne 0) { throw 'Cannot activate the reviewed source revision.' }
    & $python "$app\scripts\provision_local_backup.py" --root $Root --apply
    if ($LASTEXITCODE -ne 0) { throw 'Dedicated backup-role provisioning failed.' }
    $config = $configBefore | ConvertFrom-Json
    $config.source_revision = $Revision
    [IO.File]::WriteAllText("$configPath.repair-tmp", ($config | ConvertTo-Json -Depth 50), [Text.UTF8Encoding]::new($false))
    Move-Item -Force "$configPath.repair-tmp" $configPath
    Start-Service PolitiTrackScheduler
    (Get-Service PolitiTrackScheduler).WaitForStatus('Running', [TimeSpan]::FromSeconds(30))
    $receipt = [ordered]@{
        repository_id = 1349678672
        activated_at = (Get-Date).ToUniversalTime().ToString('o')
        previous_revision = $oldRevision
        source_revision = $Revision
        scheduler = (Get-Service PolitiTrackScheduler).Status.ToString()
        database = (Get-Service PolitiTrackDatabase).Status.ToString()
        web = (Get-Service PolitiTrackWeb).Status.ToString()
        database_or_web_restarted = $false
        production_state_reset = $false
    }
    [IO.File]::WriteAllText("$Root\backups\backup-repair-activation.json", ($receipt | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
    Write-Output 'Backup repair activated. Database and dashboard were not restarted. Verify the new backup receipt and natural production jobs.'
} catch {
    $problem = $_
    if ((Get-Service PolitiTrackScheduler).Status -ne 'Stopped') { Stop-Service PolitiTrackScheduler }
    & $git -C $app checkout --detach $oldRevision
    [IO.File]::WriteAllText($configPath, $configBefore, [Text.UTF8Encoding]::new($false))
    Start-Service PolitiTrackScheduler
    throw $problem
} finally { Stop-Transcript | Out-Null }
