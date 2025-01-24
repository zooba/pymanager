import os
import sys
import zipfile

from pathlib import Path
from subprocess import check_call as run

from _make_helper import (
    copyfile,
    get_dirs,
    get_msix_version,
    get_output_name,
    get_sdk_bins,
    unlink,
)

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
print("Packing Store upload to", DIST_MSIXUPLOAD)
with zipfile.ZipFile(DIST_MSIXUPLOAD, "w") as zf:
    zf.write(DIST_MSIX, arcname=DIST_MSIX.name)
    zf.write(DIST_APPXSYM, arcname=DIST_APPXSYM.name)

print("Copying appinstaller file to", DIST)
copyfile(LAYOUT / "pymanager.appinstaller", DIST / "pymanager.appinstaller")
