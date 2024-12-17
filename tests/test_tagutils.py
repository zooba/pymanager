import pytest
from manage._core.tagutils import CompanyTag

@pytest.mark.parametrize("tag_str", [
    "3.13", "3.13-32", "3.13-arm64",
    "cpython/3.13", "PythonCore\\3.13",
    "\\Tag",
])
def test_core_tag(tag_str):
    tag = CompanyTag(tag_str)

    assert tag.is_core

@pytest.mark.parametrize("tag_str", [
    "Company/Tag", "Company\\Tag", "Company/"
])
def test_company_tag(tag_str):
    tag = CompanyTag(tag_str)

    assert not tag.is_core


def test_tag_equality():
    assert CompanyTag("3.13") == CompanyTag("PythonCore\\3.13")
    assert CompanyTag("3.13") != CompanyTag("Company\\3.13")


def test_tag_match():
    assert not CompanyTag("3.13").match(CompanyTag("Company\\3.13"))
    assert CompanyTag("3.13").match(CompanyTag("3.13"))
    assert CompanyTag("3.13.2").match(CompanyTag("3.13"))
    assert not CompanyTag("3.13").match(CompanyTag("3.13.2"))

    assert CompanyTag("PythonCore\\3.13").match(CompanyTag("", ""))
    assert CompanyTag("PythonCore\\4.56").match(CompanyTag("", ""))
    assert CompanyTag("PythonCore\\3.13").match(CompanyTag("", "3"))
    assert not CompanyTag("PythonCore\\4.56").match(CompanyTag("", "3"))


def test_tag_order():
    assert CompanyTag("3.13.2") < CompanyTag("3.13")


def test_tag_sort():
    import random
    tags = list(map(CompanyTag, [
        "3.11-64", "3.10.4", "3.10", "3.9", "3.9-32",
        "Company/Version10", "Company/Version9",
        "OtherCompany/3.9.2", "OtherCompany/3.9-32"
    ]))
    expected = list(tags)
    random.shuffle(tags)
    actual = sorted(tags)
    assert actual == expected, actual
