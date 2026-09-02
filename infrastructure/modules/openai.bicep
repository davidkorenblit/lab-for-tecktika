@description('Base name used to derive the Azure OpenAI account name.')
param baseName string

@description('Azure region for the Azure OpenAI account. Must be a region with capacity for the chosen models.')
param location string = resourceGroup().location

@description('Tags applied to the account.')
param tags object = {}

@description('Chat/reasoning model deployment. Standard (regional) SKU: fresh/personal subscriptions commonly start with 0 approved quota on GlobalStandard until a quota increase is requested, but already have default Standard quota (50K TPM as of writing).')
param chatModel object = {
  deploymentName: 'gpt-4o'
  modelName: 'gpt-4o'
  modelVersion: '2024-11-20'
  skuName: 'Standard'
  capacity: 10
}

@description('Embedding model deployment used for indexing and query-time vectorization. text-embedding-3-small only supports GlobalStandard/DataZoneStandard (not plain Standard) as a deployment SKU; GlobalStandard has ample default quota (1000K TPM as of writing) even on fresh subscriptions.')
param embeddingModel object = {
  deploymentName: 'text-embedding-3-small'
  modelName: 'text-embedding-3-small'
  modelVersion: '1'
  skuName: 'GlobalStandard'
  capacity: 30
}

resource openAiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: 'aoai-${baseName}'
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: 'aoai-${baseName}'
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAiAccount
  name: chatModel.deploymentName
  sku: {
    name: chatModel.skuName
    capacity: chatModel.capacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: chatModel.modelName
      version: chatModel.modelVersion
    }
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAiAccount
  name: embeddingModel.deploymentName
  sku: {
    name: embeddingModel.skuName
    capacity: embeddingModel.capacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embeddingModel.modelName
      version: embeddingModel.modelVersion
    }
  }
  dependsOn: [
    chatDeployment
  ]
}

output openAiAccountName string = openAiAccount.name
output openAiAccountId string = openAiAccount.id
output openAiEndpoint string = openAiAccount.properties.endpoint
output chatDeploymentName string = chatDeployment.name
output embeddingDeploymentName string = embeddingDeployment.name
