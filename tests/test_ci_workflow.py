from app.config import REPO_ROOT


def test_deploy_job_requires_azure_repository_variables():
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci-cd.yml").read_text(encoding="utf-8")

    assert "github.ref == 'refs/heads/main'" in workflow
    assert "vars.AZURE_CLIENT_ID != ''" in workflow
    assert "vars.AZURE_TENANT_ID != ''" in workflow
    assert "vars.AZURE_SUBSCRIPTION_ID != ''" in workflow
    assert "vars.AZURE_ENV_NAME != ''" in workflow
    assert "vars.AZURE_LOCATION != ''" in workflow
