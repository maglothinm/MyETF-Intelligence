[CmdletBinding()]
param(
    [string]$ProjectNumber = '497412818801',
    [string]$Region = 'us-central1',
    [string]$PoolId = 'polititrack-github-phase3',
    [string]$ProviderId = 'phase3-main',
    [string]$DeployerServiceAccountId = 'polititrack-phase3-deployer',
    [string]$BuilderServiceAccountId = 'polititrack-phase3-builder',
    [string]$TerraformRoleId = 'polititrackPhase3Terraform',
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ExpectedRepositoryId = '1349678672'
$ExpectedRepositoryOwnerId = '225069210'
$ExpectedRef = 'refs/heads/main'
$ExpectedIssuer = 'https://token.actions.githubusercontent.com/'

function Resolve-RequiredCommand([string]$Name) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) { throw "$Name is required and was not found on PATH." }
    return $command.Source
}

function Invoke-Checked([string]$File, [string[]]$Arguments) {
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$File failed with exit code $LASTEXITCODE." }
}

function Test-GcloudResource([string[]]$Arguments) {
    try {
        & $script:gcloud @Arguments *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Ensure-ProjectBinding([string]$ProjectId, [string]$Member, [string]$Role) {
    Invoke-Checked $script:gcloud @(
        'projects', 'add-iam-policy-binding', $ProjectId,
        '--member', $Member,
        '--role', $Role,
        '--condition', 'None',
        '--quiet',
        '--format=none'
    )
}

function Ensure-ServiceAccount([string]$ProjectId, [string]$AccountId, [string]$DisplayName, [string]$Description) {
    $email = "$AccountId@$ProjectId.iam.gserviceaccount.com"
    $exists = Test-GcloudResource @('iam', 'service-accounts', 'describe', $email, '--project', $ProjectId)
    if (-not $exists) {
        Invoke-Checked $script:gcloud @(
            'iam', 'service-accounts', 'create', $AccountId,
            '--project', $ProjectId,
            '--display-name', $DisplayName,
            '--description', $Description,
            '--quiet'
        )
    }
    return $email
}

$gcloud = Resolve-RequiredCommand 'gcloud'
$git = Resolve-RequiredCommand 'git'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

$remote = (& $git -C $repositoryRoot remote get-url origin).Trim()
if ($LASTEXITCODE -ne 0 -or $remote -notmatch 'maglothinm/MyETF-Intelligence(?:\.git)?$') {
    throw 'Refusing Phase 3 identity bootstrap from a noncanonical repository remote.'
}

$account = (& $gcloud auth list --filter='status:ACTIVE' --format='value(account)').Trim()
if ($LASTEXITCODE -ne 0 -or -not $account) { throw 'An active local Google Cloud login is required.' }

$projectId = (& $gcloud projects describe $ProjectNumber --format='value(projectId)').Trim()
if ($LASTEXITCODE -ne 0 -or -not $projectId) { throw "Unable to resolve Google Cloud project number $ProjectNumber." }
$resolvedProjectNumber = (& $gcloud projects describe $projectId --format='value(projectNumber)').Trim()
if ($LASTEXITCODE -ne 0 -or $resolvedProjectNumber -ne $ProjectNumber) {
    throw 'Resolved Google Cloud project ID does not map back to the expected immutable project number.'
}

$poolResource = "projects/$ProjectNumber/locations/global/workloadIdentityPools/$PoolId"
$providerResource = "$poolResource/providers/$ProviderId"
$principalSet = "principalSet://iam.googleapis.com/$poolResource/attribute.repository_id/$ExpectedRepositoryId"
$expectedCondition = "assertion.repository_id == '$ExpectedRepositoryId' && assertion.repository_owner_id == '$ExpectedRepositoryOwnerId' && assertion.ref == '$ExpectedRef'"

$provider = (& $gcloud iam workload-identity-pools providers describe $ProviderId `
    --project $projectId `
    --location global `
    --workload-identity-pool $PoolId `
    --format json) | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or -not $provider) { throw 'The established Phase 3 Workload Identity Provider could not be resolved.' }
if ($provider.name -ne $providerResource -or $provider.state -ne 'ACTIVE') { throw 'The established Phase 3 Workload Identity Provider is not the expected active provider.' }
if ($provider.oidc.issuerUri -ne $ExpectedIssuer) { throw 'The established Phase 3 Workload Identity Provider has an unexpected issuer.' }
if ([string]$provider.attributeCondition -ne $expectedCondition) { throw 'The established Phase 3 Workload Identity Provider has an unexpected admission condition.' }

$deployerEmail = "$DeployerServiceAccountId@$projectId.iam.gserviceaccount.com"
$builderEmail = "$BuilderServiceAccountId@$projectId.iam.gserviceaccount.com"
$terraformRoleName = "projects/$projectId/roles/$TerraformRoleId"
$stateBucket = "$projectId-polititrack-tfstate"
$cloudBuildBucket = "${projectId}_cloudbuild"
$artifactRepository = 'polititrack'

$terraformPermissions = @(
    'resourcemanager.projects.get',
    'resourcemanager.projects.list',
    'serviceusage.operations.get',
    'serviceusage.services.enable',
    'serviceusage.services.get',
    'serviceusage.services.list',
    'serviceusage.services.use',
    'storage.buckets.create',
    'storage.buckets.get',
    'storage.buckets.getIamPolicy',
    'storage.buckets.list',
    'storage.buckets.setIamPolicy',
    'storage.buckets.update',
    'secretmanager.locations.get',
    'secretmanager.locations.list',
    'secretmanager.secrets.create',
    'secretmanager.secrets.get',
    'secretmanager.secrets.getIamPolicy',
    'secretmanager.secrets.list',
    'secretmanager.secrets.setIamPolicy',
    'secretmanager.secrets.update',
    'secretmanager.versions.add',
    'secretmanager.versions.get',
    'secretmanager.versions.list',
    'run.configurations.get',
    'run.configurations.list',
    'run.executions.get',
    'run.executions.list',
    'run.jobs.create',
    'run.jobs.get',
    'run.jobs.getIamPolicy',
    'run.jobs.list',
    'run.jobs.listEffectiveTags',
    'run.jobs.listTagBindings',
    'run.jobs.setIamPolicy',
    'run.jobs.update',
    'run.locations.list',
    'run.operations.get',
    'run.operations.list',
    'run.revisions.get',
    'run.revisions.list',
    'run.routes.get',
    'run.routes.list',
    'run.services.create',
    'run.services.get',
    'run.services.getIamPolicy',
    'run.services.list',
    'run.services.listEffectiveTags',
    'run.services.listTagBindings',
    'run.services.setIamPolicy',
    'run.services.update',
    'run.tasks.get',
    'run.tasks.list',
    'cloudscheduler.jobs.create',
    'cloudscheduler.jobs.fullView',
    'cloudscheduler.jobs.get',
    'cloudscheduler.jobs.list',
    'cloudscheduler.jobs.pause',
    'cloudscheduler.jobs.update',
    'cloudscheduler.locations.get',
    'cloudscheduler.locations.list'
)

$forbiddenTerraformPermissions = @(
    'secretmanager.versions.access',
    'run.jobs.run',
    'run.jobs.runWithOverrides',
    'run.routes.invoke',
    'cloudscheduler.jobs.run',
    'cloudscheduler.jobs.enable',
    'run.jobs.delete',
    'run.services.delete',
    'cloudscheduler.jobs.delete',
    'secretmanager.secrets.delete',
    'secretmanager.versions.destroy',
    'storage.buckets.delete'
)
foreach ($permission in $forbiddenTerraformPermissions) {
    if ($permission -in $terraformPermissions) { throw "Forbidden Phase 3 permission $permission entered the Terraform role." }
}

$deployerExists = Test-GcloudResource @('iam', 'service-accounts', 'describe', $deployerEmail, '--project', $projectId)
$builderExists = Test-GcloudResource @('iam', 'service-accounts', 'describe', $builderEmail, '--project', $projectId)
$roleExists = Test-GcloudResource @('iam', 'roles', 'describe', $TerraformRoleId, '--project', $projectId)
$enabledServices = @(& $gcloud services list --enabled --project $projectId --format='value(config.name)')
if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect enabled Google Cloud services.' }
$computeEnabled = 'compute.googleapis.com' -in $enabledServices
$serviceNetworkingEnabled = 'servicenetworking.googleapis.com' -in $enabledServices

Write-Output "Phase 3 execution identity preflight: account=$account project_id=$projectId project_number=$ProjectNumber region=$Region"
Write-Output "Phase 3 execution identity preflight: deployer=$deployerEmail exists=$deployerExists builder=$builderEmail exists=$builderExists"
Write-Output "Phase 3 execution identity preflight: terraform_role=$terraformRoleName exists=$roleExists"
Write-Output "Phase 3 execution identity preflight: compute_api_enabled=$computeEnabled service_networking_api_enabled=$serviceNetworkingEnabled"
Write-Output "Phase 3 execution identity preflight: provider=$providerResource principal_set=$principalSet"
Write-Output 'Phase 3 execution identity preflight: deployer custom role excludes job execution, scheduler enabling/running, secret payload access, and destructive resource permissions.'

if (-not $Apply) {
    Write-Output 'Preflight only. No service account, IAM binding, custom role, or API state was changed. Re-run with -Apply to establish the Phase 3 execution identities.'
    exit 0
}

$servicesToEnable = @()
if (-not $computeEnabled) { $servicesToEnable += 'compute.googleapis.com' }
if (-not $serviceNetworkingEnabled) { $servicesToEnable += 'servicenetworking.googleapis.com' }
if ($servicesToEnable.Count -gt 0) {
    Invoke-Checked $gcloud (@('services', 'enable') + $servicesToEnable + @('--project', $projectId, '--quiet'))
}

$deployerEmail = Ensure-ServiceAccount $projectId $DeployerServiceAccountId 'PolitiTrack Phase 3 deployer' 'Keyless Terraform reconciliation identity. Phase 3 workflows do not grant it Runtime v2 job-execution or secret-payload permissions.'
$builderEmail = Ensure-ServiceAccount $projectId $BuilderServiceAccountId 'PolitiTrack Phase 3 builder' 'Keyless immutable-image build identity. Separate from Terraform reconciliation and Runtime v2 identities.'

$permissionsArgument = $terraformPermissions -join ','
if (-not $roleExists) {
    Invoke-Checked $gcloud @(
        'iam', 'roles', 'create', $TerraformRoleId,
        '--project', $projectId,
        '--title', 'PolitiTrack Phase 3 Terraform',
        '--description', 'Constrained Phase 3 Terraform control plane: no Runtime v2 execution, scheduler activation, secret payload access, or destructive resource permissions.',
        '--permissions', $permissionsArgument,
        '--stage', 'GA',
        '--quiet'
    )
}
else {
    $existingRole = (& $gcloud iam roles describe $TerraformRoleId --project $projectId --format json) | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or -not $existingRole) { throw 'Existing Phase 3 Terraform custom role could not be verified.' }
    $actualPermissions = @($existingRole.includedPermissions | Sort-Object)
    $expectedPermissions = @($terraformPermissions | Sort-Object)
    if (Compare-Object $actualPermissions $expectedPermissions) {
        Invoke-Checked $gcloud @(
            'iam', 'roles', 'update', $TerraformRoleId,
            '--project', $projectId,
            '--permissions', $permissionsArgument,
            '--stage', 'GA',
            '--quiet'
        )
    }
}

Invoke-Checked $gcloud @(
    'iam', 'service-accounts', 'add-iam-policy-binding', $deployerEmail,
    '--project', $projectId,
    '--member', $principalSet,
    '--role', 'roles/iam.workloadIdentityUser',
    '--condition', 'None',
    '--quiet',
    '--format=none'
)
Invoke-Checked $gcloud @(
    'iam', 'service-accounts', 'add-iam-policy-binding', $builderEmail,
    '--project', $projectId,
    '--member', $principalSet,
    '--role', 'roles/iam.workloadIdentityUser',
    '--condition', 'None',
    '--quiet',
    '--format=none'
)

foreach ($role in @(
    $terraformRoleName,
    'roles/compute.networkAdmin',
    'roles/servicenetworking.networksAdmin',
    'roles/cloudsql.admin',
    'roles/iam.serviceAccountAdmin',
    'roles/iam.serviceAccountUser',
    'roles/resourcemanager.projectIamAdmin'
)) {
    Ensure-ProjectBinding $projectId "serviceAccount:$deployerEmail" $role
}

Ensure-ProjectBinding $projectId "serviceAccount:$builderEmail" 'roles/cloudbuild.builds.editor'
Ensure-ProjectBinding $projectId "serviceAccount:$builderEmail" 'roles/serviceusage.serviceUsageConsumer'
Ensure-ProjectBinding $projectId "serviceAccount:$builderEmail" 'roles/serviceusage.serviceUsageViewer'

Invoke-Checked $gcloud @(
    'storage', 'buckets', 'add-iam-policy-binding', "gs://$stateBucket",
    '--member', "serviceAccount:$deployerEmail",
    '--role', 'roles/storage.objectAdmin',
    '--quiet',
    '--format=none'
)
Invoke-Checked $gcloud @(
    'storage', 'buckets', 'add-iam-policy-binding', "gs://$cloudBuildBucket",
    '--member', "serviceAccount:$builderEmail",
    '--role', 'roles/storage.objectAdmin',
    '--quiet',
    '--format=none'
)
Invoke-Checked $gcloud @(
    'artifacts', 'repositories', 'add-iam-policy-binding', $artifactRepository,
    '--location', $Region,
    '--project', $projectId,
    '--member', "serviceAccount:$deployerEmail",
    '--role', 'roles/artifactregistry.reader',
    '--quiet',
    '--format=none'
)
Invoke-Checked $gcloud @(
    'artifacts', 'repositories', 'add-iam-policy-binding', $artifactRepository,
    '--location', $Region,
    '--project', $projectId,
    '--member', "serviceAccount:$builderEmail",
    '--role', 'roles/artifactregistry.reader',
    '--quiet',
    '--format=none'
)

Write-Output 'Phase 3 execution identities established.'
Write-Output "project_id=$projectId"
Write-Output "project_number=$ProjectNumber"
Write-Output "deployer_service_account=$deployerEmail"
Write-Output "builder_service_account=$builderEmail"
Write-Output "terraform_role=$terraformRoleName"
Write-Output "workload_identity_provider=$providerResource"
Write-Output 'compute_api_enabled=true'
Write-Output 'service_networking_api_enabled=true'
Write-Output 'deployer_runtime_execution=false'
Write-Output 'deployer_scheduler_enable_or_run=false'
Write-Output 'deployer_secret_payload_access=false'
Write-Output 'builder_terraform_authority=false'
Write-Output 'No service-account key or long-lived Google credential was created.'
