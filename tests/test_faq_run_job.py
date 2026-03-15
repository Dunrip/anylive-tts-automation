"""Tests for auto_faq run_job() wrapper."""

import inspect


from auto_faq import run_job


class TestRunJobSignature:
    """Test run_job() function signature and basic properties."""

    def test_run_job_is_callable(self):
        """run_job should be a callable function."""
        assert callable(run_job)

    def test_run_job_is_async(self):
        """run_job should be an async function."""
        assert inspect.iscoroutinefunction(run_job)

    def test_run_job_has_required_params(self):
        """run_job should have required positional parameters."""
        sig = inspect.signature(run_job)
        assert "config_path" in sig.parameters
        assert "csv_path" in sig.parameters

    def test_run_job_has_keyword_only_params(self):
        """run_job should have keyword-only parameters after *."""
        sig = inspect.signature(run_job)
        params = list(sig.parameters.values())

        # Find the * separator
        keyword_only_params = [
            p for p in params if p.kind == inspect.Parameter.KEYWORD_ONLY
        ]

        assert len(keyword_only_params) > 0, "Should have keyword-only parameters"
        assert "headless" in sig.parameters
        assert "dry_run" in sig.parameters
        assert "debug" in sig.parameters
        assert "start_product" in sig.parameters
        assert "limit" in sig.parameters
        assert "audio_dir" in sig.parameters
        assert "app_support_dir" in sig.parameters
        assert "log_callback" in sig.parameters

    def test_config_path_is_required(self):
        """config_path should be a required parameter (no default)."""
        sig = inspect.signature(run_job)
        assert sig.parameters["config_path"].default == inspect.Parameter.empty

    def test_csv_path_is_required(self):
        """csv_path should be a required parameter (no default)."""
        sig = inspect.signature(run_job)
        assert sig.parameters["csv_path"].default == inspect.Parameter.empty

    def test_headless_default_is_false(self):
        """headless should default to False."""
        sig = inspect.signature(run_job)
        assert sig.parameters["headless"].default is False

    def test_dry_run_default_is_false(self):
        """dry_run should default to False."""
        sig = inspect.signature(run_job)
        assert sig.parameters["dry_run"].default is False

    def test_debug_default_is_false(self):
        """debug should default to False."""
        sig = inspect.signature(run_job)
        assert sig.parameters["debug"].default is False

    def test_start_product_default_is_none(self):
        """start_product should default to None."""
        sig = inspect.signature(run_job)
        assert sig.parameters["start_product"].default is None

    def test_limit_default_is_none(self):
        """limit should default to None."""
        sig = inspect.signature(run_job)
        assert sig.parameters["limit"].default is None

    def test_audio_dir_default_is_none(self):
        """audio_dir should default to None."""
        sig = inspect.signature(run_job)
        assert sig.parameters["audio_dir"].default is None

    def test_app_support_dir_default_is_none(self):
        """app_support_dir should default to None."""
        sig = inspect.signature(run_job)
        assert sig.parameters["app_support_dir"].default is None

    def test_log_callback_default_is_none(self):
        """log_callback should default to None."""
        sig = inspect.signature(run_job)
        assert sig.parameters["log_callback"].default is None

    def test_run_job_has_docstring(self):
        """run_job should have a docstring."""
        assert run_job.__doc__ is not None
        assert len(run_job.__doc__) > 0
        assert "Run FAQ automation as a job" in run_job.__doc__
