import pandas as pd
import pytest

from auto_tts import ClientConfig


@pytest.fixture
def default_config():
    return ClientConfig(
        base_url="https://app.anylive.jp/scripts/TEST",
        version_template="Test_Template",
        voice_name="Test Voice",
        max_scripts_per_version=10,
        enable_voice_selection=False,
        enable_product_info=False,
        csv_columns={
            "product_number": "No",
            "product_name": "Product Name",
            "script_content": "TH Script",
            "audio_code": "Audio Code",
        },
    )


@pytest.fixture
def sample_csv_df():
    """A simple DataFrame mimicking a typical CSV with 2 products."""
    return pd.DataFrame(
        {
            "No": ["01", "01", "01", "02", "02"],
            "Product Name": [
                "JBL Speaker",
                "JBL Speaker",
                "JBL Speaker",
                "Samsung TV",
                "Samsung TV",
            ],
            "Scene": ["A", "B", "C", "A", "B"],
            "part": ["1", "2", "3", "1", "2"],
            "TH Script": ["สวัสดี", "ทดสอบ", "สคริปต์", "ซัมซุง", "ทีวี"],
            "Audio Code": ["JBL_01", "JBL_02", "JBL_03", "SAM_01", "SAM_02"],
            "col_h": ["", "", "", "", ""],
            "PIC": ["", "", "", "", ""],
        }
    )


@pytest.fixture
def sample_config_dict():
    return {
        "base_url": "https://app.anylive.jp/scripts/TEST",
        "version_template": "Test_Template",
        "voice_name": "Test Voice",
        "max_scripts_per_version": 10,
        "enable_voice_selection": False,
        "enable_product_info": False,
        "csv_columns": {
            "product_number": "No",
            "product_name": "Product Name",
            "script_content": "TH Script",
            "audio_code": "Audio Code",
        },
    }
