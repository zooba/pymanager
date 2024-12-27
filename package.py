import os
import shutil
import sys
import winreg
import zipfile

from pathlib import Path
from shutil import rmtree
from subprocess import check_call as run
from xml.etree import ElementTree as ET


APPXMANIFEST_NS = {
    "": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
    "m": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
    "uap": "http://schemas.microsoft.com/appx/manifest/uap/windows10",
    "rescap": "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities",
    "rescap4": "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities/4",
    "desktop4": "http://schemas.microsoft.com/appx/manifest/desktop/windows10/4",
    "desktop6": "http://schemas.microsoft.com/appx/manifest/desktop/windows10/6",
    "uap3": "http://schemas.microsoft.com/appx/manifest/uap/windows10/3",
    "uap4": "http://schemas.microsoft.com/appx/manifest/uap/windows10/4",
    "uap5": "http://schemas.microsoft.com/appx/manifest/uap/windows10/5",
}

def read_appxmanifest_identity(path):
    for k, v in APPXMANIFEST_NS.items():
        ET.register_namespace(k, v)
    ET.register_namespace("", APPXMANIFEST_NS["m"])

    with open(path, "r", encoding="utf-8") as f:
        xml = ET.parse(f)

    node = xml.find("m:Identity", APPXMANIFEST_NS)
    return {k: node.get(k) for k in node.keys()}


def get_sdk_bins():
    sdk = os.getenv("WindowsSdkDir")
    if not sdk:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows Kits\Installed Roots",
            access=winreg.KEY_READ | winreg.KEY_WOW64_32KEY,
        ) as key:
            sdk, keytype = winreg.QueryValueEx(key, "KitsRoot10")

        if keytype != winreg.REG_SZ:
            print("Unexpected registry value for Windows Kits root.", file=sys.stderr)
            print("Try setting %WindowsSdkDir%", file=sys.stderr)
            sys.exit(1)

    sdk = Path(sdk)

    sdk_ver = os.getenv("WindowsSDKVersion", "10.*")

    bins = list((sdk / "bin").glob(sdk_ver))[-1] / "x64"
    if not bins.is_dir():
        print("Unable to locate Windows Kits binaries.", file=sys.stderr)
        sys.exit(2)

    return bins


def get_output_info():
    # TODO: Allow overriding these (and detect PYMSBUILD_* env overrides)
    root = Path.cwd()
    src = root / "src"
    dist = root / "dist"
    build = Path.cwd() / "build/bin"
    # This directory name somewhat hard-coded in _msbuild.py
    out = root / "python-manager"

    p = src / "python" / "appxmanifest.xml"
    out_name = "python-manager-{}".format(read_appxmanifest_identity(p)["Version"])
    out_msix = out_name + ".msix"
    out_sym = out_name + ".appxsym"

    return dict(
        root=root,
        out=out,
        src=src,
        dist=dist,
        build=build,
        out_name=out_name,
        msix=dist / out_msix,
        sym=dist / out_sym,
    )


SDK_BINS = get_sdk_bins()

MAKEAPPX = SDK_BINS / "makeappx.exe"
MAKEPRI = SDK_BINS / "makepri.exe"

for tool in [MAKEAPPX, MAKEPRI]:
    if not tool.is_file():
        print("Unable to locate Windows Kit tool", tool.name, file=sys.stderr)
        sys.exit(3)

OUT = get_output_info()

rmtree(OUT["build"])
rmtree(OUT["out"])
run([sys.executable, "-m", "pymsbuild"])
run([sys.executable, "scripts/generate-nuget-index.py", OUT["out"] / "index.json"])

run([MAKEPRI, "new", "/o",
              "/pr", OUT["out"],
              "/cf", OUT["src"] / "python/resources.xml",
              "/of", OUT["out"] / "_resources.pri",
              "/mf", "appx"])

for f in OUT["out"].rglob("*.pdb"):
    print("Cleaning", f)
    f.unlink()
for f in OUT["out"].rglob("*.pyc"):
    print("Cleaning", f)
    f.unlink()
for f in OUT["out"].rglob("__pycache__"):
    print("Cleaning", f)
    try:
        f.rmdir()
    except OSError:
        pass

run([MAKEAPPX, "pack", "/o", "/d", OUT["out"], "/p", OUT["msix"]])

try:
    OUT["sym"].unlink()
except OSError:
    pass
with zipfile.ZipFile(OUT["sym"], "w") as zf:
    print("Packing symbols to", OUT["sym"])
    for f in OUT["build"].rglob("*.pdb"):
        print("Packing", f)
        zf.write(f, arcname=f.name)
