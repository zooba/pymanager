import json
import os

from .exceptions import (
    ArgumentError,
    AutomaticInstallDisabledError,
    HashMismatchError,
    NoInstallFoundError,
)
from .fsutils import ensure_tree, rmtree, unlink
from .indexutils import Index
from .logging import LOGGER, ProgressPrinter
from .pathutils import Path, PurePath
from .tagutils import install_matches_any, tag_or_range
from .urlutils import (
    sanitise_url,
    urlopen as _urlopen,
    urlretrieve as _urlretrieve,
    IndexDownloader,
)


# TODO: Consider reading the current console width
# Though there's a solid argument we should just pick one and stick with it
CONSOLE_WIDTH = 79


# In-process cache to save repeat downloads
DOWNLOAD_CACHE = {}


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


def select_package(cmd, source, tag, cache, *, urlopen=_urlopen, by_id=False):
    """Finds suitable package from index.json that looks like:
    {"versions": [
      {"id": ..., "company": ..., "tag": ..., "url": ..., "hash": {"sha256": hexdigest}},
      ...
    ]}
    tag may be a list of tags that are allowed to match exactly.
    """

    first_exc = None
    for index in IndexDownloader(cmd.source, Index, {}, cache):
        try:
            if by_id:
                for v in index.versions:
                    if v["id"].casefold() == tag.casefold():
                        return v
                raise LookupError("Could not find a runtime matching '{}' at '{}'".format(
                    tag, sanitise_url(index.source_url)
                ))
            return index.find_to_install(tag)
        except LookupError as ex:
            first_exc = ex

    if first_exc:
        raise first_exc

    assert False, "unreachable code"
    raise RuntimeError("End of select_package reached")


def download_package(cmd, install, dest, cache, *, on_progress=None, urlopen=_urlopen, urlretrieve=_urlretrieve):
    if not cmd.force and dest.is_file():
        LOGGER.verbose("Download was found in the cache. (Pass --force to ignore cached downloads.)")
        try:
            validate_package(install, dest, delete=False)
        except HashMismatchError:
            LOGGER.info("Cached file could not be verified. Downloading it again.")
        else:
            LOGGER.debug("Download skipped because %s already exists", dest)
            return dest

    if cmd.bundled_dir:
        bundled = cmd.bundled_dir / dest.name
        if bundled.is_file():
            try:
                validate_package(install, bundled, delete=False)
            except HashMismatchError:
                LOGGER.debug("Bundled file at %s did not match expected hash.", bundled)
            else:
                LOGGER.verbose("Using bundled file at %s", bundled)
                return bundled

    unlink(dest, "Removing old download is taking some time. " + 
                 "Please continue to wait, or press Ctrl+C to abort.")

    def _find_creds(url):
        from .urlutils import extract_url_auth, unsanitise_url
        LOGGER.verbose("Finding credentials for %s.", url)
        auth = extract_url_auth(unsanitise_url(url, [cmd.source]))
        if auth:
            LOGGER.debug("Found credentials in URL or configured source.")
            return auth
        auth = os.getenv("PYMANAGER_USERNAME", ""), os.getenv("PYMANAGER_PASSWORD", "")
        if auth[0]:
            LOGGER.debug("Found credentials in environment.")
            return auth
        return None

    ensure_tree(dest)
    urlretrieve(install["url"], dest, on_progress=on_progress, on_auth_request=_find_creds)
    LOGGER.debug("Downloaded to %s", dest)
    return dest


def validate_package(install, dest, *, delete=True):
    if "hash" in install:
        try:
            with open(dest, "rb") as f:
                _multihash(f, install["hash"])
        except HashMismatchError as ex:
            if not delete:
                raise
            unlink(dest, "Deleting downloaded files is taking some time. " +
                         "Please continue to wait, or press Ctrl+C to abort.")
            raise HashMismatchError() from ex


def extract_package(package, prefix, calculate_dest=Path, *, on_progress=None, repair=False):
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
            if repair:
                unlink(dest, "Deleting an existing file is taking some time. " +
                             "Please ensure Python is not running, and continue to wait " +
                             "or press Ctrl+C to abort (which will leave your install corrupted).")
            elif dest.exists():
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
    LOGGER.debug("Create %s linking to %s using %s", alias["name"], target, launcher)
    if not launcher or not launcher.is_file():
        LOGGER.warn("Skipping %s alias because the launcher template was not found.", alias["name"])
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


def _create_arp_entry(cmd, install, shortcut):
    # ARP = Add/Remove Programs
    from .arputils import create_one
    create_one(install, shortcut)


def _cleanup_arp_entries(cmd, install_shortcut_pairs):
    from .arputils import cleanup
    cleanup([i for i, s in install_shortcut_pairs])


SHORTCUT_HANDLERS = {
    "pep514": (_create_shortcut_pep514, _cleanup_shortcut_pep514),
    "start": (_create_start_shortcut, _cleanup_start_shortcut),
    "uninstall": (_create_arp_entry, _cleanup_arp_entries),
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
                    LOGGER.warn("Skipping alias '%s' because target '%s' does not exist", a["name"], a["target"])
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

    if cmd.global_dir and cmd.global_dir.is_dir() and cmd.launcher_exe:
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

    if path_warning and cmd.global_dir and cmd.global_dir.is_dir() and any(cmd.global_dir.glob("*.exe")):
        try:
            if not any(cmd.global_dir.match(p) for p in os.getenv("PATH", "").split(os.pathsep) if p):
                LOGGER.info("")
                LOGGER.info("!B!Global shortcuts directory is not on PATH. " +
                            "Add it for easy access to global Python commands.!W!")
                LOGGER.info("!B!Directory to add: !Y!%s!W!", cmd.global_dir)
                LOGGER.info("")
        except Exception:
            LOGGER.debug("Failed to display PATH warning", exc_info=True)


def print_cli_shortcuts(cmd):
    installs = cmd.get_installs()
    seen = set()
    installs = [i for i in installs if install_matches_any(i, cmd.tags)]
    for i in installs:
        aliases = sorted(a["name"] for a in i["alias"] if a["name"].casefold() not in seen)
        seen.update(n.casefold() for n in aliases)
        if i.get("default") and aliases:
            LOGGER.info("%s will be launched by !G!python.exe!W! and also %s",
                        i["display-name"], ", ".join(aliases))
        elif i.get("default"):
            LOGGER.info("%s will be launched by !G!python.exe!W!.", i["display-name"])
        elif aliases:
            LOGGER.info("%s will be launched by %s",
                        i["display-name"], ", ".join(aliases))
        else:
            LOGGER.info("Installed %s to %s", i["display-name"], i["prefix"])


def _find_one(cmd, source, tag, *, installed=None, by_id=False):
    if by_id:
        LOGGER.debug("Searching for Python with ID %s", tag)
    elif tag:
        LOGGER.verbose("Searching for Python matching %s", tag)
    else:
        LOGGER.verbose("Searching for default Python version")
    install = select_package(cmd, source, tag, DOWNLOAD_CACHE, by_id=by_id)

    if by_id:
        return install

    existing = [i for i in (installed or ()) if i["id"].casefold() == install["id"].casefold()]
    if not existing:
        return install

    if cmd.force:
        LOGGER.warn("Overwriting existing %s install because of --force.", existing[0]["display-name"])
        return install

    if cmd.repair:
        return existing[0]

    if cmd.update:
        if install["sort-version"] > existing[0]["sort-version"]:
            return install
        LOGGER.info("%s is already up to date.", existing[0]["display-name"])
        return None

    # Return the package if it was requested in a way that wouldn't have
    # selected the existing package (e.g. full version match)
    if not install_matches_any(existing[0], [tag]):
        if cmd.ask_yn("!Y!Your existing %s install will be replaced by " +
                      "%s. Continue?!W!", existing[0]["display-name"],
                      install["display-name"]):
            return install
        LOGGER.debug("Not overwriting existing install.")
        return None

    LOGGER.info("%s is already installed.", existing[0]["display-name"])
    return None


def _download_one(cmd, source, install, download_dir, *, must_copy=False):
    package = download_dir / f"{install['id']}-{install['sort-version']}.zip"
    # Preserve nupkg extensions so we can directly reference Nuget packages
    if install["url"].casefold().endswith(".nupkg".casefold()):
        package = package.with_suffix(".nupkg")

    with ProgressPrinter("Downloading", maxwidth=CONSOLE_WIDTH) as on_progress:
        package = download_package(cmd, install, package, DOWNLOAD_CACHE, on_progress=on_progress)
    validate_package(install, package)
    if must_copy and package.parent != download_dir:
        import shutil
        dst = download_dir / package.name
        shutil.copyfile(package, dst)
        return dst
    return package


def _install_one(cmd, source, install, *, target=None):
    if cmd.repair:
        LOGGER.info("Repairing %s.", install['display-name'])
    elif cmd.update:
        LOGGER.info("Updating to %s.", install['display-name'])
    else:
        LOGGER.info("Installing %s.", install['display-name'])
    LOGGER.verbose("Tag: %s\\%s", install['company'], install['tag'])

    if cmd.dry_run:
        LOGGER.info("Skipping rest of install due to --dry-run")
        return

    package = _download_one(cmd, source, install, cmd.download_dir)

    dest = target or (cmd.install_dir / install["id"])

    LOGGER.verbose("Extracting %s to %s", package, dest)
    if not cmd.repair:
        try:
            rmtree(dest, "Removing the previous install is taking some time. " +
                         "Ensure Python is not running, and continue to wait " +
                         "or press Ctrl+C to abort.")
        except FileExistsError:
            LOGGER.error(
                "Unable to remove previous install. " +
                "Please check your packages directory at %s for issues.",
                dest.parent
            )
            raise

    with ProgressPrinter("Extracting", maxwidth=CONSOLE_WIDTH) as on_progress:
        extract_package(package, dest, on_progress=on_progress, repair=cmd.repair)

    if target:
        unlink(
            dest / "__install__.json",
            "Removing metadata from the install is taking some time. Please " +
            "continue to wait, or press Ctrl+C to abort."
        )
    else:
        try:
            with open(dest / "__install__.json", "r", encoding="utf-8-sig") as f:
                LOGGER.debug("Updating from __install__.json in %s", dest)
                for k, v in json.load(f).items():
                    if not install.setdefault(k, v):
                        install[k] = v
        except FileNotFoundError:
            pass
        except (TypeError, ValueError):
            LOGGER.error(
                "Invalid data found in bundled install data. " +
                "Please report this to the provider of your package."
            )
            raise

        if "shortcuts" in install:
            # This saves our original set of shortcuts, so a later repair operation
            # can enable those that were originally disabled.
            shortcuts = install.setdefault("__original-shortcuts", install["shortcuts"])
            if cmd.enable_shortcut_kinds:
                shortcuts = [s for s in shortcuts
                             if s["kind"] in cmd.enable_shortcut_kinds]
            if cmd.disable_shortcut_kinds:
                shortcuts = [s for s in shortcuts
                             if s["kind"] not in cmd.disable_shortcut_kinds]
            install["shortcuts"] = shortcuts

        LOGGER.debug("Write __install__.json to %s", dest)
        with open(dest / "__install__.json", "w", encoding="utf-8") as f:
            json.dump({
                **install,
                "url": sanitise_url(install["url"]),
                "source": sanitise_url(source),
            }, f, default=str)

    LOGGER.verbose("Install complete")


def _fatal_install_error(cmd, ex):
    logfile = cmd.get_log_file()
    if logfile:
        LOGGER.error("An error occurred. Please check any output above, "
                     "or the log file, and try again.")
        LOGGER.info("Log file for this session: !Y!%s!W!", logfile)
        # TODO: Update issues URL to actual repository
        LOGGER.info("If you cannot resolve it yourself, please report the error with "
                    "your log file at https://discuss.python.org/t/77900/ (during testing).")
    else:
        LOGGER.error("An error occurred. Please check any output above, "
                     "and try again with -vv for more information.")
        # TODO: Update issues URL to actual repository
        LOGGER.info("If you cannot resolve it yourself, please report the error with "
                    "verbose output file at https://discuss.python.org/t/77900/ (during testing).")
    LOGGER.debug("TRACEBACK:", exc_info=True)
    raise SystemExit(getattr(ex, "winerror", getattr(ex, "errno", 0)) or 1) from ex


def execute(cmd):
    LOGGER.debug("BEGIN install_command.execute: %r", cmd.args)

    if cmd.refresh:
        if cmd.args:
            LOGGER.warn("Ignoring arguments; --refresh always refreshes all installs.")
        LOGGER.info("Refreshing install registrations.")
        update_all_shortcuts(cmd)
        LOGGER.debug("END install_command.execute")
        return

    if cmd.force:
        # Ensure we always do clean installs when --force specified
        cmd.repair = False
        cmd.update = False

    if cmd.automatic:
        if not cmd.automatic_install:
            LOGGER.debug("automatic_install is not set - exiting")
            raise AutomaticInstallDisabledError()
        LOGGER.info("!B!" + "*" * CONSOLE_WIDTH + "!W!")

    download_index = {"versions": []}

    if not cmd.by_id:
        cmd.tags = [tag_or_range(arg if arg.casefold() != "default".casefold() else cmd.default_tag)
                    for arg in cmd.args]

        if not cmd.tags and cmd.automatic:
            cmd.tags = [tag_or_range(cmd.default_tag)]
    else:
        if cmd.from_script:
            raise ArgumentError("Cannot use --by-id and --from-script together")
        cmd.tags = [arg.casefold() for arg in cmd.args]
        if not cmd.tags:
            raise ArgumentError("One or more IDs are required with --by-id")


    try:
        if cmd.target:
            if len(cmd.tags) > 1:
                raise ArgumentError("Unable to install multiple versions with --target")
            try:
                tag = cmd.tags[0]
            except IndexError:
                if cmd.default_tag:
                    LOGGER.debug("No tags provided, installing default tag %s", cmd.default_tag)
                    tag = cmd.default_tag
                else:
                    LOGGER.debug("No tags provided, installing first runtime in feed")
                    tag = None

            try:
                first_exc = None
                for source in [cmd.source, cmd.fallback_source]:
                    if not source:
                        continue
                    try:
                        install = _find_one(cmd, source, tag, by_id=cmd.by_id)
                        break
                    except LookupError:
                        LOGGER.error("Failed to find a suitable install for '%s'.", tag)
                        raise NoInstallFoundError()
                    except Exception as ex:
                        LOGGER.debug("Capturing error in case fallbacks fail", exc_info=True)
                        first_exc = first_exc or ex
                else:
                    if first_exc:
                        raise first_exc
                    # Reachable if all sources are blank
                    raise RuntimeError("All install sources failed, nothing can be installed.")
                if install:
                    _install_one(cmd, source, install, target=Path(cmd.target))
                return
            except Exception as ex:
                return _fatal_install_error(cmd, ex)

        if cmd.from_script:
            # Have already checked that we are not using --by-id
            from .scriptutils import find_install_from_script
            spec = find_install_from_script(cmd, cmd.from_script)
            if spec:
                cmd.tags.append(tag_or_range(spec))
            else:
                cmd.tags.append(tag_or_range(cmd.default_tag))

        if cmd.virtual_env:
            LOGGER.debug("Clearing virtual_env setting to avoid conflicts during install.")
            cmd.virtual_env = None
        installed = list(cmd.get_installs())

        if cmd.download:
            if cmd.force:
                rmtree(cmd.download)
            cmd.download.mkdir(exist_ok=True, parents=True)
            # Do not check for existing installs
            installed = []

        try:
            if not cmd.tags:
                if cmd.repair:
                    LOGGER.verbose("No tags provided, repairing all installs:")
                    for install in installed:
                        _install_one(cmd, install)
                    # Fallthrough is safe - cmd.tags is empty
                elif cmd.update:
                    LOGGER.verbose("No tags provided, updating all installs:")
                    for install in installed:
                        first_exc = None
                        update = None
                        for source in [install.get('source'), cmd.source, cmd.fallback_source]:
                            if not source:
                                continue
                            try:
                                update = _find_one(cmd, source, install['id'], by_id=True)
                                if update:
                                    break
                            except LookupError:
                                LOGGER.error("Failed to find a suitable update for '%s'.", install['id'])
                                raise NoInstallFoundError()
                            except Exception as ex:
                                LOGGER.debug("Capturing error in case fallbacks fail", exc_info=True)
                                first_exc = first_exc or ex
                        else:
                            if first_exc:
                                raise first_exc
                            # Reachable if all sources are blank
                            raise RuntimeError("All install sources failed, nothing can be updated.")
                        if update:
                            if update['sort-version'] > install['sort-version']:
                                _install_one(cmd, update)
                            else:
                                LOGGER.verbose("%s is already up to date.", install['display-name'])
                        else:
                            LOGGER.verbose("Could not find update for %s.",
                                install['display-name'], install['id'])
                    # Fallthrough is safe - cmd.tags is empty
                else:
                    raise ArgumentError("Specify at least one tag to install, or 'default' for "
                                        "the latest recommended release.")

            installs = []
            first_exc = None
            for source in [cmd.source, cmd.fallback_source]:
                if not source:
                    continue
                LOGGER.debug("Searching %s", source)
                try:
                    for tag in cmd.tags:
                        install = _find_one(cmd, source, tag, installed=installed, by_id=cmd.by_id)
                        if install:
                            installs.append(install)
                    break
                except LookupError:
                    LOGGER.error("Failed to find a suitable install for '%s'.", tag)
                    raise NoInstallFoundError()
                except Exception as ex:
                    LOGGER.debug("Capturing error in case fallbacks fail", exc_info=True)
                    first_exc = first_exc or ex
            else:
                if first_exc:
                    raise first_exc
                # Reachable if all sources are blank
                raise RuntimeError("All install sources failed, nothing can be installed.")
            for install in installs:
                if cmd.download:
                    LOGGER.info("Downloading %s", install["display-name"])
                    package = _download_one(cmd, source, install, cmd.download, must_copy=True)
                    download_index["versions"].append({
                        **install,
                        "url": package.name,
                    })
                else:
                    _install_one(cmd, source, install)
        except ArgumentError:
            raise
        except NoInstallFoundError as ex:
            raise SystemExit(1) from ex
        except Exception as ex:
            return _fatal_install_error(cmd, ex)

        if cmd.download:
            with open(cmd.download / "index.json", "w", encoding="utf-8") as f:
                json.dump(download_index, f, indent=2, default=str)
            LOGGER.info("Offline index has been generated at !Y!%s!W!.", cmd.download)
            LOGGER.info(
                "Use '!G!py install -s .\\%s [tags ...]!W!' to install from this index.",
                cmd.download.name
            )
        else:
            update_all_shortcuts(cmd)
            print_cli_shortcuts(cmd)

    finally:
        if cmd.automatic:
            LOGGER.info("To see all available commands, run '!G!py help!W!'")
            LOGGER.info("!B!" + "*" * CONSOLE_WIDTH + "!W!")

        LOGGER.debug("END install_command.execute")
