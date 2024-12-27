import json
import sys

from collections import OrderedDict
from pathlib import Path
from urllib.request import Request, urlopen

REPO = Path(__file__).absolute().parent.parent
sys.path.append(str(REPO / "src"))
from manage.verutils import Version


# Like Invoke-RestMethod in PowerShell
def irm(url, method="GET", headers={}):
    headers = {
        "Accepts": "application/json",
        **headers,
    }
    req = Request(url, method=method, headers=headers)
    with urlopen(req) as r:
        return json.load(r)


NUGET_SOURCE = "https://api.nuget.org/v3/index.json"

SCHEMA = {
    "python": {
        "schema": 1,
        "id": "pythoncore-$XYVERSION$",
        "sort-version": "$FULLVERSION$",
        "company": "PythonCore",
        "tag": "$FULLVERSION$",
        "install-for": ["$FULLVERSION$", "$XYVERSIONNOPRE$", "$XVERSIONNOPRE$"],
        "run-for": [
            {"tag": "$XYVERSION$", "target": "python.exe"},
            {"tag": "$XVERSION$", "target": "python.exe"}
        ],
        "alias": [
            {"name": "python$XYVERSION$.exe", "target": "python.exe"},
            {"name": "python$XVERSION$.exe", "target": "python.exe"},
            {"name": "pythonw$XYVERSION$.exe", "target": "pythonw.exe", "windowed": 1},
            {"name": "pythonw$XVERSION$.exe", "target": "pythonw.exe", "windowed": 1}
        ],
        "shortcuts": [
            {
                "kind": "pep514",
                "Key": r"PythonCore\$XYVERSION$",
                "DisplayName": "Python $FULLVERSION$",
                "SupportUrl": "https://www.python.org/",
                "SysArchitecture": "64bit",
                "SysVersion": "$XYVERSION$",
                "Version": "$FULLVERSION$",
                "InstallPath": {
                    "": "%PREFIX%",
                    "ExecutablePath": "%PREFIX%python.exe",
                    "WindowedExecutablePath": "%PREFIX%pythonw.exe",
                },
                "Help": {
                    "Online Python Documentation": {
                        "": "https://docs.python.org/$XYVERSION$/"
                    },
                },
            },
            {
                "kind": "start",
                "Name": "Python $XYVERSION$",
                "Items": [
                    {
                        "Name": "Python $XYVERSION$",
                        "Target": "%PREFIX%python.exe",
                        "Icon": "%PREFIX%python.exe",
                    },
                    {
                        "Name": "Python $XYVERSION$ Documentation",
                        "Icon": r"%SystemRoot%\System32\SHELL32.dll",
                        "IconIndex": 13,
                        "Target": "https://docs.python.org/$XYVERSION$/",
                    },
                ],
            },
        ],
        "displayName": "Python $FULLVERSION$",
        "executable": "./python.exe",
        "url": "$PACKAGEURL$"
    },
    "pythonx86": {
        "schema": 1,
        "id": "pythoncore-$XYVERSION$-32",
        "sort-version": "$FULLVERSION$",
        "company": "PythonCore",
        "tag": "$FULLVERSION$-32",
        "install-for": ["$FULLVERSION$-32", "$XYVERSIONNOPRE$-32", "$XVERSIONNOPRE$-32"],
        "run-for": [
            {"tag": "$XYVERSION$-32", "target": "python.exe"},
            {"tag": "$XVERSION$-32", "target": "python.exe"}
        ],
        "alias": [
            {"name": "python$XYVERSION$-32.exe", "target": "python.exe"},
            {"name": "python$XVERSION$-32.exe", "target": "python.exe"},
            {"name": "pythonw$XYVERSION$-32.exe", "target": "pythonw.exe", "windowed": 1},
            {"name": "pythonw$XVERSION$-32.exe", "target": "pythonw.exe", "windowed": 1}
        ],
        "shortcuts": [
            {
                "kind": "pep514",
                "Key": r"PythonCore\$XYVERSION$-32",
                "DisplayName": "Python $FULLVERSION$ (32-bit)",
                "SupportUrl": "https://www.python.org/",
                "SysArchitecture": "32bit",
                "SysVersion": "$XYVERSION$",
                "Version": "$FULLVERSION$",
                "InstallPath": {
                    "": "%PREFIX%",
                    "ExecutablePath": "%PREFIX%python.exe",
                    "WindowedExecutablePath": "%PREFIX%pythonw.exe",
                },
                "Help": {
                    "Online Python Documentation": {
                        "": "https://docs.python.org/$XYVERSION$/"
                    },
                },
            },
            {
                "kind": "start",
                "Name": "Python $XYVERSION$ (32-bit)",
                "Items": [
                    {
                        "Name": "Python $XYVERSION$ (32-bit)",
                        "Target": "%PREFIX%python.exe",
                        "Icon": "%PREFIX%python.exe",
                    },
                    {
                        "Name": "Python $XYVERSION$ Documentation",
                        "Icon": r"%SystemRoot%\System32\SHELL32.dll",
                        "IconIndex": 13,
                        "Target": "https://docs.python.org/$XYVERSION$/",
                    },
                ],
            },
        ],
        "displayName": "Python $FULLVERSION$ (32-bit)",
        "executable": "./python.exe",
        "url": "$PACKAGEURL$"
    },
    "pythonarm64": {
        "schema": 1,
        "id": "pythoncore-$XYVERSION$-arm64",
        "sort-version": "$FULLVERSION$",
        "company": "PythonCore",
        "tag": "$FULLVERSION$-arm64",
        "install-for": ["$FULLVERSION$-arm64", "$XYVERSIONNOPRE$-arm64", "$XVERSIONNOPRE$-arm64"],
        "run-for": [
            {"tag": "$XYVERSION$-arm64", "target": "python.exe"},
            {"tag": "$XVERSION$-arm64", "target": "python.exe"}
        ],
        "alias": [
            {"name": "python$XYVERSION$-arm64.exe", "target": "python.exe"},
            {"name": "python$XVERSION$-arm64.exe", "target": "python.exe"},
            {"name": "pythonw$XYVERSION$-arm64.exe", "target": "pythonw.exe", "windowed": 1},
            {"name": "pythonw$XVERSION$-arm64.exe", "target": "pythonw.exe", "windowed": 1}
        ],
        "shortcuts": [
            {
                "kind": "pep514",
                "Key": r"PythonCore\$XYVERSION$-arm64",
                "DisplayName": "Python $FULLVERSION$ (ARM64)",
                "SupportUrl": "https://www.python.org/",
                "SysArchitecture": "64bit",
                "SysVersion": "$XYVERSION$",
                "Version": "$FULLVERSION$",
                "InstallPath": {
                    "": "%PREFIX%",
                    "ExecutablePath": "%PREFIX%python.exe",
                    "WindowedExecutablePath": "%PREFIX%pythonw.exe",
                },
                "Help": {
                    "Online Python Documentation": {
                        "": "https://docs.python.org/$XYVERSION$/"
                    },
                },
            },
            {
                "kind": "start",
                "Name": "Python $XYVERSION$ (ARM64)",
                "Items": [
                    {
                        "Name": "Python $XYVERSION$ (ARM64)",
                        "Target": "%PREFIX%python.exe",
                        "Icon": "%PREFIX%python.exe",
                    },
                    {
                        "Name": "Python $XYVERSION$ Documentation",
                        "Icon": r"%SystemRoot%\System32\SHELL32.dll",
                        "IconIndex": 13,
                        "Target": "https://docs.python.org/$XYVERSION$/",
                    },
                ],
            },
        ],
        "displayName": "Python $FULLVERSION$ (ARM64)",
        "executable": "./python.exe",
        "url": "$PACKAGEURL$"
    },
    "python-freethreaded": {
        "schema": 1,
        "id": "pythoncore-$XYVERSION$-t",
        "sort-version": "$FULLVERSION$",
        "company": "PythonCore",
        "tag": "$FULLVERSION$t",
        "install-for": ["$FULLVERSION$t", "$XYVERSIONNOPRE$t", "$XVERSIONNOPRE$t"],
        "run-for": [
            {"tag": "$XYVERSION$t", "target": "python.exe"},
            {"tag": "$XVERSION$t", "target": "python.exe"}
        ],
        "alias": [
            {"name": "python$XYVERSION$t.exe", "target": "python$XYVERSION$t.exe"},
            {"name": "python$XVERSION$t.exe", "target": "python$XYVERSION$t.exe"},
            {"name": "pythonw$XYVERSION$t.exe", "target": "pythonw$XYVERSION$t.exe", "windowed": 1},
            {"name": "pythonw$XVERSION$t.exe", "target": "pythonw$XYVERSION$t.exe", "windowed": 1}
        ],
        "shortcuts": [
            {
                "kind": "pep514",
                "Key": r"PythonCoreFreeThreaded\$XYVERSION$",
                "DisplayName": "Python $FULLVERSION$ (free-threaded)",
                "SupportUrl": "https://www.python.org/",
                "SysArchitecture": "64bit",
                "SysVersion": "$XYVERSION$",
                "Version": "$FULLVERSION$",
                "InstallPath": {
                    "": "%PREFIX%",
                    "ExecutablePath": "%PREFIX%python.exe",
                    "WindowedExecutablePath": "%PREFIX%pythonw.exe",
                },
                "Help": {
                    "Online Python Documentation": {
                        "": "https://docs.python.org/$XYVERSION$/"
                    },
                },
            },
            {
                "kind": "start",
                "Name": "Python $XYVERSION$ (free-threaded)",
                "Items": [
                    {
                        "Name": "Python $XYVERSION$ (free-threaded)",
                        "Target": "%PREFIX%python.exe",
                        "Icon": "%PREFIX%python.exe",
                    },
                    {
                        "Name": "Python $XYVERSION$ Documentation",
                        "Icon": r"%SystemRoot%\System32\SHELL32.dll",
                        "IconIndex": 13,
                        "Target": "https://docs.python.org/$XYVERSION$/",
                    },
                ],
            },
        ],
        "displayName": "Python $FULLVERSION$ (free-threaded)",
        "executable": "./python$XYVERSION$t.exe",
        "url": "$PACKAGEURL$"
    },
    "pythonx86-freethreaded": {
        "schema": 1,
        "id": "pythoncore-$XYVERSION$-32-t",
        "sort-version": "$FULLVERSION$",
        "company": "PythonCore",
        "tag": "$FULLVERSION$t-32",
        "install-for": ["$FULLVERSION$t-32", "$XYVERSIONNOPRE$t-32", "$XVERSIONNOPRE$t-32"],
        "run-for": [
            {"tag": "$XYVERSION$t-32", "target": "python$XYVERSION$t.exe"},
            {"tag": "$XVERSION$t-32", "target": "python$XYVERSION$t.exe"}
        ],
        "alias": [
            {"name": "python$XYVERSION$t-32.exe", "target": "python$XYVERSION$t.exe"},
            {"name": "python$XVERSION$t-32.exe", "target": "python$XYVERSION$t.exe"},
            {"name": "pythonw$XYVERSION$t-32.exe", "target": "pythonw$XYVERSION$t.exe", "windowed": 1},
            {"name": "pythonw$XVERSION$t-32.exe", "target": "pythonw$XYVERSION$t.exe", "windowed": 1}
        ],
        "shortcuts": [
            {
                "kind": "pep514",
                "Key": r"PythonCoreFreeThreaded\$XYVERSION$-32",
                "DisplayName": "Python $FULLVERSION$ (32-bit, free-threaded)",
                "SupportUrl": "https://www.python.org/",
                "SysArchitecture": "32bit",
                "SysVersion": "$XYVERSION$",
                "Version": "$FULLVERSION$",
                "InstallPath": {
                    "": "%PREFIX%",
                    "ExecutablePath": "%PREFIX%python.exe",
                    "WindowedExecutablePath": "%PREFIX%pythonw.exe",
                },
                "Help": {
                    "Online Python Documentation": {
                        "": "https://docs.python.org/$XYVERSION$/"
                    },
                },
            },
            {
                "kind": "start",
                "Name": "Python $XYVERSION$ (32-bit, free-threaded)",
                "Items": [
                    {
                        "Name": "Python $XYVERSION$ (32-bit, free-threaded)",
                        "Target": "%PREFIX%python.exe",
                        "Icon": "%PREFIX%python.exe",
                    },
                    {
                        "Name": "Python $XYVERSION$ Documentation",
                        "Icon": r"%SystemRoot%\System32\SHELL32.dll",
                        "IconIndex": 13,
                        "Target": "https://docs.python.org/$XYVERSION$/",
                    },
                ],
            },
        ],
        "displayName": "Python $FULLVERSION$ (32-bit, free-threaded)",
        "executable": "./python$XYVERSION$t.exe",
        "url": "$PACKAGEURL$"
    },
    "pythonarm64-freethreaded": {
        "schema": 1,
        "id": "pythoncore-$XYVERSION$-arm64-t",
        "sort-version": "$FULLVERSION$",
        "company": "PythonCore",
        "tag": "$FULLVERSION$t-arm64",
        "install-for": ["$FULLVERSION$t-arm64", "$XYVERSIONNOPRE$t-arm64", "$XVERSIONNOPRE$t-arm64"],
        "run-for": [
            {"tag": "$XYVERSION$t-arm64", "target": "python$XYVERSION$t.exe"},
            {"tag": "$XVERSION$t-arm64", "target": "python$XYVERSION$t.exe"}
        ],
        "alias": [
            {"name": "python$XYVERSION$t-arm64.exe", "target": "python$XYVERSION$t.exe"},
            {"name": "python$XVERSION$t-arm64.exe", "target": "python$XYVERSION$t.exe"},
            {"name": "pythonw$XYVERSION$t-arm64.exe", "target": "pythonw$XYVERSION$t.exe", "windowed": 1},
            {"name": "pythonw$XVERSION$t-arm64.exe", "target": "pythonw$XYVERSION$t.exe", "windowed": 1}
        ],
        "shortcuts": [
            {
                "kind": "pep514",
                "Key": r"PythonCoreFreeThreaded\$XYVERSION$-arm64",
                "DisplayName": "Python $FULLVERSION$ (ARM64, free-threaded)",
                "SupportUrl": "https://www.python.org/",
                "SysArchitecture": "64bit",
                "SysVersion": "$XYVERSION$",
                "Version": "$FULLVERSION$",
                "InstallPath": {
                    "": "%PREFIX%",
                    "ExecutablePath": "%PREFIX%python.exe",
                    "WindowedExecutablePath": "%PREFIX%pythonw.exe",
                },
                "Help": {
                    "Online Python Documentation": {
                        "": "https://docs.python.org/$XYVERSION$/"
                    },
                },
            },
            {
                "kind": "start",
                "Name": "Python $XYVERSION$ (ARM64, free-threaded)",
                "Items": [
                    {
                        "Name": "Python $XYVERSION$ (ARM64, free-threaded)",
                        "Target": "%PREFIX%python.exe",
                        "Icon": "%PREFIX%python.exe",
                    },
                    {
                        "Name": "Python $XYVERSION$ Documentation",
                        "Icon": r"%SystemRoot%\System32\SHELL32.dll",
                        "IconIndex": 13,
                        "Target": "https://docs.python.org/$XYVERSION$/",
                    },
                ],
            },
        ],
        "displayName": "Python $FULLVERSION$ (ARM64, free-threaded)",
        "executable": "./python$XYVERSION$t.exe",
        "url": "$PACKAGEURL$"
    },
}


def dict_sub(d, subs):
    if isinstance(d, int):
        return d
    if isinstance(d, str):
        for k, v in subs.items():
            kk = f"${k}$"
            if kk in d:
                if v is None:
                    return None
                d = d.replace(kk, v)
        return d
    if isinstance(d, list):
        return [v for v in (dict_sub(v, subs) for v in d) if v]
    if isinstance(d, dict):
        return {k: dict_sub(v, subs) for k, v in d.items()}
    raise TypeError("unsupported type: " + repr(type(d)))


RESOURCES = {r['@type']: r['@id'] for r in irm(NUGET_SOURCE)['resources']}
BASE_URL = RESOURCES["PackageBaseAddress/3.0.0"].rstrip("/")

INDEX_OLD = {"versions": []}
INDEX_CURRENT = {"versions": [], "next": ""}

CURRENT_VERSION = Version("3.12")

for name, schema in SCHEMA.items():
    data = irm(f"{BASE_URL}/{name}/index.json")

    all_versions = sorted((Version(ver) for ver in data["versions"]), reverse=True)

    for v in all_versions:
        subs = {
            "FULLVERSION": v.to_python_style(3),
            "XYVERSION": v.to_python_style(2, False),
            "XYVERSIONNOPRE": None if v.is_prerelease else v.to_python_style(2, False),
            "XVERSION": v.to_python_style(1, False),
            "XVERSIONNOPRE": None if v.is_prerelease else v.to_python_style(1, False),
            "PACKAGEURL": f"{BASE_URL}/{name}/{v}/{name}.{v}.nupkg",
        }
        index = INDEX_CURRENT if v >= CURRENT_VERSION else INDEX_OLD
        index["versions"].append(dict_sub(schema, subs))


for file in map(Path, sys.argv[1:]):
    legacy_name = f"{file.stem}-legacy.json"
    INDEX_CURRENT["next"] = legacy_name
    with open(file, "w", encoding="utf-8") as f:
        json.dump(INDEX_CURRENT, f, indent=2)
    with open(file.with_name(legacy_name), "w", encoding="utf-8") as f:
        json.dump(INDEX_OLD, f, indent=2)


if not sys.argv[1:]:
    INDEX_CURRENT.pop("next", None)
    print(INDEX_CURRENT)
