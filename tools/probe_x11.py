#!/usr/bin/env python3
"""Capture a local FM2 X11 window and optionally send focused key presses."""

import argparse
import ctypes as c
from pathlib import Path
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="prefix for PNG captures")
    parser.add_argument("events", nargs="+", help="seconds or seconds:key[+key][/hold][,...]")
    parser.add_argument("--pid", type=int, required=True, help="PID of the FM2 process")
    parser.add_argument("--focus", action="store_true", help="focus the FM2 window before input")
    args = parser.parse_args()
    x11 = c.CDLL("libX11.so.6")
    xtest = c.CDLL("libXtst.so.6")
    pointer, window, integer, string = c.c_void_p, c.c_ulong, c.c_int, c.c_char_p
    ref = c.POINTER
    for lib, name, result, arguments in (
        (x11, "XOpenDisplay", pointer, [string]),
        (x11, "XDefaultRootWindow", window, [pointer]),
        (x11, "XQueryTree", integer,
         [pointer, window, ref(window), ref(window), ref(ref(window)), ref(c.c_uint)]),
        (x11, "XFetchName", integer, [pointer, window, ref(string)]),
        (x11, "XFree", integer, [pointer]),
        (x11, "XInternAtom", window, [pointer, string, integer]),
        (x11, "XGetWindowProperty", integer,
         [pointer, window, window, c.c_long, c.c_long, integer, window, ref(window),
          ref(integer), ref(window), ref(window), ref(pointer)]),
        (x11, "XGetInputFocus", integer, [pointer, ref(window), ref(integer)]),
        (x11, "XSetInputFocus", integer, [pointer, window, integer, window]),
        (x11, "XStringToKeysym", window, [string]),
        (x11, "XKeysymToKeycode", c.c_ubyte, [pointer, window]),
        (x11, "XFlush", integer, [pointer]),
        (xtest, "XTestFakeKeyEvent", integer, [pointer, c.c_uint, integer, window]),
    ):
        function = getattr(lib, name)
        function.restype, function.argtypes = result, arguments

    on_error = c.CFUNCTYPE(integer, pointer, pointer)(lambda *_: 0)
    x11.XSetErrorHandler(on_error)
    display = x11.XOpenDisplay(None)
    if not display:
        parser.exit(1, "No X11 display\n")
    root = x11.XDefaultRootWindow(display)
    pid_atom = x11.XInternAtom(display, b"_NET_WM_PID", 0)

    def pid_of(handle):
        atom, bits, count, remaining, data = window(), integer(), window(), window(), pointer()
        x11.XGetWindowProperty(
            display, handle, pid_atom, 0, 1, 0, 0, c.byref(atom), c.byref(bits),
            c.byref(count), c.byref(remaining), c.byref(data)
        )
        if not data:
            return None
        pid = c.cast(data, ref(window))[0] if bits.value == 32 and count.value == 1 else None
        x11.XFree(data)
        return pid

    def scan(parent):
        root, owner, count = window(), window(), c.c_uint()
        children = ref(window)()
        if not x11.XQueryTree(
            display, parent, c.byref(root), c.byref(owner), c.byref(children), c.byref(count)
        ) or not children:
            return None
        handles = [children[index] for index in range(count.value)]
        x11.XFree(children)
        for handle in handles:
            title = string()
            if x11.XFetchName(display, handle, c.byref(title)) and title:
                name = title.value.decode(errors="replace").casefold()
                x11.XFree(title)
                if ("fm2" in name or "forza" in name) and pid_of(handle) == args.pid:
                    return handle
            found = scan(handle)
            if found:
                return found
        return None

    def press(handle, key):
        name, _, hold = key.partition("/")
        duration = float(hold) if hold else 0.18
        if not 0 < duration <= 30:
            parser.exit(1, "Key duration must be greater than zero and at most 30 seconds.\n")
        focused, revert = window(), integer()
        x11.XGetInputFocus(display, c.byref(focused), c.byref(revert))
        if focused.value != handle and args.focus:
            x11.XSetInputFocus(display, handle, 1, 0)
            x11.XGetInputFocus(display, c.byref(focused), c.byref(revert))
        if focused.value != handle:
            print(f"Skipped {name}: FM2 is not focused.", flush=True)
            return
        codes = [
            x11.XKeysymToKeycode(display, x11.XStringToKeysym(symbol.encode()))
            for symbol in name.split("+")
        ]
        if not all(codes):
            parser.exit(1, f"Unknown key in: {name}\n")
        for code in codes:
            xtest.XTestFakeKeyEvent(display, code, 1, 0)
        x11.XFlush(display)
        try:
            time.sleep(duration)
        finally:
            for code in reversed(codes):
                xtest.XTestFakeKeyEvent(display, code, 0, 0)
            x11.XFlush(display)
        print(f"Sent {name} to FM2 for {duration:g}s.", flush=True)

    start = time.monotonic()
    handle = None
    while time.monotonic() < start + 25 and not handle:
        handle = scan(root)
        if not handle:
            time.sleep(0.2)
    if not handle:
        parser.exit(1, "No FM2 window found\n")

    print(f"FM2 window {handle:#x}", flush=True)
    for event in args.events:
        seconds, _, keys = event.partition(":")
        time.sleep(max(0, start + float(seconds) - time.monotonic()))
        if keys:
            for key in keys.split(","):
                press(handle, key)
                time.sleep(0.5)
        output = f"{args.output}-{seconds}s.png"
        subprocess.run(["import", "-window", hex(handle), "-resize", "960x540>", output],
                       check=True)
        print(output, flush=True)

if __name__ == "__main__":
    main()
