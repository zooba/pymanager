from .exceptions import InvalidFeedError
from .verutils import Version

SCHEMA = {
    "next": str,
    "versions": [
        {
            # Should be 1.
            "schema": int,
            # Unique ID used for install detection/side-by-sides
            "id": str,
            # Version used to sort installs. Also determines prerelease
            "sort-version": Version,
            # Company field
            "company": str,
            # Default tag, mainly for UI purposes. Must also be specified in
            # 'install-for' and 'run-for'.
            "tag": str,
            # List of tags to install this package for. Does not have to be
            # unique across all installs; the first match will be selected.
            "install-for": [str],
            # List of tags to run this package for. Does not have to be unique
            # across all installs; the first match will be selected.
            "run-for": [{"tag": str, "target": str}],
            # List of global CLI aliases to create for this package. Does not
            # have to be unique across all installs; the first match will be
            # created.
            "alias": [{"name": str, "target": str, "windowed": int}],
            # List of other kinds of shortcuts to create. Additional
            "shortcuts": [{"name": str, "target": str, "kind": str, ...: ...}],
            # Name to display in the UI
            "displayName": str,
            # [RESERVED] Install prefix. This will always be overwritten, so
            # don't specify it in the index.
            "prefix": None,
            # Default executable path (relative to 
            "executable": str,
            # URL to download the package
            "url": str,
            # Optional set of hashes to validate the download
            "hash": {
                ...: str,
            },
        },
    ],
}


def _typename(t):
    if isinstance(t, type):
        return t.__name__
    if isinstance(t, tuple):
        return ", ".join(map(_typename, t))
    return type(t).__name__


def _schema_error(actual, expect, ctxt):
    return InvalidFeedError("Expected '{}' at {}; found '{}'".format(
        _typename(expect), ".".join(ctxt), _typename(actual),
    ))


def _one_or_list(d, expect, ctxt):
    if isinstance(d, list):
        ctxt.append("[]")
        for i, e in enumerate(d):
            ctxt[-1] = f"[{i}]"
            yield _one(e, expect, ctxt)
        del ctxt[-1]
    else:
        ctxt.append("[0]")
        yield _one(d, expect, ctxt)
        del ctxt[-1]


def _one(d, expect, ctxt=None):
    if ctxt is None:
        ctxt = []
    if expect is None:
        raise InvalidFeedError("Unexpected key {}".format(".".join(ctxt)))
    if isinstance(d, dict):
        if isinstance(expect, dict):
            d2 = {}
            for k, v in d.items():
                ctxt.append(k)
                try:
                    expect2 = expect[k]
                except LookupError:
                    # Allow ... key for arbitrary key names
                    try:
                        expect2 = expect[...]
                    except LookupError:
                        raise InvalidFeedError("Unexpected key '{}' at {}".format(
                            k, ".".join(ctxt)
                        )) from None
                d2[k] = _one(v, expect2, ctxt)
                del ctxt[-1]
            return d2
        raise _schema_error(d, dict, ctxt)
    if isinstance(expect, list):
        return list(_one_or_list(d, expect[0], ctxt))
    if isinstance(expect, type) and isinstance(d, expect):
        return d
    if expect is ...:
        # Allow ... value for arbitrary value types
        return d
    try:
        return expect(d)
    except Exception as ex:
        raise _schema_error(d, expect, ctxt) from ex


class Index:
    def __init__(self, source_url, d):
        validated = _one(d, SCHEMA)
        self.source_url = source_url
        self.next_url = validated.get("next")
        self.versions = sorted(validated["versions"], key=lambda v: v["sort-version"], reverse=True)

    def __repr__(self):
        return "<Index(next={!r}, versions=[...{} entries])>".format(
            self.next_url,
            len(self.versions),
        )

    def find_to_install(self, tag, prefer_prerelease=False):
        if not tag:
            for i in self.versions:
                if prefer_prerelease or not i["sort-version"].is_prerelease:
                    return i
        else:
            c = tag.company.casefold()
            for i in self.versions:
                if c and not i.get("company", c).casefold().startswith(c):
                    continue
                if tag.tag in i.get("install-for", ()):
                    if prefer_prerelease or not i["sort-version"].is_prerelease:
                        return i
        if not prefer_prerelease:
            return self.find_to_install(tag, prefer_prerelease=True)
        raise LookupError(tag)
