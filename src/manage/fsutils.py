import os
import time

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


def _rglob(root):
    q = [root]
    while q:
        r = q.pop(0)
        for f in os.scandir(r):
            p = r / f.name
            if f.is_dir():
                q.append(p)
                yield p, None
            else:
                yield None, p


def rmtree(path, after_5s_warning=None):
    start = time.monotonic()

    if isinstance(path, (str, bytes)):
        path = Path(path)
    if not path.is_dir():
        if path.is_file():
            unlink(path)
        return

    for i in range(1000):
        if after_5s_warning and (time.monotonic() - start) > 5:
            LOGGER.warn(after_5s_warning)
            after_5s_warning = None
        new_path = path.with_name(f"{path.name}.{i}.deleteme")
        if new_path.exists():
            continue
        try:
            path = path.rename(new_path)
            break
        except OSError as ex:
            LOGGER.debug("Failed to rename to %s: %s", new_path, ex)
    else:
        raise FileExistsError(str(path))

    to_rmdir = [path]
    to_retry = []
    for d, f in _rglob(path):
        if after_5s_warning and (time.monotonic() - start) > 5:
            LOGGER.warn(after_5s_warning)
            after_5s_warning = None

        if d:
            to_rmdir.append(d)
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


def unlink(path, after_5s_warning=None):
    start = time.monotonic()

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
        if after_5s_warning and (time.monotonic() - start) > 5:
            LOGGER.warn(after_5s_warning)
            after_5s_warning = None

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
