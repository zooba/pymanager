import os
import sys
from pymsbuild import *
from pymsbuild.dllpack import *

METADATA = {
    "Metadata-Version": "2.2",
    "Name": "manage",
    "Version": "0.1a0",
    "Author": "Python Software Foundation",
    "Author-email": "steve.dower@python.org",
    "Project-url": [
        "Homepage, https://www.python.org/",
        "Sources, https://github.com/zooba/pymanager",
        "Issues, https://github.com/zooba/pymanager",
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
CPP_SETTINGS = ItemDefinition(
    'ClCompile',
    # Support C++20
    LanguageStandard='stdcpp20',
    # Statically link the C Runtime
    RuntimeLibrary='MultiThreaded',
)

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
    ItemDefinition('ClCompile', LanguageStandard="stdcpp20"),
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
    CFunction('file_url_to_path'),
    CFunction('package_get_root'),
    CFunction('shortcut_create'),
    CFunction('shortcut_get_start_programs'),
    CFunction('hide_file'),
    source='src/_native',
    RootNamespace='_native',
)


MAIN_EXE = CProject('py-manage',
    VersionInfo(FileDescription="Python Install Manager"),
    CPP_SETTINGS,
    INCLUDE_TMPDIR,
    ItemDefinition('Link', SubSystem='CONSOLE'),
    Manifest('python.manifest'),
    ResourceFile('python.rc'),
    CSourceFile('main.cpp'),
    CSourceFile('_launch.cpp'),
    IncludeFile('*.h'),
    CSourceFile('../_native/helpers.cpp'),
    IncludeFile('../_native/helpers.h'),
    source='src/python',
    ConfigurationType='Application',
)


MAINW_EXE = CProject('pyw-manage',
    VersionInfo(FileDescription="Python Install Manager (windowed)"),
    CPP_SETTINGS,
    INCLUDE_TMPDIR,
    ItemDefinition('ClCompile', PreprocessorDefinitions=Prepend("PY_WINDOWED=1;")),
    ItemDefinition('Link', SubSystem='WINDOWS'),
    Manifest('python.manifest'),
    ResourceFile('pythonw.rc'),
    CSourceFile('main.cpp'),
    CSourceFile('_launch.cpp'),
    IncludeFile('*.h'),
    CSourceFile('../_native/helpers.cpp'),
    IncludeFile('../_native/helpers.h'),
    source='src/python',
    ConfigurationType='Application',
)


PACKAGE = Package('python-manager',
    PyprojectTomlFile('pyproject.toml'),
    # MSIX manifest
    File('src/python/appxmanifest.xml', name='appxmanifest.xml'),
    File('src/python/pymanager.appinstaller', name='pymanager.appinstaller'),

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
        File('src/python/templates/template.py'),
        CProject('launcher',
            VersionInfo(FileDescription="Python launcher", OriginalFilename="launcher.exe"),
            CPP_SETTINGS,
            ItemDefinition('Link', SubSystem='CONSOLE'),
            Manifest('python.manifest'),
            ResourceFile('python.rc'),
            CSourceFile('launcher.cpp'),
            CSourceFile('_launch.cpp'),
            IncludeFile('*.h'),
            source='src/python',
            ConfigurationType='Application',
        ),
        CProject('launcherw',
            VersionInfo(FileDescription="Python launcher (windowed)", OriginalFilename="launcherw.exe"),
            CPP_SETTINGS,
            ItemDefinition('Link', SubSystem='WINDOWS'),
            Manifest('python.manifest'),
            ResourceFile('pythonw.rc'),
            CSourceFile('launcher.cpp'),
            CSourceFile('_launch.cpp'),
            IncludeFile('*.h'),
            source='src/python',
            ConfigurationType='Application',
        ),
    ),

    # Directory for MSIX resources
    Package(
        '_resources',
        File('src/python/_resources/*.png'),
        File('src/python/_resources/*.ico'),
    ),

    # Directory for bundled runtime and our modules
    Package(
        'runtime',
        MANAGE_PYD,
        NATIVE_PYD,
        # Other files added during init_PACKAGE
    ),

    # Main entry-point executables
    MAIN_EXE,
    MAINW_EXE,
)


DLL_NAMES = {
    "cp313": "python313",
    "cp314": "python314",
}


EMBED_URLS = {
    "cp313-cp313-win_amd64": "https://www.python.org/ftp/python/3.13.1/python-3.13.1-embed-amd64.zip",
    "cp313-cp313-win_arm64": "https://www.python.org/ftp/python/3.13.1/python-3.13.1-embed-arm64.zip",
    "cp314-cp314-win_amd64": "https://www.python.org/ftp/python/3.14.0a2/python-3.14.0a2-embed-amd64.zip",
    "cp314-cp314-win_arm64": "https://www.python.org/ftp/python/3.14.0a2/python-3.14.0a2-embed-arm64.zip",
}


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


def _patch_appinstaller(file, tmp):
    if not file:
        return
    with open(file.source, "r", encoding="utf-8") as f:
        txt = f.read()
    txt = txt.replace("${VERSION}", _make_xyzw_version(METADATA["Version"]))
    txt = txt.replace("${URL}", os.getenv("PYMANAGER_PUBLISH_URL", "https://example.com"))
    txt = txt.replace("${MSIX_FILENAME}", f"python-manager-{METADATA['Version']}.msix")
    update_file(tmp, txt)
    file.source = tmp


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

    # PATCH VERSION INTO appxmanifest.xml
    appx_xml = tmpdir / "appxmanifest.xml"
    _patch_appx_identity(PACKAGE.find("appxmanifest.xml").source, appx_xml,
        Version=_make_xyzw_version(METADATA["Version"]),
        Publisher=os.getenv("PYMANAGER_APPX_PUBLISHER"),
    )
    PACKAGE.find("appxmanifest.xml").source = appx_xml

    # PATCH VERSION INTO pymanager.appinstaller
    _patch_appinstaller(PACKAGE.find("pymanager.appinstaller"), tmpdir / "pymanager.appinstaller")

    # GENERATE SUBCOMMAND LIST
    cmds = get_commands()
    cmds_h = tmpdir / "commands.g.h"
    cmds_txt = "static const wchar_t *subcommands[] = {" + ", ".join(f'L"{c}"' for c in cmds) + ", NULL};"
    update_file(cmds_h, cmds_txt)

    # BUNDLE EMBEDDABLE DISTRO
    dll_name = DLL_NAMES[tag.partition("-")[0]]
    PACKAGE.find("py-manage/ItemDefinition(Link)").options["DelayLoadDLLs"] = f"{dll_name}.dll"
    PACKAGE.find("pyw-manage/ItemDefinition(Link)").options["DelayLoadDLLs"] = f"{dll_name}.dll"

    embed_files = [tmpdir / tag / n for n in [
        f"{dll_name}.dll",
        f"{dll_name}.zip",
        f"{dll_name}._pth",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
    ]]
    if any(not f.is_file() for f in embed_files):
        from urllib.request import urlretrieve
        from zipfile import ZipFile
        package = tmpdir / tag / "package.zip"
        package.parent.mkdir(exist_ok=True, parents=True)
        urlretrieve(EMBED_URLS[tag], package)
        with ZipFile(package) as zf:
            for f in embed_files:
                f.write_bytes(zf.read(f.name))
    PACKAGE.find("runtime").members.extend(File(f) for f in embed_files)
