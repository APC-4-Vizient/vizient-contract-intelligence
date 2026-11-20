targetScope = 'resourceGroup'

param location string = resourceGroup().location

@description('Region for the Azure AI Search service. Defaults to the deployment location; set it when that region has no Search capacity.')
param searchLocation string = location
param functionPrincipalId string
param deployerPrincipalId string

var name = 'aif-qa-${uniqueString(resourceGroup().id)}'
var projectName = 'contract-questions'
var aiUserRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
var openaiUserRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
var searchDataRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
var searchServiceRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7ca78c08-252a-4471-8644-bb5ff32d4ba0')

resource search 'Microsoft.Search/searchServices@2025-05-01' = {
  name: 'srch-contract-${uniqueString(resourceGroup().id)}'
  location: searchLocation
  sku: { name: 'basic' }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    disableLocalAuth: true
    publicNetworkAccess: 'enabled'
  }
}

resource searchDataAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principal in [
  { id: functionPrincipalId, type: 'ServicePrincipal' }
  { id: deployerPrincipalId, type: 'User' }
]: {
  name: guid(search.id, principal.id, searchDataRole)
  scope: search
  properties: {
    principalId: principal.id
    principalType: principal.type
    roleDefinitionId: searchDataRole
  }
}]

resource searchSchemaAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, deployerPrincipalId, searchServiceRole)
  scope: search
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: searchServiceRole
  }
}

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: name
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: name
    allowProjectManagement: true
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource model 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: account
  dependsOn: [project]
  name: 'gpt-4.1-mini'
  sku: { name: 'GlobalStandard', capacity: 30 }
  properties: {
    model: { format: 'OpenAI', name: 'gpt-4.1-mini', version: '2025-04-14' }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

resource embedding 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: account
  dependsOn: [model]
  name: 'text-embedding-3-small'
  sku: { name: 'GlobalStandard', capacity: 30 }
  properties: {
    model: { format: 'OpenAI', name: 'text-embedding-3-small', version: '1' }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

resource embeddingAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principal in [
  { id: functionPrincipalId, type: 'ServicePrincipal' }
  { id: deployerPrincipalId, type: 'User' }
]: {
  name: guid(account.id, principal.id, openaiUserRole)
  scope: account
  properties: {
    principalId: principal.id
    principalType: principal.type
    roleDefinitionId: openaiUserRole
  }
}]
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: projectName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    displayName: 'Contract questions'
    description: 'Record-scoped contract Q&A, separate from checklist extraction.'
  }
}

resource functionAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, functionPrincipalId, aiUserRole)
  scope: account
  properties: {
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: aiUserRole
  }
}

resource deployerAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, deployerPrincipalId, aiUserRole)
  scope: account
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: aiUserRole
  }
}

output projectEndpoint string = 'https://${name}.services.ai.azure.com/api/projects/${projectName}'
output searchEndpoint string = 'https://${search.name}.search.windows.net'
output embeddingEndpoint string = 'https://${name}.openai.azure.com'
