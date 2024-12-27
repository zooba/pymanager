import json
import os

from pathlib import Path, PurePath

from .exceptions import ArgumentError, HashMismatchError
from .fsutils import ensure_tree, rmtree, unlink
from .indexutils import Index
from .logging import LOGGER, ProgressPrinter
from .tagutils import CompanyTag, tag_or_range
from .urlutils import (
    sanitise_url,
    urljoin,
    urlopen as _urlopen,
    urlretrieve as _urlretrieve,
)


def _multihash(file, hashes):
    import hashlib
    LOGGER.debug("Calculating hashes: %s", ", ".join(hashes))
    hashers = [(hashlib.new(k), k, v) for k, v in hashes.items()]

    for chunk in iter(lambda: file.read(1024 * 1024), b""):
        for h in hashers:
            h[0].update(chunk)

    for h, alg, expect in hashers:
        actual = h.hexdigest().casefold()
        expect = expect.casefold()
        if expect and actual != expect:
            raise HashMismatchError(f"Hash mismatch: {alg}:{actual} (expected {expect})")
        else:
            LOGGER.debug("%s digest: %s (matched)", alg, actual)


def _expand_versions_by_tag(versions):
    for v in versions:
        if isinstance(v["tag"], str):
            yield v
        else:
            for t in v["tag"]:
                yield {**v, "tag": t}


def select_package(cmd, tag, cache, *, urlopen=_urlopen):
    """Finds suitable package from index.json that looks like:
    {"versions": [
      {"id": ..., "company": ..., "tag": ..., "url": ..., "hash": {"sha256": hexdigest}},
      ...
    ]}
    tag may be a list of tags that are allowed to match exactly.
    """
    url = cmd.source.rstrip("/")
    if not url.casefold().endswith(".json".casefold()):
        url = f"{url}/index.json"

    while url:
        LOGGER.debug("Fetching: %s", url)
        try:
            index = cache[url]
            LOGGER.debug("Used cached: %r", index)
        except LookupError:
            index = Index(url, json.loads(urlopen(url, "GET", {"Accepts": "application/json"})))
            LOGGER.debug("Downloaded: %r", index)
            cache[url] = index

        try:
            return index.find_to_install(tag)
        except LookupError:
            if not index.next_url:
                raise
            url = urljoin(url, index.next_url, to_parent=True)

    assert False, "unreachable code"
    raise RuntimeError("End of select_package reached")


def download_package(cmd, install, dest, cache, *, on_progress=None, urlopen=_urlopen, urlretrieve=_urlretrieve):
    if not cmd.force and dest.is_file():
        LOGGER.info("Download was found in the cache")
        LOGGER.debug("Download skipped because %s already exists", dest)
    else:
        unlink(dest, "Removing old downloads is taking some time. " + 
                     "Please continue to wait, or press Ctrl+C to abort.")
        urlretrieve(install["url"], dest, on_progress=on_progress)
        LOGGER.debug("Downloaded to %s", dest)

    if "hash" in install:
        try:
            with open(dest, "rb") as f:
                _multihash(f, install["hash"])
        except HashMismatchError as ex:
            LOGGER.debug("ERROR:", exc_info=True)
            unlink(dest, "Deleting downloaded files is taking some time. " +
                         "Please continue to wait, or press Ctrl+C to abort.")
            raise HashMismatchError() from ex


def extract_package(package, prefix, calculate_dest=Path, *, on_progress=None):
    import zipfile

    if not on_progress:
        def on_progress(*_): pass

    if package.match("*.nupkg"):
        def _calc(prefix, filename, calculate_dest=calculate_dest):
            if not filename.startswith("tools/"):
                return None
            return calculate_dest(prefix, *PurePath(filename).parts[1:])
        calculate_dest = _calc

    # TODO: Optimise/parallelise extract

    warn_out_of_prefix = []
    warn_overwrite = []
    with zipfile.ZipFile(package, "r") as zf:
        items = list(zf.infolist())
        total = len(items) if on_progress else 0
        for i, member in enumerate(items):
            on_progress((i * 100) // total)
            dest = calculate_dest(prefix, member.filename)
            if not dest:
                continue
            try:
                dest.relative_to(prefix)
            except ValueError:
                warn_out_of_prefix.append(dest)
                continue
            if dest.exists():
                warn_overwrite.append(dest)
                continue
            ensure_tree(dest)
            with open(dest, "wb") as f:
                f.write(zf.read(member))
    on_progress(100)

    if warn_out_of_prefix:
        on_progress(None)
        LOGGER.warn("**********************************************************************")
        LOGGER.warn("Package attempted to extract outside of its prefix, but was prevented.")
        LOGGER.warn("THIS PACKAGE MAY BE MALICIOUS. Take care before using it, or uninstall")
        LOGGER.warn("it immediately.")
        LOGGER.warn("**********************************************************************")
        for dest in warn_out_of_prefix:
            LOGGER.debug("Attempted to create: %s", dest)
    if warn_overwrite:
        on_progress(None)
        LOGGER.warn("**********************************************************************")
        LOGGER.warn("Package attempted to overwrite existing item, but was prevented.")
        LOGGER.warn("THIS PACKAGE MAY BE MALICIOUS OR CORRUPT. Take care before using it,")
        LOGGER.warn("and report this issue to the provider.")
        LOGGER.warn("**********************************************************************")
        for dest in warn_overwrite:
            LOGGER.debug("Attempted to overwrite: %s", dest)


def _write_alias(cmd, alias, target):
    p = (cmd.global_dir / alias["name"])
    ensure_tree(p)
    unlink(p)
    launcher = cmd.launcher_exe
    if alias.get("windowed"):
        launcher = cmd.launcherw_exe or launcher
    LOGGER.debug("Copy %s to %s using %s", alias["name"], target, launcher)
    if not launcher or not launcher.is_file():
        LOGGER.info("Skipping %s alias because the launcher template was not found.", alias["name"])
        return
    p.write_bytes(launcher.read_bytes())
    p.with_name(p.name + ".__target__").write_text(str(target), encoding="utf-8")


def _create_shortcut_pep514(cmd, install, shortcut):
    from .pep514utils import update_registry
    update_registry(cmd.pep514_root, install, shortcut)


def _cleanup_shortcut_pep514(cmd, install_shortcut_pairs):
    from .pep514utils import cleanup_registry
    cleanup_registry(cmd.pep514_root, {s["Key"] for i, s in install_shortcut_pairs})


def _create_start_shortcut(cmd, install, shortcut):
    from .startutils import create_one
    create_one(cmd.start_folder, install, shortcut)

def _cleanup_start_shortcut(cmd, install_shortcut_pairs):
    from .startutils import cleanup
    cleanup(cmd.start_folder, [s for i, s in install_shortcut_pairs])

SHORTCUT_HANDLERS = {
    "pep514": (_create_shortcut_pep514, _cleanup_shortcut_pep514),
    "start": (_create_start_shortcut, _cleanup_start_shortcut),
}


def update_all_shortcuts(cmd, path_warning=True):
    LOGGER.debug("Updating global shortcuts")
    alias_written = set()
    shortcut_written = {}
    for i in cmd.get_installs():
        if cmd.global_dir:
            for a in i.get("alias", ()):
                target = i["prefix"] / a["target"]
                if not target.is_file():
                    LOGGER.info("Skipping '%s' because target '%s' does not exist", a["name"], a["target"])
                    continue
                _write_alias(cmd, a, target)
                alias_written.add(a["name"].casefold())

        for s in i.get("shortcuts", ()):
            if cmd.enable_shortcut_kinds and s["kind"] not in cmd.enable_shortcut_kinds:
                continue
            if cmd.disable_shortcut_kinds and s["kind"] in cmd.disable_shortcut_kinds:
                continue
            try:
                create, cleanup = SHORTCUT_HANDLERS[s["kind"]]
            except LookupError:
                LOGGER.warn("Skipping invalid shortcut for '%s'", i["id"])
                LOGGER.debug("shortcut: %s", s)
            else:
                create(cmd, i, s)
                shortcut_written.setdefault(s["kind"], []).append((i, s))

    if cmd.global_dir and cmd.launcher_exe:
        for target in cmd.global_dir.glob("*.exe.__target__"):
            alias = target.with_suffix("")
            if alias.name.casefold() not in alias_written:
                LOGGER.debug("Unlink %s", alias)
                unlink(alias, f"Attempting to remove {alias} is taking some time. " +
                               "Ensure it is not is use, and please continue to wait " +
                               "or press Ctrl+C to abort.")
                target.unlink()

    for k, (_, cleanup) in SHORTCUT_HANDLERS.items():
        cleanup(cmd, shortcut_written.get(k, []))

    if path_warning and any(cmd.global_dir.glob("*.exe")):
        try:
            if not any(cmd.global_dir.match(p) for p in os.getenv("PATH", "").split(os.pathsep) if p):
                LOGGER.warn("""
Global shortcuts directory is not on PATH. Add it for global commands.
Directory: %s
""", cmd.global_dir)
        except Exception:
            LOGGER.debug("Failed to display PATH warning", exc_info=True)


def print_cli_shortcuts(cmd, tags):
    installs = cmd.get_installs()
    for tag in tags:
        for i in installs:
            if CompanyTag.from_dict(i).match(tag):
                aliases = ", ".join(sorted(a["name"] for a in i["alias"]))
                if aliases:
                    LOGGER.info("Installed %s as %s", i["displayName"], aliases)
                else:
                    LOGGER.info("Installed %s to %s", i["displayName"], i["prefix"])
                if i.get("default"):
                    LOGGER.info("This will be launched by default when you run 'python.exe'")
                break


def execute(cmd):
    LOGGER.debug("BEGIN install_command.execute: %r", cmd.args)

    # TODO: Consider reading the current console width
    # Though there's a solid argument we should just pick one and stick with it
    console_width = 79
    skip_shortcuts = False

    if cmd.target:
        target = Path(cmd.target)
        skip_shortcuts = True
        if len(cmd.args) > 1:
            raise ArgumentError("Unable to install multiple versions with --target")
        installed = []
    else:
        target = None
        installed = list(cmd.get_installs())

    if cmd.refresh:
        if cmd.args:
            LOGGER.warn("Ignoring arguments; --refresh always refreshes all installs.")
        update_all_shortcuts(cmd)

    if not cmd.args and not installed:
        LOGGER.debug("No tags provided, installing first version in index")
        cmd.args = [""]

    if cmd.automatic:
        LOGGER.info("*" * console_width)

    if cmd.from_script:
        from .scriptutils import find_install_from_script
        spec = find_install_from_script(cmd, cmd.from_script)
        if spec:
            cmd.args.append(spec)

    # In-process cache to save repeat downloads
    download_cache = {}

    for spec in cmd.args:
        if not spec:
            tag = None
        else:
            tag = tag_or_range(spec)
            LOGGER.info("Searching for Python matching %s", tag)
            if not cmd.force and installed:
                already_installed = [i for i in installed if tag.satisfied_by(CompanyTag.from_dict(i))]
                if already_installed:
                    # TODO: Implement install --update
                    LOGGER.info("%s is already installed", already_installed[0]["displayName"])
                    continue

        install = select_package(cmd, tag, download_cache)

        if cmd.dry_run:
            LOGGER.info("Selected to install %s (tag %s\\%s)",
                install['displayName'], install['company'], install['tag']
            )
            LOGGER.debug("Skipping rest of install due to --dry-run")
            continue

        package = cmd.download_dir / f"{install['id']}.zip"
        # Preserve nupkg extensions so we can directly reference Nuget packages
        if install["url"].casefold().endswith(".nupkg".casefold()):
            package = package.with_suffix(".nupkg")

        with ProgressPrinter("Downloading", maxwidth=console_width) as on_progress:
            download_package(cmd, install, package, download_cache, on_progress=on_progress)

        dest = target or (cmd.install_dir / install["id"])

        LOGGER.debug("Extracting %s", package)
        LOGGER.debug("To %s", dest)
        try:
            rmtree(dest, "Cleaning up a previous install is taking some time. " +
                         "Ensure Python is not running, and continue to wait " +
                         "or press Ctrl+C to abort.")
        except FileExistsError:
            LOGGER.warn(
                "Unable to remove previous install. " +
                "Please check your packages directory at %s for issues.",
                dest.parent
            )
            LOGGER.error("Install failed. Please check any output above and try again.")
            skip_shortcuts = True
            break

        with ProgressPrinter("Installing", maxwidth=console_width) as on_progress:
            extract_package(package, dest, on_progress=on_progress)

        if "shortcuts" in install:
            if cmd.enable_shortcut_kinds:
                install["shortcuts"] = [s for s in install["shortcuts"]
                                        if s["kind"] in cmd.enable_shortcut_kinds]
            if cmd.disable_shortcut_kinds:
                install["shortcuts"] = [s for s in install["shortcuts"]
                                        if s["kind"] not in cmd.disable_shortcut_kinds]

        LOGGER.debug("Write __install__.json to %s", dest)
        with open(dest / "__install__.json", "w", encoding="utf-8") as f:
            json.dump({
                **install,
                "url": sanitise_url(install["url"]),
                "source": sanitise_url(cmd.source),
            }, f, default=str)

        LOGGER.debug("Install complete")

    if not skip_shortcuts:
        update_all_shortcuts(cmd)
        print_cli_shortcuts(cmd, tags=map(CompanyTag, cmd.args))

    if cmd.automatic:
        LOGGER.info("To see all available commands, run 'python help'")
        LOGGER.info("*" * console_width)

    LOGGER.debug("END install_command.execute")
