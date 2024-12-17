import re


class NewEncoding(Exception):
    pass


def _read_script(script, root, encoding):
    with open(script, "r", encoding=encoding, errors="replace") as f:
        first_line = next(f).rstrip()
        shebang = re.match(r"#!\s*\S+?python([-\w.]+).*", first_line)
        if shebang:
            return shebang.group(1)

        coding = re.match(r"\s*#.*coding[=:]\s*([-\w.]+)", first_line)
        if coding:
            raise NewEncoding(coding.group(1))

        # TODO: Parse inline script metadata
        # This involves finding '# /// script' followed by
        # a line with '# requires-python = <spec>'.
        # That spec needs to be processed as a version constraint, which
        # is currently entirely unsupported.
        return None


def find_tag(script, root):
    try:
        return _read_script(script, root, "utf-8-sig")
    except NewEncoding as ex:
        encoding = ex.args[0]
    return _read_script(script, root, encoding)
