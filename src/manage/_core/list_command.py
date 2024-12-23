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
        # TODO: Better override for unmanaged installs
        "tag": f"{i['tag']} ?" if i.get("unmanaged") else i['tag'],
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
    for i in installs:
        for c in columns:
            v = i.get(c, "")
            if c == "company" and v == "PythonCore":
                v = "CPython"
            print(v.ljust(cwidth[c]), end="  ", flush=False)
        print()


def format_csv(installs):
    import csv
    columns = {}
    # TODO: Exclude complex columns
    installs = list(installs)
    for i in installs:
        for k in i:
            columns[k] = True
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
        print(i["prefix"])


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
    "legacy": format_legacy,
    "legacy-paths": lambda i: format_legacy(i, paths=True),
}


def execute(cmd):
    LOGGER.debug("BEGIN list_command.execute: %r", cmd.args)

    try:
        LOGGER.debug("Get formatter %s", cmd.format)
        formatter = FORMATTERS[cmd.format]
    except LookupError:
        expect = ", ".join(sorted(FORMATTERS))
        raise ArgumentError(f"'{cmd.format}' is not a valid format; expect one of: {expect}") from None

    LOGGER.debug("Reading installs from %s", cmd.install_dir)
    try:
        installs = cmd.get_installs(include_unmanaged=cmd.unmanaged)
    except OSError:
        LOGGER.debug("Unable to read installs", exc_info=True)
        installs = []

    if not cmd.args:
        if cmd.one:
            installs = installs[:1]
        formatter(installs)
    else:
        from .tagutils import CompanyTag, tag_or_range
        tags = [tag_or_range(arg) for arg in cmd.args]
        if tags:
            LOGGER.debug("Filtering to following items")
            for t in tags:
                LOGGER.debug("* %r", t)
        filtered = [i for i in installs
                    if any(t.satisfied_by(CompanyTag.from_dict(i)) for t in tags)]
        if cmd.one:
            filtered = filtered[:1]
        if filtered:
            formatter(filtered)

    LOGGER.debug("END list_command.execute")
