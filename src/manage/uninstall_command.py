from pathlib import PurePath

from .fsutils import rmtree, unlink
from .logging import LOGGER


def find_install(installed, company, tag):
    for i in installed:
        if i["tag"].casefold().startswith(tag):
            if company and i("company").casefold() != company:
                continue
            return i


def ask_yn(*prompt):
    print(*prompt, " [Y/n]", sep="", end="")
    try:
        resp = input().lower()
    except Exception:
        return False
    return not resp or resp.startswith("y")


def execute(cmd):
    LOGGER.debug("BEGIN uninstall_command.execute: %r", cmd.args)

    from .install_command import update_all_shortcuts

    warn_msg = ("Attempting to remove {} is taking longer than expected. " +
        "Ensure no Python interpreters are running, and continue to wait " +
        "or press Ctrl+C to abort.")

    installed = list(cmd.get_installs())
    if cmd.purge:
        if not cmd.confirm or ask_yn("Uninstall all runtimes?"):
            for i in installed:
                LOGGER.info("Purging %s from %s", i["displayName"], i["prefix"])
                unlink(i["prefix"] / "__install__.json", after_5s_warning=warn_msg.format(i["displayName"]))
                rmtree(i["prefix"], after_5s_warning=warn_msg.format(i["displayName"]))
            LOGGER.info("Purging saved downloads")
            for f in cmd.install_dir.iterdir():
                rmtree(f, after_5s_warning=warn_msg.format("cached downloads"))
            LOGGER.info("Purging global commands")
            for f in cmd.global_dir.iterdir():
                rmtree(f, after_5s_warning=warn_msg.format("global commands"))

    for tag in cmd.args:
        company, _, tag = tag.casefold().replace("/", "\\").rpartition("\\")
        i = find_install(installed, company, tag)
        if i:
            LOGGER.debug("Uninstalling %s from %s", i["displayName"], i["prefix"])
            if cmd.confirm and not ask_yn("Uninstall ", i["displayName"], "?"):
                break
            # Remove registration first to avoid stray installs showing up
            unlink(i["prefix"] / "__install__.json", after_5s_warning=warn_msg.format(i["displayName"]))
            rmtree(i["prefix"], after_5s_warning=warn_msg.format(i["displayName"]))
            LOGGER.info("Removed %s", i["displayName"])
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
        else:
            LOGGER.warn("No install found matching '%s'", tag)

    update_all_shortcuts(cmd, path_warning=False)

    LOGGER.debug("END uninstall_command.execute")
