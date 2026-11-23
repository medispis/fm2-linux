import hashlib
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, ZipFile


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from prepare_display_menu import DISPLAY_OPTIONS, OPTIONS, QUERY, TITLE, patch_options, prepare


class PrepareDisplayMenuTests(unittest.TestCase):
    @staticmethod
    def stock_flow():
        query = (
            "SELECT * FROM GameOptionCategories, GameOptionGroupMap "
            "WHERE GroupId=4 AND CatId=Id"
        )
        return (
            "<flow><!--" + "padding " * 1000 + "--><strings></strings><logic>\n"
            + f'DB:execute("{query}")\n' * 6
            + TITLE + "category)\n"
            + '</logic><branch><choice event="Credits"></choice></branch></flow>'
        ).encode()

    def test_native_branch_and_stock_category_are_both_present(self):
        stock = self.stock_flow()
        updated = patch_options(stock)
        self.assertLessEqual(len(updated), len(stock))
        flow = ElementTree.fromstring(updated)
        self.assertIsNotNone(flow.find('.//choice[@event="Credits"]'))
        display = flow.find('.//choice[@event="FM2Display"]')
        scene = display.find("scene")
        self.assertEqual(scene.get("path"),
                         r"GAME:\Media\UI\Scenes\P_Scenes\P_OPT\P_OPT.xgf")
        for key, _, _, action, _ in DISPLAY_OPTIONS:
            popup = display.find(f'./branch/choice[@event="{key}"]/popup')
            self.assertEqual(popup.get("path"), r"GAME:\Media\UI\Scenes\PopUp_Message.xgf")
            self.assertIn(f'UI:fireEvent("{action}")', popup.text)
            self.assertIn('UI:fireEvent("FM2DisplayBack")', popup.text)
            self.assertNotIn("dofile", popup.text)
            if key == "FM2RefreshRate":
                self.assertIn('UI:fireEvent("FM2ReadRefreshStatus")', popup.text)
                self.assertIn("Restart to apply", popup.text)
        self.assertIsNotNone(display.find("GoToStart"))
        self.assertIsNotNone(flow.find('.//string[@id="IDS_FM2Display_Help"]'))

        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.executescript("""
            CREATE TABLE GameOptionCategories (Id INT, CategoryName TEXT, DisplayName TEXT);
            CREATE TABLE GameOptionGroupMap (GroupId INT, CatId INT);
            INSERT INTO GameOptionCategories VALUES (13, 'Credits', 'Credits');
            INSERT INTO GameOptionGroupMap VALUES (4, 13);
        """)
        display_query = re.search(r'DB:execute\("([^"]+)"\)', scene.findtext("OnEnter"))[1]
        self.assertEqual(
            [row[1:3] for row in db.execute(display_query)],
            [(key, label) for key, label, _, _, _ in DISPLAY_OPTIONS],
        )
        lua = flow.findtext("logic")
        self.assertEqual(lua.count('" .. string.char(38) .. "'), 7)
        queries = re.findall(QUERY, lua.replace('" .. string.char(38) .. "', "&"))
        self.assertEqual(len(queries), 6)
        for query in queries:
            self.assertEqual(db.execute(query).fetchall(), [
                (13, "Credits", "Credits", 4, 13),
                (1000, "FM2Display", "Display & Performance", 4, 1000),
            ])

    def test_rejects_unknown_flow(self):
        with self.assertRaisesRegex(ValueError, "Options category queries"):
            patch_options(b"<flow/>")

    def test_setup_preserves_stock_archive_and_is_repeatable(self):
        stock = self.stock_flow()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / "disc" / "Media"
            media.mkdir(parents=True)
            archive_path = media / "UI.zip"
            with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
                archive.writestr(OPTIONS, stock)
            original_archive = archive_path.read_bytes()
            output = root / "display-menu"
            with self.assertRaisesRegex(ValueError, "unexpected stock European Options flow"):
                prepare(media.parent, output)
            self.assertFalse(output.exists())
            with patch("prepare_display_menu.STOCK_SHA256", hashlib.sha256(stock).hexdigest()):
                prepare(media.parent, output)
                generated = (output / "options.xml").read_bytes()
                prepare(media.parent, output)
            self.assertEqual((output / "stock.xml").read_bytes(), stock)
            self.assertEqual((output / "options.xml").read_bytes(), generated)
            self.assertEqual(archive_path.read_bytes(), original_archive)
