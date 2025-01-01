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


class ResourceFile(CSourceFile):
    _ITEMNAME = "ResourceCompile"


PACKAGE = Package('python-manager',
    PyprojectTomlFile('pyproject.toml'),
    File('src/python/appxmanifest.xml', name='appxmanifest.xml'),
    File('src/pymanager.json'),
    # Default index feed, mainly for testing right now
    Package(
        'bundled',
        File('src/index*.json'),
    ),
    Package(
        'templates',
        File('src/python/templates/template.py'),
        CProject('launcher',
            VersionInfo(FileDescription="Python launcher", OriginalFilename="launcher.exe"),
            ItemDefinition('ClCompile', LanguageStandard='stdcpp20'),
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
            ItemDefinition('ClCompile', LanguageStandard='stdcpp20'),
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
    Package(
        '_resources',
        File('src/python/_resources/*.png'),
        File('src/python/_resources/*.ico'),
    ),
    DllPackage(
        'manage',
        VersionInfo(FileDescription="Implementation of PyManager"),
        PyFile('*.py'),
        source='src/manage',
    ),
    DllPackage(
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
    ),
    CProject('py-manage',
        VersionInfo(FileDescription="Python Install Manager"),
        ItemDefinition('ClCompile', LanguageStandard='stdcpp20'),
        ItemDefinition('Link', SubSystem='CONSOLE'),
        Manifest('python.manifest'),
        ResourceFile('python.rc'),
        CSourceFile('main.cpp'),
        CSourceFile('_launch.cpp'),
        IncludeFile('*.h'),
        CSourceFile('../_native/helpers.cpp'),
        IncludeFile('../_native/helpers.h'),
        File(r'$(VC_CppRuntimeFilesPath_x64)\Microsoft.VC143.CRT\vcruntime140.dll',
            Name='vcruntime140.dll'),
        File(r'$(VC_CppRuntimeFilesPath_x64)\Microsoft.VC143.CRT\vcruntime140_1.dll',
            Name='vcruntime140_1.dll'),
        source='src/python',
        ConfigurationType='Application',
    ),
    CProject('pyw-manage',
        VersionInfo(FileDescription="Python Install Manager (windowed)"),
        ItemDefinition('ClCompile',
            PreprocessorDefinitions=Prepend("PY_WINDOWED=1;"),
            LanguageStandard='stdcpp20',
        ),
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
    ),
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


def _make_xyzw_version(v):
    from packaging.version import parse
    v = parse(v)
    if not v.pre:
        return "{}.{}.{}.{}".format(v.major, v.minor, v.micro, 0xF0)
    return "{}.{}.{}.{}".format(
        v.major,
        v.minor,
        v.micro,
        {"a": 0xA0, "b": 0xB0, "rc": 0xC0}.get(v.pre[0].lower(), 0) | v.pre[1]
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


def update_file(file, content):
    if not file.is_file() or file.read_text("utf-8").strip() != content.strip():
        file.parent.mkdir(parents=True, exist_ok=True)
        with file.open("w", encoding="utf-8") as f:
            print(content, file=f)


def init_METADATA():
    import os, re
    _, sep, version = os.getenv("GITHUB_REF", "").rpartition("/")
    if sep:
        from packaging.version import parse
        try:
            # Looks like a version tag
            METADATA["Version"] = parse(version).public
        except Exception:
            pass

    PACKAGE.find("pyproject.toml").from_metadata(METADATA)
    for vi in PACKAGE.findall("*/VersionInfo"):
        vi.from_metadata(METADATA)


def init_PACKAGE(tag=None):
    if not tag:
        return

    tmpdir = get_current_build_state().temp_dir

    # GENERATE _version MODULE
    ver_py = tmpdir / "_version.py"
    update_file(ver_py, f"__version__ = {METADATA['Version']!r}")
    PACKAGE.find("manage").members.append(PyFile(ver_py))

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

    # GENERATE SUBCOMMAND LIST
    cmds = get_commands()
    cmds_h = tmpdir / "commands.g.h"
    cmds_txt = "static const wchar_t *subcommands[] = {" + ", ".join(f'L"{c}"' for c in cmds) + ", NULL};"
    update_file(cmds_h, cmds_txt)

    incl = ItemDefinition("ClCompile", AdditionalIncludeDirectories = Prepend(f"{tmpdir};"))
    PACKAGE.find("py-manage").members.append(incl)
    PACKAGE.find("pyw-manage").members.append(incl)

    # BUNDLE EMBEDDABLE DISTRO
    dll_name = {
        "cp313": "python313.dll",
        "cp314": "python314.dll",
    }[tag.partition("-")[0]]
    PACKAGE.find("py-manage/ItemDefinition(Link)").options["DelayLoadDLLs"] = dll_name
    PACKAGE.find("pyw-manage/ItemDefinition(Link)").options["DelayLoadDLLs"] = dll_name

    embed_url = {
        "cp313-cp313-win_amd64": "https://www.python.org/ftp/python/3.13.1/python-3.13.1-embed-amd64.zip",
        "cp313-cp313-win_arm64": "https://www.python.org/ftp/python/3.13.1/python-3.13.1-embed-arm64.zip",
        "cp314-cp314-win_amd64": "https://www.python.org/ftp/python/3.14.0a2/python-3.14.0a2-embed-amd64.zip",
        "cp314-cp314-win_arm64": "https://www.python.org/ftp/python/3.14.0a2/python-3.14.0a2-embed-arm64.zip",
    }[tag]

    dll = tmpdir / tag / dll_name
    stdlibzip = dll.with_suffix(".zip")
    pth = dll.with_suffix("._pth")
    if not dll.is_file() or not stdlibzip.is_file() or not pth.is_file():
        dll.parent.mkdir(exist_ok=True, parents=True)
        from urllib.request import urlretrieve
        from zipfile import ZipFile
        urlretrieve(embed_url, dll.parent / "package.zip")
        with ZipFile(dll.parent / "package.zip") as zf:
            dll.write_bytes(zf.read(dll_name))
            stdlibzip.write_bytes(zf.read(stdlibzip.name))
            pth.write_bytes(zf.read(pth.name))
    PACKAGE.members.append(File(dll, dll.name))
    PACKAGE.members.append(File(stdlibzip, stdlibzip.name))
    PACKAGE.members.append(File(pth, pth.name))

    # BUNDLE VCRUNTIME
    # TODO: Bundle vcruntime140 and vcruntime140_1
