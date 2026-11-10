import tempfile
import unittest
from pathlib import Path

from watcher import config

GOOD = """
[watch]
zipcode = "95051"
[llm]
bulk_model = "claude-haiku-5-5"
report_model = "claude-sonnet-5-5"
[budget]
daily_cap_usd = 1.0
"""


def write(text):
    d = tempfile.mkdtemp()
    p = Path(d) / "config.toml"
    p.write_text(text)
    return p


class ConfigTests(unittest.TestCase):
    def test_loads_good_config(self):
        p = write(GOOD)
        cfg = config.load(p)
        self.assertEqual(cfg.zipcode, "95051")
        self.assertEqual(cfg.daily_cap_usd, 1.0)
        self.assertEqual(cfg.db_path, p.parent / "data" / "watcher.db")

    def test_bad_zipcode(self):
        with self.assertRaises(ValueError):
            config.load(write(GOOD.replace("95051", "9505")))

    def test_missing_key(self):
        with self.assertRaises(ValueError):
            config.load(write(GOOD.replace("[budget]\ndaily_cap_usd = 1.0", "")))

    def test_nonpositive_cap(self):
        with self.assertRaises(ValueError):
            config.load(write(GOOD.replace("1.0", "0")))

    def test_repo_config_is_valid(self):
        config.load()


if __name__ == "__main__":
    unittest.main()
