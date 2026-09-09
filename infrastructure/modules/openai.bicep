@description('Base name used to derive the Azure OpenAI account name.')
param baseName string

@description('Azure region for the Azure OpenAI account. Must be a region with capacity for the chosen models.')
param location string = resourceGroup().location

@description('Tags applied to the account.')
param tags object = {}

@description('Chat model deployment. Standard (regional) SKU keeps inference in swedencentral, matching the data-residency posture the rest of the stack is built on; GlobalStandard would route outside the region.')
param chatModel object = {
  deploymentName: 'gpt-4o-mini'
  modelName: 'gpt-4o-mini'
  modelVersion: '2024-07-18'
  skuName: 'Standard'
  // gpt-4o was the wrong model for this workload on both axes. A single RAG
  // turn carries the retrieved chunks plus history, and on gpt-4o's regional
  // Standard quota of 50K TPM that meant a 429 on the call that writes the
  // answer - the failure users actually hit. gpt-4o-mini has its own quota
  // bucket with 200K TPM available in this region, and costs roughly a
  // sixteenth per input token.
  capacity: 200
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
