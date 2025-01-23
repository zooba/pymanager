from .exceptions import (
    ArgumentError,
    AutomaticInstallDisabledError,
    NoInstallFoundError,
    NoInstallsError,
    SilentError,
)
from .logging import LOGGER

try:
    from ._version import __version__
except ImportError:
    __version__ = "0.0"


__all__ = ["main", "NoInstallFoundError", "NoInstallsError", "find_one"]


def main(args, root=None):
    delete_log = None
    try:
        from .commands import find_command, show_help
        args = list(args)
        if not root:
            from pathlib import Path
            root = Path(args[0]).parent

        try:
            cmd = find_command(args[1:], root)
        except LookupError:
            cmd = show_help([])
            return 1
        except ArgumentError as ex:
            cmd = show_help(args[1:])
            LOGGER.error("%s", ex)
            return 1

        if cmd.show_help:
            cmd.help()
            return 0

        log_file = cmd.get_log_file()
        if log_file:
            LOGGER.file = open(log_file, "w", encoding="utf-8", errors="replace")
            LOGGER.verbose("Writing logs to %s", log_file)

        cmd.execute()
        if not cmd.keep_log:
            delete_log = log_file
    except AutomaticInstallDisabledError as ex:
        LOGGER.error("%s", ex)
        return ex.exitcode
    except SilentError as ex:
        LOGGER.debug("SILENCED ERROR", exc_info=True)
        return ex.exitcode
    except Exception as ex:
        LOGGER.error("INTERNAL ERROR: %s: %s", type(ex).__name__, ex)
        LOGGER.debug("TRACEBACK:", exc_info=True)
        return getattr(ex, "winerror", getattr(ex, "errno", 1))
    finally:
        f, LOGGER.file = LOGGER.file, None
        if f:
            f.flush()
            f.close()
        if delete_log:
            try:
                delete_log.unlink()
            except OSError:
                pass
    return 0


def find_one(root, tag, script, windowed, allow_autoinstall, show_not_found_error):
    autoinstall_permitted = False
    try:
        from .commands import load_default_config
        from .scriptutils import quote_args
        i = None
        cmd = load_default_config(root)
        autoinstall_permitted = cmd.automatic_install
        LOGGER.debug("Finding runtime for '%s' or '%s'%s", tag, script, " (windowed)" if windowed else "")
        try:
            i = cmd.get_install_to_run(tag, script, windowed=windowed)
        except NoInstallsError:
            # We always allow autoinstall when there are no runtimes at all
            # (Noting that user preference may still prevent it)
            allow_autoinstall = True
            raise
        exe = str(i["executable"])
        args = quote_args(i.get("executable_args", ()))
        LOGGER.debug("Selected %s %s", exe, args)
        return exe, args
    except (NoInstallFoundError, NoInstallsError) as ex:
        if not autoinstall_permitted or not allow_autoinstall:
            LOGGER.error("%s", ex)
            raise AutomaticInstallDisabledError() from ex
        if show_not_found_error:
            LOGGER.error("%s", ex)
            LOGGER.debug("TRACEBACK:", exc_info=True)
        raise
    except SilentError:
        LOGGER.debug("SILENCED ERROR", exc_info=True)
        raise
    except Exception as ex:
        LOGGER.error("INTERNAL ERROR: %s: %s", type(ex).__name__, ex)
        LOGGER.debug("TRACEBACK:", exc_info=True)
        raise
