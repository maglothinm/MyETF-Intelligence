param([string]$Root = 'C:\ProgramData\PolitiTrack', [switch]$PrepareOnly)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Escape-Xml([string]$Value) { [Security.SecurityElement]::Escape($Value) }
$wrapper = Join-Path $Root 'tools\WinSW-x64.exe'
if ((Get-FileHash $wrapper -Algorithm SHA256).Hash.ToLowerInvariant() -ne '05b82d46ad331cc16bdc00de5c6332c1ef818df8ceefcd49c726553209b3a0da') {
    throw 'Unexpected service wrapper checksum.'
}
$python = Join-Path $Root 'venv\Scripts\python.exe'
$pg = Join-Path $Root 'tools\postgresql16\pgsql\bin'
$services = Join-Path $Root 'services'
New-Item -ItemType Directory -Force $services | Out-Null
$entries = @(
    @{ Id='PolitiTrackDatabase'; Name='PolitiTrack Database'; Exe="$pg\postgres.exe"; Args="-D `"$Root\postgres-data`""; Extra="<stopexecutable>$(Escape-Xml "$pg\pg_ctl.exe")</stopexecutable><stoparguments>-D &quot;$(Escape-Xml "$Root\postgres-data")&quot; -m fast -w stop</stoparguments>" },
    @{ Id='PolitiTrackWeb'; Name='PolitiTrack Dashboard'; Exe=$python; Args="-m runtime_v2.local_host --config `"$Root\config\runtime.json`" web"; Extra='<depend>PolitiTrackDatabase</depend><delayedAutoStart>true</delayedAutoStart>' },
    @{ Id='PolitiTrackScheduler'; Name='PolitiTrack Background Updates'; Exe=$python; Args="-m runtime_v2.local_host --config `"$Root\config\runtime.json`" schedule"; Extra='<depend>PolitiTrackDatabase</depend><delayedAutoStart>true</delayedAutoStart>' }
)
foreach ($entry in $entries) {
    $path = Join-Path $services $entry.Id
    if (Test-Path "$path.exe") {
        if ((Get-FileHash "$path.exe").Hash -ne (Get-FileHash $wrapper).Hash) {
            throw "Unexpected existing service binary: $($entry.Id)"
        }
    } else { Copy-Item $wrapper "$path.exe" }
    $argumentElement = if ($entry.Id -eq 'PolitiTrackDatabase') { 'startarguments' } else { 'arguments' }
    $xml = @"
<service>
  <id>$($entry.Id)</id>
  <name>$($entry.Name)</name>
  <description>PolitiTrack local Runtime v2. Starts with Windows; no Google Cloud runtime.</description>
  <executable>$(Escape-Xml $entry.Exe)</executable>
  <$argumentElement>$(Escape-Xml $entry.Args)</$argumentElement>
  <workingdirectory>$(Escape-Xml "$Root\app")</workingdirectory>
  <startmode>Automatic</startmode>
  $($entry.Extra)
  <serviceaccount><domain>NT AUTHORITY</domain><user>LocalService</user></serviceaccount>
  <env name="PYTHONUTF8" value="1" />
  <env name="PYTHONUNBUFFERED" value="1" />
  <env name="TEMP" value="$(Escape-Xml "$Root\temp")" />
  <env name="TMP" value="$(Escape-Xml "$Root\temp")" />
  <stoptimeout>60 sec</stoptimeout>
  <onfailure action="restart" delay="10 sec" />
  <resetfailure>1 hour</resetfailure>
  <logpath>$(Escape-Xml "$Root\logs")</logpath>
  <log mode="roll-by-size"><sizeThreshold>10240</sizeThreshold><keepFiles>5</keepFiles></log>
</service>
"@
    [IO.File]::WriteAllText("$path.xml", $xml, [Text.UTF8Encoding]::new($false))
    [xml]$validated = $xml
}
if ($PrepareOnly) { Write-Output 'Three service configurations prepared.'; exit 0 }
$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Windows requires administrator approval to register startup services. Run this reviewed installer as administrator.'
}
Start-Transcript -Path (Join-Path $Root 'logs\service-install.log') -Append | Out-Null
try {
    if (-not (Test-Path "$Root\config\runtime.json")) { throw 'Private runtime configuration is missing.' }
    foreach ($id in @('PolitiTrackScheduler','PolitiTrackWeb','PolitiTrackDatabase')) {
        $existing = Get-Service $id -ErrorAction SilentlyContinue
        if ($existing -and $existing.Status -ne 'Stopped') { Stop-Service $id -Force }
    }
    # A dashboard may be running under the owner during migration acceptance.
    # Stop only that dedicated loopback web process before binding its service.
    $rootPattern = [regex]::Escape($Root)
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match $rootPattern -and
                       $_.CommandLine -match 'runtime_v2\.local_host.*\sweb\s*$' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    # The migration temporarily runs PostgreSQL under the owner. Transfer it
    # cleanly to LocalService, retaining the exact existing data directory.
    if (Test-Path "$Root\postgres-data\postmaster.pid") {
        & "$pg\pg_ctl.exe" -D "$Root\postgres-data" -m fast -w stop
        if ($LASTEXITCODE -ne 0) { throw 'Could not stop migration database cleanly.' }
    }
    foreach ($entry in $entries) {
        $exe = Join-Path $services ($entry.Id + '.exe')
        if (Get-Service $entry.Id -ErrorAction SilentlyContinue) {
            $current = Get-CimInstance Win32_Service -Filter "Name='$($entry.Id)'"
            if ($current.PathName.Trim('"') -ne $exe) { throw 'An existing service uses a different installation path.' }
            $mode = if ($entry.Id -eq 'PolitiTrackDatabase') { 'auto' } else { 'delayed-auto' }
            & sc.exe config $entry.Id start= $mode obj= 'NT AUTHORITY\LocalService'
        } else { & $exe install }
        if ($LASTEXITCODE -ne 0) { throw "Service registration failed: $($entry.Id)" }
        Start-Service $entry.Id
        (Get-Service $entry.Id).WaitForStatus('Running', [TimeSpan]::FromSeconds(30))
    }
    $ready = $false
    for ($attempt=0; $attempt -lt 60; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8765/readyz' -TimeoutSec 5
            if ($response.StatusCode -eq 200) { $ready = $true; break }
        } catch { Start-Sleep -Seconds 1 }
    }
    if (-not $ready) { throw 'Services were registered, but dashboard readiness did not pass. Inspect the service logs.' }
    foreach ($entry in $entries) {
        if ((Get-Service $entry.Id).Status -ne 'Running') { throw "Service exited during verification: $($entry.Id)" }
    }
    Get-CimInstance Win32_Service -Filter "Name LIKE 'PolitiTrack%'" |
        Select-Object Name, State, StartMode, StartName, PathName |
        ConvertTo-Json | Set-Content "$Root\backups\installed-services.json"
    Write-Output 'All three local services are registered and running.'
} finally { Stop-Transcript | Out-Null }
