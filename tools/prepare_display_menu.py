#!/usr/bin/env python3
"""Prepare a local Options flow for the supported European FM2 disc."""

import argparse
import hashlib
from pathlib import Path
import re
from xml.etree import ElementTree
from zipfile import ZipFile


OPTIONS = "Flows/Options.xml"
STOCK_SHA256 = "44f4caaea93740f5d0236a4029e1859167500cb1c81a8680f2e627a6ab6ae20e"
QUERY = r'(SELECT \* FROM GameOptionCategories, GameOptionGroupMap WHERE GroupId=4 [^"]+)'
ROW = """ UNION ALL SELECT 1000, 'FM2Display', 'Display " .. string.char(38) .. " Performance', 4, 1000"""
HELP = '<string id="IDS_FM2Display_Help" text="Linux display and performance settings."/>'
TITLE = "UI.Strings.SceneTitle = UI:getLocDisplayString("
BRANCH = r"""
<choice event="FM2Display">
    <popup path="GAME:\Media\UI\Scenes\PopUp_Message.xgf">
        PopupTitle = "Display " .. string.char(38) .. " Performance"
        PopupMessage = "Window Mode"
        HelpButtonTexts = {
            A = "{colour='255 255 255 255'}Toggle Fullscreen",
            B = "{colour='255 255 255 255'}[UI.Strings.IDS_Back]"
        }
        PopupFuncs = {
            A = function() UI:fireEvent("FM2ToggleFullscreen") end,
            B = function() UI:fireEvent("FM2DisplayBack") end
        }
    </popup>
    <GoToStart/>
</choice>
"""


def replace_once(text, anchor, replacement):
    if text.count(anchor) != 1:
        raise ValueError(f"unexpected Options flow anchor: {anchor}")
    return text.replace(anchor, replacement)


def patch_options(stock):
    text = stock.decode("utf-8")
    text, count = re.subn(QUERY, lambda m: m[1] + ROW, text)
    if count != 6:
        raise ValueError("unexpected number of Options category queries")
    text = replace_once(text, "</strings>", HELP + "\n</strings>")
    text = replace_once(text, '<choice event="Credits">', BRANCH + '<choice event="Credits">')
    text = replace_once(
        text, TITLE,
        'UI.Strings.SceneTitle = UI.Flow.OptionCategory == "FM2Display" '
        'and ("Display " .. string.char(38) .. " Performance") or UI:getLocDisplayString(',
    )
    # The runtime parser owns the original buffer. Fit within that allocation.
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"(?m)^[ \t]+", "", text)
    ElementTree.fromstring(text)
    updated = text.encode()
    if len(updated) > len(stock):
        raise ValueError("updated Options flow does not fit in the original buffer")
    return updated


def prepare(disc, output):
    with ZipFile(disc / "Media" / "UI.zip") as archive:
        stock = archive.read(OPTIONS)
    if hashlib.sha256(stock).hexdigest() != STOCK_SHA256:
        raise ValueError("unexpected stock European Options flow")
    updated = patch_options(stock)
    output.mkdir(parents=True, exist_ok=True)
    for name, payload in (("stock.xml", stock), ("options.xml", updated)):
        pending = output / (name + ".tmp")
        pending.write_bytes(payload)
        pending.replace(output / name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("disc", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        prepare(args.disc, args.output)
    except (OSError, ValueError, ElementTree.ParseError, KeyError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")


if __name__ == "__main__":
    main()
