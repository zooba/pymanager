import os
import sys
import zipfile

from pathlib import Path
from subprocess import check_call as run

from _make_helper import (
    download_zip_into,
    get_dirs,
    get_msbuild,
    get_msix_version,
    get_output_name,
    get_sdk_bins,
    rmtree,
    unlink,
)

MSBUILD_CMD = get_msbuild()
SDK_BINS = get_sdk_bins()

MAKEAPPX = SDK_BINS / "makeappx.exe"
MAKEPRI = SDK_BINS / "makepri.exe"

for tool in [MAKEAPPX, MAKEPRI]:
    if not tool.is_file():
        print("Unable to locate Windows Kit tool", tool.name, file=sys.stderr)
        sys.exit(3)

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
run([sys.executable, "scripts/generate-nuget-index.py", LAYOUT / "index.json"])

# Calculate output names (must be after building)
NAME = get_output_name(DIRS)
VERSION = get_msix_version(DIRS)
DIST_MSIX = DIST / f"{NAME}.msix"
DIST_APPXSYM = DIST / f"{NAME}.appxsym"
DIST_MSIXUPLOAD = DIST / f"{NAME}.msixupload"
DIST_MSI = DIST / f"{NAME}.msi"

unlink(DIST_MSIX, DIST_APPXSYM, DIST_MSIXUPLOAD, DIST_MSI)

# Generate resources info in LAYOUT
run([MAKEPRI, "new", "/o",
              "/pr", LAYOUT,
              "/cf", SRC / "python/resources.xml",
              "/of", LAYOUT / "_resources.pri",
              "/mf", "appx"])

# Clean up non-shipping files from LAYOUT
unlink(
    *LAYOUT.rglob("*.pdb"),
    *LAYOUT.rglob("*.pyc"),
    *LAYOUT.rglob("__pycache__"),
)

# Package into DIST
run([MAKEAPPX, "pack", "/o", "/d", LAYOUT, "/p", DIST_MSIX])

# Pack symbols
print("Packing symbols to", DIST_APPXSYM)
with zipfile.ZipFile(DIST_APPXSYM, "w") as zf:
    for f in BUILD.rglob("*.pdb"):
        zf.write(f, arcname=f.name)

# Pack upload MSIX for Store
with zipfile.ZipFile(DIST_MSIXUPLOAD, "w") as zf:
    zf.write(DIST_MSIX, arcname=DIST_MSIX.name)
    zf.write(DIST_APPXSYM, arcname=DIST_APPXSYM.name)


# Package into MSI
pydllname = [p.stem for p in LAYOUT.glob("python*.dll")][0]
pydsuffix = [p.name.partition(".")[-1] for p in LAYOUT.glob("manage*.pyd")][0]

run([
    *MSBUILD_CMD,
    "-Restore",
    SRC / "python/msi.wixproj",
    "/p:Platform=x64",
    "/p:Configuration=Release",
    f"/p:OutputPath={DIST}",
    f"/p:IntermediateOutputPath={TEMP}\\",
    f"/p:TargetName={NAME}",
    f"/p:Version={VERSION}",
    f"/p:PythonDLLName={pydllname}",
    f"/p:PydSuffix={pydsuffix}",
    f"/p:LayoutDir={LAYOUT}",
])
