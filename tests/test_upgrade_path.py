from shopware_intel.retrieval.upgrade_path import _section_key, _version_tuple


def test_version_tuple_parses_4_components():
    assert _version_tuple("6.7.0.1") == (6, 7, 0, 1)
    assert _version_tuple("6.4.20.2") == (6, 4, 20, 2)


def test_version_tuple_ordering():
    assert _version_tuple("6.7.0.0") < _version_tuple("6.7.0.1")
    assert _version_tuple("6.6.10.4") < _version_tuple("6.7.0.0")
    assert _version_tuple("6.4.20.2") < _version_tuple("6.5.0.0")


def test_version_tuple_invalid_returns_empty():
    assert _version_tuple("not.a.version") == ()
    assert _version_tuple("") == ()


def test_section_key_orders_canonically():
    assert _section_key("upgrade information") < _section_key("core")
    assert _section_key("core") < _section_key("administration")
    assert _section_key("administration") < _section_key("storefront")
    assert _section_key("unknown") > _section_key("storefront")
