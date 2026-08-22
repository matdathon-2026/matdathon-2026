import yaml

from app.config import REPO_ROOT


def test_deploy_job_requires_azure_repository_variables():
    with (REPO_ROOT / ".github" / "workflows" / "ci-cd.yml").open(encoding="utf-8") as handle:
        workflow = yaml.safe_load(handle)

    deploy_if = workflow["jobs"]["deploy"]["if"]

    assert "github.ref == 'refs/heads/main'" in deploy_if
    assert "vars.AZURE_CLIENT_ID != ''" in deploy_if
    assert "vars.AZURE_TENANT_ID != ''" in deploy_if
    assert "vars.AZURE_SUBSCRIPTION_ID != ''" in deploy_if
    assert "vars.AZURE_ENV_NAME != ''" in deploy_if
    assert "vars.AZURE_LOCATION != ''" in deploy_if
