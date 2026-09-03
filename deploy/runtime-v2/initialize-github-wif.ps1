[CmdletBinding()]
param(
    [string]$ProjectNumber = '497412818801',
    [string]$PoolId = 'polititrack-github',
    [string]$ProviderId = 'phase3-main',
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

$gcloud = Resolve-RequiredCommand 'gcloud'
$git = Resolve-RequiredCommand 'git'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$remote = (& $git -C $repositoryRoot remote get-url origin).Trim()
if ($LASTEXITCODE -ne 0 -or $remote -notmatch 'maglothinm/MyETF-Intelligence(?:\.git)?$') {
    throw 'Refusing WIF bootstrap from a noncanonical repository remote.'
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
$attributeMapping = 'google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.repository_owner_id=assertion.repository_owner_id,attribute.ref=assertion.ref'
$attributeCondition = "assertion.repository_id == '$ExpectedRepositoryId' && assertion.repository_owner_id == '$ExpectedRepositoryOwnerId' && assertion.ref == '$ExpectedRef'"

$poolExists = Test-GcloudResource @('iam','workload-identity-pools','describe',$PoolId,'--project',$projectId,'--location','global')
$providerExists = $false
if ($poolExists) {
    $providerExists = Test-GcloudResource @('iam','workload-identity-pools','providers','describe',$ProviderId,'--project',$projectId,'--location','global','--workload-identity-pool',$PoolId)
}

Write-Output "Phase 3 WIF preflight: account=$account"
Write-Output "Phase 3 WIF preflight: project_id=$projectId project_number=$ProjectNumber"
Write-Output "Phase 3 WIF preflight: pool=$PoolId exists=$poolExists provider=$ProviderId exists=$providerExists"
Write-Output "Phase 3 WIF preflight: repository_id=$ExpectedRepositoryId repository_owner_id=$ExpectedRepositoryOwnerId ref=$ExpectedRef"
Write-Output 'Phase 3 WIF preflight: direct federation; no service account or service-account key is required.'
if (-not $Apply) {
    Write-Output 'Preflight only. No Google Cloud resource or IAM policy was changed. Re-run with -Apply to create the narrowly scoped GitHub trust.'
    exit 0
}

$requiredServices = @('iam.googleapis.com','sts.googleapis.com','cloudresourcemanager.googleapis.com','serviceusage.googleapis.com')
$enabledServices = @(& $gcloud services list --enabled --project $projectId --format='value(config.name)')
if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect enabled Google Cloud services.' }
$missingServices = @($requiredServices | Where-Object { $_ -notin $enabledServices })
if ($missingServices.Count -gt 0) {
    Invoke-Checked $gcloud (@('services','enable') + $missingServices + @('--project',$projectId,'--quiet'))
}
if (-not $poolExists) {
    Invoke-Checked $gcloud @('iam','workload-identity-pools','create',$PoolId,'--project',$projectId,'--location','global','--display-name','PolitiTrack GitHub Actions','--description','Keyless GitHub Actions trust for PolitiTrack Phase 3 and later explicitly gated runtime operations.')
}
if (-not $providerExists) {
    Invoke-Checked $gcloud @('iam','workload-identity-pools','providers','create-oidc',$ProviderId,'--project',$projectId,'--location','global','--workload-identity-pool',$PoolId,'--display-name','PolitiTrack Phase 3 main','--issuer-uri',$ExpectedIssuer,'--attribute-mapping',$attributeMapping,'--attribute-condition',$attributeCondition)
}
$provider = (& $gcloud iam workload-identity-pools providers describe $ProviderId --project $projectId --location global --workload-identity-pool $PoolId --format json) | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or -not $provider) { throw 'Unable to verify the Workload Identity Provider after creation.' }
if ($provider.name -ne $providerResource) { throw 'Workload Identity Provider resolved to an unexpected immutable resource name.' }
if ($provider.oidc.issuerUri -ne $ExpectedIssuer) { throw 'Existing Workload Identity Provider has an unexpected issuer URI; refusing to reuse it.' }
if ([string]$provider.attributeCondition -ne $attributeCondition) { throw 'Existing Workload Identity Provider has an unexpected attribute condition; refusing to reuse it.' }
$requiredMappings = [ordered]@{'google.subject'='assertion.sub';'attribute.repository_id'='assertion.repository_id';'attribute.repository_owner_id'='assertion.repository_owner_id';'attribute.ref'='assertion.ref'}
foreach ($mapping in $requiredMappings.GetEnumerator()) {
    $actual = $provider.attributeMapping.PSObject.Properties[$mapping.Key]
    if (-not $actual -or [string]$actual.Value -ne $mapping.Value) { throw "Existing Workload Identity Provider has an unexpected or missing mapping $($mapping.Key)." }
}
$readOnlyRoles = @('roles/serviceusage.serviceUsageViewer','roles/artifactregistry.viewer','roles/storage.bucketViewer','roles/cloudsql.viewer','roles/compute.networkViewer','roles/iam.securityReviewer','roles/iam.workloadIdentityPoolViewer','roles/secretmanager.viewer','roles/run.viewer','roles/cloudscheduler.viewer')
foreach ($role in $readOnlyRoles) {
    Invoke-Checked $gcloud @('projects','add-iam-policy-binding',$projectId,'--member',$principalSet,'--role',$role,'--condition','None','--quiet')
}
Write-Output 'Phase 3 direct GitHub Workload Identity Federation bootstrap complete.'
Write-Output "project_id=$projectId"
Write-Output "project_number=$ProjectNumber"
Write-Output "workload_identity_provider=$providerResource"
Write-Output "principal_set=$principalSet"
Write-Output "read_only_roles=$($readOnlyRoles -join ',')"
Write-Output 'No service account, service-account key, secret value, or long-lived GitHub credential was created, read, or exported.'
