# Deploy from GitHub Actions to Azure Container Apps

GitHub Pages only serves static files; it cannot run the Flask API, PostgreSQL, reminder worker, or private uploads. DeadlineOS uses a manual GitHub Actions workflow to build its Docker image, push it to Azure Container Registry (ACR), deploy it to an existing Azure Container App, and check `/api/health`.

The workflow is `.github/workflows/deploy-azure.yml`. It is intentionally `workflow_dispatch` only and will run only from `main` in the protected `production` GitHub environment. A pull request never gets Azure deployment credentials.

## Required Azure resources

Provision these before running the workflow:

- An Azure Container Apps environment and Container App with external HTTPS ingress forwarding to port `5000`.
- An Azure Container Registry. The workflow identity needs `AcrPush`; the Container App's managed identity needs `AcrPull`.
- A PostgreSQL database reachable from the Container Apps environment. Store its connection string as a Container App secret, then set `DATABASE_URL` to a `secretref:` value.
- A persistent upload mount at `/app/backend/instance/uploads`. The current app uses filesystem paths; do not deploy with ephemeral container storage if uploaded work must persist.
- Container App secrets and environment values: `DATABASE_URL`, a random `JWT_SECRET_KEY` with at least 32 characters, `ENVIRONMENT=production`, `SEED_DEMO=false`, `ENABLE_REMINDERS=true`, `CLAMAV_REQUIRED=true` and `CLAMAV_HOST` if a reachable ClamAV service is provisioned. Set quota values deliberately. Keep PostgreSQL and malware-scanner endpoints private. Production mode refuses the local fallback JWT secret and disables wildcard CORS unless an explicit origin is configured.

Configure the Container App to use its managed identity to pull from ACR. Configure durable storage, TLS ingress, health probes, resource limits, and database network rules before exposing student data. The app's configured instance count should be considered with the reminder scheduler; the database's unique reminder keys prevent duplicate records, but the scheduler is intended to run in one app replica for this semester project.

## Configure GitHub OIDC

1. Create a Microsoft Entra application or user-assigned managed identity and a federated identity credential that trusts this repository's `production` GitHub environment. Use audience `api://AzureADTokenExchange` and subject `repo:YuvrajChaudhary7/DeadlineOS:environment:production`.
2. Grant only the deployment permissions needed: ACR push on the registry and Container Apps update permission scoped to the app/resource group. The Container App's separate pull identity gets ACR pull.
3. In GitHub, create an environment named `production`. Add these environment secrets:

   - `AZURE_CLIENT_ID`
   - `AZURE_TENANT_ID`
   - `AZURE_SUBSCRIPTION_ID`
   - `AZURE_ACR_NAME`
   - `AZURE_RESOURCE_GROUP`
   - `AZURE_CONTAINER_APP_NAME`

4. Protect the environment with a reviewer if available. Merge reviewed changes to `main`, then use **Actions → Deploy Azure Container App → Run workflow** and select `main`.
5. Confirm the workflow's health check passes, open the HTTPS URL shown in the run log, and test registration/login and private file persistence after a new revision.

GitHub Actions uses Azure OIDC, so the workflow does not need a long-lived Azure client secret. Follow the [GitHub OIDC for Azure guide](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure) and [Azure Container Apps GitHub Actions guide](https://learn.microsoft.com/en-us/azure/container-apps/github-actions) when configuring Azure resources.

## Current deployment boundary

The workflow updates an existing Azure Container App; it does not create Azure resources. A hosted DeadlineOS demo is available at [the live app](https://deadlineos-app.wonderfulpond-3d54e124.centralindia.azurecontainerapps.io/). Its availability does not confirm that every optional Azure service or control described above is configured. Check the deployment workflow and active resource settings before describing those controls as enabled. Azure services can incur charges.
