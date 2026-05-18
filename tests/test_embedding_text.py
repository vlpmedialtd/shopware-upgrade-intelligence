from shopware_intel.ingest.chunk.base import Chunk, embedding_text


def _make(language: str, fqn: str = "", name: str = "", content: str = "body") -> Chunk:
    return Chunk(
        file_path="src/Core/Foo/Bar.php",
        language=language,
        area="core",
        content=content,
        start_line=1,
        end_line=1,
        symbol_kind="method",
        symbol_name=name,
        symbol_fqn=fqn,
    )


def test_fqn_prepended_when_not_in_content_prefix():
    c = _make("php", fqn="Shopware\\Core\\Foo\\Bar::quux", content="public function quux(): int {}")
    text = embedding_text(c)
    assert text.startswith("Shopware\\Core\\Foo\\Bar::quux\n")


def test_fqn_not_duplicated_when_full_fqn_already_in_content():
    full = "Shopware\\Core\\Foo\\Bar"
    c = _make(
        "php",
        fqn=full,
        content=f"// {full}\nclass Bar extends Foo {{ public function quux(): int {{ return 1; }} }}",
    )
    text = embedding_text(c)
    assert text == c.content


def test_filepath_only_when_no_symbol():
    c = Chunk(
        file_path="src/Storefront/component/listing/filter-panel.html.twig",
        language="twig",
        area="storefront",
        content="{% block component_filter_panel %}{% endblock %}",
        start_line=1,
        end_line=1,
        symbol_kind="file",
    )
    text = embedding_text(c)
    assert text.startswith("src/Storefront/component/listing/filter-panel.html.twig\n")


def test_markdown_passes_through():
    c = _make("markdown", content="# Some changelog entry\nbody...")
    assert embedding_text(c) == c.content


def test_locale_path_does_not_pollute_when_method_has_fqn():
    """Regression: previously `src/.../Migration/Fixtures/mails/de-html.html.twig`
    file path was prepended to every chunk, hijacking German queries by matching
    the `de-` locale segment. With fqn-only prefixing this can't happen for any
    chunk that has a symbol_fqn."""
    c = Chunk(
        file_path="src/Core/Migration/Fixtures/mails/de-html.html.twig",
        language="twig",
        area="core",
        content="Sehr geehrte Kundin, sehr geehrter Kunde, ...",
        start_line=1,
        end_line=10,
        symbol_kind="twig_block",
        symbol_name="customer_registration_de_html",
        symbol_fqn="",
    )
    text = embedding_text(c)
    # Has the (English) block name, not the de- locale path.
    assert "customer_registration_de_html\n" in text
    assert not text.startswith("src/Core/Migration/Fixtures/mails/de-html.html.twig")
