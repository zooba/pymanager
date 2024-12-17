# Build script for test module. This is needed to run tests in-tree.
#
#  python -m pymsbuild -c _msbuild_test.py
#  python -m pytest
#
from pymsbuild import *
from pymsbuild.dllpack import *

METADATA = {
    "Metadata-Version": "2.2",
    "Name": "manage",
    "Version": "1.0.0.0",
    "Author": "Steve Dower",
    "Author-email": "steve.dower@python.org",
    "Summary": "Test build",
}


PACKAGE = Package('src',
    DllPackage('_core_test',
        PyFile('__init__.py'),
        ItemDefinition("ClCompile", PreprocessorDefinitions=Prepend("ERROR_LOCATIONS=1;")),
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
        source='src/manage/_core',
    ),
)
