import json
import sys

from .exceptions import ArgumentError
from .installs import get_installs
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
    installs = list(installs)
    for i in installs:
        for k, v in i.items():
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


FORMATTERS = {
    "table": format_table,
    "csv": format_csv,
    "json": format_json,
    "jsonl": format_json_lines,
    "exe": format_bare_exe,
    "prefix": format_bare_prefix,
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
        installs = get_installs(cmd.install_dir, cmd.default_tag)
    except OSError:
        LOGGER.debug("Unable to read installs", exc_info=True)
        installs = []

    if not cmd.args:
        if cmd.one:
            installs = installs[:1]
        formatter(installs)
    else:
        from .tagutils import CompanyTag
        for arg in cmd.args:
            ct = CompanyTag(arg)
            filtered = [i for i in installs if CompanyTag.from_dict(i).match(ct)]
            if cmd.one:
                filtered = filtered[:1]
            if filtered:
                formatter(filtered)

    LOGGER.debug("END list_command.execute")
