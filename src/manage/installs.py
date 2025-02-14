import json

from pathlib import Path

from .exceptions import NoInstallFoundError, NoInstallsError
from .logging import LOGGER
from .tagutils import CompanyTag, tag_or_range
from .verutils import Version


def _make_sort_key(install):
    # Our sort key orders from most-preferred to least
    return (
        # Non-prereleases always sort last
        0 if not Version(install["sort-version"]).is_prerelease else 1,
        # Order by descending tags
        CompanyTag(install.get("company"), install.get("tag")),
    )


def _get_installs(install_dir):
    for p in Path(install_dir).glob("*/__install__.json"):
        with p.open("r", encoding="utf-8") as f:
            j = json.load(f)

        if j.get("schema", 0) == 1:
            yield {
                **j,
                "prefix": p.parent,
                "executable": p.parent / j["executable"],
            }
        else:
            LOGGER.warn(
                "Unrecognized schema %s in %s. You may need to update.",
                j.get("schema", "None"),
                p,
            )
            continue


def _get_unmanaged_installs():
    from .pep514utils import get_unmanaged_installs
    try:
        return get_unmanaged_installs()
    except Exception as ex:
        LOGGER.warn("Failed to read unmanaged installs: %s", ex)
        LOGGER.debug("TRACEBACK:", exc_info=True)
    return []


def _get_venv_install(virtual_env):
    if not virtual_env:
        raise LookupError
    venv = Path(virtual_env)
    try:
        pyvenv_cfg = (venv / "pyvenv.cfg").read_text("utf-8", "ignore")
    except OSError as ex:
        raise LookupError from ex
    ver = [v.strip() for k, _, v in (s.partition("=") for s in pyvenv_cfg.splitlines())
           if k.strip().casefold() == "version".casefold()]
    return {
        "id": "__active-virtual-env",
        "display-name": "Active virtual environment",
        "sort-version": ver[0] if ver else "0.0",
        "company": "<venv>",
        "tag": "---",
        "default": True,
        "alias": [
            {"name": "python.exe", "target": r"Scripts\python.exe"},
            {"name": "pythonw.exe", "target": r"Scripts\pythonw.exe", "windowed": 1},
        ],
        # Invalid tags, but the target will be used to determine whether to use
        # python.exe or pythonw.exe
        "run-for": [
            {"tag": "<>", "target": r"Scripts\python.exe"},
            {"tag": "<>", "target": r"Scripts\pythonw.exe", "windowed": 1},
        ],
        "prefix": Path(virtual_env),
        "executable": Path(virtual_env) / r"Scripts\python.exe",
    }


def get_installs(
    install_dir,
    include_unmanaged=True,
    virtual_env=None,
):
    installs = list(_get_installs(install_dir))

    if include_unmanaged:
        um_installs = _get_unmanaged_installs()
        installs.extend(um_installs)

    installs.sort(key=_make_sort_key)

    if virtual_env:
        try:
            installs.insert(0, _get_venv_install(virtual_env))
        except LookupError:
            pass

    return installs


def _patch_install_to_run(i, run_for):
    return {
        **i,
        "executable": i["prefix"] / run_for["target"],
        "executable_args": run_for.get("args", ()),
    }


def get_matching_install_tags(
    installs,
    tag,
    windowed=None,
    default_platform=None,
    single_tag=False,
):
    exact_matches = []
    core_matches = []
    matches = []
    unmanaged_matches = []

    # Installs are in the correct order, so we'll first collect all the matches.
    for i in installs:
        for t in i.get("run-for", ()):
            ct = CompanyTag(i["company"], t["tag"])
            if tag and ct == tag:
                exact_matches.append((i, t))
            elif not tag or tag.satisfied_by(ct):
                if i.get("unmanaged"):
                    unmanaged_matches.append((i, t))
                elif ct.is_core:
                    core_matches.append((i, t))
                else:
                    matches.append((i, t))
            if single_tag:
                break

    matches = [*core_matches, *matches, *unmanaged_matches]

    LOGGER.debug("Tag %s matched %s installs exactly, %s core installs by "
                 "prefix, %s other installs by prefix, and %s unmanaged.",
                 tag, len(exact_matches), len(core_matches), len(matches),
                 len(unmanaged_matches))

    best = [*exact_matches, *core_matches, *matches, *unmanaged_matches]

    # Filter for 'windowed' matches. If none, keep them all
    if windowed is not None:
        windowed = bool(windowed)
        best = [(i, t) for i, t in best if windowed == bool(t.get("windowed"))] or best
        LOGGER.debug("%s left after filtering for windowed = %s", len(best), windowed)

    # Filter for default_platform matches (by tag suffix). If none, keep them all
    if default_platform:
        default_platform = default_platform.casefold()
        best = [(i, t) for i, t in best
                if t["tag"].casefold().endswith(default_platform)] or best
        LOGGER.debug("%s left after filtering for default_platform = %s",
                     len(best), default_platform)

    return best


def get_install_to_run(
    install_dir,
    default_tag,
    tag,
    include_unmanaged=True,
    windowed=False,
    virtual_env=None,
    default_platform=None,
):
    """Returns the first install matching 'tag'.
    """
    installs = get_installs(
        install_dir,
        include_unmanaged=include_unmanaged,
        virtual_env=virtual_env,
    )

    if not installs:
        raise NoInstallsError

    if not tag:
        tag = tag_or_range(default_tag)
        used_default = True
    else:
        tag = tag_or_range(tag)
        used_default = False

    best = get_matching_install_tags(
        installs,
        tag,
        windowed=windowed,
        default_platform=default_platform,
    )

    if best:
        return _patch_install_to_run(*best[0])

    if used_default:
        # It's legitimate to have no default runtime, but we're going to treat
        # it as if you have none at all. That way we get useful auto-install
        # behaviour.
        raise NoInstallsError

    raise NoInstallFoundError(tag=tag)
