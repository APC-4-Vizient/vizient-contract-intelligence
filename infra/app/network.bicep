// Private networking for the Function app's storage account. Deployed by main.bicep only when
// enablePrivateNetworking is true.
//
// A virtual network with one subnet for the Function app's regional VNet integration (delegated to
// Microsoft.App/environments, which Flex Consumption uses) and one for the storage private endpoint, a network
// security group on each subnet, and a blob private endpoint with its private DNS zone. The app has HTTP triggers
// and uses blob storage only, so no queue or table endpoint is created.
//
// Names, tags and properties match the environment this was reproduced from, so a what-if against it reports no change
// except server-populated metadata on the DNS zone group.

param location string
param tags object = {}

@description('Name of the virtual network.')
param vnetName string

@description('Address space of the virtual network.')
param addressPrefix string

@description('Subnet for the Function app VNet integration.')
param functionSubnetPrefix string

@description('Subnet for the storage private endpoint.')
param privateEndpointSubnetPrefix string

@description('Resource id of the storage account that gets the private endpoint.')
param storageAccountId string

@description('Name of the storage account. Names the private endpoint.')
param storageAccountName string

var functionSubnetName = 'snet-func'
var privateEndpointSubnetName = 'snet-private-endpoints'
var blobDnsZoneName = 'privatelink.blob.${environment().suffixes.storage}'

// The network security groups have no custom rules. They are declared here because tenant policy commonly requires one
// on every subnet and would otherwise create and attach its own.
resource functionNsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: '${vnetName}-${functionSubnetName}-nsg-${location}'
  location: location
  tags: tags
  properties: {
    securityRules: []
  }
}

resource privateEndpointNsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: '${vnetName}-${privateEndpointSubnetName}-nsg-${location}'
  location: location
  tags: tags
  properties: {
    securityRules: []
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        addressPrefix
      ]
    }
    privateEndpointVNetPolicies: 'Disabled'
    subnets: [
      {
        name: functionSubnetName
        properties: {
          addressPrefix: functionSubnetPrefix
          networkSecurityGroup: {
            id: functionNsg.id
          }
          delegations: [
            {
              name: 'Microsoft.App/environments'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
      {
        name: privateEndpointSubnetName
        properties: {
          addressPrefix: privateEndpointSubnetPrefix
          networkSecurityGroup: {
            id: privateEndpointNsg.id
          }
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

resource blobDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: blobDnsZoneName
  location: 'global'
  tags: tags
}

resource blobDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: blobDnsZone
  name: '${vnetName}-blob-link'
  location: 'global'
  tags: tags
  properties: {
    registrationEnabled: false
    resolutionPolicy: 'Default'
    virtualNetwork: {
      id: vnet.id
    }
  }
}

resource blobPrivateEndpoint 'Microsoft.Network/privateEndpoints@2025-05-01' = {
  name: 'pe-${storageAccountName}-blob'
  location: location
  tags: tags
  properties: {
    ipVersionType: 'IPv4'
    subnet: {
      id: '${vnet.id}/subnets/${privateEndpointSubnetName}'
    }
    privateLinkServiceConnections: [
      {
        name: 'blob'
        properties: {
          privateLinkServiceId: storageAccountId
          groupIds: [
            'blob'
          ]
        }
      }
    ]
  }
}

// The zone group registers the endpoint's address in the private DNS zone and keeps it current.
resource blobDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2025-05-01' = {
  parent: blobPrivateEndpoint
  name: 'blob'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'blob'
        properties: {
          privateDnsZoneId: blobDnsZone.id
        }
      }
    ]
  }
}

output functionSubnetId string = '${vnet.id}/subnets/${functionSubnetName}'
output vnetName string = vnet.name
