#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
import unittest

from scripts.tests.v3_browser_test_utils import ROOT


class V3PageBuildTests(unittest.TestCase):
    def test_v3_page_build_check_passes(self) -> None:
        process = subprocess.run(
            [sys.executable, "scripts/build/build_v3_page.py", "--check"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertIn("v3 page mirror is in sync", process.stdout)

    def test_legacy_web_bundle_builder_uses_docs_v3_as_source_of_truth(self) -> None:
        source = (ROOT / "scripts" / "dev" / "build_web_client_bundle.py").read_text(encoding="utf-8")
        self.assertIn('V3_MAPLIBRE_SOURCE_HTML = DOCS_DIR / "v3.html"', source)
        self.assertIn("V3_LOCAL_MIRROR_HTML.write_text(v3_html", source)


if __name__ == "__main__":
    unittest.main()
