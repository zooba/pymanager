from pathlib import PurePath

from .exceptions import ArgumentError
from .fsutils import rmtree, unlink
from .logging import LOGGER


def ask_yn(*prompt):
    print(*prompt, " [Y/n]", sep="", end="")
    try:
        resp = input().lower()
    except Exception:
        return False
    return not resp or resp.startswith("y")


def _iterdir(p):
    try:
        return list(p.iterdir())
    except FileNotFoundError:
        LOGGER.debug("Skipping %s because it does not exist", p)
        return []


def execute(cmd):
    LOGGER.debug("BEGIN uninstall_command.execute: %r", cmd.args)

    from .install_command import update_all_shortcuts
    from .tagutils import install_matches_any, tag_or_range

    warn_msg = ("Attempting to remove {} is taking longer than expected. " +
        "Ensure no Python interpreters are running, and continue to wait " +
        "or press Ctrl+C to abort.")

    # Clear any active venv so we don't try to delete it
    # (we'll succeed... ask me how I know...)
    cmd.virtual_env = None
    installed = list(cmd.get_installs())

    if cmd.purge:
        if not cmd.confirm or ask_yn("Uninstall all runtimes?"):
            for i in installed:
                LOGGER.info("Purging %s from %s", i["display-name"], i["prefix"])
                unlink(i["prefix"] / "__install__.json", after_5s_warning=warn_msg.format(i["display-name"]))
                rmtree(i["prefix"], after_5s_warning=warn_msg.format(i["display-name"]))
            LOGGER.info("Purging saved downloads")
            for f in _iterdir(cmd.install_dir):
                rmtree(f, after_5s_warning=warn_msg.format("cached downloads"))
            LOGGER.info("Purging global commands")
            for f in _iterdir(cmd.global_dir):
                rmtree(f, after_5s_warning=warn_msg.format("global commands"))
        LOGGER.debug("END uninstall_command.execute")
        return

    if not cmd.args:
        raise ArgumentError("Please specify one or more runtimes to uninstall.")

    to_uninstall = []
    for tag in cmd.args:
        if tag.casefold() == "default".casefold():
            tag = cmd.default_tag
        filters = [tag_or_range(tag) if tag else None]
        try:
            i = next(i for i in installed if install_matches_any(i, filters))
        except StopIteration:
            LOGGER.warn("No install found matching '%s'", tag)
            continue
        to_uninstall.append(i)
        installed.remove(i)

    if not to_uninstall:
        LOGGER.info("No runtimes selected to uninstall.")
        return
    elif cmd.confirm:
        if len(to_uninstall) == 1:
            if not ask_yn("Uninstall ", to_uninstall[0]["display-name"], "?"):
                return
        else:
            msg = ", ".join(i["display-name"] for i in to_uninstall)
            if not ask_yn("Uninstall these runtimes: ", msg, "?"):
                return

    for i in to_uninstall:
        LOGGER.debug("Uninstalling %s from %s", i["display-name"], i["prefix"])
        # Remove registration first to avoid stray installs showing up
        unlink(i["prefix"] / "__install__.json", after_5s_warning=warn_msg.format(i["display-name"]))
        rmtree(i["prefix"], after_5s_warning=warn_msg.format(i["display-name"]))
        LOGGER.info("Removed %s", i["display-name"])
        try:
            for target in cmd.global_dir.glob("*.__target__"):
                alias = target.with_suffix("")
                entry = target.read_text(encoding="utf-8-sig", errors="strict")
                if PurePath(entry).match(i["executable"]):
                    LOGGER.debug("Unlink %s", alias)
                    unlink(alias, after_5s_warning=warn_msg.format(alias))
                    unlink(target, after_5s_warning=warn_msg.format(target))
        except OSError as ex:
            LOGGER.warn("Failed to remove alias: %s", ex)
            LOGGER.debug("TRACEBACK:", exc_info=True)

    if to_uninstall:
        update_all_shortcuts(cmd, path_warning=False)

    LOGGER.debug("END uninstall_command.execute")
