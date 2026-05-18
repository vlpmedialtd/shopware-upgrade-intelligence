from shopware_intel.ingest.chunk.twig import chunk_twig

SAMPLE = """{% sw_extends '@Storefront/storefront/page/product-detail/index.html.twig' %}

{# @deprecated tag:v6.8.0 - Block will be renamed in 6.8 #}
{% block product_description_outer %}
    <div class="product-description">
        {% block product_description_title %}
            <h2>{{ product.translated.name }}</h2>
        {% endblock %}
        {% block product_description_body %}
            <p>{{ product.translated.description|raw }}</p>
        {% endblock %}
    </div>
{% endblock %}

{% block product_meta %}
    <meta name="og:title" content="{{ product.translated.name }}">
{% endblock %}
"""


def test_extracts_blocks():
    chunks = chunk_twig(
        SAMPLE,
        file_path="src/Storefront/Resources/views/storefront/page/product-detail/index.html.twig",
        area="storefront",
    )
    names = {c.symbol_name for c in chunks if c.symbol_kind == "twig_block"}
    assert "product_description_outer" in names
    assert "product_description_title" in names
    assert "product_description_body" in names
    assert "product_meta" in names


def test_deprecation_captured_on_file_level():
    chunks = chunk_twig(
        SAMPLE,
        file_path="src/Storefront/Resources/views/storefront/page/product-detail/index.html.twig",
        area="storefront",
    )
    file_chunk = next(c for c in chunks if c.symbol_kind == "file")
    assert file_chunk.deprecated_in == "v6.8.0"


def test_extends_target_in_extra():
    chunks = chunk_twig(
        SAMPLE,
        file_path="src/Storefront/Resources/views/storefront/page/product-detail/index.html.twig",
        area="storefront",
    )
    file_chunk = next(c for c in chunks if c.symbol_kind == "file")
    assert (
        file_chunk.extra.get("extends")
        == "@Storefront/storefront/page/product-detail/index.html.twig"
    )
