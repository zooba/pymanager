import os

from pathlib import Path

from .logging import LOGGER


def ensure_tree(path, overwrite_files=True):
    if isinstance(path, (str, bytes)):
        path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except FileExistsError:
        if not overwrite_files:
            raise
        for p in path.parents:
            if p.is_file():
                unlink(p)
                break
        path.parent.mkdir(parents=True, exist_ok=True)


def rmtree(path):
    if isinstance(path, (str, bytes)):
        path = Path(path)
    if not path.is_dir():
        if path.is_file():
            unlink(path)
        return

    for i in range(1000):
        new_path = path.with_name(f"{path.name}.{i}.deleteme")
        if new_path.exists():
            continue
        try:
            path = path.rename(new_path)
            break
        except OSError as ex:
            LOGGER.debug("Failed to rename to %s: %s", new_path, ex)
    else:
        LOGGER.warn("Failed to remove %s", path)
        return

    to_rmdir = [path]
    to_retry = []
    for f in path.rglob("*"):
        if f.is_dir():
            to_rmdir.append(f)
        else:
            try:
                f.unlink()
            except OSError:
                to_retry.append(f)

    if to_retry:
        for f in to_retry:
            try:
                f.unlink()
            except OSError:
                LOGGER.warn("Failed to remove %s", f)

    to_warn = []
    for d in sorted(to_rmdir, key=lambda p: len(p.parts), reverse=True):
        try:
            d.rmdir()
        except OSError:
            to_warn.append(d)

    if to_warn:
        f = os.path.commonprefix(to_warn)
        if f:
            LOGGER.warn("Failed to remove %s", f)
        else:
            for f in to_warn:
                LOGGER.warn("Failed to remove %s", f)


def unlink(path):
    if isinstance(path, (str, bytes)):
        path = Path(path)
    try:
        path.unlink()
        return
    except FileNotFoundError:
        return
    except OSError:
        pass

    for i in range(1000):
        try:
            path = path.rename(path.with_name(f"{path.name}.{i}.deleteme"))
            try:
                path.unlink()
            except OSError:
                pass
            break
        except OSError:
            pass
    else:
        LOGGER.warn("Failed to remove %s", path)
        return
