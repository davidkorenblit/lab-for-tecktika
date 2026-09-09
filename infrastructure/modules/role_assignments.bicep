@description('Name of the storage account backing blob/queue/table.')
param storageAccountName string

@description('Name of the Azure OpenAI account.')
param openAiAccountName string

@description('Name of the Azure AI Search service.')
param searchServiceName string

@description('Name of the Document Intelligence (multi-service Cognitive Services) account.')
param documentIntelligenceAccountName string

@description('Principal ID of the backend Container App system-assigned identity.')
param backendPrincipalId string

@description('Principal ID of the worker Function App system-assigned identity.')
param workerPrincipalId string

@description('Principal ID of the Azure AI Search service system-assigned identity.')
param searchServicePrincipalId string

var roleIds = {
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  storageBlobDataReader: '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
  storageQueueDataContributor: '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
  storageTableDataContributor: '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
  cognitiveServicesOpenAiUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  cognitiveServicesUser: 'a97b65f3-24c7-4388-baec-2e87135dc908'
  searchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}

resource openAiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: openAiAccountName
}

resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' existing = {
  name: searchServiceName
}

resource documentIntelligenceAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: documentIntelligenceAccountName
}

// --- Backend (Container App): reads/writes documents, enqueues jobs, tracks status, queries the index, calls the chat model. ---

resource backendBlob 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, backendPrincipalId, roleIds.storageBlobDataContributor)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.storageBlobDataContributor)
    principalId: backendPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource backendQueue 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, backendPrincipalId, roleIds.storageQueueDataContributor)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.storageQueueDataContributor)
    principalId: backendPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource backendTable 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, backendPrincipalId, roleIds.storageTableDataContributor)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.storageTableDataContributor)
    principalId: backendPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource backendSearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, backendPrincipalId, roleIds.searchIndexDataContributor)
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.searchIndexDataContributor)
    principalId: backendPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource backendOpenAi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAiAccount.id, backendPrincipalId, roleIds.cognitiveServicesOpenAiUser)
  scope: openAiAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.cognitiveServicesOpenAiUser)
    principalId: backendPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// --- Worker (Function App): reads/writes documents, consumes the queue, tracks status, triggers indexer runs and surgical deletes. ---

resource workerBlob 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, workerPrincipalId, roleIds.storageBlobDataContributor)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.storageBlobDataContributor)
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource workerQueue 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, workerPrincipalId, roleIds.storageQueueDataContributor)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.storageQueueDataContributor)
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource workerTable 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, workerPrincipalId, roleIds.storageTableDataContributor)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.storageTableDataContributor)
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource workerSearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, workerPrincipalId, roleIds.searchIndexDataContributor)
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.searchIndexDataContributor)
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Search Index Data Contributor above only covers documents in an index, which
// is enough for the worker's surgical chunk deletion. Running the indexer is a
// different permission: services/search_service.py calls run_indexer() and
// get_indexer_status() through SearchIndexerClient, and those need Search
// Service Contributor. Without it the worker 403s the moment it picks up its
// first job.
resource workerSearchService 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, workerPrincipalId, roleIds.searchServiceContributor)
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.searchServiceContributor)
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// --- Azure AI Search service identity: reads source blobs for indexing, calls the embedding model for vectorization. ---

resource searchBlobRead 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, searchServicePrincipalId, roleIds.storageBlobDataReader)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.storageBlobDataReader)
    principalId: searchServicePrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource searchOpenAi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAiAccount.id, searchServicePrincipalId, roleIds.cognitiveServicesOpenAiUser)
  scope: openAiAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.cognitiveServicesOpenAiUser)
    principalId: searchServicePrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Lets the skillset's DocumentIntelligenceLayoutSkill bill against this
// account via the search service's own identity (AIServicesAccountIdentity),
// instead of a stored API key.
resource searchDocumentIntelligence 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(documentIntelligenceAccount.id, searchServicePrincipalId, roleIds.cognitiveServicesUser)
  scope: documentIntelligenceAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.cognitiveServicesUser)
    principalId: searchServicePrincipalId
    principalType: 'ServicePrincipal'
  }
}
