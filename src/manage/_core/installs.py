import json

from pathlib import Path

from .logging import LOGGER
from .tagutils import CompanyTag
from .verutils import Version


def _make_sort_key(kwargs):
    # Our sort key orders from most-preferred to least
    return (
        # Non-prereleases always sort last
        0 if not Version(kwargs["sort-version"]).is_prerelease else 1,
        # Order by descending tags
        CompanyTag(kwargs.get("company"), kwargs.get("tag")),
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


def get_installs(install_dir, default_tag):
    installs = sorted(_get_installs(install_dir), key=_make_sort_key)
    seen_alias = set()
    for i in installs:
        i_tag = CompanyTag.from_dict(i)
        aliases = i.setdefault("alias", ())
        if aliases:
            new_aliases = [a for a in aliases if a["name"].casefold() not in seen_alias]
            seen_alias.update(a["name"].casefold() for a in aliases)
            i["alias"] = new_aliases
        if default_tag and i_tag.match(default_tag):
            default_tag = None
            i["default"] = True
    return installs


def get_install_to_run(install_dir, default_tag, tag):
    """Returns the first install matching 'tag'.
    """
    installs = get_installs(install_dir, default_tag)
    if not installs:
        return
    if not tag:
        return installs[0]
    tag = CompanyTag(tag)
    # Exact match search
    for i in installs:
        for t in i.get("run-for", ()):
            if CompanyTag(i["company"], t["tag"]) == tag:
                return {**i, "executable": i["prefix"] / t["target"]}
    # Prefix match search
    for i in installs:
        for t in i.get("run-for", ()):
            if CompanyTag(i["company"], t["tag"]).match(tag):
                return {**i, "executable": i["prefix"] / t["target"]}
    raise LookupError(tag)
