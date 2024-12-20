from .exceptions import InvalidFeedError
from .tagutils import CompanyTag, TagRange, tag_or_range
from .verutils import Version

SCHEMA = {
    "next": str,
    "versions": [
        {
            "schema": 1,
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
            # List of other kinds of shortcuts to create.
            "shortcuts": [{"kind": str, ...: ...}],
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


# More specific for better internal handling. Users don't need to distinguish.
class InvalidFeedVersionError(InvalidFeedError):
    pass


def _version_error(actual, expect, ctxt):
    return InvalidFeedVersionError("Expected {} {}; found {}".format(
        ".".join(ctxt), expect, actual,
    ))


def _one_dict_match(d, expect):
    if not isinstance(d, dict):
        return True
    if not isinstance(expect, dict):
        return True
    try:
        if expect["schema"] == d["schema"]:
            return True
    except KeyError:
        pass
    try:
        if expect["version"] == d["version"]:
            return True
    except KeyError:
        pass

    for k, v in expect.items():
        if isinstance(v, int) and d.get(k) != v:
            return False
    if ... not in expect:
        for k in d:
            if k not in expect:
                return False
    return True
    

def _one_or_list(d, expects, ctxt):
    if not isinstance(d, list):
        d = [d]
    ctxt.append("[]")
    for i, e in enumerate(d):
        ctxt[-1] = f"[{i}]"
        for expect in expects:
            if _one_dict_match(e, expect):
                yield _one(e, expect, ctxt)
                break
        else:
            raise InvalidFeedError("No matching item format at {}".format(
                ".".join(ctxt)
            ))
    del ctxt[-1]


def _one(d, expect, ctxt=None):
    if ctxt is None:
        ctxt = []
    if expect is None:
        raise InvalidFeedError("Unexpected key {}".format(".".join(ctxt)))
    if isinstance(expect, int):
        if d != expect:
            raise _version_error(d, expect, ctxt)
        return d
    if isinstance(expect, list):
        return list(_one_or_list(d, expect, ctxt))
    if expect is ...:
        # Allow ... value for arbitrary value types
        return d
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
                        raise InvalidFeedError("Unexpected key {}".format(".".join(ctxt))) from None
                d2[k] = _one(v, expect2, ctxt)
                del ctxt[-1]
            return d2
        raise _schema_error(dict, expect, ctxt)
    if isinstance(expect, type) and isinstance(d, expect):
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
        return "<Index({!r}, next={!r}, versions=[...{} entries])>".format(
            self.source_url,
            self.next_url,
            len(self.versions),
        )

    def find_to_install(self, tag, *, loose_company=False, prefer_prerelease=False):
        if not tag:
            tag = CompanyTag("", "")
        if isinstance(tag, str):
            tag = tag_or_range(tag)
        for i in self.versions:
            if prefer_prerelease or not i["sort-version"].is_prerelease:
                if isinstance(tag, TagRange):
                    for_tags = [CompanyTag(i["company"], i["tag"], loose_company=loose_company)]
                else:
                    for_tags = [CompanyTag(i["company"], t, loose_company=loose_company)
                                for t in i.get("install-for", [])]
                if any(tag.satisfied_by(t) for t in for_tags):
                    return i
        if not prefer_prerelease:
            return self.find_to_install(tag, loose_company=loose_company, prefer_prerelease=True)
        if not loose_company:
            return self.find_to_install(tag, loose_company=True, prefer_prerelease=prefer_prerelease)
        raise LookupError(tag)
