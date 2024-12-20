from ._core.commands import find_command, load_default_config, show_help
from ._core.exceptions import ArgumentError
from ._core.logging import LOGGER

try:
    from ._core._version import __version__
except ImportError:
    __version__ = "0.0"


def _with_errno_result(fn):
    def _wrapped(*a, **kw):
        try:
            return fn(*a, **kw) or 0
        except Exception as ex:
            return getattr(ex, "errno", 1)
    return _wrapped


def _with_error_log(fn):
    def _wrapped(*a, **kw):
        try:
            return fn(*a, **kw)
        except Exception as ex:
            LOGGER.error("INTERNAL ERROR: %s: %s", type(ex).__name__, ex)
            LOGGER.debug("TRACEBACK:", exc_info=True)
            raise
    return _wrapped


@_with_errno_result
@_with_error_log
def main(args, root=None):
    args = list(args)
    if not root:
        from pathlib import Path
        root = Path(args[0]).parent

    try:
        cmd = find_command(args[1:], root)
    except ArgumentError:
        cmd = show_help(args[1:])
        return 0

    if cmd.show_help:
        cmd.help()
    else:
        cmd.execute()


@_with_error_log
def _find_one(root, tag, script):
    i = None
    cmd = load_default_config(root)
    i = cmd.get_install_to_run(tag, script)
    if i and "executable" in i:
        return str(i["executable"])
    # TODO: Regular PEP 514 search
    return None


@_with_error_log
def _find_any(root):
    cmd = load_default_config(root)
    return bool(cmd.get_installs())
