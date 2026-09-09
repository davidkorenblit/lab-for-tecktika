@description('Base name used to derive the Document Intelligence account name.')
param baseName string

@description('Azure region for the Document Intelligence account.')
param location string = resourceGroup().location

@description('Tags applied to the account.')
param tags object = {}

// A multi-service "CognitiveServices" account, not a single-service Form
// Recognizer/Document Intelligence one - Azure AI Search's skillset-level
// billing attachment (used to unlock DocumentIntelligenceLayoutSkill beyond
// the small daily free quota) only accepts a multi-service resource.
resource documentIntelligence 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: 'di-${baseName}'
  location: location
  tags: tags
  kind: 'CognitiveServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    // Required for AAD/identity-based auth (AIServicesAccountIdentity) -
    // without a custom subdomain the account only supports key auth.
    customSubDomainName: 'di-${baseName}'
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

output accountName string = documentIntelligence.name
output accountId string = documentIntelligence.id
output endpoint string = documentIntelligence.properties.endpoint
