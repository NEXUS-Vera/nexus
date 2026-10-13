"""Offline regression coverage for Python workspace setup and interpreter selection."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SetupTests(unittest.TestCase):
    def test_setup_creates_and_reuses_venv_and_tests_use_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / "scripts"
            scripts.mkdir()
            for name in ("setup.sh", "run-tests.sh"):
                shutil.copy2(ROOT / "scripts" / name, scripts / name)
            shutil.copy2(ROOT / "Makefile", root / "Makefile")
            for name in ("agents", "apps", "packages", "tools"):
                (root / name).mkdir()
            (root / "tools" / "test_example.py").touch()
            bin_dir = root / "bin"
            bin_dir.mkdir()
            python = bin_dir / "python3.13"
            python.write_text(
                "#!/bin/bash\n"
                'echo "$0 $*" >> "$TEST_LOG"\n'
                'if [[ "$1 $2" == "-m venv" ]]; then\n'
                '  mkdir -p "$3/bin"\n'
                '  cp "$0" "$3/bin/python"\n'
                "fi\n"
            )
            python.chmod(0o755)
            pnpm = bin_dir / "pnpm"
            pnpm.write_text("#!/bin/bash\nexit 0\n")
            pnpm.chmod(0o755)
            log = root / "calls.log"
            env = os.environ.copy()
            env.pop("PYTHON", None)
            env.update(PATH=f"{bin_dir}:/usr/bin:/bin", TEST_LOG=str(log))
            for _ in range(2):
                subprocess.run(
                    ["make", "setup"],
                    cwd=root,
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            subprocess.run(
                ["make", "test-unit"],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            # Direct script invocation also uses the repository environment.
            subprocess.run(
                [str(scripts / "run-tests.sh"), "unit"],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            calls = log.read_text().splitlines()
            self.assertEqual(sum("-m venv" in call for call in calls), 1)
            self.assertEqual(sum("-m pip install .[dev]" in call for call in calls), 2)
            test_calls = [call for call in calls if "-m pytest" in call]
            self.assertEqual(len(test_calls), 2)
            self.assertTrue(
                all(call.startswith(str(root / ".venv" / "bin")) for call in test_calls)
            )


if __name__ == "__main__":
    unittest.main()
