[CmdletBinding(DefaultParameterSetName = 'Plan')]
param(
    [string]$ProjectId = '',
    [string]$Region = 'us-central1',
    [string]$RuntimeSecretsFile = '',
    [string]$RuntimeEnvironmentFile = '',
    [string]$MigrationDirectory = '',
    [switch]$EnableVault,
    [switch]$DisableVault,
    [string]$Image = '',
    [string]$PlanFile = '',
    [Parameter(ParameterSetName = 'Initialize')]
    [switch]$InitializeFoundation,
    [Parameter(ParameterSetName = 'Build')]
    [switch]$BuildImage,
    [Parameter(ParameterSetName = 'PrepareApply')]
    [switch]$PrepareApplyPlan,
    [Parameter(ParameterSetName = 'Apply')]
    [switch]$Apply,
    [switch]$EnableSchedules
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$terraformRoot = Join-Path $PSScriptRoot 'terraform'
if ($EnableVault -and $DisableVault) {
    throw 'EnableVault and DisableVault are mutually exclusive.'
}
# Phase 3 defaults Filing Vault off. DisableVault is retained as an explicit
# compatibility no-op; only EnableVault opts the isolated acceptance runtime in.
$vaultEnabled = $EnableVault.IsPresent

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

function Read-JsonHashtable([string]$Path, [string]$Description) {
    if (-not $Path) {
        return @{}
    }
    $resolved = Resolve-Path $Path
    $mapping = Get-Content $resolved -Raw | ConvertFrom-Json -AsHashtable
    if ($null -eq $mapping) {
        throw "$Description mapping is empty or invalid JSON."
    }
    return $mapping
}

function Assert-ImmutableImage([string]$Candidate) {
    $escapedRegion = [regex]::Escape($Region)
    $escapedProject = [regex]::Escape($ProjectId)
    $pattern = "^${escapedRegion}-docker\.pkg\.dev/${escapedProject}/polititrack/runtime-v2@sha256:[0-9a-f]{64}$"
    if ($Candidate -notmatch $pattern) {
        throw 'Image must be the immutable Runtime v2 Artifact Registry digest for the selected project and region.'
    }
}

if ($EnableSchedules) {
    throw 'Phase 3 bootstrap refuses schedule activation. schedules_enabled must remain false until a later explicit owner gate.'
}
if ($MigrationDirectory -and -not $Apply) {
    throw 'MigrationDirectory is accepted only when applying a previously prepared Phase 3 plan.'
}

$gcloud = Resolve-RequiredCommand 'gcloud'
$terraform = Resolve-RequiredCommand 'terraform'
$git = Resolve-RequiredCommand 'git'

$sourceRevision = (& $git -C $repositoryRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sourceRevision -notmatch '^[0-9a-f]{40}$') {
    throw 'The canonical Git revision could not be resolved.'
}
$remote = (& $git -C $repositoryRoot remote get-url origin).Trim()
if ($LASTEXITCODE -ne 0 -or $remote -notmatch 'maglothinm/MyETF-Intelligence(?:\.git)?$') {
    throw 'Refusing deployment from a noncanonical repository remote.'
}
$workingTree = (& $git -C $repositoryRoot status --porcelain)
if ($LASTEXITCODE -ne 0) {
    throw 'The Git working tree could not be inspected.'
}
if ($workingTree) {
    throw 'Refusing Phase 3 execution from a dirty working tree.'
}
$mainRef = (& $git -C $repositoryRoot ls-remote origin refs/heads/main).Trim()
if ($LASTEXITCODE -ne 0 -or $mainRef -notmatch '^(?<sha>[0-9a-f]{40})\s+') {
    throw 'The canonical origin/main revision could not be resolved.'
}
$canonicalMainRevision = $Matches.sha
if ($sourceRevision -ne $canonicalMainRevision) {
    throw "Refusing Phase 3 execution from $sourceRevision because canonical origin/main is $canonicalMainRevision."
}

$account = (& $gcloud auth list --filter='status:ACTIVE' --format='value(account)').Trim()
if ($LASTEXITCODE -ne 0 -or -not $account) {
    throw 'Google Cloud authentication is required before Phase 3 execution.'
}

if (-not $ProjectId) {
    $configuredProject = (& $gcloud config get-value project --quiet 2>$null).Trim()
    if ($LASTEXITCODE -eq 0 -and $configuredProject -and $configuredProject -ne '(unset)') {
        $ProjectId = $configuredProject
    }
}
if (-not $ProjectId) {
    throw 'No Google Cloud project was supplied or configured. Refusing to invent a project ID.'
}
if ($ProjectId -notmatch '^[a-z][a-z0-9-]{4,28}[a-z0-9]$') {
    throw 'The selected Google Cloud project ID has an invalid format.'
}

$projectNumber = (& $gcloud projects describe $ProjectId --format='value(projectNumber)').Trim()
if ($LASTEXITCODE -ne 0 -or $projectNumber -notmatch '^\d+$') {
    throw 'The selected Google Cloud project could not be resolved read-only.'
}

$stateBucket = "$ProjectId-polititrack-tfstate"
$migrationBucket = "$ProjectId-polititrack-migration"
$repositoryName = 'polititrack'
$requiredServices = @(
    'artifactregistry.googleapis.com',
    'cloudbuild.googleapis.com',
    'compute.googleapis.com',
    'run.googleapis.com',
    'cloudscheduler.googleapis.com',
    'sqladmin.googleapis.com',
    'secretmanager.googleapis.com',
    'servicenetworking.googleapis.com',
    'storage.googleapis.com',
    'cloudresourcemanager.googleapis.com',
    'iam.googleapis.com'
)

$enabledServices = @(
    & $gcloud services list --enabled --project $ProjectId --format='value(config.name)'
)
if ($LASTEXITCODE -ne 0) {
    throw 'Enabled Google Cloud services could not be inspected read-only.'
}
$missingServices = @($requiredServices | Where-Object { $_ -notin $enabledServices })
$stateBucketExists = Test-GcloudResource @('storage', 'buckets', 'describe', "gs://$stateBucket", '--project', $ProjectId)
$repositoryExists = Test-GcloudResource @('artifacts', 'repositories', 'describe', $repositoryName, '--location', $Region, '--project', $ProjectId)

Write-Output "Phase 3 preflight: account=$account project=$ProjectId project_number=$projectNumber region=$Region source=$sourceRevision"
Write-Output "Phase 3 preflight: state_bucket=$stateBucket exists=$stateBucketExists artifact_repository=$repositoryName exists=$repositoryExists"
Write-Output "Phase 3 preflight: missing_services=$($missingServices -join ',') mode=shadow schedules_enabled=false public_dashboard_enabled=false vault_enabled=$($vaultEnabled.ToString().ToLowerInvariant())"

if ($InitializeFoundation) {
    if ($missingServices.Count -gt 0) {
        Invoke-Checked $gcloud (@('services', 'enable') + $missingServices + @('--project', $ProjectId, '--quiet'))
    }
    if (-not $stateBucketExists) {
        Invoke-Checked $gcloud @(
            'storage', 'buckets', 'create', "gs://$stateBucket",
            '--project', $ProjectId,
            '--location', $Region,
            '--uniform-bucket-level-access',
            '--public-access-prevention'
        )
    }
    Invoke-Checked $gcloud @('storage', 'buckets', 'update', "gs://$stateBucket", '--versioning', '--public-access-prevention', '--project', $ProjectId)
    if (-not $repositoryExists) {
        Invoke-Checked $gcloud @(
            'artifacts', 'repositories', 'create', $repositoryName,
            '--repository-format', 'docker',
            '--location', $Region,
            '--project', $ProjectId,
            '--description', 'PolitiTrack immutable runtime images'
        )
    }
    Write-Output "Phase 3 foundation initialized explicitly for $ProjectId. No Terraform apply or image build was performed."
    exit 0
}

if ($BuildImage) {
    if (-not $repositoryExists) {
        throw 'Artifact Registry foundation is missing. Run the explicit -InitializeFoundation step first.'
    }
    $tag = $sourceRevision.Substring(0, 12)
    $taggedImage = "$Region-docker.pkg.dev/$ProjectId/$repositoryName/runtime-v2:$tag"
    Invoke-Checked $gcloud @(
        'builds', 'submit', $repositoryRoot,
        '--project', $ProjectId,
        '--config', (Join-Path $PSScriptRoot 'cloudbuild.yaml'),
        '--substitutions', "_REGION=$Region,_REPOSITORY=$repositoryName,_IMAGE=runtime-v2,_TAG=$tag",
        '--quiet'
    )
    $digest = (& $gcloud artifacts docker images describe $taggedImage --project $ProjectId --format='value(image_summary.digest)').Trim()
    if ($LASTEXITCODE -ne 0 -or $digest -notmatch '^sha256:[0-9a-f]{64}$') {
        throw 'Cloud Build completed without a resolvable immutable image digest.'
    }
    $immutableImage = "$Region-docker.pkg.dev/$ProjectId/$repositoryName/runtime-v2@$digest"
    Write-Output "Phase 3 immutable image: $immutableImage"
    exit 0
}

if (-not $stateBucketExists) {
    throw 'Terraform state foundation is missing. Run the explicit -InitializeFoundation step before planning.'
}

$runtimeSecrets = Read-JsonHashtable $RuntimeSecretsFile 'Runtime secret'
foreach ($entry in $runtimeSecrets.GetEnumerator()) {
    if ($entry.Key -notmatch '^[A-Z][A-Z0-9_]+$' -or $entry.Value -notmatch '^[A-Za-z0-9_-]+$') {
        throw 'Runtime secret mapping must contain environment names and Secret Manager IDs only.'
    }
    Invoke-Checked $gcloud @('secrets', 'describe', $entry.Value, '--project', $ProjectId, '--quiet')
}
$runtimeSecretsJson = $runtimeSecrets | ConvertTo-Json -Compress

$runtimeEnvironment = Read-JsonHashtable $RuntimeEnvironmentFile 'Runtime environment'
foreach ($entry in @($runtimeEnvironment.GetEnumerator())) {
    if ($entry.Key -notmatch '^[A-Z][A-Z0-9_]+$' -or $entry.Value -isnot [string]) {
        throw 'Runtime environment mapping must contain non-secret string values keyed by environment name.'
    }
    if ($runtimeSecrets.ContainsKey($entry.Key)) {
        throw "Runtime environment and secret mappings both define $($entry.Key)."
    }
}
if ($runtimeEnvironment.ContainsKey('POLITITRACK_MODE') -and $runtimeEnvironment['POLITITRACK_MODE'].ToLowerInvariant() -ne 'shadow') {
    throw 'Phase 3 bootstrap refuses any POLITITRACK_MODE other than shadow.'
}
$runtimeEnvironment['POLITITRACK_MODE'] = 'shadow'
$runtimeEnvironmentJson = $runtimeEnvironment | ConvertTo-Json -Compress

$terraformData = Join-Path ([System.IO.Path]::GetTempPath()) 'PolitiTrack/terraform-runtime-v2'
$env:TF_DATA_DIR = $terraformData
Invoke-Checked $terraform @(
    "-chdir=$terraformRoot", 'init', '-reconfigure',
    "-backend-config=bucket=$stateBucket",
    '-backend-config=prefix=runtime-v2'
)

if ($Apply) {
    if (-not $PlanFile -or -not (Test-Path -LiteralPath $PlanFile)) {
        throw 'Apply requires an existing -PlanFile created by -PrepareApplyPlan.'
    }
    $receiptPath = "$PlanFile.receipt.json"
    if (-not (Test-Path -LiteralPath $receiptPath)) {
        throw 'Apply requires the companion Phase 3 plan receipt.'
    }
    $receipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
    $actualPlanHash = (Get-FileHash -LiteralPath $PlanFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($receipt.plan_sha256 -ne $actualPlanHash) {
        throw 'Phase 3 apply plan hash no longer matches its receipt.'
    }
    if ($receipt.project_id -ne $ProjectId -or $receipt.project_number -ne $projectNumber -or $receipt.region -ne $Region) {
        throw 'Phase 3 plan receipt does not match the selected Google Cloud boundary.'
    }
    if ($receipt.source_revision -ne $sourceRevision) {
        throw 'Phase 3 plan receipt does not match canonical origin/main.'
    }
    if ($receipt.mode -ne 'shadow' -or $receipt.schedules_enabled -ne $false -or $receipt.public_dashboard_enabled -ne $false) {
        throw 'Phase 3 plan receipt violates shadow/schedules-disabled/private-dashboard controls.'
    }
    if ([bool]$receipt.vault_enabled -ne $vaultEnabled) {
        throw 'Phase 3 plan receipt vault setting does not match this apply invocation.'
    }
    Assert-ImmutableImage ([string]$receipt.image)
    if ($Image -and $Image -ne [string]$receipt.image) {
        throw 'The optional Apply -Image value does not match the immutable image recorded in the plan receipt.'
    }

    Invoke-Checked $terraform @("-chdir=$terraformRoot", 'apply', '-auto-approve', $PlanFile)
    Invoke-Checked $gcloud @('run', 'jobs', 'execute', 'polititrack-admin', '--region', $Region, '--project', $ProjectId, '--wait', '--quiet')

    if ($MigrationDirectory) {
        $migrationRoot = (Resolve-Path $MigrationDirectory).Path
        foreach ($namespace in @('legislative', 'executive', 'ai')) {
            $archive = Join-Path $migrationRoot "$namespace-tracker-state.zip"
            if ($namespace -eq 'ai') { $archive = Join-Path $migrationRoot 'ai-analysis-state.zip' }
            $migrationReceipt = Join-Path $migrationRoot "$namespace-receipt.json"
            if (-not (Test-Path -LiteralPath $archive) -or -not (Test-Path -LiteralPath $migrationReceipt)) {
                throw "Missing migration archive or receipt for $namespace."
            }
            $provenance = Get-Content $migrationReceipt -Raw | ConvertFrom-Json
            $actualDigest = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($provenance.archive_sha256 -ne $actualDigest) {
                throw "$namespace migration archive does not match its receipt."
            }
            Invoke-Checked $gcloud @('storage', 'cp', $archive, "gs://$migrationBucket/migration/$namespace.zip", '--quiet')
            Invoke-Checked $gcloud @('storage', 'cp', $migrationReceipt, "gs://$migrationBucket/migration/$namespace-receipt.json", '--quiet')
            Invoke-Checked $gcloud @('run', 'jobs', 'execute', "polititrack-import-$namespace", '--region', $Region, '--project', $ProjectId, '--wait', '--quiet')
        }
        Invoke-Checked $gcloud @('run', 'jobs', 'execute', 'polititrack-dashboard', '--region', $Region, '--project', $ProjectId, '--wait', '--quiet')
    }

    $serviceUrl = (& $gcloud run services describe polititrack-web --region $Region --project $ProjectId --format='value(status.url)').Trim()
    if ($LASTEXITCODE -ne 0 -or -not $serviceUrl) {
        throw 'The deployed dashboard service URL could not be resolved.'
    }
    if ($MigrationDirectory) {
        $identityToken = (& $gcloud auth print-identity-token).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $identityToken) {
            throw 'Could not obtain an identity token for the private Runtime v2 readiness check.'
        }
        $headers = @{ Authorization = "Bearer $identityToken" }
        $ready = Invoke-RestMethod -Uri "$serviceUrl/readyz" -Headers $headers -TimeoutSec 30
        if ($ready.status -ne 'ready') {
            throw 'The deployed dashboard did not pass authenticated readiness after migration.'
        }
    }

    Write-Output "PolitiTrack Runtime v2 Phase 3 apply completed at $serviceUrl from $sourceRevision. mode=shadow schedules_enabled=false public_dashboard_enabled=false vault_enabled=$($vaultEnabled.ToString().ToLowerInvariant())."
    exit 0
}

$placeholderDigest = 'sha256:' + ('0' * 64)
$placeholderImage = "$Region-docker.pkg.dev/$ProjectId/$repositoryName/runtime-v2@$placeholderDigest"
$selectedImage = $Image
if (-not $selectedImage -and $PSCmdlet.ParameterSetName -eq 'Plan') {
    $selectedImage = $placeholderImage
    Write-Output 'Phase 3 structural plan is using a nondeployable placeholder image digest. Build the immutable image only after this plan is accepted.'
}
if (-not $selectedImage) {
    throw 'An immutable -Image digest is required for the final apply plan.'
}
if ($selectedImage -ne $placeholderImage) {
    Assert-ImmutableImage $selectedImage
}

$baseVariables = @(
    "-var=project_id=$ProjectId",
    "-var=region=$Region",
    "-var=image=$selectedImage",
    "-var=vault_enabled=$($vaultEnabled.ToString().ToLowerInvariant())",
    "-var=runtime_secrets=$runtimeSecretsJson",
    "-var=runtime_environment=$runtimeEnvironmentJson",
    '-var=schedules_enabled=false',
    '-var=public_dashboard_enabled=false'
)

if ($PSCmdlet.ParameterSetName -eq 'Plan') {
    Invoke-Checked $terraform (@("-chdir=$terraformRoot", 'plan', '-lock=false') + $baseVariables)
    Write-Output "Validated read-only Phase 3 structural plan for $ProjectId from $sourceRevision. No infrastructure apply, image build, scheduler activation, producer execution, or public dashboard publication occurred."
    exit 0
}

if ($PrepareApplyPlan) {
    if (-not $PlanFile) {
        $PlanFile = Join-Path ([System.IO.Path]::GetTempPath()) "polititrack-runtime-v2-$($sourceRevision.Substring(0, 12)).tfplan"
    }
    $planParent = Split-Path -Parent $PlanFile
    if ($planParent -and -not (Test-Path $planParent)) {
        New-Item -ItemType Directory -Path $planParent -Force | Out-Null
    }
    Invoke-Checked $terraform (@("-chdir=$terraformRoot", 'plan', '-lock=false', "-out=$PlanFile") + $baseVariables)
    $planHash = (Get-FileHash -LiteralPath $PlanFile -Algorithm SHA256).Hash.ToLowerInvariant()
    $receipt = [ordered]@{
        schema_version = 1
        project_id = $ProjectId
        project_number = $projectNumber
        region = $Region
        source_revision = $sourceRevision
        image = $selectedImage
        mode = 'shadow'
        schedules_enabled = $false
        public_dashboard_enabled = $false
        vault_enabled = $vaultEnabled
        plan_sha256 = $planHash
    }
    $receiptPath = "$PlanFile.receipt.json"
    $receipt | ConvertTo-Json | Set-Content -LiteralPath $receiptPath -Encoding utf8
    Write-Output "Prepared Phase 3 apply plan: $PlanFile"
    Write-Output "Prepared Phase 3 plan receipt: $receiptPath sha256=$planHash"
    exit 0
}

throw "Unhandled Phase 3 bootstrap parameter set: $($PSCmdlet.ParameterSetName)."
