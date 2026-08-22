// 디딤하트(DidimHeart) — Azure Container Apps infrastructure (judging evidence).
//
// The live deployment was created with `az containerapp up --source .`, which
// provisions the environment + app and performs a cloud-side ACR build. This
// Bicep captures the same topology for a reproducible `az deployment group create`.
//
// Resource names match the live deployment:
//   RG: rg-didimheart / CAE: cae-didimheart / App: didimheart / region: koreacentral
//
// The GitHub token is injected as a Container Apps secret (COPILOT_GITHUB_TOKEN)
// and is never baked into the image or committed. Pass it via --parameters at deploy.

@description('Deployment location.')
param location string = resourceGroup().location

@description('Container Apps environment name.')
param environmentName string = 'cae-didimheart'

@description('Container App name.')
param appName string = 'didimheart'

@description('Log Analytics workspace name.')
param logAnalyticsName string = 'log-didimheart'

@description('Fully qualified container image, e.g. <acr>.azurecr.io/didimheart:latest')
param containerImage string

@description('GitHub token used only by the Copilot SDK at runtime. Injected as a secret.')
@secure()
param copilotGithubToken string

@description('Target container port.')
param targetPort int = 8000

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  identity: {
    // System-assigned Managed Identity for Foundry / Cosmos DB access.
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'auto'
        // No session affinity: state lives server-side keyed by demo session id.
        allowInsecure: false
      }
      secrets: [
        {
          name: 'copilot-github-token'
          value: copilotGithubToken
        }
      ]
    }
    template: {
      containers: [
        {
          name: appName
          image: containerImage
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            {
              name: 'COPILOT_GITHUB_TOKEN'
              secretRef: 'copilot-github-token'
            }
            {
              name: 'COPILOT_SKIP_CLI_DOWNLOAD'
              value: '1'
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/healthz'
                port: targetPort
              }
              initialDelaySeconds: 10
              periodSeconds: 15
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/readyz'
                port: targetPort
              }
              initialDelaySeconds: 5
              periodSeconds: 15
            }
          ]
        }
      ]
      scale: {
        // Keep 1 warm replica during judging to avoid cold starts.
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

output appFqdn string = app.properties.configuration.ingress.fqdn
output principalId string = app.identity.principalId
