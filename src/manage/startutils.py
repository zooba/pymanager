import _native

from pathlib import Path

from .fsutils import rmtree, unlink
from .logging import LOGGER


def _unprefix(p, prefix):
    if p is None:
        return None
    if p.startswith("%PREFIX%"):
        return prefix / p[8:]
    return p

def _make(root, prefix, item):
    n = item["Name"]
    try:
        _make_directory(root, n, prefix, item["Items"])
        return
    except LookupError:
        pass

    lnk = root / (n + ".lnk")
    target = _unprefix(item["Target"], prefix)
    LOGGER.debug("Creating shortcut %s to %s", lnk, target)
    try:
        lnk.relative_to(root)
    except ValueError:
        LOGGER.warn("Package attempted to create shortcut outside of its directory")
        return None
    _native.shortcut_create(
        lnk,
        target,
        arguments=_unprefix(item.get("Arguments"), prefix),
        working_directory=_unprefix(item.get("WorkingDirectory"), prefix),
        icon=_unprefix(item.get("Icon"), prefix),
        icon_index=item.get("IconIndex", 0),
    )
    return lnk


def _make_directory(root, name, prefix, items):
    cleanup_dir = True
    subdir = root / name
    try:
        subdir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        cleanup_dir = False

    cleanup_items = []
    try:
        for i in items:
            cleanup_items.append(_make(subdir, prefix, i))
    except Exception:
        if cleanup_dir:
            rmtree(subdir)
        else:
            for i in cleanup_items:
                if i:
                    unlink(i)
        raise

    ini = subdir / "pymanager.ini"
    with open(ini, "a", encoding="utf-8") as f:
        for i in cleanup_items:
            if i:
                try:
                    print(i.relative_to(subdir), file=f)
                except ValueError:
                    LOGGER.warn("Package attempted to create shortcut outside of its directory")
    _native.hide_file(ini, True)

    return subdir


def create_one(root, install, shortcut):
    _make(Path(root), install["prefix"], shortcut)


def _cleanup(root, keep):
    if root in keep:
        return

    ini = root / "pymanager.ini"
    try:
        with open(ini, "r", encoding="utf-8") as f:
            files = {root / s.strip() for s in f if s.strip()}
    except FileNotFoundError:
        return
    _native.hide_file(ini, False)
    unlink(ini)

    retained = []
    for f in files:
        if f in keep:
            retained.append(f)
            continue
        LOGGER.debug("Removing %s", f)
        try:
            unlink(f)
        except IsADirectoryError:
            _cleanup(f, keep)

    if retained:
        with open(ini, "w", encoding="utf-8") as f:
            for i in retained:
                try:
                    print(i.relative_to(root), file=f)
                except ValueError:
                    LOGGER.debug("Ignoring file outside of current directory %s", i)
        _native.hide_file(ini, True)
    elif not any(root.iterdir()):
        LOGGER.debug("Removing %s", root)
        rmtree(root)


def _get_to_keep(keep, root, item):
    keep.add(root / item["Name"])
    for i in item.get("Items", ()):
        try:
            _get_to_keep(keep, root / item["Name"], i)
        except LookupError:
            pass


def cleanup(root, preserve):
    if isinstance(root, str):
        root = Path(root)

    if not root.is_dir():
        if root.is_file():
            unlink(root)
        return

    keep = set()
    for item in preserve:
        _get_to_keep(keep, root, item)

    LOGGER.debug("Cleaning up Start menu shortcuts")
    for item in keep:
        LOGGER.debug("Except: %s", item)

    for entry in root.iterdir():
        _cleanup(entry, keep)

    if not any(root.iterdir()):
        LOGGER.debug("Removing %s", root)
        rmtree(root)
