from shopware_intel.ingest.chunk.php_ts import chunk_php_ts

SAMPLE = """<?php

namespace Shopware\\Core\\Framework\\Foo;

use Shopware\\Core\\Framework\\Bar;

/**
 * Top-level docblock.
 *
 * @deprecated tag:v6.8.0 - use NewFoo
 */
#[Package('framework')]
final class FooService
{
    /** Doc for bar */
    public function bar(int $x): int
    {
        return $x;
    }

    /**
     * @deprecated tag:v6.8.0 - removed soon
     */
    public function legacyMethod(): string
    {
        return 'x';
    }

    private function helper(): void {}
}
"""


def test_emits_class_header_and_per_method_chunks():
    chunks = chunk_php_ts(SAMPLE, file_path="src/Core/Framework/Foo/FooService.php", area="core")
    kinds = [c.symbol_kind for c in chunks]
    assert "class" in kinds
    method_names = sorted(c.symbol_name for c in chunks if c.symbol_kind == "method")
    assert method_names == ["bar", "helper", "legacyMethod"]


def test_class_level_deprecation_captured():
    chunks = chunk_php_ts(SAMPLE, file_path="src/Core/Framework/Foo/FooService.php", area="core")
    cls = next(c for c in chunks if c.symbol_kind == "class")
    assert cls.deprecated_in == "v6.8.0"
    assert cls.symbol_fqn == "Shopware\\Core\\Framework\\Foo\\FooService"


def test_method_level_deprecation_captured():
    chunks = chunk_php_ts(SAMPLE, file_path="src/Core/Framework/Foo/FooService.php", area="core")
    legacy = next(c for c in chunks if c.symbol_name == "legacyMethod")
    assert legacy.deprecated_in == "v6.8.0"
    assert legacy.symbol_fqn == "Shopware\\Core\\Framework\\Foo\\FooService::legacyMethod"


def test_method_without_doc_has_no_deprecation():
    chunks = chunk_php_ts(SAMPLE, file_path="src/Core/Framework/Foo/FooService.php", area="core")
    helper = next(c for c in chunks if c.symbol_name == "helper")
    assert helper.deprecated_in is None


def test_no_classes_emits_one_file_chunk():
    chunks = chunk_php_ts("<?php\necho 'hi';\n", file_path="a.php", area="other")
    assert len(chunks) == 1
    assert chunks[0].symbol_kind == "file"
