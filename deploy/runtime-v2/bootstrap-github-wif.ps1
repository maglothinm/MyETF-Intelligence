[CmdletBinding()]
param(
    [string]$ProjectId = 'project-38008d5f-4918-46e6-920',
    [string]$ExpectedProjectNumber = '497412818801',
    [string]$PoolId = 'polititrack-runtime-v2',
    [string]$ProviderId = 'github-main',
    [string]$ServiceAccountId = 'polititrack-p3-deployer',
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepositoryId = '1349678672'
$RepositoryFullName = 'maglothinm/MyETF-Intelligence'
$Location = 'global'

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

$activeAccount = (& $gcloud auth list --filter='status:ACTIVE' --format='value(account)').Trim()
if ($LASTEXITCODE -ne 0 -or -not $activeAccount) {
    throw 'An authenticated gcloud account is required. Run gcloud auth login first.'
}

$projectNumber = (& $gcloud projects describe $ProjectId --format='value(projectNumber)').Trim()
if ($LASTEXITCODE -ne 0 -or $projectNumber -notmatch '^\d+$') {
    throw "Google Cloud project $ProjectId could not be resolved."
}
if ($projectNumber -ne $ExpectedProjectNumber) {
    throw "Project number mismatch. Expected $ExpectedProjectNumber but resolved $projectNumber."
}

$serviceAccountEmail = "$ServiceAccountId@$ProjectId.iam.gserviceaccount.com"
$providerResource = "projects/$projectNumber/locations/$Location/workloadIdentityPools/$PoolId/providers/$ProviderId"
$poolResource = "projects/$projectNumber/locations/$Location/workloadIdentityPools/$PoolId"
$principalSet = "principalSet://iam.googleapis.com/$poolResource/attribute.repository_id/$RepositoryId"

$attributeMapping = @(
    'google.subject=assertion.sub',
    'attribute.repository_id=assertion.repository_id',
    'attribute.ref=assertion.ref',
    'attribute.workflow_ref=assertion.workflow_ref'
) -join ','

$allowedWorkflowRefs = @(
    "$RepositoryFullName/.github/workflows/phase3_cloud_discovery.yml@refs/heads/main",
    "$RepositoryFullName/.github/workflows/phase3_prepare.yml@refs/heads/main",
    "$RepositoryFullName/.github/workflows/phase3_apply.yml@refs/heads/main"
)
$workflowCondition = ($allowedWorkflowRefs | ForEach-Object { "assertion.workflow_ref=='$_'" }) -join ' || '
$attributeCondition = "assertion.repository_id=='$RepositoryId' && assertion.ref=='refs/heads/main' && ($workflowCondition)"

$requiredServices = @(
    'iam.googleapis.com',
    'iamcredentials.googleapis.com',
    'sts.googleapis.com',
    'cloudresourcemanager.googleapis.com'
)

$deployerRoles = @(
    'roles/viewer',
    'roles/serviceusage.serviceUsageAdmin',
    'roles/serviceusage.serviceUsageConsumer',
    'roles/storage.admin',
    'roles/artifactregistry.admin',
    'roles/cloudbuild.builds.editor',
    'roles/compute.networkAdmin',
    'roles/servicenetworking.networksAdmin',
    'roles/cloudsql.admin',
    'roles/run.admin',
    'roles/cloudscheduler.admin',
    'roles/secretmanager.admin',
    'roles/iam.serviceAccountAdmin',
    'roles/iam.serviceAccountUser',
    'roles/resourcemanager.projectIamAdmin'
)

$poolExists = Test-GcloudResource @(
    'iam', 'workload-identity-pools', 'describe', $PoolId,
    '--location', $Location,
    '--project', $ProjectId
)
$providerExists = Test-GcloudResource @(
    'iam', 'workload-identity-pools', 'providers', 'describe', $ProviderId,
    '--workload-identity-pool', $PoolId,
    '--location', $Location,
    '--project', $ProjectId
)
$serviceAccountExists = Test-GcloudResource @(
    'iam', 'service-accounts', 'describe', $serviceAccountEmail,
    '--project', $ProjectId
)

Write-Output "PolitiTrack Phase 3 durable WIF bootstrap"
Write-Output "  active_account=$activeAccount"
Write-Output "  project_id=$ProjectId"
Write-Output "  project_number=$projectNumber"
Write-Output "  repository_id=$RepositoryId"
Write-Output "  repository=$RepositoryFullName"
Write-Output "  pool=$PoolId exists=$poolExists"
Write-Output "  provider=$ProviderId exists=$providerExists"
Write-Output "  service_account=$serviceAccountEmail exists=$serviceAccountExists"
Write-Output "  provider_resource=$providerResource"
Write-Output '  trust_scope=canonical repository ID + refs/heads/main + Phase 3 cloud workflows only'
Write-Output "  roles=$($deployerRoles -join ',')"

if (-not $Apply) {
    Write-Output 'Preview only. No Google Cloud mutation occurred. Re-run with -Apply to create/update the durable Phase 3 trust boundary.'
    exit 0
}

Invoke-Checked $gcloud (@('services', 'enable') + $requiredServices + @('--project', $ProjectId, '--quiet'))

if (-not $poolExists) {
    Invoke-Checked $gcloud @(
        'iam', 'workload-identity-pools', 'create', $PoolId,
        '--location', $Location,
        '--project', $ProjectId,
        '--display-name', 'PolitiTrack Runtime v2 GitHub',
        '--description', 'Durable keyless trust for canonical PolitiTrack Phase 3 cloud workflows'
    )
}

if (-not $providerExists) {
    Invoke-Checked $gcloud @(
        'iam', 'workload-identity-pools', 'providers', 'create-oidc', $ProviderId,
        '--workload-identity-pool', $PoolId,
        '--location', $Location,
        '--project', $ProjectId,
        '--issuer-uri', 'https://token.actions.githubusercontent.com/',
        "--attribute-mapping=$attributeMapping",
        "--attribute-condition=$attributeCondition",
        '--display-name', 'PolitiTrack Phase 3 GitHub main'
    )
} else {
    $providerState = (& $gcloud iam workload-identity-pools providers describe $ProviderId --workload-identity-pool $PoolId --location $Location --project $ProjectId --format='value(state)').Trim()
    if ($LASTEXITCODE -ne 0 -or $providerState -ne 'ACTIVE') {
        throw "Existing provider $ProviderId is not ACTIVE (state=$providerState). Refusing to mutate an ambiguous trust resource."
    }
    Invoke-Checked $gcloud @(
        'iam', 'workload-identity-pools', 'providers', 'update-oidc', $ProviderId,
        '--workload-identity-pool', $PoolId,
        '--location', $Location,
        '--project', $ProjectId,
        '--issuer-uri', 'https://token.actions.githubusercontent.com/',
        "--attribute-mapping=$attributeMapping",
        "--attribute-condition=$attributeCondition"
    )
}

if (-not $serviceAccountExists) {
    Invoke-Checked $gcloud @(
        'iam', 'service-accounts', 'create', $ServiceAccountId,
        '--project', $ProjectId,
        '--display-name', 'PolitiTrack Phase 3 deployer',
        '--description', 'Keyless deployer for isolated Runtime v2 Phase 3 only'
    )
}

Invoke-Checked $gcloud @(
    'iam', 'service-accounts', 'add-iam-policy-binding', $serviceAccountEmail,
    '--project', $ProjectId,
    '--role', 'roles/iam.workloadIdentityUser',
    '--member', $principalSet,
    '--condition', 'None',
    '--quiet'
)

foreach ($role in $deployerRoles) {
    Invoke-Checked $gcloud @(
        'projects', 'add-iam-policy-binding', $ProjectId,
        '--member', "serviceAccount:$serviceAccountEmail",
        '--role', $role,
        '--condition', 'None',
        '--quiet'
    )
}

$resolvedProvider = (& $gcloud iam workload-identity-pools providers describe $ProviderId --workload-identity-pool $PoolId --location $Location --project $ProjectId --format='value(name)').Trim()
if ($LASTEXITCODE -ne 0 -or $resolvedProvider -ne $providerResource) {
    throw 'Durable Workload Identity provider did not resolve to the expected resource name.'
}

Write-Output 'Durable PolitiTrack Phase 3 GitHub→Google Cloud trust is ready.'
Write-Output "  workload_identity_provider=$resolvedProvider"
Write-Output "  service_account=$serviceAccountEmail"
Write-Output 'No service-account key was created or exported.'
