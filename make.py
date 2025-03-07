import os
import subprocess
import sys
from subprocess import check_call as run
from _make_helper import get_dirs, rmtree, unlink

DIRS = get_dirs()
BUILD = DIRS["build"]
TEMP = DIRS["temp"]
LAYOUT = DIRS["out"]
SRC = DIRS["src"]
DIST = DIRS["dist"]

if "-i" not in sys.argv:
    rmtree(BUILD)
    rmtree(TEMP)
    rmtree(LAYOUT)

ref = "none"
try:
    if os.getenv("BUILD_SOURCEBRANCH"):
        ref = os.getenv("BUILD_SOURCEBRANCH")
    else:
        with subprocess.Popen(
            ["git", "describe", "HEAD", "--tags"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        ) as p:
            out, err = p.communicate()
        if out:
            ref = "refs/tags/" + out.decode().strip()
    ref = os.getenv("OVERRIDE_REF", ref)
    print("Building for tag", ref)
except subprocess.CalledProcessError:
    pass

# Run main build - this fills in BUILD and LAYOUT
run([sys.executable, "-m", "pymsbuild", "wheel"],
    cwd=DIRS["root"],
    env={**os.environ, "BUILD_SOURCEBRANCH": ref})

# Overwrite bundled feed. This will be removed eventually
run([sys.executable, "scripts/generate-nuget-index.py", LAYOUT / "bundled" / "index.json"])

# Bundle current latest release
run([LAYOUT / "py-manager.exe", "install", "-v", "-f", "--download", TEMP / "bundle", "default"])
(TEMP / "bundle" / "index.json").rename(LAYOUT / "bundled" / "fallback-index.json")
for f in (TEMP / "bundle").iterdir():
    f.rename(LAYOUT / "bundled" / f.name)
