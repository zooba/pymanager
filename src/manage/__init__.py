import sys

def main(args, root=None):
    from ._core.commands import find_command, show_help
    from ._core.exceptions import ArgumentError
    from ._core.logging import LOGGER

    try:
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
    except Exception as ex:
        LOGGER.error("INTERNAL ERROR: %s: %s", type(ex).__name__, ex)
        LOGGER.debug("TRACEBACK:", exc_info=True)
        return getattr(ex, "errno", 1)
    return 0


def _find_one(tag, root):
    from ._core.commands import find_command
    from ._core.installs import get_install_to_run
    from ._core.logging import LOGGER

    try:
        cmd = find_command(["list"], root)
        i = get_install_to_run(cmd.install_dir, tag)
        if i:
            return str(i["executable"])
    except Exception as ex:
        LOGGER.error("INTERNAL ERROR: %s: %s", type(ex).__name__, ex)
        LOGGER.error("TRACEBACK:", exc_info=True)
        raise


def _find_tag_in_script(script, root):
    from ._core.scripthelper import find_tag
    from ._core.logging import LOGGER

    try:
        return find_tag(script, root)
    except OSError:
        LOGGER.debug("Failed to read tag", exc_info=True)
        return None
    except Exception as ex:
        LOGGER.error("INTERNAL ERROR: %s: %s", type(ex).__name__, ex)
        LOGGER.error("TRACEBACK:", exc_info=True)
        raise


def _find_any(root):
    from ._core.commands import find_command
    from ._core.installs import get_installs
    cmd = find_command(["list"], root)
    return bool(get_installs(cmd.install_dir))
