"""Use case: Verifies fail-fast runtime configuration.

What it does: Prevents incomplete model routes from reaching startup.
"""

import pytest
from pydantic import ValidationError

from execplus.config import Settings


def test_models_can_remain_disabled() -> None:
    settings = Settings(_env_file=None, llm_mode="disabled")

    assert settings.llm_mode == "disabled"


def test_local_route_requires_both_model_names() -> None:
    with pytest.raises(ValidationError, match="EXECPLUS_LLM_LARGE_MODEL"):
        Settings(
            _env_file=None,
            llm_mode="local",
            llm_small_model="small-local",
            llm_large_model="",
        )


def test_hosted_route_requires_an_api_key() -> None:
    with pytest.raises(ValidationError, match="EXECPLUS_LLM_API_KEY"):
        Settings(
            _env_file=None,
            llm_mode="hosted",
            llm_small_model="small-hosted",
            llm_large_model="large-hosted",
            llm_api_key="",
        )


@pytest.mark.parametrize("limit", [0, 20 * 1024 * 1024 + 1])
def test_upload_limit_cannot_exceed_product_cap(limit):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, max_upload_bytes=limit)


def test_whitespace_model_name_is_not_configured():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_mode="local", llm_small_model="   ", llm_large_model="large")


def test_settings_repr_and_validation_do_not_expose_secrets():
    settings = Settings(_env_file=None, llm_api_key="private-test-secret")
    assert "private-test-secret" not in repr(settings)
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, llm_mode="local", llm_api_key="private-test-secret")
    assert "private-test-secret" not in str(error.value)
