[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z][a-z0-9-]{4,28}[a-z0-9]$')]
    [string]$ProjectId,
    [string]$Region = 'us-central1',
    [string]$RuntimeSecretsFile = '',
    [string]$MigrationDirectory = '',
    [switch]$DisableVault,
    [switch]$EnableSchedules,
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$terraformRoot = Join-Path $PSScriptRoot 'terraform'
$stateBucket = "$ProjectId-polititrack-tfstate"
$migrationBucket = "$ProjectId-polititrack-migration"
$vaultEnabled = -not $DisableVault

function Resolve-RequiredCommand([string]$Name) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "$Name is required and was not found on PATH."
    }
    return $command.Source
}

function Invoke-Checked([string]$File, [string[]]$Arguments) {
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$File failed with exit code $LASTEXITCODE."
    }
}

function Test-GcloudResource([string[]]$Arguments) {
    & $script:gcloud @Arguments *> $null
    return $LASTEXITCODE -eq 0
}

$gcloud = Resolve-RequiredCommand 'gcloud'
$terraform = Resolve-RequiredCommand 'terraform'
$sourceRevision = (& git -C $repositoryRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sourceRevision -notmatch '^[0-9a-f]{40}$') {
    throw 'The canonical Git revision could not be resolved.'
}
$remote = (& git -C $repositoryRoot remote get-url origin).Trim()
if ($remote -notmatch 'maglothinm/MyETF-Intelligence(?:\.git)?$') {
    throw 'Refusing deployment from a noncanonical repository remote.'
}

$account = (& $gcloud auth list --filter='status:ACTIVE' --format='value(account)').Trim()
if (-not $account) {
    throw 'Google Cloud authentication is required before deployment.'
}
Invoke-Checked $gcloud @('config', 'set', 'project', $ProjectId, '--quiet')
Invoke-Checked $gcloud @(
    'services', 'enable',
    'artifactregistry.googleapis.com',
    'cloudbuild.googleapis.com',
    'run.googleapis.com',
    'cloudscheduler.googleapis.com',
    'sqladmin.googleapis.com',
    'secretmanager.googleapis.com',
    'storage.googleapis.com',
    '--project', $ProjectId,
    '--quiet'
)

if (-not (Test-GcloudResource @('storage', 'buckets', 'describe', "gs://$stateBucket", '--project', $ProjectId))) {
    Invoke-Checked $gcloud @(
        'storage', 'buckets', 'create', "gs://$stateBucket",
        '--project', $ProjectId,
        '--location', $Region,
        '--uniform-bucket-level-access',
        '--public-access-prevention'
    )
}
Invoke-Checked $gcloud @('storage', 'buckets', 'update', "gs://$stateBucket", '--versioning')

if (-not (Test-GcloudResource @('artifacts', 'repositories', 'describe', 'polititrack', '--location', $Region, '--project', $ProjectId))) {
    Invoke-Checked $gcloud @(
        'artifacts', 'repositories', 'create', 'polititrack',
        '--repository-format', 'docker',
        '--location', $Region,
        '--project', $ProjectId,
        '--description', 'PolitiTrack immutable runtime images'
    )
}

$tag = $sourceRevision.Substring(0, 12)
$taggedImage = "$Region-docker.pkg.dev/$ProjectId/polititrack/runtime-v2:$tag"
Invoke-Checked $gcloud @(
    'builds', 'submit', $repositoryRoot,
    '--project', $ProjectId,
    '--config', (Join-Path $PSScriptRoot 'cloudbuild.yaml'),
    '--substitutions', "_REGION=$Region,_REPOSITORY=polititrack,_IMAGE=runtime-v2,_TAG=$tag",
    '--quiet'
)
$digest = (& $gcloud artifacts docker images describe $taggedImage --project $ProjectId --format='value(image_summary.digest)').Trim()
if ($LASTEXITCODE -ne 0 -or $digest -notmatch '^sha256:[0-9a-f]{64}$') {
    throw 'Cloud Build completed without a resolvable immutable image digest.'
}
$image = "$Region-docker.pkg.dev/$ProjectId/polititrack/runtime-v2@$digest"

$runtimeSecrets = @{}
if ($RuntimeSecretsFile) {
    $runtimeSecrets = Get-Content (Resolve-Path $RuntimeSecretsFile) -Raw | ConvertFrom-Json -AsHashtable
    foreach ($entry in $runtimeSecrets.GetEnumerator()) {
        if ($entry.Key -notmatch '^[A-Z][A-Z0-9_]+$' -or $entry.Value -notmatch '^[A-Za-z0-9_-]+$') {
            throw 'Runtime secret mapping must contain environment names and Secret Manager IDs only.'
        }
        Invoke-Checked $gcloud @('secrets', 'describe', $entry.Value, '--project', $ProjectId, '--quiet')
    }
}
$runtimeSecretsJson = $runtimeSecrets | ConvertTo-Json -Compress

$terraformData = Join-Path $env:LOCALAPPDATA 'PolitiTrack\terraform-runtime-v2'
$env:TF_DATA_DIR = $terraformData
Invoke-Checked $terraform @(
    "-chdir=$terraformRoot", 'init', '-reconfigure',
    "-backend-config=bucket=$stateBucket",
    '-backend-config=prefix=runtime-v2'
)

$baseVariables = @(
    "-var=project_id=$ProjectId",
    "-var=region=$Region",
    "-var=image=$image",
    "-var=vault_enabled=$($vaultEnabled.ToString().ToLowerInvariant())",
    "-var=runtime_secrets=$runtimeSecretsJson",
    '-var=schedules_enabled=false'
)

if (-not $Apply) {
    Invoke-Checked $terraform (@("-chdir=$terraformRoot", 'plan') + $baseVariables)
    Write-Output "Validated plan for $ProjectId using immutable image $image. No infrastructure was changed."
    exit 0
}

Invoke-Checked $terraform (@("-chdir=$terraformRoot", 'apply', '-auto-approve') + $baseVariables)
Invoke-Checked $gcloud @('run', 'jobs', 'execute', 'polititrack-admin', '--region', $Region, '--project', $ProjectId, '--wait', '--quiet')

if ($MigrationDirectory) {
    $migrationRoot = (Resolve-Path $MigrationDirectory).Path
    foreach ($namespace in @('legislative', 'executive', 'ai')) {
        $archive = Join-Path $migrationRoot "$namespace-tracker-state.zip"
        if ($namespace -eq 'ai') { $archive = Join-Path $migrationRoot 'ai-analysis-state.zip' }
        $receipt = Join-Path $migrationRoot "$namespace-receipt.json"
        if (-not (Test-Path -LiteralPath $archive) -or -not (Test-Path -LiteralPath $receipt)) {
            throw "Missing migration archive or receipt for $namespace."
        }
        $provenance = Get-Content $receipt -Raw | ConvertFrom-Json
        $actualDigest = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($provenance.archive_sha256 -ne $actualDigest) {
            throw "$namespace migration archive does not match its receipt."
        }
        Invoke-Checked $gcloud @('storage', 'cp', $archive, "gs://$migrationBucket/migration/$namespace.zip", '--quiet')
        Invoke-Checked $gcloud @('storage', 'cp', $receipt, "gs://$migrationBucket/migration/$namespace-receipt.json", '--quiet')
        Invoke-Checked $gcloud @('run', 'jobs', 'execute', "polititrack-import-$namespace", '--region', $Region, '--project', $ProjectId, '--wait', '--quiet')
    }
    Invoke-Checked $gcloud @('run', 'jobs', 'execute', 'polititrack-dashboard', '--region', $Region, '--project', $ProjectId, '--wait', '--quiet')
}

$serviceUrl = (& $gcloud run services describe polititrack-web --region $Region --project $ProjectId --format='value(status.url)').Trim()
if ($LASTEXITCODE -ne 0 -or -not $serviceUrl) {
    throw 'The deployed dashboard service URL could not be resolved.'
}
if ($MigrationDirectory) {
    $ready = Invoke-RestMethod -Uri "$serviceUrl/readyz" -TimeoutSec 30
    if ($ready.status -ne 'ready') {
        throw 'The deployed dashboard did not pass readiness after migration.'
    }
}

if ($EnableSchedules) {
    if (-not $MigrationDirectory) {
        throw 'Schedule activation requires the verified migration directory in the same acceptance run.'
    }
    $enabledVariables = $baseVariables | Where-Object { $_ -ne '-var=schedules_enabled=false' }
    $enabledVariables += '-var=schedules_enabled=true'
    Invoke-Checked $terraform (@("-chdir=$terraformRoot", 'apply', '-auto-approve') + $enabledVariables)
}

Write-Output "PolitiTrack Runtime v2 deployed at $serviceUrl from $sourceRevision. Schedules enabled: $($EnableSchedules.IsPresent)."
