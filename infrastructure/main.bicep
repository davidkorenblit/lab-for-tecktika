targetScope = 'resourceGroup'

@description('Short project prefix used to derive resource names (lowercase letters/numbers only).')
@minLength(3)
@maxLength(12)
param projectName string = 'ragpoc'

@description('Environment name, e.g. dev, staging, prod.')
param environmentName string = 'dev'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Azure region for the Azure OpenAI account, if capacity requires a different region than the rest of the stack.')
param openAiLocation string = location

@description('Azure region for the Static Web App. Static Web Apps only deploys to a short fixed list of regions, which often excludes the region used for everything else.')
param staticWebAppLocation string = 'eastus2'

@description('Tags applied to every resource.')
param tags object = {
  project: projectName
  environment: environmentName
  managedBy: 'bicep'
}

@description('Name of the blob container that holds the source-of-truth PDFs.')
param blobContainerName string = 'pdf-library'

@description('Name of the queue that receives ingestion/deletion jobs for the Worker to consume.')
param queueName string = 'index-jobs'

@description('Name of the table that tracks job status and per-file ETags.')
param jobStatusTableName string = 'jobstatus'

@description('Azure AI Search pricing tier.')
@allowed([
  'free'
  'basic'
  'standard'
])
param searchSkuName string = 'basic'

@description('Placeholder container image for the backend Container App until the first CI/CD deploy replaces it.')
param backendContainerImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

@description('Entra ID tenant ID used for backend token validation (from the App Registration created for this project).')
param entraTenantId string = ''

@description('Entra ID API app registration client ID exposed by the backend.')
param entraApiClientId string = ''

var baseName = '${projectName}-${environmentName}-${uniqueString(resourceGroup().id)}'

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    baseName: baseName
    location: location
    tags: tags
  }
}

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    location: location
    blobContainerName: blobContainerName
    queueName: queueName
    jobStatusTableName: jobStatusTableName
  }
}

module aiSearch 'modules/ai_search.bicep' = {
  name: 'aiSearch'
  params: {
    baseName: baseName
    location: location
    tags: tags
    skuName: searchSkuName
  }
}

module openAi 'modules/openai.bicep' = {
  name: 'openAi'
  params: {
    baseName: baseName
    location: openAiLocation
    tags: tags
  }
}

module compute 'modules/compute.bicep' = {
  name: 'compute'
  params: {
    baseName: baseName
    location: location
    staticWebAppLocation: staticWebAppLocation
    tags: tags
    logAnalyticsWorkspaceId: monitoring.outputs.logAnalyticsWorkspaceId
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    storageAccountName: storage.outputs.storageAccountName
    blobContainerName: storage.outputs.blobContainerName
    queueName: storage.outputs.queueName
    jobStatusTableName: storage.outputs.jobStatusTableName
    searchEndpoint: aiSearch.outputs.searchEndpoint
    openAiEndpoint: openAi.outputs.openAiEndpoint
    chatDeploymentName: openAi.outputs.chatDeploymentName
    embeddingDeploymentName: openAi.outputs.embeddingDeploymentName
    backendContainerImage: backendContainerImage
    entraTenantId: entraTenantId
    entraApiClientId: entraApiClientId
  }
}

module roleAssignments 'modules/role_assignments.bicep' = {
  name: 'roleAssignments'
  params: {
    storageAccountName: storage.outputs.storageAccountName
    openAiAccountName: openAi.outputs.openAiAccountName
    searchServiceName: aiSearch.outputs.searchServiceName
    backendPrincipalId: compute.outputs.backendAppPrincipalId
    workerPrincipalId: compute.outputs.functionAppPrincipalId
    searchServicePrincipalId: aiSearch.outputs.searchServicePrincipalId
  }
}

output resourceGroupName string = resourceGroup().name
output storageAccountName string = storage.outputs.storageAccountName
output blobContainerName string = storage.outputs.blobContainerName
output queueName string = storage.outputs.queueName
output jobStatusTableName string = storage.outputs.jobStatusTableName
output searchServiceName string = aiSearch.outputs.searchServiceName
output searchEndpoint string = aiSearch.outputs.searchEndpoint
output openAiAccountName string = openAi.outputs.openAiAccountName
output openAiEndpoint string = openAi.outputs.openAiEndpoint
output chatDeploymentName string = openAi.outputs.chatDeploymentName
output embeddingDeploymentName string = openAi.outputs.embeddingDeploymentName
output backendAppName string = compute.outputs.backendAppName
output backendFqdn string = compute.outputs.backendFqdn
output functionAppName string = compute.outputs.functionAppName
output staticWebAppName string = compute.outputs.staticWebAppName
output staticWebAppDefaultHostname string = compute.outputs.staticWebAppDefaultHostname
output appInsightsConnectionString string = monitoring.outputs.appInsightsConnectionString
