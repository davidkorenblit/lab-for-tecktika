@description('Base name used to derive the Azure OpenAI account name.')
param baseName string

@description('Azure region for the Azure OpenAI account. Must be a region with capacity for the chosen models.')
param location string = resourceGroup().location

@description('Tags applied to the account.')
param tags object = {}

@description('Chat model deployment. DataZoneStandard keeps inference inside the EU data zone - the closest available option to the regional posture the rest of the stack uses, since this model has no plain Standard quota here.')
param chatModel object = {
  deploymentName: 'gpt-5-mini'
  modelName: 'gpt-5-mini'
  modelVersion: '2025-08-07'
  skuName: 'DataZoneStandard'
  // gpt-4o was the wrong model for this workload on both axes: a single RAG
  // turn carries the retrieved chunks plus history, and its regional Standard
  // quota of 50K TPM meant a 429 on the call that writes the answer - the
  // failure users actually hit.
  //
  // gpt-4o-mini would have been the obvious cheap replacement, but its only
  // version (2024-07-18) is refused at preflight: "has been deprecated since
  // 03/31/2026". gpt-4.1-mini has no quota in swedencentral in any Standard
  // bucket. gpt-5-mini does, is current, and is far cheaper than gpt-4o.
  //
  // DataZoneStandard rather than GlobalStandard: it keeps inference inside the
  // EU rather than routing it anywhere.
  //
  // Deliberately half the 300K quota, not all of it. CognitiveServices
  // preflight validates a redeploy as if the deployment were new: it asks for
  // the full target capacity against what is *unallocated*. Sitting at the
  // quota ceiling therefore makes the template deploy exactly once and fail
  // every time after with InsufficientQuota ("require 300 new capacity ...
  // available capacity 0"). Leaving half free keeps the deploy repeatable,
  // which brief 3.2 requires. 150K TPM is still fifteen times the capacity
  // this workload started on.
  capacity: 150
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
