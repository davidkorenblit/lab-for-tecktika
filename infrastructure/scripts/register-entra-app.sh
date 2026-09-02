#!/usr/bin/env bash
# Registers (or reuses) the Microsoft Entra ID App Registration used for sign-in.
#
# This is the one piece of setup that Bicep cannot express (Microsoft Graph objects
# are not ARM resources), so it lives as a small idempotent az CLI script instead.
#
# Usage:
#   ./register-entra-app.sh <display-name> <spa-redirect-url> [extra-redirect-url ...]
#
# Example:
#   ./register-entra-app.sh ragpoc-dev https://swa-ragpoc-dev.azurestaticapps.net http://localhost:5173
set -euo pipefail

DISPLAY_NAME="${1:?Usage: register-entra-app.sh <display-name> <spa-redirect-url> [extra-redirect-url ...]}"
shift
REDIRECT_URIS=("$@")
if [ ${#REDIRECT_URIS[@]} -eq 0 ]; then
  REDIRECT_URIS=("http://localhost:5173")
fi

EXISTING_APP_ID=$(az ad app list --display-name "$DISPLAY_NAME" --query "[0].appId" -o tsv)

if [ -n "$EXISTING_APP_ID" ]; then
  echo "==> Reusing existing app registration '$DISPLAY_NAME' ($EXISTING_APP_ID)"
  APP_ID="$EXISTING_APP_ID"
else
  echo "==> Creating app registration '$DISPLAY_NAME'"
  APP_ID=$(az ad app create \
    --display-name "$DISPLAY_NAME" \
    --sign-in-audience AzureADMyOrg \
    --query appId -o tsv)

  # Ensure a service principal exists so users can consent/sign in.
  az ad sp create --id "$APP_ID" --output none 2>/dev/null || true

  # Expose an API scope the SPA requests and the backend validates the audience against.
  IDENTIFIER_URI="api://$APP_ID"
  az ad app update --id "$APP_ID" --identifier-uris "$IDENTIFIER_URI" --output none

  SCOPE_ID=$(python3 -c "import uuid; print(uuid.uuid4())" 2>/dev/null || uuidgen)
  az ad app update --id "$APP_ID" --set api="{\"oauth2PermissionScopes\":[{\"id\":\"$SCOPE_ID\",\"adminConsentDescription\":\"Allow the app to act on behalf of the signed-in user.\",\"adminConsentDisplayName\":\"Access ${DISPLAY_NAME} as user\",\"userConsentDescription\":\"Allow the app to act on your behalf.\",\"userConsentDisplayName\":\"Access ${DISPLAY_NAME}\",\"value\":\"access_as_user\",\"type\":\"User\",\"isEnabled\":true}]}" --output none
fi

echo "==> Configuring SPA redirect URIs: ${REDIRECT_URIS[*]}"
REDIRECTS_JSON=$(printf '"%s",' "${REDIRECT_URIS[@]}")
REDIRECTS_JSON="[${REDIRECTS_JSON%,}]"
az ad app update --id "$APP_ID" --set spa="{\"redirectUris\":${REDIRECTS_JSON}}" --output none

TENANT_ID=$(az account show --query tenantId -o tsv)

echo ""
echo "==> Entra ID App Registration ready:"
echo "    AZURE_TENANT_ID=$TENANT_ID"
echo "    AZURE_CLIENT_ID_API=$APP_ID"
echo "    API scope: api://$APP_ID/access_as_user"
echo ""
echo "==> Set entraTenantId/entraApiClientId in infrastructure/main.bicepparam to these"
echo "    values and re-run deploy.sh so the backend Container App gets them as env vars."
