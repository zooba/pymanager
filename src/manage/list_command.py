import json
import sys

from .exceptions import ArgumentError, SilentError
from .logging import LOGGER


def _exe_partition(n):
    n1, sep, n2 = n.rpartition(".")
    n2 = sep + n2
    while n1 and n1[-1] in "0123456789.-":
        n2 = n1[-1] + n2
        n1 = n1[:-1]
    w = ""
    if n1 and n1[-1] == "w":
        w = "w"
        n1 = n1[:-1]
    return n1, w, n2


def _format_alias(i):
    try:
        alias = i["alias"]
    except KeyError:
        return ""
    if not alias:
        return ""
    if len(alias) == 1:
        return i["alias"][0]["name"]
    names = {_exe_partition(a["name"].casefold()): a["name"] for a in alias}
    for n1, w, n2 in list(names):
        k = (n1, "", n2)
        if w and k in names:
            del names[n1, w, n2]
            n1, _, n2 = _exe_partition(names[k])
            names[k] = f"{n1}[w]{n2}"
    return ", ".join(names[n] for n in sorted(names))


def _ljust(s, n):
    if len(s) <= n:
        return s.ljust(n)
    return s[:n - 3] + "..."


def format_table(installs):
    columns = {
        "company": "Managed By",
        "tag": "Tag",
        "displayName": "Name",
        "sort-version": "Version",
        "alias": "Alias",
    }
    installs = [{
        **i,
        "alias": _format_alias(i),
        "sort-version": str(i['sort-version']),
    } for i in installs]

    cwidth = {k: len(v) for k, v in columns.items()}
    for i in installs:
        for k, v in i.items():
            try:
                cwidth[k] = max(cwidth[k], len(v))
            except LookupError:
                pass

    # Maximum column widths
    show_truncated_warning = False
    mwidth = {"company": 30, "tag": 30, "name": 60, "version": 15, "alias": 50}
    for k in list(cwidth):
        try:
            if cwidth[k] > mwidth[k]:
                cwidth[k] = mwidth[k]
                show_truncated_warning = True
        except LookupError:
            pass

    LOGGER.print("!B!%s!W!", "  ".join(columns[c].ljust(cwidth[c]) for c in columns))

    any_shown = False
    for i in installs:
        if not i.get("unmanaged"):
            clr = "!G!" if i.get("default") else ""
            LOGGER.print(f"{clr}%s!W!", "  ".join(_ljust(i.get(c, ""), cwidth[c]) for c in columns))
            any_shown = True
    if not any_shown:
        LOGGER.print("!Y!-- No runtimes. Use 'py install <version>' to install one. --!W!")
    shown_header = False
    for i in installs:
        if i.get("unmanaged"):
            if not shown_header:
                LOGGER.print()
                LOGGER.print("!B!* These runtimes may be run, but cannot be updated or uninstalled. *!W!")
                shown_header = True
            clr = "!G!" if i.get("default") else ""
            LOGGER.print(f"{clr}%s!W!", "  ".join(i.get(c, "").ljust(cwidth[c]) for c in columns))

    if show_truncated_warning:
        LOGGER.print()
        LOGGER.print("!B!Some columns were truncated. Use '!G!--format=json!B!'"
                     " or '!G!--format=jsonl!B!' for full information.!W!")


CSV_EXCLUDE = {
    "schema", "unmanaged",
    # Complex columns of limited value
    "install-for", "shortcuts", "__original-shortcuts",
    "executable", "executable_args",
}

CSV_EXPAND = ["run-for", "alias"]

def _csv_filter_and_expand(installs):
    for i in installs:
        i = {k: v for k, v in i.items() if k not in CSV_EXCLUDE}
        to_expand = {k: i.pop(k, ()) for k in CSV_EXPAND}
        yield i
        for k2, vlist in to_expand.items():
            for vv in vlist:
                yield {f"{k2}.{k}": v for k, v in vv.items()}


def format_csv(installs):
    import csv
    installs = list(_csv_filter_and_expand(installs))
    if not installs:
        return
    s = set()
    columns = [c for i in installs for c in i
               if c not in s and (s.add(c) or True)]
    writer = csv.DictWriter(sys.stdout, columns)
    writer.writeheader()
    writer.writerows(installs)


def format_json(installs):
    print(json.dumps({"versions": installs}, default=str))


def format_json_lines(installs):
    for i in installs:
        print(json.dumps(i, default=str))


def format_bare_exe(installs):
    for i in installs:
        print(i["executable"])


def format_bare_prefix(installs):
    for i in installs:
        try:
            print(i["prefix"])
        except KeyError:
            pass


def format_bare_url(installs):
    for i in installs:
        print(i["url"])


def format_legacy(installs, paths=False):
    for i in installs:
        if i["company"].casefold() != "PythonCore".casefold():
            tag = f" -V:{i['company']}/{i['tag']}"
        else:
            tag = f" -V:{i['tag']}"
        if i.get("default"):
            tag = f"{tag} *"
        print(tag.ljust(17), i["executable"] if paths else i["displayName"])


FORMATTERS = {
    "table": format_table,
    "csv": format_csv,
    "json": format_json,
    "jsonl": format_json_lines,
    "exe": format_bare_exe,
    "prefix": format_bare_prefix,
    "url": format_bare_url,
    "legacy": format_legacy,
    "legacy-paths": lambda i: format_legacy(i, paths=True),
}


def _get_installs_from_index(source, filters):
    from .indexutils import Index
    from .urlutils import sanitise_url, urljoin, urlopen

    installs = []
    seen_ids = set()

    url = source
    while url:
        index = Index(url, json.loads(urlopen(url, "GET", {"Accepts": "application/json"})))

        count = 0
        for i in index.find_all(filters, seen_ids=seen_ids, with_prerelease=True):
            installs.append(i)
            count += 1
        LOGGER.debug("Fetched %i installs from %s", count, sanitise_url(url))

        if index.next_url:
            url = urljoin(url, index.next_url, to_parent=True)
        else:
            url = None

    return installs


def execute(cmd):
    LOGGER.debug("BEGIN list_command.execute: %r", cmd.args)

    try:
        LOGGER.debug("Get formatter %s", cmd.format)
        formatter = FORMATTERS[cmd.format]
    except LookupError:
        expect = ", ".join(sorted(FORMATTERS))
        raise ArgumentError(f"'{cmd.format}' is not a valid format; expect one of: {expect}") from None

    from .tagutils import tag_or_range, install_matches_any
    tags = [tag_or_range(arg if arg.casefold() != "default".casefold() else cmd.default_tag)
            for arg in cmd.args]
    if tags:
        LOGGER.debug("Filtering to following items")
        for t in tags:
            LOGGER.debug("* %r", t)

    if cmd.source:
        from .urlutils import sanitise_url
        LOGGER.debug("Reading potential installs from %s", sanitise_url(cmd.source))
        try:
            installs = _get_installs_from_index(cmd.source, tags)
        except OSError as ex:
            LOGGER.error("Unable to read the index at %s", sanitise_url(cmd.source))
            raise SilentError from ex
    elif cmd.install_dir:
        LOGGER.debug("Reading installs from %s", cmd.install_dir)
        try:
            installs = cmd.get_installs(include_unmanaged=cmd.unmanaged)
        except OSError:
            LOGGER.debug("Unable to read installs", exc_info=True)
            installs = []
        installs = [i for i in installs if install_matches_any(i, tags)]
    else:
        raise ArgumentError("Configuration file does not specify install directory.")

    if cmd.one:
        installs = [i for i in installs if i.get("default")][:1] or installs[:1]
    formatter(installs)

    LOGGER.debug("END list_command.execute")
