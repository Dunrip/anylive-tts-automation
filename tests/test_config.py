import json

import pytest

from auto_tts import ClientConfig, load_config


class TestLoadConfig:
    def test_valid_config(self, tmp_path, sample_config_dict):
        config_file = tmp_path / "test.json"
        config_file.write_text(json.dumps(sample_config_dict))
        config = load_config(str(config_file))
        assert isinstance(config, ClientConfig)
        assert config.base_url == "https://app.anylive.jp/scripts/TEST"
        assert config.max_scripts_per_version == 10

    def test_missing_required_fields(self, tmp_path):
        config_file = tmp_path / "bad.json"
        config_file.write_text(json.dumps({"base_url": "https://example.com"}))
        with pytest.raises(TypeError):
            load_config(str(config_file))

    def test_cli_overrides(self, tmp_path, sample_config_dict):
        config_file = tmp_path / "test.json"
        config_file.write_text(json.dumps(sample_config_dict))
        config = load_config(str(config_file), cli_overrides={"voice_name": "Override Voice"})
        assert config.voice_name == "Override Voice"

    def test_nonexistent_file(self):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config("/nonexistent/path/config.json")
