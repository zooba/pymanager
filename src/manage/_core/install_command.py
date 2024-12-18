import json
import os

from pathlib import Path, PurePath

from .exceptions import ArgumentError, HashMismatchError
from .fsutils import ensure_tree, rmtree, unlink
from .indexutils import Index
from .logging import LOGGER, ProgressPrinter
from .tagutils import CompanyTag
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


def download_package(cmd, tag, cache, urlopen=_urlopen, urlretrieve=_urlretrieve):
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
            install = index.find_to_install(tag)
            break
        except LookupError:
            if not index.next_url:
                raise
            url = urljoin(url, index.next_url, to_parent=True)
            
    LOGGER.info("Installing %s", install["displayName"])

    dest = cmd.download_dir / f"{install['id']}.zip"

    # Preserve nupkg extensions so we can directly reference Nuget packages
    if install["url"].casefold().endswith(".nupkg".casefold()):
        dest = dest.with_suffix(".nupkg")

    if cmd.dry_run:
        LOGGER.info("Download skipped because of --dry-run")
        return dest, install

    if not cmd.force and dest.is_file():
        LOGGER.info("Download was found in the cache")
        LOGGER.debug("Download skipped because %s already exists", dest)
    else:
        with ProgressPrinter("Downloading") as on_progress:
            urlretrieve(install["url"], dest, on_progress=on_progress)
        LOGGER.debug("Downloaded to %s", dest)

    if "hash" in install:
        try:
            with open(dest, "rb") as f:
                _multihash(f, install["hash"])
        except HashMismatchError:
            unlink(dest)
            raise HashMismatchError("""The downloaded file could not be verified and has been deleted.
Please retry the installation and download the file again.""")
    return dest, install


def extract_package(package, prefix, calculate_dest=Path, on_progress=None):
    import zipfile

    if not on_progress:
        on_progress = lambda *_: None

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
    LOGGER.debug("Link %s to %s using %s", alias["name"], target, launcher)
    p.write_bytes(launcher.read_bytes())
    p.with_name(p.name + ".__target__").write_text(str(target), encoding="utf-8")


def update_all_shortcuts(cmd, path_warning=True):
    LOGGER.debug("Updating global shortcuts")
    written = set()
    for i in cmd.get_installs():
        for a in i["alias"]:
            target = i["prefix"] / a["target"]
            if not target.is_file():
                LOGGER.info("Skipping '%s' because target '%s' does not exist", a["name"], a["target"])
                continue
            _write_alias(cmd, a, target)
            written.add(a["name"].casefold())

    for target in cmd.global_dir.glob("*.exe.__target__"):
        alias = target.with_suffix("")
        if alias.name.casefold() not in written:
            LOGGER.debug("Unlink %s", alias)
            alias.unlink()
            target.unlink()

    if path_warning and any(cmd.global_dir.glob("*.exe")):
        if not any(cmd.global_dir.match(p) for p in os.getenv("PATH", "").split(os.pathsep)):
            LOGGER.warn("""
Global shortcuts directory is not on PATH. Add it for global commands.
Directory: %s
""", cmd.global_dir)


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

    if cmd.target:
        target = Path(cmd.target)
        if len(cmd.args) > 1:
            raise ArgumentError("Unable to install multiple versions with --target")
        installed = []
    else:
        target = None
        installed = list(cmd.get_installs())

    if not cmd.args and not installed:
        LOGGER.debug("No tags provided, installing first version in index")
        cmd.args = [""]

    if cmd.automatic:
        LOGGER.info("**********************************************************************")

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
        elif spec.lstrip().startswith(("<", ">", "=")):
            # TODO: Implement install from version range
            raise NotImplementedError("Version ranges are not yet supported")
        else:
            tag = CompanyTag(spec)
            LOGGER.info("Searching for Python matching %s", tag)
            if not cmd.force and installed:
                already_installed = [i for i in installed if CompanyTag.from_dict(i).match(tag)]
                if already_installed:
                    LOGGER.info("%s is already installed", already_installed[0]["displayName"])
                    continue

        package, install = download_package(cmd, tag, download_cache)

        dest = target or (cmd.install_dir / install["id"])

        LOGGER.debug("Extracting %s", package)
        LOGGER.debug("To %s", dest)
        rmtree(dest)
        if cmd.dry_run:
            LOGGER.info("Extract skipped because of --dry-run")
        else:
            with ProgressPrinter("Installing") as on_progress:
                extract_package(package, dest, on_progress=on_progress)
            LOGGER.debug("Write __install__.json to %s", dest)
            with open(dest / "__install__.json", "w", encoding="utf-8") as f:
                json.dump({
                    **install,
                    "url": sanitise_url(install["url"]),
                    "source": sanitise_url(cmd.source),
                }, f, default=str)

        LOGGER.debug("Install complete")

    if cmd.global_dir and cmd.launcher_exe and not cmd.target:
        update_all_shortcuts(cmd)

    print_cli_shortcuts(cmd, tags=map(CompanyTag, cmd.args))

    if cmd.automatic:
        LOGGER.info("**********************************************************************")

    LOGGER.debug("END install_command.execute")
