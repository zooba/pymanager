import re

from pathlib import Path, PurePath

from .logging import LOGGER


class NewEncoding(Exception):
    pass


def _find_shebang_command(cmd, full_cmd):
    sh_cmd = PurePath(full_cmd)
    # HACK: Assuming alias/executable suffix is '.exe' here
    # (But correctly assuming we can't use with_suffix() or .stem)
    if not sh_cmd.match("*.exe"):
        sh_cmd = sh_cmd.with_name(sh_cmd.name + ".exe")

    is_default = sh_cmd.match("python.exe") or sh_cmd.match("py.exe")

    for i in cmd.get_installs():
        if is_default and i.get("default"):
            return i
        for a in i["alias"]:
            if sh_cmd.match(a["name"]):
                LOGGER.debug("Matched alias %s in %s", a["name"], i["id"])
                return {**i, "executable": i["prefix"] / a["target"]}
        if sh_cmd.full_match(PurePath(i["executable"]).name):
            LOGGER.debug("Matched executable name %s in %s", i["executable"], i["id"])
            return i
        if sh_cmd.match(i["executable"]):
            LOGGER.debug("Matched executable %s in %s", i["executable"], i["id"])
            return i
    else:
        raise LookupError


def _find_on_path(cmd, full_cmd):
    import os
    import shutil
    # Recursion prevention
    if os.getenv("__PYTHON_MANAGER_SUPPRESS_ARBITRARY_SHEBANG"):
        raise LookupError
    os.environ["__PYTHON_MANAGER_SUPPRESS_ARBITRARY_SHEBANG"] = "1"

    exe = shutil.which(full_cmd)
    if not exe:
        raise LookupError
    return {
        "displayName": "Shebang command",
        "sort-version": "0.0",
        "executable": Path(exe),
    }


def _read_script(cmd, script, encoding):
    try:
        f = open(script, "r", encoding=encoding, errors="replace")
    except OSError as ex:
        raise LookupError(script) from ex
    with f:
        first_line = next(f).rstrip()
        # For /usr[/local]/bin, we look for a matching alias name.
        shebang = re.match(r"#!\s*/usr/(?:local/)?bin/(?!env\b)([^\\/\s]+).*", first_line)
        if shebang:
            # Handle the /usr[/local]/bin/python cases
            full_cmd = shebang.group(1)
            LOGGER.debug("Matching shebang: %s", full_cmd)
            try:
                return _find_shebang_command(cmd, full_cmd)
            except LookupError:
                LOGGER.warn("A shebang '%s' was found, but could not be matched "
                            "to an installed runtime.", full_cmd)
                LOGGER.warn('If the script does not behave properly, try '
                            'installing the correct runtime with "py install".')
                raise LookupError(script) from None

        # For /usr/bin/env, we look for a matching alias, followed by PATH search.
        # We warn about the PATH search, because we don't know we'll be launching
        # Python at all in this case.
        shebang = re.match(r"#!\s*/usr/bin/env\s+([^\\/\s]+).*", first_line)
        if shebang:
            # First do regular install lookup for /usr/bin/env shebangs
            full_cmd = shebang.group(1)
            try:
                return _find_shebang_command(cmd, full_cmd)
            except LookupError:
                pass
            # If not, warn and do regular PATH search
            if cmd.shebang_can_run_anything or cmd.shebang_can_run_anything_silently:
                try:
                    i = _find_on_path(cmd, full_cmd)
                    if not cmd.shebang_can_run_anything_silently:
                        LOGGER.warn("A shebang '%s' was found, but could not be matched "
                                    "to an installed runtime.", full_cmd)
                        LOGGER.warn("Arbitrary command was found on PATH instead. Configure "
                                    "'shebang_can_run_anything' to disable this.")
                    return i
                except LookupError:
                    raise LookupError(script) from None
            else:
                LOGGER.warn("A shebang '%s' was found, but could not be matched "
                            "to an installed runtime.", full_cmd)
                LOGGER.warn("Arbitrary command execution is disabled. Reconfigure "
                            "'shebang_can_run_anything' to enable it. "
                            "Launching with default runtime.")
                raise LookupError(script)

        # All other shebangs get treated as arbitrary commands. We warn about
        # this case, because we don't know we'll be launching Python at all.
        shebang = re.match(r"#!\s*(.+)\S*$", first_line)
        if shebang:
            full_cmd = shebang.group(1)
            # A regular lookup will handle the case where the entire shebang is
            # a valid alias.
            try:
                return _find_shebang_command(cmd, full_cmd)
            except LookupError:
                pass
            if cmd.shebang_can_run_anything or cmd.shebang_can_run_anything_silently:
                if not cmd.shebang_can_run_anything_silently:
                    LOGGER.warn("A shebang '%s' was found, but does not match any "
                                "supported template (e.g. '/usr/bin/python').", full_cmd)
                    LOGGER.warn("Using the shebang as an arbitrary command instead. "
                                "Configure 'shebang_can_run_anything' to disable this.")
                return _find_on_path(cmd, full_cmd)
            else:
                LOGGER.warn("A shebang '%s' was found, but could not be matched "
                            "to an installed runtime.", full_cmd)
                LOGGER.warn("Arbitrary command execution is disabled. Reconfigure "
                            "'shebang_can_run_anything' to enable it. "
                            "Launching with default runtime.")
                raise LookupError(script)

        coding = re.match(r"\s*#.*coding[=:]\s*([-\w.]+)", first_line)
        if coding and coding.group(1) != encoding:
            raise NewEncoding(coding.group(1))

        # TODO: Parse inline script metadata
        # This involves finding '# /// script' followed by
        # a line with '# requires-python = <spec>'.
        # That spec needs to be processed as a version constraint, which
        # is currently entirely unsupported.
    raise LookupError(script)


def find_install_from_script(cmd, script):
    try:
        return _read_script(cmd, script, "utf-8-sig")
    except NewEncoding as ex:
        encoding = ex.args[0]
    return _read_script(cmd, script, encoding)


def _maybe_quote(a):
    if a[:1] == a[-1:] == '"':
        a = a[1:-1]
    if " " not in a and '"' not in a:
        return a
    if a.endswith("\\"):
        c = len(a) - len(a.rstrip("\\"))
        a += "\\" * c
    if '"' in a:
        bits = []
        for b in a.split('"'):
            if bits:
                bits.append('\\"')
            bits.append(b)
            if b[-1:] == "\\":
                bits.append("\\" * (len(b) - len(b.rstrip("\\"))))
        print(a.split('"'), bits)
        a = ''.join(bits)
    return f'"{a}"' if ' ' in a else a


def quote_args(args):
    """Quotes the provided sequence of arguments preserving all characters.

All backslashes and quotes in the existing arguments will be preserved and will
round-trip through CreateProcess to another Python instance (or another app
using the same parsing rules).

When an argument already starts and ends with a double quote ('"'), they will be
removed and only replaced if necessary.
"""
    return " ".join(_maybe_quote(a) for a in args)


def split_args(arg_string, argv0=False):
    """Splits a single argument string into separate unquoted items.

If argv0 is True, the first argument is parsed as if it is the executable name.
"""
    args = []
    if argv0 and arg_string[:1] == '"':
        a, _, arg_string = arg_string[1:].partition('"')
        args.append(a)

    arg_buffer = None
    quoted_arg = []
    bits = arg_string.strip().split(' ')
    while bits:
        a = bits.pop(0)
        pre, quot, post = a.partition('"')
        if arg_buffer:
            pre = arg_buffer + pre
            arg_buffer = None
        if not quot:
            if quoted_arg:
                quoted_arg.append(pre)
                quoted_arg.append(' ')
            else:
                args.append(pre.replace('\\\\', '\\'))
            continue
        if pre[-1:] == '\\' and (len(pre) - len(pre.rstrip('\\'))) % 2 == 1:
            arg_buffer = pre[:-1] + quot
            if post:
                bits.insert(0, post)
            continue
        elif quoted_arg:
            quoted_arg.append(pre)
            args.append(''.join(quoted_arg).replace('\\\\', '\\'))
            quoted_arg.clear()
            continue

        quoted_arg.append(pre)
        if pre:
            quoted_arg.append(quot)
        if post:
            bits.insert(0, post)
    if quoted_arg:
        args.append(''.join(quoted_arg))
    return args
