"""Tests for auto_script run_job() wrapper."""

import inspect


from auto_script import run_job


class TestRunJobSignature:
    """Test run_job() function signature and parameters."""

    def test_run_job_is_callable(self) -> None:
        """Verify run_job is a callable function."""
        assert callable(run_job)

    def test_run_job_is_async(self) -> None:
        """Verify run_job is an async function."""
        assert inspect.iscoroutinefunction(run_job)

    def test_csv_path_is_optional(self) -> None:
        """Verify csv_path parameter defaults to None."""
        sig = inspect.signature(run_job)
        assert "csv_path" in sig.parameters
        assert sig.parameters["csv_path"].default is None

    def test_delete_scripts_parameter_exists(self) -> None:
        """Verify delete_scripts parameter exists with default False."""
        sig = inspect.signature(run_job)
        assert "delete_scripts" in sig.parameters
        assert sig.parameters["delete_scripts"].default is False

    def test_run_job_has_required_params(self) -> None:
        """Verify run_job has all required parameters."""
        sig = inspect.signature(run_job)
        required_params = [
            "config_path",
            "csv_path",
            "headless",
            "dry_run",
            "debug",
            "delete_scripts",
            "start_product",
            "limit",
            "audio_dir",
            "app_support_dir",
            "log_callback",
        ]
        for param in required_params:
            assert param in sig.parameters, f"Missing parameter: {param}"

    def test_run_job_returns_dict(self) -> None:
        """Verify run_job return type annotation is dict."""
        sig = inspect.signature(run_job)
        assert sig.return_annotation == "dict"

    def test_config_path_is_required(self) -> None:
        """Verify config_path is a required positional parameter."""
        sig = inspect.signature(run_job)
        param = sig.parameters["config_path"]
        assert param.default == inspect.Parameter.empty

    def test_keyword_only_params(self) -> None:
        """Verify keyword-only parameters after csv_path."""
        sig = inspect.signature(run_job)
        params = list(sig.parameters.values())
        csv_path_idx = next(i for i, p in enumerate(params) if p.name == "csv_path")
        headless_idx = next(i for i, p in enumerate(params) if p.name == "headless")
        assert headless_idx > csv_path_idx
        assert sig.parameters["headless"].kind == inspect.Parameter.KEYWORD_ONLY

    def test_log_callback_type_annotation(self) -> None:
        """Verify log_callback has correct type annotation."""
        sig = inspect.signature(run_job)
        param = sig.parameters["log_callback"]
        assert param.default is None
