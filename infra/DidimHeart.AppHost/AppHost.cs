// DidimHeart infrastructure, modelled with .NET Aspire.
//
// This AppHost owns every Azure resource: the API container app, the scheduled
// benefit-ingestion job, Cosmos DB, the raw-response blob archive and the
// Foundry model. `azd up` turns this file into Bicep, so the deployment stays
// reproducible from the submitted commit.

using Aspire.Hosting.Azure;
using Azure.Provisioning;
using Azure.Provisioning.AppContainers;
using Azure.Provisioning.CognitiveServices;
using Azure.Provisioning.Resources;
using Azure.Provisioning.Storage;

var builder = DistributedApplication.CreateBuilder(args);

// Cron is UTC. 18:00 UTC == 03:00 KST, outside Korean office hours.
var ingestCron = builder.Configuration["IngestCron"] ?? "0 18 * * *";

// No 온통청년 key has been issued yet, so the ingestion job falls back to the
// repository snapshot. The placeholder keeps `azd provision` non-interactive;
// a real key is supplied with `azd env set YouthCenterApiKey <key>`.
var youthCenterApiKey = builder.AddParameter(
    "youthCenterApiKey",
    builder.Configuration["YouthCenterApiKey"] ?? "unset",
    publishValueAsDefault: true);

// Container image for both workloads.
//
// azd 1.31 has no remote-build support for container apps, so the image is
// built inside Azure with `az acr build` (no local Docker daemon) and passed
// in here. The placeholder lets the very first `azd provision` succeed before
// any image exists.
var appImage = builder.Configuration["DIDIMHEART_IMAGE"]
    ?? "mcr.microsoft.com/k8se/quickstart:latest";

// ---------------------------------------------------------------------------
// Hosting environment
// ---------------------------------------------------------------------------

var containerEnv = builder
    .AddAzureContainerAppEnvironment("cae")
    .WithAzdResourceNaming();

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

var cosmos = builder.AddAzureCosmosDB("cosmos");

var didimheartDb = cosmos.AddCosmosDatabase("didimheart");
didimheartDb.AddContainer("benefits", "/category");
didimheartDb.AddContainer("sessions", "/id");
didimheartDb.AddContainer("plans", "/sessionId");
didimheartDb.AddContainer("heartLedger", "/sessionId");

// Untouched upstream payloads are kept so every recommendation can be traced
// back to what the government API actually returned.
var storage = builder.AddAzureStorage("archive");
var rawBenefits = storage.AddBlobContainer("raw-benefits");

// ---------------------------------------------------------------------------
// Model
// ---------------------------------------------------------------------------

var foundry = builder.AddAzureOpenAI("foundry");

// gpt-4o-mini is deprecating and rejects new deployments, and koreacentral
// grants this subscription no GlobalStandard quota for it. gpt-4.1-mini is the
// cheapest currently deployable chat model here (200K TPM).
var chatModel = foundry
    .AddDeployment("chat", "gpt-4.1-mini", "2025-04-14")
    .WithProperties(deployment =>
    {
        deployment.SkuName = "GlobalStandard";
        deployment.SkuCapacity = 20;
    });

// ---------------------------------------------------------------------------
// API container app
// ---------------------------------------------------------------------------

var api = builder
    .AddContainer("api", appImage)
    .WithHttpEndpoint(targetPort: 8000, name: "http")
    .WithExternalHttpEndpoints()
    .WithReference(didimheartDb)
    .WithReference(rawBenefits)
    .WithReference(chatModel)
    .WithRoleAssignments(foundry, CognitiveServicesBuiltInRole.CognitiveServicesOpenAIUser)
    .WithRoleAssignments(storage, StorageBuiltInRole.StorageBlobDataReader)
    .WithEnvironment("COSMOS_ENDPOINT", cosmos.Resource.ConnectionStringExpression)
    .WithEnvironment("COSMOS_DATABASE", "didimheart")
    .WithEnvironment("FOUNDRY_RESOURCE_URL", foundry.Resource.ConnectionStringExpression)
    .WithEnvironment("FOUNDRY_MODEL", chatModel.Resource.DeploymentName)
    .WithEnvironment("INGEST_ARCHIVE_ACCOUNT_URL", storage.Resource.BlobEndpoint)
    .WithEnvironment("INGEST_ARCHIVE_CONTAINER", "raw-benefits")
    .PublishAsAzureContainerApp((infra, app) =>
    {
        AttachRegistry(infra, app.Identity, app.Configuration.Registries);

        // Judges hit a cold URL once, so keep one replica warm (TRD 16).
        app.Template.Scale.MinReplicas = 1;
        app.Template.Scale.MaxReplicas = 3;
    });

// ---------------------------------------------------------------------------
// Scheduled catalog ingestion job
// ---------------------------------------------------------------------------
// Same image as the API, different command. The job is the only writer of the
// benefit catalog; the API and its agents only read it.

var ingest = builder
    .AddContainer("ingest", appImage)
    .WithArgs("python", "-m", "app.ingestion")
    .WithReference(didimheartDb)
    .WithReference(rawBenefits)
    .WithReference(chatModel)
    .WithRoleAssignments(foundry, CognitiveServicesBuiltInRole.CognitiveServicesOpenAIUser)
    .WithRoleAssignments(storage, StorageBuiltInRole.StorageBlobDataContributor)
    .WithEnvironment("COSMOS_ENDPOINT", cosmos.Resource.ConnectionStringExpression)
    .WithEnvironment("COSMOS_DATABASE", "didimheart")
    .WithEnvironment("FOUNDRY_RESOURCE_URL", foundry.Resource.ConnectionStringExpression)
    .WithEnvironment("FOUNDRY_MODEL", chatModel.Resource.DeploymentName)
    .WithEnvironment("INGEST_ARCHIVE_ACCOUNT_URL", storage.Resource.BlobEndpoint)
    .WithEnvironment("INGEST_ARCHIVE_CONTAINER", "raw-benefits")
    .WithEnvironment("YOUTHCENTER_API_KEY", youthCenterApiKey)
    .PublishAsScheduledAzureContainerAppJob(ingestCron, (infra, job) =>
    {
        AttachRegistry(infra, job.Identity, job.Configuration.Registries);

        job.Configuration.ReplicaTimeout = 1800;
        job.Configuration.ReplicaRetryLimit = 1;
    });

builder.Build().Run();

// `AddContainer` describes an image that already exists, so Aspire assumes it is
// public and omits the registry credentials that `AddDockerfile` would have
// emitted. Our image lives in the private registry that the container app
// environment creates, and it is built there by `az acr build` rather than by a
// local Docker daemon, so the pull identity has to be wired back in by hand.
void AttachRegistry(
    AzureResourceInfrastructure infra,
    ManagedServiceIdentity identity,
    BicepList<ContainerAppRegistryCredentials> registries)
{
    var registry = (IAzureContainerRegistry)containerEnv.Resource;

    // The names must follow Aspire's `<resource>_outputs_<output>` convention so
    // that azd resolves them from the container app environment's outputs.
    var server = registry.Endpoint
        .AsProvisioningParameter(infra, "cae_outputs_azure_container_registry_endpoint");
    var pullIdentity = registry.ManagedIdentityId
        .AsProvisioningParameter(infra, "cae_outputs_azure_container_registry_managed_identity_id");

    identity.UserAssignedIdentities[$"${{{pullIdentity.BicepIdentifier}}}"] =
        new UserAssignedIdentityDetails();

    registries.Add(new ContainerAppRegistryCredentials
    {
        Server = server,
        Identity = pullIdentity,
    });
}
