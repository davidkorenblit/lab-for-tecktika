#!/usr/bin/env bash
# Registers (or reuses) the Entra ID App Registration that GitHub Actions uses to
# deploy infrastructure via OIDC federated credentials — no client secret is ever
# generated or stored. This is separate from register-entra-app.sh, which handles
# end-user sign-in; this app exists purely so deploy-infra.yml can log in as itself.
#
# Usage:
#   ./register-github-oidc.sh <github-owner/repo> <resource-group-name> [location] [environment-name]
#
# Example:
#   ./register-github-oidc.sh davidkorenblit/lab-for-tecktika rg-ragpoc-dev swedencentral dev
set -euo pipefail

GITHUB_REPO="${1:?Usage: register-github-oidc.sh <github-owner/repo> <resource-group-name> [location] [environment-name]}"
RESOURCE_GROUP="${2:?Usage: register-github-oidc.sh <github-owner/repo> <resource-group-name> [location] [environment-name]}"
LOCATION="${3:-swedencentral}"
GH_ENVIRONMENT="${4:-dev}"
APP_DISPLAY_NAME="gha-oidc-$(echo "$RESOURCE_GROUP" | tr '[:upper:]' '[:lower:]')"

echo "==> Ensuring resource group '$RESOURCE_GROUP' exists in $LOCATION"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

EXISTING_APP_ID=$(az ad app list --display-name "$APP_DISPLAY_NAME" --query "[0].appId" -o tsv)

if [ -n "$EXISTING_APP_ID" ]; then
  echo "==> Reusing existing app registration '$APP_DISPLAY_NAME' ($EXISTING_APP_ID)"
  APP_ID="$EXISTING_APP_ID"
else
  echo "==> Creating app registration '$APP_DISPLAY_NAME'"
  APP_ID=$(az ad app create --display-name "$APP_DISPLAY_NAME" --sign-in-audience AzureADMyOrg --query appId -o tsv)
fi

SP_ID=$(az ad sp list --filter "appId eq '$APP_ID'" --query "[0].id" -o tsv)
if [ -z "$SP_ID" ]; then
  echo "==> Creating service principal for the app"
  SP_ID=$(az ad sp create --id "$APP_ID" --query id -o tsv)
fi

echo "==> Configuring federated credentials for $GITHUB_REPO"
# Matches deploy-infra.yml's `environment: dev` job setting — GitHub issues the OIDC
# token with an environment-scoped subject whenever a job declares `environment:`,
# regardless of which branch or trigger fired it.
az ad app federated-credential create --id "$APP_ID" --parameters "{
  \"name\": \"gh-environment-${GH_ENVIRONMENT}\",
  \"issuer\": \"https://token.actions.githubusercontent.com\",
  \"subject\": \"repo:${GITHUB_REPO}:environment:${GH_ENVIRONMENT}\",
  \"audiences\": [\"api://AzureADTokenExchange\"]
}" --output none 2>/dev/null || echo "    (already exists, skipping)"

# Fallback credential in case the `environment:` block is ever removed from the
# workflow, so plain pushes to main keep working without re-running this script.
az ad app federated-credential create --id "$APP_ID" --parameters "{
  \"name\": \"gh-branch-main\",
  \"issuer\": \"https://token.actions.githubusercontent.com\",
  \"subject\": \"repo:${GITHUB_REPO}:ref:refs/heads/main\",
  \"audiences\": [\"api://AzureADTokenExchange\"]
}" --output none 2>/dev/null || echo "    (already exists, skipping)"

echo "==> Granting least-privilege roles on '$RESOURCE_GROUP' only (not the whole subscription)"
RG_ID=$(az group show --name "$RESOURCE_GROUP" --query id -o tsv)

# Contributor to create/update resources...
az role assignment create --assignee-object-id "$SP_ID" --assignee-principal-type ServicePrincipal \
  --role "Contributor" --scope "$RG_ID" --output none 2>/dev/null || echo "    (Contributor already assigned)"

# ...plus RBAC Administrator, because role_assignments.bicep creates role assignments,
# and Contributor alone cannot grant Microsoft.Authorization/roleAssignments/write.
az role assignment create --assignee-object-id "$SP_ID" --assignee-principal-type ServicePrincipal \
  --role "Role Based Access Control Administrator" --scope "$RG_ID" --output none 2>/dev/null || echo "    (RBAC Administrator already assigned)"

TENANT_ID=$(az account show --query tenantId -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

echo ""
echo "==> Done. Add these as GitHub Actions secrets on $GITHUB_REPO:"
echo "    AZURE_CLIENT_ID=$APP_ID"
echo "    AZURE_TENANT_ID=$TENANT_ID"
echo "    AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID"
echo ""
echo "    Also set the repo VARIABLE (not secret) AZURE_RESOURCE_GROUP=$RESOURCE_GROUP"
echo "    (and AZURE_LOCATION=$LOCATION if you want something other than the workflow default)."
echo ""
echo "==> If you have the GitHub CLI (gh) authenticated, this does it for you:"
echo "    gh secret set AZURE_CLIENT_ID -b\"$APP_ID\" -R $GITHUB_REPO"
echo "    gh secret set AZURE_TENANT_ID -b\"$TENANT_ID\" -R $GITHUB_REPO"
echo "    gh secret set AZURE_SUBSCRIPTION_ID -b\"$SUBSCRIPTION_ID\" -R $GITHUB_REPO"
echo "    gh variable set AZURE_RESOURCE_GROUP -b\"$RESOURCE_GROUP\" -R $GITHUB_REPO"
echo "    gh variable set AZURE_LOCATION -b\"$LOCATION\" -R $GITHUB_REPO"
echo ""
echo "==> Also create a GitHub 'dev' environment (Settings > Environments) if it"
echo "    doesn't exist yet — deploy-infra.yml targets it, and the federated"
echo "    credential above is scoped to that exact environment name."
