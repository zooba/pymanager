import os
import sys
from pymsbuild import *
from pymsbuild.dllpack import *

METADATA = {
    "Metadata-Version": "2.2",
    "Name": "manage",
    "Version": "1.0.0.0",
    "Author": "Steve Dower",
    "Author-email": "steve.dower@python.org",
    "Home-page": "TODO",
    "Project-url": [
        "Bug Tracker, TODO",
    ],
    "Summary": "Proof of concept for Python install manager app",
    "Description": File("README.md"),
    "Description-Content-Type": "text/markdown",
    "Keywords": "python,install,manager",
    "Classifier": [
        # See https://pypi.org/classifiers/ for the full list
    ],
    "Requires-Dist": [
        # https://packaging.python.org/en/latest/specifications/dependency-specifiers/
    ],
}


PACKAGE = Package('python-manager',
    PyprojectTomlFile('pyproject.toml'),
    File('src/python/appxmanifest.xml'),
    File('pymanager.json'),
    # Default index feed, mainly for testing right now
    File('index*.json'),
    Package(
        'templates',
        File('src/python/templates/template.py'),
    ),
    Package(
        '_resources',
        File('src/python/_resources/*.png'),
        File('src/python/_resources/*.ico'),
    ),
    DllPackage(
        'manage',
        PyFile('*.py'),
        source='src/manage',
    ),
    DllPackage('_native',
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
        CFunction('file_url_to_path'),
        CFunction('package_get_root'),
        source='src/_native',
    ),
    CProject('launcher',
        ItemDefinition('ClCompile', LanguageStandard='stdcpp20'),
        ItemDefinition('Link', SubSystem='CONSOLE'),
        Manifest('python.manifest'),
        CSourceFile('launcher.cpp'),
        CSourceFile('_launch.cpp'),
        IncludeFile('*.h'),
        source='src/python',
        ConfigurationType='Application',
    ),
    CProject('launcherw',
        ItemDefinition('ClCompile', LanguageStandard='stdcpp20'),
        ItemDefinition('Link', SubSystem='WINDOWS'),
        Manifest('python.manifest'),
        CSourceFile('launcher.cpp'),
        CSourceFile('_launch.cpp'),
        IncludeFile('*.h'),
        source='src/python',
        ConfigurationType='Application',
    ),
    CProject('py-manage',
        ItemDefinition('ClCompile', LanguageStandard='stdcpp20'),
        ItemDefinition('Link', SubSystem='CONSOLE'),
        CSourceFile('main.cpp'),
        CSourceFile('_launch.cpp'),
        IncludeFile('*.h'),
        CSourceFile('../_native/helpers.cpp'),
        IncludeFile('../_native/helpers.h'),
        source='src/python',
        ConfigurationType='Application',
    ),
    CProject('pyw-manage',
        ItemDefinition('ClCompile',
            PreprocessorDefinitions=Prepend("PY_WINDOWED=1;"),
            LanguageStandard='stdcpp20',
        ),
        ItemDefinition('Link', SubSystem='WINDOWS'),
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


def init_METADATA():
    import os, re
    _, sep, version = os.getenv("GITHUB_REF", "").rpartition("/")
    if sep and re.match(r"(\d+!)?\d+(\.\d+)+((a|b|rc)\d+)?(\.post\d+)?(\.dev\d+)?$", version):
        # Looks like a version tag
        METADATA["Version"] = version

    PACKAGE.find("pyproject.toml").from_metadata(METADATA)


def init_PACKAGE(tag=None):
    if not tag:
        return

    tmpdir = get_current_build_state().temp_dir

    # GENERATE _version MODULE
    ver_py = tmpdir / "_version.py"
    ver_code = f"__version__ = {METADATA['Version']!r}"
    if not ver_py.is_file() or ver_py.read_text("utf-8").strip() != ver_code:
        ver_py.parent.mkdir(parents=True, exist_ok=True)
        with ver_py.open("w", encoding="utf-8") as f:
            print(ver_code, file=f)
    PACKAGE.find("manage").members.append(PyFile(ver_py))

    # GENERATE SUBCOMMAND LIST
    cmds = get_commands()
    cmds_h = tmpdir / "commands.g.h"
    cmds_txt = "static const wchar_t *subcommands[] = {" + ", ".join(f'L"{c}"' for c in cmds) + ", NULL};"
    if not cmds_h.is_file() or cmds_h.read_text("utf-8").strip() != cmds_txt:
        cmds_h.parent.mkdir(parents=True, exist_ok=True)
        with cmds_h.open("w", encoding="utf-8") as f:
            print(cmds_txt, file=f)

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
    if not dll.is_file():
        dll.parent.mkdir(exist_ok=True, parents=True)
        from urllib.request import urlretrieve
        from zipfile import ZipFile
        urlretrieve(embed_url, dll.parent / "package.zip")
        with ZipFile(dll.parent / "package.zip") as zf:
            dll.write_bytes(zf.read(dll_name))
            stdlibzip.write_bytes(zf.read(stdlibzip.name))
    PACKAGE.members.append(File(dll, dll.name))
    PACKAGE.members.append(File(stdlibzip, stdlibzip.name))
