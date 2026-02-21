import json
import logging

from auto_tts import Report, Version, generate_report

logger = logging.getLogger("auto_tts")


class TestGenerateReport:
    def _make_versions(self):
        v1 = Version(
            name="01_Widget",
            products=["Widget"],
            scripts=["s1", "s2"],
            audio_codes=["a1", "a2"],
            product_number="01",
            success=True,
        )
        v2 = Version(
            name="02_Gadget",
            products=["Gadget"],
            scripts=["s3"],
            audio_codes=["a3"],
            product_number="02",
            success=False,
            error="Timeout",
        )
        return [v1, v2]

    def test_success_failure_counting(self, default_config):
        versions = self._make_versions()
        report = generate_report(versions, default_config, "20260101_120000", logger, logs_dir="/tmp")
        assert report.total == 2
        assert report.successful == 1
        assert report.failed == 1

    def test_json_file_output(self, tmp_path, default_config):
        versions = self._make_versions()
        generate_report(versions, default_config, "20260101_120000", logger, logs_dir=str(tmp_path))
        report_file = tmp_path / "report_20260101_120000.json"
        assert report_file.exists()
        data = json.loads(report_file.read_text())
        assert data["total"] == 2
        assert len(data["versions"]) == 2

    def test_report_dataclass_structure(self, default_config):
        versions = self._make_versions()
        report = generate_report(versions, default_config, "20260101_120000", logger, logs_dir="/tmp")
        assert isinstance(report, Report)
        assert isinstance(report.versions, list)
        assert report.versions[0]["version"] == "01_Widget"
        assert report.versions[1]["error"] == "Timeout"
