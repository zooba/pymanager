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

# Run main build - this fills in BUILD and LAYOUT
run([sys.executable, "-m", "pymsbuild"], cwd=DIRS["root"])

# Overwrite bundled feed. This will be removed eventually
run([sys.executable, "scripts/generate-nuget-index.py", LAYOUT / "bundled" / "index.json"])
