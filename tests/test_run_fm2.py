import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import unittest


class RunFm2Tests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        tools = self.root / "tools"
        tools.mkdir()
        self.launcher = tools / "run-fm2.sh"
        shutil.copyfile(
            Path(__file__).resolve().parents[1] / "tools" / self.launcher.name, self.launcher
        )
        self.executable = self.root / "build" / "smoke-native" / "fm2"
        self.executable.parent.mkdir(parents=True)
        self.executable.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
        self.executable.chmod(0o755)
        disc = self.root / "private" / "disc"
        (disc / "Media").mkdir(parents=True)
        (disc / "default.xex").touch()

    def launch(self, *args, env=None):
        return subprocess.run(
            ["sh", self.launcher, *args], capture_output=True, text=True, env=env
        )

    def test_default_keeps_original_timing(self):
        result = self.launch("--hid.mnk_mode=true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("--ui.video_mode_refresh_rate", result.stdout)
        self.assertNotIn("--gpu.vsync", result.stdout)
        self.assertNotIn("--gpu.vulkan.unsynced_present", result.stdout)
        self.assertIn("--hid.mnk_mode=true", result.stdout.splitlines())

    def test_audio_prefers_local_pulse_server_and_preserves_overrides(self):
        self.executable.write_text(
            '#!/bin/sh\nprintf "%s\\n" "${SDL_AUDIO_DRIVER-unset}"\n'
        )
        runtime = self.root / "runtime"
        pulse = runtime / "pulse"
        pulse.mkdir(parents=True)
        env = {**os.environ, "XDG_RUNTIME_DIR": str(runtime)}
        env.pop("SDL_AUDIO_DRIVER", None)
        self.assertEqual(self.launch(env=env).stdout.strip(), "unset")
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(pulse / "native"))
            self.assertEqual(
                self.launch(env=env).stdout.strip(), "pulseaudio,pipewire,alsa"
            )
            for override in ("pipewire", ""):
                with self.subTest(override=override):
                    result = self.launch(env={**env, "SDL_AUDIO_DRIVER": override})
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip(), override)

    def test_experimental_mode_sets_guest_refresh_and_preserves_extra_options(self):
        result = self.launch("--experimental-120fps", "--hid.mnk_mode=true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[-4:], [
            "--ui.video_mode_refresh_rate=120",
            "--gpu.vsync=true",
            "--gpu.vulkan.unsynced_present=true",
            "--hid.mnk_mode=true",
        ])
        self.assertIn("not validated", result.stderr)

    def test_original_timing_overrides_saved_preference(self):
        result = self.launch("--original-timing")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[-3:], [
            "--ui.video_mode_refresh_rate=60",
            "--gpu.vsync=true",
            "--gpu.vulkan.unsynced_present=false",
        ])

    def test_experimental_mode_rejects_conflicting_options(self):
        for override in (
            "--gpu.vsync=false",
            "--no-gpu.vsync",
            "--video_mode_refresh_rate=60",
            "--gpu.vulkan.unsynced_present=false",
        ):
            with self.subTest(override=override):
                result = self.launch("--experimental-120fps", override)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("VSync overrides", result.stderr)

    def test_setup_launch_check_does_not_start_game(self):
        (self.root / "tools" / "configure_smoke.py").touch()
        strings = self.root / "private" / "disc" / "Media" / "StringTables" / "EN"
        strings.mkdir(parents=True)
        (strings / "AIDiff.str").touch()
        mock_bin = self.root / "bin"
        mock_bin.mkdir()
        ldd = mock_bin / "ldd"
        ldd.write_text("#!/bin/sh\nexit 0\n")
        ldd.chmod(0o755)
        env = {**os.environ, "PATH": f"{mock_bin}:{os.environ['PATH']}"}
        missing = self.launch("--check", env=env)
        self.assertEqual(missing.returncode, 1)
        self.assertIn("Missing the Vulkan runtime", missing.stderr)
        (self.executable.parent / "librexgpu-xenos-vulkan.so").touch()
        missing = self.launch("--check", env=env)
        self.assertEqual(missing.returncode, 1)
        self.assertIn("Missing native display menu data", missing.stderr)
        menu = self.root / "private" / "display-menu"
        menu.mkdir()
        for name in ("stock.xml", "options.xml"):
            (menu / name).write_text("<flow/>\n")
        art = self.root / "private/disc/Media/UI/Textures/P_Map/P_OPT"
        art.mkdir(parents=True)
        for category in ("FM2WindowMode", "FM2AspectMode", "FM2PerformanceHud",
                         "FM2RefreshRate", "FM2RenderResolution", "FM2DisplayDefaults"):
            (art / f"P_OPT_ICON_{category}.xds").write_bytes(b"art")
        missing = self.launch("--check", env=env)
        self.assertEqual(missing.returncode, 1)
        self.assertIn("Missing native display menu artwork", missing.stderr)
        (art / "P_OPT_ICON_FM2Display.xds").write_bytes(b"art")
        result = self.launch("--check", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            "FM2 launch files and shared libraries verified; the game was not started.",
        )
        self.assertFalse((self.root / "private" / "fm2-state").exists())

    def test_native_rendering_override_pairs_with_timing_override(self):
        for args in (("--native-rendering", "--original-timing"),
                     ("--original-timing", "--native-rendering")):
            with self.subTest(args=args):
                result = self.launch(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("--ui.video_mode_refresh_rate=60", result.stdout.splitlines())
                for axis in ("x", "y"):
                    self.assertIn(f"--gpu.resolution_scale_{axis}=1", result.stdout.splitlines())
        conflict = self.launch("--native-rendering", "--gpu.resolution_scale_x=2")
        self.assertEqual(conflict.returncode, 2)
        self.assertIn("render scale overrides", conflict.stderr)
