import time
import winreg

from .logging import LOGGER


REG_TYPES = {
    str: winreg.REG_SZ,
    int: winreg.REG_DWORD,
}


class KeyNotFoundSentinel:
    def __bool__(self):
        return False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def _reg_open(root, subkey, writable=False, x86_only=None):
    access = winreg.KEY_ALL_ACCESS if writable else winreg.KEY_READ
    if x86_only is not None:
        if x86_only:
            access |= winreg.KEY_WOW64_32KEY
        else:
            access |= winreg.KEY_WOW64_64KEY
    try:
        return winreg.OpenKeyEx(root, subkey, access=access)
    except FileNotFoundError:
        return KeyNotFoundSentinel()


def _iter_keys(key):
    if not key:
        return
    for i in range(0, 1024):
        try:
            yield winreg.EnumKey(key, i)
        except OSError:
            return


def _iter_values(key):
    if not key:
        return
    for i in range(0, 1024):
        try:
            yield winreg.EnumValue(key, i)
        except OSError:
            return


def _delete_key(key, name):
    if not key:
        return
    for _ in range(5):
        try:
            winreg.DeleteKey(key, name)
            break
        except PermissionError:
            time.sleep(0.01)
        except FileNotFoundError:
            return


def _reg_rmtree(key, name):
    if not key:
        return
    try:
        subkey = winreg.OpenKey(key, name, access=winreg.KEY_ALL_ACCESS)
    except FileNotFoundError:
        return
    with subkey:
        keys = list(_iter_keys(subkey))
        while keys:
            for k in keys:
                _reg_rmtree(subkey, k)
            keys = list(_iter_keys(subkey))
    _delete_key(key, name)


def _update_reg_values(key, data, install, exclude=set()):
    skip = set(exclude)

    for k in _iter_keys(key):
        if k in skip:
            continue
        if k not in data:
            _reg_rmtree(key, k)

    for k, v, v_kind in _iter_values(key):
        if k in skip:
            continue
        if k not in data:
            winreg.DeleteValue(key, k)
        elif REG_TYPES.get(data[k]) == v_kind and data[k] == v:
            skip.add(k)

    for k, v in data.items():
        if k in skip:
            continue
        if isinstance(v, dict):
            with winreg.CreateKey(key, k) as subkey:
                # Exclusions are not recursive
                _update_reg_values(subkey, v, install)
            continue

        try:
            v_kind = REG_TYPES[type(v)]
        except LookupError:
            raise TypeError("require str or int; not '{}'".format(
                type(v).__name__
            ))

        if isinstance(v, str):
            if v.startswith("%PREFIX%"):
                v = str(install["prefix"] / v[8:])
            # TODO: Other substitutions?

        try:
            existing, kind = winreg.QueryValueEx(key, k)
        except OSError:
            existing, kind = None, None
        if v_kind != kind or existing != v:
            winreg.SetValueEx(key, k, None, v_kind, v)


def _is_tag_managed(company_key, tag_name):
    try:
        tag = winreg.OpenKey(company_key, tag_name)
    except FileNotFoundError:
        return True
    with tag:
        try:
            if winreg.QueryValueEx(tag, "ManagedByPyManager")[0]:
                return True
        except FileNotFoundError:
            pass
    return False


def update_registry(root_name, install, data):
    hive_name, _, root_name = root_name.partition("\\")
    hive = getattr(winreg, hive_name)
    with winreg.CreateKey(hive, root_name) as root:
        with winreg.CreateKey(root, install["company"]) as company:
            if _is_tag_managed(company, install["tag"]):
                with winreg.CreateKey(company, install["tag"]) as tag:
                    winreg.SetValueEx(tag, "ManagedByPyManager", None, winreg.REG_DWORD, 1)
                    _update_reg_values(tag, data, install, {"kind", "ManagedByPyManager"})


def cleanup_registry(root_name, keep):
    hive_name, _, root_name = root_name.partition("\\")
    hive = getattr(winreg, hive_name)
    with _reg_open(hive, root_name, writable=True) as root:
        for company_name in _iter_keys(root):
            any_left = False
            with winreg.OpenKey(root, company_name, access=winreg.KEY_ALL_ACCESS) as company:
                for tag_name in _iter_keys(company):
                    if (company_name, tag_name) in keep or not _is_tag_managed(company, tag_name):
                        any_left = True
                    else:
                        _reg_rmtree(company, tag_name)
            if not any_left:
                _delete_key(root, company_name)


def _read_str(key, value_name):
    if not key:
        return None
    try:
        v, vt = winreg.QueryValueEx(key, value_name)
    except OSError:
        return None
    if vt == winreg.REG_SZ:
        return v
    if vt == winreg.REG_EXPAND_SZ:
        import os
        return os.path.expandvars(v)
    return None


def _read_one_unmanaged_install(company_name, tag_name, is_core, tag):
    from pathlib import Path
    from .verutils import Version

    with _reg_open(tag, "InstallPath") as dirs:
        prefix = _read_str(dirs, None)
        exe = _read_str(dirs, "ExecutablePath")
        exe_arg = _read_str(dirs, "ExecutableArguments")
        exew = _read_str(dirs, "WindowedExecutablePath")
        exew_arg = _read_str(dirs, "WindowedExecutableArguments")

    display = _read_str(tag, "DisplayName")
    ver = _read_str(tag, "Version")
    
    if not prefix or (not exe and not is_core):
        raise ValueError("Registration is incomplete")
    if is_core:
        display = display or f"Python {tag_name}"
        exe = exe or "python.exe"
        exew = exew or "pythonw.exe"
    if not ver:
        ver = tag_name
    while ver:
        try:
            Version(ver)
            break
        except Exception:
            ver = ver[:-1]
    else:
        ver = "0"

    prefix = Path(prefix)

    try:
        exe = (prefix / exe).relative_to(prefix)
    except (TypeError, ValueError):
        pass
    try:
        exew = (prefix / exew).relative_to(prefix)
    except (TypeError, ValueError):
        pass

    i = {
        "schema": 1,
        "unmanaged": 1,
        "id": f"__unmanaged-{company_name}-{tag_name}",
        "sort-version": ver,
        "company": company_name,
        "tag": tag_name,
        "run-for": [
            {"tag": tag_name, "target": exe},
        ],
        "displayName": display or f"Unknown Python {company_name}\\{tag_name}",
        "prefix": prefix,
        "executable": prefix / exe,
    }
    if exe_arg:
        i["run-for"][0]["args"] = exe_arg
    if exew:
        i["run-for"].append({"tag": tag_name, "target": exew, "windowed": 1})
        if exew_arg:
            i["run-for"][-1]["args"] = exew_arg
    return i


def _get_unmanaged_installs(root):
    if not root:
        return
    for company_name in _iter_keys(root):
        is_core = company_name.casefold() == "PythonCore".casefold()
        with _reg_open(root, company_name) as company:
            for tag_name in _iter_keys(company):
                if _is_tag_managed(company, tag_name):
                    continue
                with _reg_open(company, tag_name) as tag:
                    try:
                        yield _read_one_unmanaged_install(company_name, tag_name, is_core, tag)
                    except Exception:
                        LOGGER.debug("Failed to read %s\\%s registration", company_name, tag_name)
                        LOGGER.debug("ERROR", exc_info=True)


def get_unmanaged_installs(sort_key=None):
    installs = []
    with _reg_open(winreg.HKEY_CURRENT_USER, "SOFTWARE\\Python") as root:
        installs.extend(_get_unmanaged_installs(root))
    with _reg_open(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\Python", x86_only=False) as root:
        installs.extend(_get_unmanaged_installs(root))
    with _reg_open(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\Python", x86_only=True) as root:
        installs.extend(_get_unmanaged_installs(root))
    if not sort_key:
        return installs
    return sorted(installs, key=sort_key)