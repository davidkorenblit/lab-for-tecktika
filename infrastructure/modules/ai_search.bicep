@description('Base name used to derive the search service name.')
param baseName string

@description('Azure region for the search service.')
param location string = resourceGroup().location

@description('Tags applied to the search service.')
param tags object = {}

@description('Pricing tier. Basic is the minimum tier that supports the Integrated Vectorization indexer/skillset pipeline used by this project at a predictable low cost.')
@allowed([
  'free'
  'basic'
  'standard'
])
param skuName string = 'basic'

@description('Number of replicas. 1 is sufficient for the dev/demo workload; raise for HA + query throughput at scale.')
param replicaCount int = 1

@description('Number of partitions. 1 is sufficient for the dev/demo workload; raise to shard the index at scale.')
param partitionCount int = 1

resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: 'srch-${baseName}'
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    replicaCount: replicaCount
    partitionCount: partitionCount
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
    disableLocalAuth: false
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
    // Semantic ranking is not available on the Free tier.
    semanticSearch: skuName == 'free' ? 'disabled' : 'free'
  }
}

output searchServiceName string = searchService.name
output searchServiceId string = searchService.id
output searchServicePrincipalId string = searchService.identity.principalId
output searchEndpoint string = 'https://${searchService.name}.search.windows.net'
