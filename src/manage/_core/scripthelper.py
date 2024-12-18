import re


class NewEncoding(Exception):
    pass


def _read_script(script, cmd, encoding):
    with open(script, "r", encoding=encoding, errors="replace") as f:
        first_line = next(f).rstrip()
        shebang = re.match(r"#!\s*(\S+).*", first_line)
        if shebang:
            from .installs import get_installs
            from pathlib import PurePath
            full_cmd = shebang.group(1)
            sh_cmd = PurePath(full_cmd)
            # HACK: Assuming alias/executable suffix is '.exe' here
            # (But correctly assuming we can't use with_suffix() or .stem)
            if not sh_cmd.match("*.exe"):
                sh_cmd = sh_cmd.with_name(sh_cmd.name + ".exe")
            for i in get_installs(cmd.install_dir, cmd.default_tag):
                for a in i["alias"]:
                    if sh_cmd.match(a["name"]):
                        return {**i, "executable": i["prefix"] / a["target"]}
                if sh_cmd.match(i["executable"]):
                    return i

        coding = re.match(r"\s*#.*coding[=:]\s*([-\w.]+)", first_line)
        if coding:
            raise NewEncoding(coding.group(1))

        # TODO: Parse inline script metadata
        # This involves finding '# /// script' followed by
        # a line with '# requires-python = <spec>'.
        # That spec needs to be processed as a version constraint, which
        # is currently entirely unsupported.
        return None


def find_install_from_script(script, cmd):
    try:
        return _read_script(script, cmd, "utf-8-sig")
    except NewEncoding as ex:
        encoding = ex.args[0]
    return _read_script(script, cmd, encoding)
