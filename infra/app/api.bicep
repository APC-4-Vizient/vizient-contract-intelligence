// Flex Consumption Function app with a user-assigned identity and identity-based storage.
// Adapted from Azure-Samples/functions-quickstart-python-http-azd v1.0.1 (MIT, see ../LICENSE-functions-quickstart.txt).
// Differences: user-assigned identity only, no VNet integration, Blob-only storage settings, maximumInstanceCount 10.

param name string

@description('Primary location for all resources and the Flex Consumption Function app.')
param location string = resourceGroup().location

param tags object = {}
param applicationInsightsName string
param appServicePlanId string

@description('Extra app settings. The required storage and Application Insights settings always win on a name clash.')
param appSettings object = {}

param runtimeName string
param runtimeVersion string

@description('Must match the service name in azure.yaml: azd finds the deploy target by the azd-service-name tag.')
param serviceName string = 'api'

param storageAccountName string
param deploymentStorageContainerName string
param instanceMemoryMB int = 2048
param maximumInstanceCount int = 10

@description('Resource id of the user-assigned identity the app runs as.')
param identityId string

@description('Client id of the same identity.')
param identityClientId string

@description('Resource id of the subnet for the app\'s regional VNet integration. Empty for no VNet integration.')
param virtualNetworkSubnetId string = ''

resource stg 'Microsoft.Storage/storageAccounts@2022-09-01' existing = {
  name: storageAccountName
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: applicationInsightsName
}

var baseAppSettings = {
  AzureWebJobsStorage__credential: 'managedidentity'
  AzureWebJobsStorage__clientId: identityClientId
  AzureWebJobsStorage__blobServiceUri: stg.properties.primaryEndpoints.blob
  APPLICATIONINSIGHTS_AUTHENTICATION_STRING: 'ClientId=${identityClientId};Authorization=AAD'
  APPLICATIONINSIGHTS_CONNECTION_STRING: applicationInsights.properties.ConnectionString
}

module api 'br/public:avm/res/web/site:0.15.1' = {
  name: '${serviceName}-flex-consumption'
  params: {
    kind: 'functionapp,linux'
    name: name
    location: location
    tags: union(tags, { 'azd-service-name': serviceName })
    serverFarmResourceId: appServicePlanId
    // Flex Consumption does not use session affinity; the AVM default of true only showed up as a permanent what-if difference.
    clientAffinityEnabled: false
    virtualNetworkSubnetId: empty(virtualNetworkSubnetId) ? null : virtualNetworkSubnetId
    managedIdentities: {
      systemAssigned: false
      userAssignedResourceIds: [
        identityId
      ]
    }
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${stg.properties.primaryEndpoints.blob}${deploymentStorageContainerName}'
          authentication: {
            type: 'UserAssignedIdentity'
            userAssignedIdentityResourceId: identityId
          }
        }
      }
      scaleAndConcurrency: {
        instanceMemoryMB: instanceMemoryMB
        maximumInstanceCount: maximumInstanceCount
      }
      runtime: {
        name: runtimeName
        version: runtimeVersion
      }
    }
    siteConfig: {
      alwaysOn: false
    }
    appSettingsKeyValuePairs: union(appSettings, baseAppSettings)
  }
}

output SERVICE_API_NAME string = api.outputs.name
output SERVICE_API_URI string = 'https://${api.outputs.defaultHostname}'
