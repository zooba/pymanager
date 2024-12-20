import pytest

from pathlib import PurePath

from manage._core.scriptutils import find_install_from_script, _read_script, NewEncoding

def _fake_install(v, **kwargs):
    return {
        "company": "Test",
        "id": f"test-{v}",
        "tag": str(v),
        "version": str(v),
        "prefix": PurePath(f"./pkgs/test-{v}"),
        "executable": PurePath(f"./pkgs/test-{v}/test-binary-{v}.exe"),
        **kwargs
    }

INSTALLS = [
    _fake_install("1.0", alias=[{"name": "test1.0.exe", "target": "./test-binary-1.0.exe"}]),
    _fake_install("1.1", alias=[{"name": "test1.1.exe", "target": "./test-binary-1.1.exe"}]),
    _fake_install("2.0", alias=[{"name": "test2.0.exe", "target": "./test-binary-2.0.exe"}]),
]

@pytest.mark.parametrize("script, expect", [
    ("#! /usr/bin/test1.0\n#! /usr/bin/test2.0\n", "1.0"),
    ("#! /usr/bin/test2.0\n#! /usr/bin/test1.0\n", "2.0"),
    ("#! /usr/bin/test1.0.exe\n#! /usr/bin/test2.0\n", "1.0"),
    ("#!test1.0.exe\n", "1.0"),
    ("#!test1.1.exe\n", "1.1"),
    ("#!test1.2.exe\n", None),
    ("#!test-binary-1.1.exe\n", "1.1"),
    ("#!.\\pkgs\\test-1.1\\test-binary-1.1.exe\n", "1.1"),
    ("#!.\\pkgs\\test-1.0\\test-binary-1.1.exe\n", None),
    ("#! /usr/bin/env test1.0\n", "1.0"),
    ("#! /usr/bin/env test2.0\n", "2.0"),
])
def test_read_shebang(fake_config, tmp_path, script, expect):
    fake_config.installs.extend(INSTALLS)
    if expect:
        expect = [i for i in INSTALLS if i["tag"] == expect][0]

    script_py = tmp_path / "test-script.py"
    if isinstance(script, str):
        script = script.encode()
    script_py.write_bytes(script)
    try:
        actual = find_install_from_script(fake_config, script_py)
        assert expect == actual
    except LookupError:
        assert not expect


@pytest.mark.parametrize("script, expect", [
    ("# not a coding comment", None),
    ("# coding: utf-8-sig", None),
    ("# coding: utf-8", "utf-8"),
    ("# coding: ascii", "ascii"),
    ("# actually a coding: comment", "comment"),
    ("#~=~=~=coding:ascii=~=~=~=~", "ascii"),
    ("#! /usr/bin/env python\n# coding: ascii", None),
])
def test_read_coding_comment(fake_config, tmp_path, script, expect):
    script_py = tmp_path / "test-script.py"
    if isinstance(script, str):
        script = script.encode()
    script_py.write_bytes(script)
    try:
        _read_script(fake_config, script_py, "utf-8-sig")
    except NewEncoding as enc:
        assert enc.args[0] == expect
    except LookupError:
        assert not expect
    else:
        assert not expect
