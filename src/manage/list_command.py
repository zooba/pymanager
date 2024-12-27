import json
import sys

from .exceptions import ArgumentError
from .logging import LOGGER


def format_table(installs):
    columns = {
        "company": "Publisher",
        "tag": "Tag",
        "displayName": "Name",
        "sort-version": "Version",
        "alias": "Alias",
    }
    installs = [{
        **i,
        "alias": ", ".join(a["name"] for a in i.get("alias", ())),
        "sort-version": str(i['sort-version']),
    } for i in installs]

    cwidth = {k: len(v) for k, v in columns.items()}
    for i in installs:
        for k, v in i.items():
            try:
                cwidth[k] = max(cwidth[k], len(v))
            except LookupError:
                pass
    for c in columns:
        print(columns[c].ljust(cwidth[c]), end="  ", flush=False)
    print()
    any_shown = False
    for i in installs:
        if not i.get("unmanaged"):
            for c in columns:
                v = i.get(c, "")
                if c == "company" and v == "PythonCore":
                    v = "CPython"
                print(v.ljust(cwidth[c]), end="  ", flush=False)
            print()
            any_shown=True
    if not any_shown:
        print("-- No runtimes. Use 'python install <version>' to install one. --")
    shown_header = False
    for i in installs:
        if i.get("unmanaged"):
            if not shown_header:
                print()
                print("* These runtimes may be run, but cannot be updated or uninstalled. *")
                shown_header = True
            for c in columns:
                v = i.get(c, "")
                print(v.ljust(cwidth[c]), end="  ", flush=False)
            print()


CSV_EXCLUDE = {
    "schema", "unmanaged",
    # Complex columns of limited value
    "install-for", "shortcuts",
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
    print(json.dumps({"installs": installs}, default=str))


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
        for i in index.find_all(filters, seen_ids=seen_ids):
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
    tags = [tag_or_range(arg) for arg in cmd.args]
    if tags:
        LOGGER.debug("Filtering to following items")
        for t in tags:
            LOGGER.debug("* %r", t)

    if cmd.source:
        from .urlutils import sanitise_url
        LOGGER.debug("Reading potential installs from %s", sanitise_url(cmd.source))
        installs = _get_installs_from_index(cmd.source, tags)
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
        installs = installs[:1]
    if installs:
        formatter(installs)

    LOGGER.debug("END list_command.execute")
