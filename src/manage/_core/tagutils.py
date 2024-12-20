CORE_COMPANY_NAMES = frozenset(map(str.casefold, ["CPython", "PythonCore", ""]))

CORE_PLATFORM_SORTKEY = {
    "arm64": 0,
    "64": 1,
    "32": 2,
}


def _sort_tag(tag):
    import re
    return re.sub(
        r"(\d+)",
        lambda m: "{:016}".format(int(m.group(0))),
        tag.casefold(),
    )


class CompanyTag:
    def __init__(self, company_or_tag, tag=None):
        if tag:
            company = company_or_tag
        else:
            company, _, tag = company_or_tag.replace("/", "\\").rpartition("\\")
        self.company = company or ""
        self._company = self.company.casefold()
        self.is_core = self._company in CORE_COMPANY_NAMES
        if self.is_core:
            self._company = ""
        self.tag = tag
        self._platform = 100
        if self.is_core:
            tag, _, plat = tag.partition("-")
            self._platform = CORE_PLATFORM_SORTKEY.get(plat, 1)
        self._sortkey = _sort_tag(tag)

    @classmethod
    def from_dict(cls, d, default=None):
        try:
            return cls(d["company"], d["tag"])
        except LookupError:
            return default

    def match_any(self, company, tags, exact_company=False, exact_tag=False):
        if exact_company:
            if not company or self._company != company.casefold():
                return False
        elif company and not company.casefold().startswith(self._company):
            return False
        if not tags:
            return False
        if exact_tag:
            return any(self == CompanyTag(self.company, t) for t in tags)
        return any(self.match(CompanyTag(self.company, t)) for t in tags)

    def match(self, pattern):
        if isinstance(pattern, str):
            other = type(self)(pattern)
        else:
            other = pattern
        if self._company != other._company:
            return False
        if not self._sortkey.startswith(other._sortkey):
            return False
        if self._platform != other._platform:
            return False
        return True

    def __str__(self):
        if self.is_core:
            return self.tag
        return f"{self.company}\\{self.tag}"

    def __repr__(self):
        return repr(str(self))

    def __hash__(self):
        return hash(self._sortkey)

    def __eq__(self, other):
        if other is None:
            return False
        if self._company != other._company:
            return False
        if self._sortkey != other._sortkey:
            return False
        if self._platform != other._platform:
            return False
        return True

    def __gt__(self, other):
        if other is None:
            return True
        if self._company != other._company:
            if self.is_core:
                return False
            if other.is_core:
                return True
            return self._company > other._company
        if self._sortkey < other._sortkey:
            return True
        if self._platform > other._platform:
            return True
        return False

    def __lt__(self, other):
        if other is None:
            return False
        if self._company != other._company:
            if self.is_core:
                return True
            if other.is_core:
                return False
            return self._company < other._company
        if self._sortkey > other._sortkey:
            return True
        if self._platform < other._platform:
            return True
        return False

    def __ge__(self, other):
        return self > other or self == other

    def __le__(self, other):
        return self < other or self == other
