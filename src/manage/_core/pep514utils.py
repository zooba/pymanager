import time
import winreg


REG_TYPES = {
    str: winreg.REG_SZ,
    int: winreg.REG_DWORD,
}


def _iter_keys(key):
    for i in range(0, 1024):
        try:
            yield winreg.EnumKey(key, i)
        except OSError:
            return


def _iter_values(key):
    for i in range(0, 1024):
        try:
            yield winreg.EnumValue(key, i)
        except OSError:
            return


def _delete_key(key, name):
    for _ in range(5):
        try:
            winreg.DeleteKey(key, name)
            break
        except PermissionError:
            time.sleep(0.01)
        except FileNotFoundError:
            return


def _reg_rmtree(key, name):
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
    try:
        root = winreg.OpenKey(hive, root_name, access=winreg.KEY_ALL_ACCESS)
    except OSError:
        return
    with root:
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
