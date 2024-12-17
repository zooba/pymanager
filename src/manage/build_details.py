import json
import os
import sys

from pathlib import Path, PurePath


def _version(vi):
    return {
        "major": vi.major,
        "minor": getattr(vi, "minor", 0),
        "micro": getattr(vi, "micro", 0),
        "releaselevel": getattr(vi, "releaselevel", ""),
        "serial": getattr(vi, "serial", 0),
    }


def _print_my_details():
    import sysconfig
    prefix = Path(sys.prefix)
    details = {
        "schema_version": "1.0",
        "base_prefix": ".",
        "platform": sysconfig.get_platform(),
        "language": {
            "version": sys.version,
            "version_info": _version(sys.version_info),
        },
        "implementation": {
            "name": sys.implementation.name,
            "version": _version(sys.implementation.version),
        },
        "interpreter": {
            "path": sys.executable,
        }
    }

    try:
        details["interpreter"]["path"] = Path(sys.executable).relative_to(sys.prefix)
    except ValueError:
        pass

    pythonw = Path(sys.executable).with_name(Path(sys.executable).stem + "w.exe")
    if pythonw.is_file():
        details["interpreter"]["windows_path"] = pythonw.relative_to(sys.prefix)

    try:
        import _winapi
        dll = Path(_winapi.GetModuleFileName(sys.dllhandle))
        try:
            dll = dll.relative_to(sys.prefix)
        except ValueError:
            pass
    except (AttributeError, ImportError, OSError):
        pass
    else:
        details["libpython"] = {
            "dynamic": dll,
            "link_to_libpython": True,
        }
        if (prefix / "libs" / dll.name).with_suffix(".lib").is_file():
            details["libpython"]["libdir"] = "libs"

    if (prefix / "Include/Python.h").is_file():
        details["c_api"] = {
            "headers": "Include",
        }

    short_ver = "{0.major}.{0.minor}".format(sys.implementation.version)
    if sys.implementation.name == "cpython" and hasattr(sys, "winver"):
        details["arbitrary_data"] = {
            "company": "PythonCore",
            "tag": sys.winver,
            "displayName": f"Python {short_ver}",
        }
    else:
        details["arbitrary_data"] = {
            "company": sys.implementation.name,
            "tag": getattr(sys, "winver", None) or short_ver,
            "displayName": f"{sys.implementation.name} {short_ver}",
        }

    print(json.dumps(details, indent="  ", default=str))


def generate_build_details(prefix, **additional):
    from ._core.exceptions import ArgumentError, InvalidInstallError
    from ._core.logging import LOGGER

    prefix = Path(prefix)
    details_json = prefix / "build-details.json"
    if details_json.is_file():
        LOGGER.debug("build-details.json already exists.")
        return

    LOGGER.debug("Generating %s", details_json)

    exe = prefix / "python.exe"
    if not exe.is_file():
        LOGGER.error("Unable to locate %s", exe)
        raise InvalidInstallError("Unable to locate python.exe", prefix)

    import subprocess
    LOGGER.debug("Running %s %s", exe, __file__)
    with open(details_json, "w", encoding="utf-8") as f:
        with subprocess.Popen([exe, "-I", __file__], encoding="utf-8", errors="strict",
                              stdout=f.fileno(), stderr=subprocess.PIPE) as p:
            p.wait()
            LOGGER.debug("stderr: %s", p.stderr.read())

    if additional:
        with open(details_json, "r", encoding="utf-8") as f:
            details = json.load(f)
        details.setdefault("arbitrary_data", {}).update(additional)
        with open(details_json, "w", encoding="utf-8") as f:
            details = json.dump(details, f, indent="  ", default=str)


if __name__ == "__main__":
    _print_my_details()
