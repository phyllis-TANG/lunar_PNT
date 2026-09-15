import tempfile
import unittest
from pathlib import Path

from pptx import Presentation

from tools.generate_bilingual_ppt import SOURCE, build, parse_slides


class BilingualDeckTests(unittest.TestCase):
    def test_source_has_twelve_bilingual_content_slides(self):
        title, slides = parse_slides(SOURCE)
        self.assertIn("双车协同定位", title)
        self.assertIn("Cooperative Localization", title)
        self.assertEqual(12, len(slides))
        for heading, bullets in slides:
            text = " ".join([heading, *bullets])
            self.assertTrue(any("\u4e00" <= char <= "\u9fff" for char in text))
            self.assertTrue(any(char.isascii() and char.isalpha() for char in text))

    def test_generated_deck_is_readable_and_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "deck.pptx"
            build(SOURCE, output)
            presentation = Presentation(output)
            self.assertEqual(13, len(presentation.slides))
            self.assertEqual(13.333, round(presentation.slide_width / 914400, 3))
            self.assertEqual(7.5, presentation.slide_height / 914400)

if __name__ == "__main__":
    unittest.main()
