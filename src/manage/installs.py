import json

from pathlib import Path

from .exceptions import NoInstallFoundError, NoInstallsError
from .logging import LOGGER
from .tagutils import CompanyTag
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


def get_installs(install_dir, default_tag, include_unmanaged=True):
    installs = sorted(_get_installs(install_dir), key=_make_sort_key)

    if include_unmanaged:
        from .pep514utils import get_unmanaged_installs
        try:
            um_installs = get_unmanaged_installs()
        except Exception as ex:
            LOGGER.warn("Failed to read unmanaged installs: %s", ex)
            LOGGER.debug("TRACEBACK:", exc_info=True)
        else:
            installs.extend(um_installs)
            installs.sort(key=_make_sort_key)

    seen_alias = set()
    for i in installs:
        i_tag = CompanyTag.from_dict(i)
        if default_tag and not i.get("unmanaged") and i_tag.match(default_tag):
            default_tag = None
            i["default"] = True
        aliases = i.setdefault("alias", ())
        if aliases:
            new_aliases = [a for a in aliases if a["name"].casefold() not in seen_alias]
            if i.get("default"):
                new_aliases.insert(0, {"name": "python.exe", "target": i["executable"]})
            seen_alias.update(a["name"].casefold() for a in aliases)
            i["alias"] = new_aliases
    return installs


def _patch_install_to_run(i, run_for):
    return {
        **i,
        "executable": i["prefix"] / run_for["target"],
        "executable_args": run_for.get("args", ()),
    }

def get_install_to_run(install_dir, default_tag, tag, include_unmanaged=True, windowed=False):
    """Returns the first install matching 'tag'.
    """
    installs = get_installs(install_dir, default_tag, include_unmanaged=include_unmanaged)

    if not installs:
        raise NoInstallsError

    best_non_windowed = None

    if not tag:
        for i in installs:
            if i.get("default"):
                for t in i.get("run-for", ()):
                    if bool(windowed) == bool(t.get("windowed")):
                        return _patch_install_to_run(i, t)
                    if not best_non_windowed:
                        best_non_windowed = _patch_install_to_run(i, t)
                if best_non_windowed:
                    return best_non_windowed
                break
        raise NoInstallFoundError()

    tag = CompanyTag(tag)

    # Exact match search
    for i in installs:
        for t in i.get("run-for", ()):
            if CompanyTag(i["company"], t["tag"]) == tag:
                if bool(windowed) == bool(t.get("windowed")):
                    return _patch_install_to_run(i, t)
                if not best_non_windowed:
                    best_non_windowed = _patch_install_to_run(i, t)

    # Prefix match search
    for i in installs:
        for t in i.get("run-for", ()):
            if CompanyTag(i["company"], t["tag"]).match(tag):
                if bool(windowed) == bool(t.get("windowed")):
                    return _patch_install_to_run(i, t)
                if not best_non_windowed:
                    best_non_windowed = _patch_install_to_run(i, t)

    # No matches found for correct windowed mode, so pick the best non-match
    if best_non_windowed:
        return best_non_windowed

    raise NoInstallFoundError(tag=tag)
