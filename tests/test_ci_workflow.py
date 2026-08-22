import yaml

from app.config import REPO_ROOT


def test_deploy_job_requires_azure_repository_variables():
    with (REPO_ROOT / ".github" / "workflows" / "ci-cd.yml").open(encoding="utf-8") as handle:
        workflow = yaml.safe_load(handle)

    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict) and "deploy" in jobs

    deploy = jobs["deploy"]
    assert isinstance(deploy, dict)

    deploy_if = deploy.get("if")
    assert isinstance(deploy_if, str)
    normalized_if = " ".join(deploy_if.split())

    assert "github.ref == 'refs/heads/main'" in normalized_if
    assert "vars.AZURE_CLIENT_ID != ''" in normalized_if
    assert "vars.AZURE_TENANT_ID != ''" in normalized_if
    assert "vars.AZURE_SUBSCRIPTION_ID != ''" in normalized_if
    assert "vars.AZURE_ENV_NAME != ''" in normalized_if
    assert "vars.AZURE_LOCATION != ''" in normalized_if
