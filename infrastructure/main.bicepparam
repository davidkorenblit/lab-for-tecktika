using 'main.bicep'

param projectName = 'ragpoc'
param environmentName = 'dev'
param location = 'swedencentral'
param openAiLocation = 'swedencentral'

param blobContainerName = 'pdf-library'
param queueName = 'index-jobs'
param jobStatusTableName = 'jobstatus'

// 'free' has no cost but caps you at 3 indexes / 50MB and no semantic ranking.
// 'basic' is the minimum tier this project is designed against.
param searchSkuName = 'basic'

// Placeholder until the backend CI/CD pipeline (ci-backend.yml) pushes a real image
// and updates the Container App's revision.
param backendContainerImage = 'mcr.microsoft.com/k8se/quickstart:latest'

// Fill these in after running `az ad app create` for the Entra ID App Registration
// (see infrastructure/scripts/deploy.sh). Left blank, the backend simply has no
// tenant/client configured yet — auth wiring happens once the registration exists.
param entraTenantId = ''
param entraApiClientId = ''
