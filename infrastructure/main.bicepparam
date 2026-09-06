using 'main.bicep'

param projectName = 'ragpoc'
param environmentName = 'dev'
param location = 'swedencentral'
param openAiLocation = 'swedencentral'

param blobContainerName = 'pdf-library'
param stagingContainerName = 'staging'
param queueName = 'index-jobs'
param jobStatusTableName = 'jobstatus'

// Frontend origins allowed to PUT/GET directly against the staging container.
// Static Web App hostname from infrastructure/scripts/.generated.env (STATIC_WEB_APP_HOSTNAME).
param stagingCorsAllowedOrigins = [
  'http://localhost:5173'
  'https://delightful-river-0f09b360f.5.azurestaticapps.net'
]

// 'free' has no cost but caps you at 3 indexes / 50MB and no semantic ranking.
// 'basic' is the minimum tier this project is designed against.
param searchSkuName = 'basic'

// Placeholder until the backend CI/CD pipeline (ci-backend.yml) pushes a real image
// and updates the Container App's revision.
param backendContainerImage = 'mcr.microsoft.com/k8se/quickstart:latest'

// From register-entra-app.sh (Entra ID App Registration for user sign-in).
param entraTenantId = '6fc8a795-8bcb-4e52-8b36-41c1971e6816'
param entraApiClientId = '7267f8e7-50eb-4247-88b7-da2cc3adf6f6'
