from shopware_intel.ingest.chunk.scss import chunk_scss, extract_classes

SAMPLE = """
.product-description {
    color: #333;
}

.product-description-title,
.product-description-meta {
    font-weight: bold;
}

.is-active-route {
    background: red;
}
"""


def test_extract_classes_unique_sorted():
    classes = extract_classes(SAMPLE)
    assert classes == [
        "is-active-route",
        "product-description",
        "product-description-meta",
        "product-description-title",
    ]


def test_chunk_scss_emits_single_file_chunk_with_classes_extra():
    chunks = chunk_scss(SAMPLE, file_path="a.scss", area="storefront")
    assert len(chunks) == 1
    c = chunks[0]
    assert c.language == "scss"
    assert "product-description" in c.extra["css_classes"]
