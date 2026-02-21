import logging

import pandas as pd

from auto_tts import parse_csv_data

logger = logging.getLogger("auto_tts")


class TestSanitizeProductName:
    """Tests for the sanitize_product_name helper nested inside parse_csv_data.

    We exercise it indirectly through parse_csv_data version naming.
    """

    def _version_names(self, product_name, config):
        df = pd.DataFrame(
            {
                "No": ["01"],
                "Product Name": [product_name],
                "Scene": ["A"],
                "part": ["1"],
                "TH Script": ["test"],
                "Audio Code": ["code"],
                "col_h": [""],
                "PIC": [""],
            }
        )
        versions = parse_csv_data(df, config, logger)
        return [v.name for v in versions]

    def test_spaces_converted_to_underscores(self, default_config):
        names = self._version_names("JBL Speaker Pro", default_config)
        assert names == ["01_JBL_Speaker_Pro"]

    def test_special_characters_removed(self, default_config):
        names = self._version_names("Product (v2) #1!", default_config)
        # Parentheses, hash, exclamation should be stripped
        assert names == ["01_Product_v2_1"]

    def test_thai_characters_preserved(self, default_config):
        names = self._version_names("ลำโพง JBL", default_config)
        assert names == ["01_ลำโพง_JBL"]

    def test_thai_tone_marks_preserved(self, default_config):
        """Tone marks (่ ้ ๊ ๋) and vowel marks (ิ ี ึ ื ุ ู ั) must survive sanitization."""
        names = self._version_names("น้ำหอม", default_config)
        assert "น้ำหอม" in names[0]

    def test_empty_product_name(self, default_config):
        names = self._version_names("", default_config)
        assert names == ["01_"]


class TestParseCsvData:
    def test_standard_csv_multiple_products(self, default_config, sample_csv_df):
        versions = parse_csv_data(sample_csv_df, default_config, logger)
        assert len(versions) == 2
        assert versions[0].name == "01_JBL_Speaker"
        assert len(versions[0].scripts) == 3
        assert versions[1].name == "02_Samsung_TV"
        assert len(versions[1].scripts) == 2

    def test_forward_fill_empty_cells(self, default_config):
        df = pd.DataFrame(
            {
                "No": ["01", "", "", "02", ""],
                "Product Name": ["Widget", "", "", "Gadget", ""],
                "Scene": ["A", "B", "C", "A", "B"],
                "part": ["1", "2", "3", "1", "2"],
                "TH Script": ["s1", "s2", "s3", "s4", "s5"],
                "Audio Code": ["a1", "a2", "a3", "a4", "a5"],
                "col_h": [""] * 5,
                "PIC": [""] * 5,
            }
        )
        versions = parse_csv_data(df, default_config, logger)
        assert len(versions) == 2
        assert len(versions[0].scripts) == 3  # Widget: 3 rows
        assert len(versions[1].scripts) == 2  # Gadget: 2 rows

    def test_header_row_filtered(self, default_config):
        """Rows containing the header text 'Product Name' should be dropped."""
        df = pd.DataFrame(
            {
                "No": ["No", "01"],
                "Product Name": ["Product Name", "Widget"],
                "Scene": ["Scene", "A"],
                "part": ["part", "1"],
                "TH Script": ["TH Script", "hello"],
                "Audio Code": ["Audio Code", "a1"],
                "col_h": ["", ""],
                "PIC": ["", ""],
            }
        )
        versions = parse_csv_data(df, default_config, logger)
        assert len(versions) == 1
        assert versions[0].scripts == ["hello"]

    def test_version_splitting_overflow(self, default_config):
        """Products with >max_scripts should split into _v2, _v3, etc."""
        default_config.max_scripts_per_version = 3
        rows = 8
        df = pd.DataFrame(
            {
                "No": ["01"] * rows,
                "Product Name": ["BigProduct"] * rows,
                "Scene": [f"S{i}" for i in range(rows)],
                "part": [str(i) for i in range(rows)],
                "TH Script": [f"script_{i}" for i in range(rows)],
                "Audio Code": [f"audio_{i}" for i in range(rows)],
                "col_h": [""] * rows,
                "PIC": [""] * rows,
            }
        )
        versions = parse_csv_data(df, default_config, logger)
        assert len(versions) == 3
        assert versions[0].name == "01_BigProduct"
        assert versions[1].name == "01_BigProduct_v2"
        assert versions[2].name == "01_BigProduct_v3"
        assert len(versions[0].scripts) == 3
        assert len(versions[1].scripts) == 3
        assert len(versions[2].scripts) == 2

    def test_single_product_single_script(self, default_config):
        df = pd.DataFrame(
            {
                "No": ["01"],
                "Product Name": ["Solo"],
                "Scene": ["A"],
                "part": ["1"],
                "TH Script": ["only script"],
                "Audio Code": ["only_audio"],
                "col_h": [""],
                "PIC": [""],
            }
        )
        versions = parse_csv_data(df, default_config, logger)
        assert len(versions) == 1
        assert versions[0].scripts == ["only script"]

    def test_empty_dataframe(self, default_config):
        df = pd.DataFrame(
            columns=["No", "Product Name", "Scene", "part", "TH Script", "Audio Code", "col_h", "PIC"]
        )
        versions = parse_csv_data(df, default_config, logger)
        assert versions == []
