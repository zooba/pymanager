from .verutils import Version


class _CompanyKey:
    CORE_COMPANY_NAMES = frozenset(map(str.casefold, ["CPython", "PythonCore", ""]))

    def __init__(self, company, allow_prefix=True):
        self.company = company or ""
        self._company = self.company.casefold()
        self.is_core = self._company in self.CORE_COMPANY_NAMES
        if self.is_core:
            self._company = ""
        self.allow_prefix = allow_prefix

    def startswith(self, other):
        if self.is_core and other.is_core:
            return True
        if self.allow_prefix:
            if self.is_core:
                return any(c.startswith(other._company) for c in self.CORE_COMPANY_NAMES)
            return self._company.startswith(other._company)
        return self._company == other._company

    def __eq__(self, other):
        return self._company == other._company

    def __ne__(self, other):
        return self._company != other._company

    def __lt__(self, other):
        if self.is_core and not other.is_core:
            return True
        if other.is_core:
            return False
        return self._company < other._company

    def __le__(self, other):
        return self == other or self < other

    def __gt__(self, other):
        return not (self <= other)

    def __ge__(self, other):
        return not (self < other)



class _PlatformKey:
    _SUFFIXES = {
        "-32": 1,
        "-64": 2,
        "-arm64": 3,
    }
    _ANY = 1000

    DEFAULT = None

    def __init__(self, tag):
        for suffix, level in self._SUFFIXES.items():
            if tag.endswith(suffix):
                tag = tag[:-len(suffix)]
                break
        else:
            suffix = "-*"
            level = self._ANY
        self.tag = tag
        self.suffix = suffix
        self.level = level

    def __repr__(self):
        return f"<Platform({self.suffix!r})>"

    def startswith(self, other):
        if not isinstance(other, type(self)):
            raise TypeError("expected '{}', got '{}'".format(
                type(self).__name__, type(other).__name__
            ))
        return self.level == other.level or other.level == self._ANY

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.level == other.level

    def __lt__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.level < other.level

    def __ne__(self, other):
        return not (self == other)

    def __le__(self, other):
        return self < other or self == other

    def __gt__(self, other):
        return not (self <= other)

    def __ge__(self, other):
        return not (self < other)

_PlatformKey.DEFAULT = _PlatformKey("")


class _DescendingVersion(Version):
    def __gt__(self, other):
        if other is None:
            return True
        if isinstance(other, str):
            other = type(self)(other)
        return self.sortkey < other.sortkey

    def __lt__(self, other):
        if other is None:
            return False
        if isinstance(other, str):
            other = type(self)(other)
        return self.sortkey > other.sortkey


def _sort_tag(tag):
    import re
    key = []
    text = True
    if not tag:
        return ()

    for bit in re.split(r"(\d+(?:\.\d+)*)", tag):
        if text:
            key.append(bit.casefold())
        else:
            key.append(_DescendingVersion(bit))
        text = not text
    return tuple(key)


def _sort_tag_with_platform(tag):
    platform = _PlatformKey(tag)
    return _sort_tag(platform.tag), platform


class CompanyTag:
    def __init__(self, company_or_tag, tag=None, *, loose_company=True):
        if tag is not None:
            company = company_or_tag
        else:
            company, _, tag = (company_or_tag or "").replace("/", "\\").rpartition("\\")
        self._company = _CompanyKey(company, allow_prefix=loose_company)
        self.tag = tag
        if self.is_core:
            self._sortkey, self._platform = _sort_tag_with_platform(tag)
        else:
            self._sortkey = _sort_tag(tag)
            self._platform = _PlatformKey.DEFAULT

    @property
    def company(self):
        return self._company.company

    @property
    def is_core(self):
        return self._company.is_core

    @classmethod
    def from_dict(cls, d, default=None):
        try:
            return cls(d["company"], d["tag"])
        except LookupError:
            return default

    def match(self, pattern):
        if isinstance(pattern, str):
            other = type(self)(pattern)
        else:
            other = pattern
        if not self._company.startswith(other._company):
            return False
        if not self._platform.startswith(other._platform):
            return False
        if len(self._sortkey) < len(other._sortkey):
            return False
        for x, y in zip(self._sortkey, other._sortkey):
            if not x.startswith(y):
                return False
        return True

    def satisfied_by(self, tag):
        return tag.match(self)

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
        if self._platform != other._platform:
            return False
        if self._sortkey != other._sortkey:
            return False
        return True

    def __gt__(self, other):
        if other is None:
            return True
        if self._company != other._company:
            return self._company > other._company
        if self._sortkey != other._sortkey:
            return self._sortkey > other._sortkey
        if self._platform != other._platform:
            return self._platform < other._platform
        return False

    def matches_bound(self, other):
        if other is None:
            return True
        if not self._company.startswith(other._company):
            return False
        if not self._platform.startswith(other._platform):
            return False
        if len(self._sortkey) != len(other._sortkey):
            return False
        for x, y in zip(self._sortkey, other._sortkey):
            if isinstance(x, Version):
                if not x.startswith(y):
                    return False
            elif x != y:
                return False
        return True

    def above_lower_bound(self, other):
        if other is None:
            return True
        if not self._company.startswith(other._company):
            return False
        if not self._platform.startswith(other._platform):
            return False
        if len(self._sortkey) != len(other._sortkey):
            return False
        for x, y in zip(self._sortkey, other._sortkey):
            if isinstance(x, Version):
                if not x.above_lower_bound(y):
                    return False
            elif x != y:
                return False
        return True

    def __lt__(self, other):
        if other is None:
            return False
        if self._company != other._company:
            return self._company < other._company
        if self._sortkey != other._sortkey:
            return self._sortkey < other._sortkey
        if self._platform != other._platform:
            return self._platform > other._platform
        return False

    def below_upper_bound(self, other):
        if other is None:
            return True
        if not self._company.startswith(other._company):
            return False
        if not self._platform.startswith(other._platform):
            return False
        if len(self._sortkey) != len(other._sortkey):
            return False
        for x, y in zip(self._sortkey, other._sortkey):
            if isinstance(x, Version):
                if not x.below_upper_bound(y):
                    return False
            elif x != y:
                return False
        return True

    def __ge__(self, other):
        return self > other or self == other

    def __le__(self, other):
        return self < other or self == other


class TagRange:
    def __init__(self, spec):
        self.ranges = ranges = []
        for s in spec.replace(";", ",").split(","):
            s = s.strip()
            for r_cls in self.Range.__subclasses__():
                if s.startswith(r_cls.OP):
                    ranges.append(r_cls(s[len(r_cls.OP):].strip()))
                    break
            else:
                raise ValueError(f"Unsupported range specifier: '{s}'")

    def __repr__(self):
        return "<TagRange({})>".format(", ".join(repr(r) for r in self.ranges))

    def satisfied_by(self, tag):
        return all(r(tag) for r in self.ranges)

    class Range:
        def __init__(self, tag):
            self.tag = CompanyTag(tag)

        def __repr__(self):
            return f"{self.OP}{self.tag}"

    class RangeGreaterEqual(Range):
        OP = ">="
        def __call__(self, other):
            return other.matches_bound(self.tag) or other.above_lower_bound(self.tag)

    class RangeGreater(Range):
        OP = ">"
        def __call__(self, other):
            return other.above_lower_bound(self.tag)

    class RangeLessEqual(Range):
        OP = "<="
        def __call__(self, other):
            return other.matches_bound(self.tag) or other.below_upper_bound(self.tag)

    class RangeLess(Range):
        OP = "<"
        def __call__(self, other):
            return other.below_upper_bound(self.tag)

    class RangeExclude(Range):
        OP = "!="
        def __call__(self, other):
            return not other.matches_bound(self.tag)


def tag_or_range(tag):
    if not isinstance(tag, str):
        return tag
    tag = tag.lstrip(" =")
    if not tag:
        return CompanyTag("", "")
    if tag[:1] in "<>!":
        return TagRange(tag)
    return CompanyTag(tag)


def install_matches_any(install, tags_or_ranges, *, loose_company=False):
    if not tags_or_ranges:
        return True

    own_tag = CompanyTag(install["company"], install["tag"], loose_company=loose_company)
    install_tags = [CompanyTag(install["company"], t, loose_company=loose_company)
                    for t in install.get("install-for", ())]
    if not install_tags:
        install_tags.append(own_tag)

    for f in tags_or_ranges:
        if not f:
            if install.get("default"):
                return True
            continue
        if isinstance(f, TagRange):
            if f.satisfied_by(own_tag):
                return True
        else:
            if any(f.satisfied_by(t) for t in install_tags):
                return True
    return False
