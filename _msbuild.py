import os
import sys
from pymsbuild import *
from pymsbuild.dllpack import *


DLL_NAME = "python314"
EMBED_URL = "https://www.python.org/ftp/python/3.14.0/python-3.14.0a7-embed-amd64.zip"

def can_embed(tag):
    """Return False if tag doesn't match DLL_NAME and EMBED_URL.
    This is used for validation at build time, we don't currently handle
    requesting a different build target."""
    return tag == "cp314-cp314-win_amd64"


METADATA = {
    "Metadata-Version": "2.2",
    "Name": "manage",
    "Version": "0.1a0",
    "Author": "Python Software Foundation",
    "Author-email": "steve.dower@python.org",
    "Project-url": [
        "Homepage, https://www.python.org/",
        "Sources, https://github.com/python/pymanager",
        "Issues, https://github.com/python/pymanager",
    ],
    "Summary": "Proof of concept for Python install manager app",
    "Description": File("README.md"),
    "Description-Content-Type": "text/markdown",
    "Keywords": "python,install,manager",
}


# Define additional file type so we can specify .rc files
class ResourceFile(CSourceFile):
    _ITEMNAME = "ResourceCompile"


# Default C++ compiler settings
CPP_SETTINGS = ItemDefinition('ClCompile', LanguageStandard='stdcpp20')


# AdditionalIncludes will be set during init_PACKAGE
INCLUDE_TMPDIR = ItemDefinition("ClCompile")


MANAGE_PYD = DllPackage(
    'manage',
    VersionInfo(FileDescription="Implementation of PyManager"),
    PyFile('*.py'),
    source='src/manage',
    RootNamespace='manage',
)


NATIVE_PYD = DllPackage(
    '_native',
    VersionInfo(FileDescription="Native helper functions for PyManager"),
    PyFile('__init__.py'),
    CPP_SETTINGS,
    IncludeFile('*.h'),
    CSourceFile('*.cpp'),
    CFunction('coinitialize'),
    CFunction('bits_connect'),
    CFunction('bits_begin'),
    CFunction('bits_cancel'),
    CFunction('bits_get_progress'),
    CFunction('bits_retry_with_auth'),
    CFunction('bits_find_job'),
    CFunction('bits_serialize_job'),
    CFunction('winhttp_urlopen'),
    CFunction('winhttp_isconnected'),
    CFunction('winhttp_urlsplit'),
    CFunction('winhttp_urlunsplit'),
    CFunction('file_url_to_path'),
    CFunction('file_lock_for_delete'),
    CFunction('file_unlock_for_delete'),
    CFunction('file_locked_delete'),
    CFunction('package_get_root'),
    CFunction('shortcut_create'),
    CFunction('shortcut_get_start_programs'),
    CFunction('hide_file'),
    CFunction('fd_supports_vt100'),
    CFunction('date_as_str'),
    CFunction('datetime_as_str'),
    source='src/_native',
    RootNamespace='_native',
)


def main_exe(name):
    return CProject(name,
        VersionInfo(FileDescription="Python Install Manager"),
        CPP_SETTINGS,
        ItemDefinition('ClCompile', PreprocessorDefinitions=Prepend(f'EXE_NAME=L"{name}";')),
        ItemDefinition('Link', SubSystem='CONSOLE', DelayLoadDLLs=f"{DLL_NAME}.dll"),
        INCLUDE_TMPDIR,
        Manifest('default.manifest'),
        ResourceFile('pyicon.rc'),
        CSourceFile('main.cpp'),
        CSourceFile('_launch.cpp'),
        IncludeFile('*.h'),
        CSourceFile('../_native/helpers.cpp'),
        IncludeFile('../_native/helpers.h'),
        source='src/pymanager',
        ConfigurationType='Application',
    )

def mainw_exe(name):
    return CProject(name,
        VersionInfo(FileDescription="Python Install Manager (windowed)"),
        CPP_SETTINGS,
        ItemDefinition('Link', SubSystem='WINDOWS', DelayLoadDLLs=f"{DLL_NAME}.dll"),
        INCLUDE_TMPDIR,
        ItemDefinition('ClCompile', PreprocessorDefinitions=Prepend(f'EXE_NAME=L"{name}";')),
        ItemDefinition('ClCompile', PreprocessorDefinitions=Prepend("PY_WINDOWED=1;")),
        Manifest('default.manifest'),
        ResourceFile('pywicon.rc'),
        CSourceFile('main.cpp'),
        CSourceFile('_launch.cpp'),
        IncludeFile('*.h'),
        CSourceFile('../_native/helpers.cpp'),
        IncludeFile('../_native/helpers.h'),
        source='src/pymanager',
        ConfigurationType='Application',
    )


PACKAGE = Package('python-manager',
    PyprojectTomlFile('pyproject.toml'),
    # MSIX manifest
    File('src/pymanager/appxmanifest.xml', name='appxmanifest.xml'),
    File('src/pymanager/pymanager.appinstaller', name='pymanager.appinstaller'),

    # Default settings
    File('src/pymanager.json'),

    # Default index feed, mainly for testing right now
    Package(
        'bundled',
        File('src/index*.json'),
    ),

    # Directory for template files
    Package(
        'templates',
        File('src/pymanager/templates/template.py'),
        CProject('launcher',
            VersionInfo(FileDescription="Python launcher", OriginalFilename="launcher.exe"),
            CPP_SETTINGS,
            Property('DynamicLibcppLinkage', 'true'),
            ItemDefinition('ClCompile', RuntimeLibrary='MultiThreaded'),
            ItemDefinition('Link', SubSystem='CONSOLE'),
            Manifest('default.manifest'),
            ResourceFile('pyicon.rc'),
            CSourceFile('launcher.cpp'),
            CSourceFile('_launch.cpp'),
            IncludeFile('*.h'),
            source='src/pymanager',
            ConfigurationType='Application',
        ),
        CProject('launcherw',
            VersionInfo(FileDescription="Python launcher (windowed)", OriginalFilename="launcherw.exe"),
            CPP_SETTINGS,
            Property('DynamicLibcppLinkage', 'true'),
            ItemDefinition('ClCompile', RuntimeLibrary='MultiThreaded'),
            ItemDefinition('Link', SubSystem='WINDOWS'),
            Manifest('default.manifest'),
            ResourceFile('pywicon.rc'),
            CSourceFile('launcher.cpp'),
            CSourceFile('_launch.cpp'),
            IncludeFile('*.h'),
            source='src/pymanager',
            ConfigurationType='Application',
        ),
    ),

    # Directory for MSIX resources
    Package(
        '_resources',
        File('src/pymanager/_resources/*.png'),
        File('src/pymanager/_resources/*.ico'),
    ),

    # Directory for bundled runtime and our modules
    Package(
        'runtime',
        MANAGE_PYD,
        NATIVE_PYD,
        # Other files added during init_PACKAGE
    ),

    # Main entry-point executables
    main_exe("py-manager"),
    mainw_exe("pyw-manager"),
    main_exe("py"),
    mainw_exe("pyw"),
    main_exe("pymanager"),
    mainw_exe("pywmanager"),
    main_exe("python"),
    mainw_exe("pythonw"),
    main_exe("python3"),
    mainw_exe("pythonw3"),
)


def get_commands():
    import ast
    command_bases = {"BaseCommand"}
    commands = []
    with open("src/manage/commands.py", "r", encoding="utf-8") as f:
        mod = ast.parse(f.read())
    for cls in filter(lambda c: isinstance(c, ast.ClassDef), mod.body):
        # Check if a subclass of BaseCommand
        if not any(b.id in command_bases for b in cls.bases):
            continue
        command_bases.add(cls.name)
        for a in filter(lambda s: isinstance(s, ast.Assign), cls.body):
            if not any(t.id == "CMD" for t in a.targets):
                continue
            try:
                commands.append(a.value.value)
            except AttributeError:
                commands.append(a.value.s)
            break
    return [c for c in commands if c[:1] != "_"]


def _make_xyzw_version(v, sep="."):
    from packaging.version import parse
    v = parse(v)
    if not v.pre:
        return "{0}{4}{1}{4}{2}{4}{3}".format(v.major, v.minor, v.micro, 0xF0, sep)
    return "{0}{4}{1}{4}{2}{4}{3}".format(
        v.major,
        v.minor,
        v.micro,
        {"a": 0xA0, "b": 0xB0, "rc": 0xC0}.get(v.pre[0].lower(), 0) | v.pre[1],
        sep,
    )


def _patch_appx_identity(source, dest, **new):
    from xml.etree import ElementTree as ET
    NS = {}
    with open(source, "r", encoding="utf-8") as f:
        NS = dict(e for _, e in ET.iterparse(f, events=("start-ns",)))
    for k, v in NS.items():
        ET.register_namespace(k, v)

    with open(source, "r", encoding="utf-8") as f:
        xml = ET.parse(f)

    identity = xml.find(f"x:Identity", {"x": NS[""]})
    for k, v in new.items():
        if v:
            identity.set(k, v)
    
    with open(dest, "wb") as f:
        xml.write(f, "utf-8")


def _patch_appinstaller(source, dest, **new):
    with open(source, "r", encoding="utf-8") as f:
        txt = f.read()
    for k, v in new.items():
        if v:
            txt = txt.replace(f"${{{k}}}", v)
    update_file(dest, txt)


def update_file(file, content):
    if not file.is_file() or file.read_text("utf-8").strip() != content.strip():
        file.parent.mkdir(parents=True, exist_ok=True)
        with file.open("w", encoding="utf-8") as f:
            print(content, file=f)


def init_METADATA():
    import os, re
    _, sep, version = os.getenv("BUILD_SOURCEBRANCH", os.getenv("GITHUB_REF", "")).rpartition("/")
    if sep and "." in version:
        from packaging.version import parse
        try:
            # Looks like a version tag
            METADATA["Version"] = parse(version).public
        except Exception:
            pass

    PACKAGE.find("pyproject.toml").from_metadata(METADATA)

    fileversion = _make_xyzw_version(METADATA["Version"], ",")
    for vi in PACKAGE.findall("**/VersionInfo"):
        vi.from_metadata(METADATA)
        vi.options["FILEVERSION"] = fileversion


def init_PACKAGE(tag=None):
    if not tag:
        return

    tmpdir = get_current_build_state().temp_dir
    INCLUDE_TMPDIR.options["AdditionalIncludeDirectories"] = Prepend(f"{tmpdir};")

    # GENERATE _version MODULE
    ver_py = tmpdir / "_version.py"
    update_file(ver_py, f"__version__ = {METADATA['Version']!r}")
    MANAGE_PYD.members.append(PyFile(ver_py))

    # GENERATE version.txt
    ver_txt = tmpdir / "version.txt"
    update_file(ver_txt, str(METADATA['Version']))
    PACKAGE.members.append(PyFile(ver_txt))

    # PATCH appxmanifest.xml AND pymanager.appinstaller
    appx_version = _make_xyzw_version(METADATA["Version"])
    appx_publisher = os.getenv("PYMANAGER_APPX_PUBLISHER", "CN=00000000-0000-0000-0000-000000000000")
    appx_url = os.getenv("PYMANAGER_PUBLISH_URL", "https://example.com").rstrip("/")
    appx_filename = f"python-manager-{METADATA['Version']}.msix"

    appx_xml = tmpdir / "appxmanifest.xml"
    _patch_appx_identity(PACKAGE.find("appxmanifest.xml").source, appx_xml,
        Version=appx_version,
        Publisher=os.getenv("PYMANAGER_APPX_PUBLISHER"),
    )
    PACKAGE.find("appxmanifest.xml").source = appx_xml

    appinstaller = tmpdir / "pymanager.appinstaller"
    _patch_appinstaller(PACKAGE.find("pymanager.appinstaller").source, appinstaller,
        Version=appx_version,
        Publisher=appx_publisher,
        Url=appx_url,
        Filename=appx_filename,
    )
    PACKAGE.find("pymanager.appinstaller").source = appinstaller

    # GENERATE SUBCOMMAND LIST
    cmds = get_commands()
    cmds_h = tmpdir / "commands.g.h"
    cmds_txt = ("static const wchar_t *subcommands[] = {"
                + ", ".join(f'L"{c}"' for c in cmds)
                + ", NULL};")
    update_file(cmds_h, cmds_txt)

    # BUNDLE EMBEDDABLE DISTRO
    if not can_embed(tag):
        print("[WARNING] Unable to bundle embeddable distro for this runtime.")
        return

    embed_files = [tmpdir / tag / n for n in [
        f"{DLL_NAME}.dll",
        f"{DLL_NAME}.zip",
        f"{DLL_NAME}._pth",
    ]]
    runtime_files = [tmpdir / tag / n for n in [
        "vcruntime140.dll",
        "vcruntime140_1.dll",
    ]]
    if any(not f.is_file() for f in embed_files):
        from urllib.request import urlretrieve
        from zipfile import ZipFile
        package = tmpdir / tag / "package.zip"
        package.parent.mkdir(exist_ok=True, parents=True)
        urlretrieve(EMBED_URL, package)
        with ZipFile(package) as zf:
            for f in [*embed_files, *runtime_files]:
                f.write_bytes(zf.read(f.name))
    PACKAGE.find("runtime").members.extend(File(f) for f in embed_files)
    PACKAGE.members.extend(File(f) for f in runtime_files)
