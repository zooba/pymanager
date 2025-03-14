import os


class PurePath:
    def __init__(self, p):
        try:
            p = p.__fspath__().replace("/", "\\")
        except AttributeError:
            p = str(p).replace("/", "\\")
        p = p.replace("\\\\", "\\")
        if p.startswith(".\\"):
            p = p[2:]
        self._parent, _, self.name = p.rpartition("\\")
        self._p = p.rstrip("\\")

    def __fspath__(self):
        return self._p

    def __repr__(self):
        return self._p

    def __str__(self):
        return self._p

    @property
    def parent(self):
        return type(self)(self._parent)

    @property
    def parts(self):
        drive, root, tail = os.path.splitroot(self._p)
        bits = [drive + root, *tail.split("\\")]
        while "." in bits:
            bits.remove(".")
        while ".." in bits:
            i = bits.index("..")
            bits.pop(i)
            bits.pop(i - 1)
        return bits

    def __truediv__(self, other):
        return type(self)(os.path.join(self._p, other))

    def with_name(self, name):
        return type(self)(os.path.join(self._parent, name))

    def relative_to(self, base):
        base = PurePath(base).parts
        parts = self.parts
        if not all(x.casefold() == y.casefold() for x, y in zip(base, parts)):
            raise ValueError("path not relative to base")
        return type(self)("\\".join(parts[len(base):]))

    def as_uri(self):
        drive, root, tail = os.path.splitroot(self._p)
        if drive[1:2] == ":" and root:
            return "file:///" + self._p.replace("\\", "/")
        if drive[:2] == "\\\\":
            return "file:" + self._p.replace("\\", "/")
        return "file://" + self._p.replace("\\", "/")

    def full_match(self, pattern):
        return self.match(pattern, full_match=True)

    def match(self, pattern, full_match=False):
        p = str(pattern).casefold().replace("/", "\\")
        assert "?" not in p

        m = self._p if full_match or "\\" in p else self.name
        m = m.casefold()

        if "*" not in p:
            return m.casefold() == p

        allow_skip = False
        for bit in p.split("*"):
            if bit:
                if allow_skip:
                    allow_skip = False
                    try:
                        i = m.index(bit)
                    except ValueError:
                        return False
                    m = m[i + len(bit):]
                elif m.startswith(bit):
                    m = m[len(bit):]
                else:
                    return False
            else:
                allow_skip = True
        return True


class Path(PurePath):
    @classmethod
    def cwd(cls):
        return cls(os.getcwd())

    def absolute(self):
        return Path.cwd() / self

    def exists(self):
        return os.path.exists(self._p)

    def is_dir(self):
        return os.path.isdir(self._p)

    def is_file(self):
        return os.path.isfile(self._p)

    def iterdir(self):
        return (self / n for n in os.listdir(self._p))

    def glob(self, pattern):
        return (f for f in self.iterdir() if f.match(pattern))

    def lstat(self):
        return os.lstat(self._p)

    def rename(self, new_name):
        os.rename(self._p, new_name)
        return self.parent / PurePath(new_name)

    def rmdir(self):
        os.rmdir(self._p)

    def unlink(self):
        os.unlink(self._p)

    def open(self, mode="r", encoding=None, errors=None):
        if "b" in mode:
            return open(self._p, mode)
        if not encoding:
            encoding = "utf-8-sig" if "r" in mode else "utf-8"
        return open(self._p, mode, encoding=encoding, errors=errors or "strict")

    def read_bytes(self):
        with open(self._p, "rb") as f:
            return f.read()

    def read_text(self, encoding="utf-8-sig", errors="strict"):
        with open(self._p, "r", encoding=encoding, errors=errors) as f:
            return f.read()

    def write_bytes(self, data):
        with open(self._p, "wb") as f:
            f.write(data)

    def write_text(self, text, encoding="utf-8", errors="strict"):
        with open(self._p, "w", encoding=encoding, errors=errors) as f:
            f.write(text)
