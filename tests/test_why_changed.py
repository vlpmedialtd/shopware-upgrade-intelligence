from shopware_intel.retrieval.why_changed import _structural_diff


def test_twig_block_added_and_removed():
    a = "{% block product_card_top %}old{% endblock %}\n{% block product_card_meta %}m{% endblock %}"
    b = "{% block product_card_top %}new{% endblock %}\n{% block product_card_footer %}f{% endblock %}"
    d = _structural_diff("twig", a, b)
    assert d.added == ["product_card_footer"]
    assert d.removed == ["product_card_meta"]


def test_scss_classes_diff():
    a = ".product-old { color: red; }\n.shared { color: blue; }"
    b = ".product-new { color: green; }\n.shared { color: blue; }"
    d = _structural_diff("scss", a, b)
    assert "product-new" in d.added
    assert "product-old" in d.removed
    assert "shared" not in d.added and "shared" not in d.removed


def test_php_method_signature_change_marked_as_changed():
    a = "class Foo {\n    public function bar(int $x): int { return $x; }\n}"
    b = "class Foo {\n    public function bar(int $x, ?string $y = null): int { return $x; }\n}"
    d = _structural_diff("php", a, b)
    assert "bar" in d.changed
    assert "bar" not in d.added
    assert "bar" not in d.removed


def test_php_class_added():
    a = "class Foo {}"
    b = "class Foo {}\nclass Bar {}"
    d = _structural_diff("php", a, b)
    assert "Bar" in d.added
