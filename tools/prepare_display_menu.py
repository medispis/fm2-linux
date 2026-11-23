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
DISPLAY_OPTIONS = (
    ("FM2WindowMode", "Window Mode", "Switch between windowed and fullscreen.",
     "FM2ToggleFullscreen", "Toggle Fullscreen"),
    ("FM2AspectMode", "Aspect Ratio", "Switch between Original (fit) and Stretch.",
     "FM2ToggleAspect", "Toggle Aspect Ratio"),
    ("FM2PerformanceHud", "Performance HUD", "Show or hide guest FPS and frame time.",
     "FM2ToggleHud", "Toggle HUD"),
    ("FM2RefreshRate", "Refresh Rate", "Switch between Original (60 Hz) and Experimental "
     "(120 Hz). Restart required. 120 Hz may tear and does not guarantee 120 FPS.",
     "FM2ToggleRefresh", "Toggle Refresh Rate"),
    ("FM2DisplayDefaults", "Restore Display Defaults", "Restore the port's display settings? "
     "Refresh rate changes after restart.", "FM2RestoreDisplay", "Restore Defaults"),
)


def display_branch():
    rows = " UNION ALL ".join(
        f"SELECT {1001 + i} AS Id, '{key}' AS CategoryName, '{label}' AS DisplayName, "
        f"4 AS GroupId, {1001 + i} AS CatId"
        for i, (key, label, _, _, _) in enumerate(DISPLAY_OPTIONS)
    )
    def popup_message(key, description):
        if key == "FM2RefreshRate":
            return r'''
        local status = UI:fireEvent("FM2ReadRefreshStatus")
        if type(status) ~= "string" then status = "Refresh status unavailable." end
        PopupMessage = status .. "\nRestart to apply. 120 Hz is experimental."'''
        return f'\n        PopupMessage = "{description}"'

    choices = "".join(rf"""
<choice event="{key}">
    <popup path="GAME:\Media\UI\Scenes\PopUp_Message.xgf">
        PopupTitle = "{label}"{popup_message(key, description)}
        HelpButtonTexts = {{
            A = "{{colour='255 255 255 255'}}{accept}",
            B = "{{colour='255 255 255 255'}}[UI.Strings.IDS_Back]"
        }}
        PopupFuncs = {{
            A = function() UI:fireEvent("{event}") end,
            B = function() UI:fireEvent("FM2DisplayBack") end
        }}
    </popup>
</choice>
""" for key, label, description, event, accept in DISPLAY_OPTIONS)
    return rf"""
<choice event="FM2Display">
    <scene path="GAME:\Media\UI\Scenes\P_Scenes\P_OPT\P_OPT.xgf" canGoBack="true">
        <OnEnter>
            UI.Flow.SceneTitle = "Display " .. string.char(38) .. " Performance"
            OptionCategories = DB:execute("{rows}")
            HelpButtonTexts = {{
                A = "{{colour='255 255 255 255'}}[UI.Strings.IDS_Select]",
                B = "{{colour='255 255 255 255'}}[UI.Strings.IDS_Back]"
            }}
        </OnEnter>
    </scene>
    <logic>UI:setEvent(UI.Flow.OptionCategory)</logic>
    <branch>{choices}</branch>
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
    help_strings = "".join(
        f'<string id="IDS_{key}_Help" text="{description}"/>\n'
        for key, _, description, _, _ in DISPLAY_OPTIONS
    )
    text = replace_once(text, "</strings>", HELP + "\n" + help_strings + "</strings>")
    text = replace_once(text, '<choice event="Credits">',
                        display_branch() + '<choice event="Credits">')
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
