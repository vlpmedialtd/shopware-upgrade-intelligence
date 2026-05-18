from shopware_intel.ingest.chunk.php import chunk_php

SAMPLE = """<?php

namespace Shopware\\Core\\Framework\\Foo;

use Shopware\\Core\\Framework\\Bar;

/**
 * Does foo.
 *
 * @deprecated tag:v6.8.0 - use {@see NewFoo}
 */
#[Package('framework')]
final class FooService
{
    public function bar(): int
    {
        return 42;
    }
}

/**
 * Helper.
 */
class FooHelper
{
    public const X = 1;
}
"""


def test_chunks_one_per_class():
    chunks = chunk_php(SAMPLE, file_path="src/Core/Framework/Foo/FooService.php", area="core")
    assert len(chunks) == 2
    names = [c.symbol_name for c in chunks]
    assert names == ["FooService", "FooHelper"]


def test_deprecated_extracted():
    chunks = chunk_php(SAMPLE, file_path="src/Core/Framework/Foo/FooService.php", area="core")
    foo = next(c for c in chunks if c.symbol_name == "FooService")
    assert foo.deprecated_in == "v6.8.0"


def test_namespace_in_fqn():
    chunks = chunk_php(SAMPLE, file_path="src/Core/Framework/Foo/FooService.php", area="core")
    foo = next(c for c in chunks if c.symbol_name == "FooService")
    assert foo.symbol_fqn == "Shopware\\Core\\Framework\\Foo\\FooService"


def test_no_classes_returns_file_chunk():
    chunks = chunk_php("<?php echo 'hi';", file_path="a.php", area="other")
    assert len(chunks) == 1
    assert chunks[0].symbol_kind == "file"
