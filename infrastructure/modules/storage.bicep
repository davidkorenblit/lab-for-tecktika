@description('Base name used to derive the storage account name (must be globally unique, lowercase, no dashes).')
param storageAccountName string = 'stragpocdev${uniqueString(resourceGroup().id)}'

@description('Azure region for the storage account.')
param location string = resourceGroup().location

@description('Name of the blob container that holds the source-of-truth PDFs.')
param blobContainerName string = 'pdf-library'

@description('Name of the queue that receives change events for the Worker to consume.')
param queueName string = 'index-jobs'

@description('Name of the table that tracks job status and per-file ETags.')
param jobStatusTableName string = 'jobstatus'

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
}

resource pdfContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: blobContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource queueService 'Microsoft.Storage/storageAccounts/queueServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
}

resource indexQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-01-01' = {
  parent: queueService
  name: queueName
}

resource tableService 'Microsoft.Storage/storageAccounts/tableServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
}

resource jobStatusTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = {
  parent: tableService
  name: jobStatusTableName
}

output storageAccountName string = storageAccount.name
output blobContainerName string = pdfContainer.name
output queueName string = indexQueue.name
output jobStatusTableName string = jobStatusTable.name
