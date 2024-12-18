import re


class NewEncoding(Exception):
    pass


def _read_script(cmd, script, encoding):
    with open(script, "r", encoding=encoding, errors="replace") as f:
        first_line = next(f).rstrip()
        shebang = re.match(r"#!\s*(\S+).*", first_line)
        if shebang:
            from pathlib import PurePath
            full_cmd = shebang.group(1)
            sh_cmd = PurePath(full_cmd)
            # HACK: Assuming alias/executable suffix is '.exe' here
            # (But correctly assuming we can't use with_suffix() or .stem)
            if not sh_cmd.match("*.exe"):
                sh_cmd = sh_cmd.with_name(sh_cmd.name + ".exe")
            for i in cmd.get_installs():
                for a in i["alias"]:
                    if sh_cmd.match(a["name"]):
                        return {**i, "executable": i["prefix"] / a["target"]}
                if sh_cmd.match(i["executable"]):
                    return i

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
