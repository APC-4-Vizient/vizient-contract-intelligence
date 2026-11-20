// Vizient Contract Intelligence POC infrastructure (azd, Bicep, subscription scope).
// Function app, storage and role assignment structure adapted from
// Azure-Samples/functions-quickstart-python-http-azd v1.0.1 (MIT, see LICENSE-functions-quickstart.txt).

targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('azd environment name. Drives the resource group name (rg-<name>) and the unique resource token.')
param environmentName string

@minLength(1)
@description('Primary location. East US 2 is the only region this template has been deployed and verified in. Another region needs Flex Consumption, Content Understanding (GA API 2025-11-01) and every model and SKU in modelDeployments and qa.bicep, so run azd provision --preview and the checks in docs/deployment-runbook.md first.')
@metadata({
  azd: {
    type: 'location'
  }
})
param location string

@description('Object id of the signed-in deployer (azd sets AZURE_PRINCIPAL_ID). Receives the Content Understanding Contributor role so admin scripts can set defaults and create analyzers. Leave empty to skip.')
param principalId string = ''

@description('Region for the Azure AI Search service. Empty uses the primary location. Search capacity is regional and can be unavailable in the primary region, so set this to a region that has it. A Search service cannot be moved, so changing it later means a new service.')
param searchLocation string = ''

@description('Name of a governance exemption tag to put on the Function app storage account and on nothing else. Leave empty unless a policy in your tenant forces public network access off on storage accounts, which breaks a Flex Consumption app that is not on a virtual network. Use the tag your governance team prescribes, and obtain their approval first. An exemption can be withdrawn later; private networking is the durable alternative (docs/deployment-runbook.md, Appendix E).')
param storageExemptionTagName string = ''

@description('Value of the exemption tag. Ignored when storageExemptionTagName is empty.')
param storageExemptionTagValue string = ''

@description('Set to true to put the Function app on a virtual network and the storage account behind a private endpoint, with public network access off. Choose this when a policy in your tenant forces public network access off on storage accounts, or when your standards require private storage. Needs the Microsoft.Network and Microsoft.App resource providers. Only the lowercase values true and false are accepted, so a typo fails the deployment instead of silently choosing public access. A string because azd passes environment values as text.')
@allowed([
  'true'
  'false'
])
param enablePrivateNetworking string = 'false'

@description('Address space of the virtual network. Used only when enablePrivateNetworking is true. Pick one that does not overlap networks you may connect it to.')
param vnetAddressPrefix string = '10.20.0.0/24'

@description('Subnet for the Function app VNet integration (delegated to Microsoft.App/environments). Inside vnetAddressPrefix.')
param functionSubnetPrefix string = '10.20.0.0/27'

@description('Subnet for the storage private endpoint. Inside vnetAddressPrefix.')
param privateEndpointSubnetPrefix string = '10.20.0.32/28'

@description('Set to true to let the Function index documents that are not marked as synthetic samples for contract Q&A. With false, Q&A indexing is restricted to synthetic samples. It does not gate checklist extraction: any PDF that reaches the analysis flow is processed either way. Real contract text is then stored in Azure AI Search as well as Dataverse, so settle retention, legal and security review first. Only the lowercase values true and false are accepted, so a typo fails the deployment. A string because azd passes environment values as text.')
@allowed([
  'true'
  'false'
])
param allowRealContracts string = 'false'

@description('Python runtime version for the Function app.')
param pythonVersion string = '3.12'

@description('Maximum Flex Consumption instances. Each instance is 2,048 MB, so this also caps the cores used against the regional Flex quota.')
@minValue(1)
@maxValue(100)
param maximumInstanceCount int = 10

@description('One model deployment on the Foundry account. capacity is thousands of tokens per minute (GlobalStandard).')
type modelDeploymentType = {
  name: string
  model: string
  version: string
  capacity: int
}

@description('Model deployments. Each name equals its model name so Content Understanding defaults map one to one. All are GlobalStandard (pay per token); a provisioned-throughput (PTU) SKU is not used.')
param modelDeployments modelDeploymentType[] = [
  {
    name: 'gpt-5.5'
    model: 'gpt-5.5'
    version: '2026-04-24'
    capacity: 250
  }
  {
    name: 'gpt-5.4'
    model: 'gpt-5.4'
    version: '2026-03-05'
    capacity: 100
  }
  {
    name: 'text-embedding-3-large'
    model: 'text-embedding-3-large'
    version: '1'
    capacity: 50
  }
]

var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = {
  'azd-env-name': environmentName
  project: 'vizient-contract-intelligence'
}
var storageTags = empty(storageExemptionTagName)
  ? tags
  : union(tags, { '${storageExemptionTagName}': storageExemptionTagValue })
var realContractsAllowed = allowRealContracts == 'true'
var privateNetworking = enablePrivateNetworking == 'true'
var functionAppName = 'func-api-${resourceToken}'
var foundryName = 'aif-vz-${resourceToken}'
var deploymentStorageContainerName = 'app-package-${take(functionAppName, 32)}-${take(toLower(uniqueString(functionAppName, resourceToken)), 7)}'

var cuReaderRoleId = '379c52cb-64de-498c-8b5b-c6170d6c49d4' // Cognitive Services Content Understanding Reader
var cuContributorRoleId = '59a2dba3-6303-4fd8-9a2e-8cbb4bdda972' // Cognitive Services Content Understanding Contributor

resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

// The Function app runs as this identity. Role assignments below grant it only what it needs.
module apiUserAssignedIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.1' = {
  name: 'apiUserAssignedIdentity'
  scope: rg
  params: {
    name: 'id-api-${resourceToken}'
    location: location
    tags: tags
  }
}

module appServicePlan 'br/public:avm/res/web/serverfarm:0.1.1' = {
  name: 'appserviceplan'
  scope: rg
  params: {
    name: 'plan-${resourceToken}'
    sku: {
      name: 'FC1'
      tier: 'FlexConsumption'
    }
    reserved: true
    location: location
    tags: tags
  }
}

// Function app storage (code package and host state only, never contract content). Shared-key and anonymous
// blob access are set off explicitly. A tenant policy that flips publicNetworkAccess to Disabled on storage
// accounts breaks a Flex app that is not on a VNet. There are two ways out: enablePrivateNetworking (the durable one:
// the app goes on a VNet and the account gets a private endpoint, with public access off), or
// storageExemptionTagName/Value, which tags only this account and lasts only as long as the tag does. An exemption tag
// can also switch off the policies that force shared-key and anonymous access off, which is why those properties are
// explicit here rather than left to policy.
module storage 'br/public:avm/res/storage/storage-account:0.8.3' = {
  name: 'storage'
  scope: rg
  params: {
    name: 'st${resourceToken}'
    location: location
    tags: storageTags
    kind: 'StorageV2'
    skuName: 'Standard_LRS'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    allowCrossTenantReplication: false
    defaultToOAuthAuthentication: true
    dnsEndpointType: 'Standard'
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: privateNetworking ? 'Disabled' : 'Enabled'
    networkAcls: privateNetworking
      ? {
          defaultAction: 'Deny'
          bypass: 'None'
        }
      : {
          defaultAction: 'Allow'
          bypass: 'AzureServices'
        }
    blobServices: {
      containers: [
        {
          name: deploymentStorageContainerName
        }
      ]
    }
  }
}

// Optional private networking. The Function app joins this VNet and reaches storage through the private endpoint.
module network './app/network.bicep' = if (privateNetworking) {
  name: 'network'
  scope: rg
  params: {
    location: location
    tags: tags
    vnetName: 'vnet-${resourceToken}'
    addressPrefix: vnetAddressPrefix
    functionSubnetPrefix: functionSubnetPrefix
    privateEndpointSubnetPrefix: privateEndpointSubnetPrefix
    storageAccountId: storage.outputs.resourceId
    storageAccountName: storage.outputs.name
  }
}

module logAnalytics 'br/public:avm/res/operational-insights/workspace:0.7.0' = {
  name: '${uniqueString(deployment().name, location)}-loganalytics'
  scope: rg
  params: {
    name: 'log-${resourceToken}'
    location: location
    tags: tags
    dataRetention: 30
  }
}

module monitoring 'br/public:avm/res/insights/component:0.4.1' = {
  name: '${uniqueString(deployment().name, location)}-appinsights'
  scope: rg
  params: {
    name: 'appi-${resourceToken}'
    location: location
    tags: tags
    workspaceResourceId: logAnalytics.outputs.resourceId
    disableLocalAuth: true
  }
}

var functionIdentityFoundryRole = {
  principalId: apiUserAssignedIdentity.outputs.principalId
  principalType: 'ServicePrincipal'
  roleDefinitionIdOrName: cuReaderRoleId
  description: 'Function app: analyze documents and read results'
}
var deployerFoundryRole = {
  principalId: principalId
  principalType: 'User'
  roleDefinitionIdOrName: cuContributorRoleId
  description: 'Deployer: set Content Understanding defaults and manage analyzers'
}

// Microsoft Foundry resource that hosts Content Understanding and the model deployments.
// No API keys: local auth is off and every caller uses Entra tokens.
// publicNetworkAccess is explicit because the AVM module otherwise defaults it to Disabled.
module foundry 'br/public:avm/res/cognitive-services/account:0.19.1' = {
  name: 'foundry'
  scope: rg
  params: {
    name: foundryName
    location: location
    tags: tags
    kind: 'AIServices'
    sku: 'S0'
    customSubDomainName: foundryName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
    restrictOutboundNetworkAccess: false
    deployments: [
      for modelDeployment in modelDeployments: {
        name: modelDeployment.name
        model: {
          format: 'OpenAI'
          name: modelDeployment.model
          version: modelDeployment.version
        }
        sku: {
          name: 'GlobalStandard'
          capacity: modelDeployment.capacity
        }
        versionUpgradeOption: 'NoAutoUpgrade'
      }
    ]
    roleAssignments: empty(principalId)
      ? [functionIdentityFoundryRole]
      : [functionIdentityFoundryRole, deployerFoundryRole]
  }
}

module api './app/api.bicep' = {
  name: 'api'
  scope: rg
  params: {
    name: functionAppName
    location: location
    tags: tags
    applicationInsightsName: monitoring.outputs.name
    appServicePlanId: appServicePlan.outputs.resourceId
    runtimeName: 'python'
    runtimeVersion: pythonVersion
    storageAccountName: storage.outputs.name
    deploymentStorageContainerName: deploymentStorageContainerName
    maximumInstanceCount: maximumInstanceCount
    identityId: apiUserAssignedIdentity.outputs.resourceId
    identityClientId: apiUserAssignedIdentity.outputs.clientId
    virtualNetworkSubnetId: privateNetworking ? network!.outputs.functionSubnetId : ''
    appSettings: {
      AZURE_CLIENT_ID: apiUserAssignedIdentity.outputs.clientId
      CU_ENDPOINT: foundry.outputs.endpoint
      CU_ANALYZER_ID: 'vizientContractChecklist'
      CU_API_VERSION: '2025-11-01'
      FOUNDRY_PROJECT_ENDPOINT: 'https://aif-qa-${uniqueString(rg.id)}.services.ai.azure.com/api/projects/contract-questions'
      FOUNDRY_QA_AGENT: 'contract-questions'
      FOUNDRY_QA_MODEL: 'gpt-4.1-mini'
      AZURE_SEARCH_ENDPOINT: 'https://srch-contract-${uniqueString(rg.id)}.search.windows.net'
      AZURE_SEARCH_INDEX: 'contract-chunks'
      EMBEDDING_ENDPOINT: 'https://aif-qa-${uniqueString(rg.id)}.openai.azure.com'
      EMBEDDING_MODEL: 'text-embedding-3-small'
      ALLOW_REAL_CONTRACTS: realContractsAllowed ? 'true' : 'false'
    }
  }
}

module contractQuestions './qa.bicep' = if (!empty(principalId)) {
  name: 'contract-questions'
  scope: rg
  dependsOn: [api]
  params: {
    location: location
    functionPrincipalId: apiUserAssignedIdentity.outputs.principalId
    deployerPrincipalId: principalId
    searchLocation: empty(searchLocation) ? location : searchLocation
  }
}

module rbac './app/rbac.bicep' = {
  name: 'rbacAssignments'
  scope: rg
  params: {
    storageAccountName: storage.outputs.name
    appInsightsName: monitoring.outputs.name
    managedIdentityPrincipalId: apiUserAssignedIdentity.outputs.principalId
  }
}

output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = rg.name
output SERVICE_API_NAME string = api.outputs.SERVICE_API_NAME
output SERVICE_API_URI string = api.outputs.SERVICE_API_URI
output AZURE_FUNCTION_NAME string = api.outputs.SERVICE_API_NAME
output CU_ENDPOINT string = foundry.outputs.endpoint
output CU_FOUNDRY_NAME string = foundry.outputs.name
