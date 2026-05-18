from shopware_intel.areas import Area, classify, is_ingest_candidate, language_of


def test_core_paths_classify():
    assert classify("src/Core/Framework/DataAbstractionLayer/EntityRepository.php") == Area.CORE
    assert classify("src/Core/System/SalesChannel/SalesChannelEntity.php") == Area.CORE


def test_storefront_paths_classify():
    assert classify("src/Storefront/Controller/HomeController.php") == Area.STOREFRONT
    assert (
        classify("src/Storefront/Resources/views/storefront/component/product/card.html.twig")
        == Area.STOREFRONT
    )


def test_administration_paths_classify():
    assert (
        classify(
            "src/Administration/Resources/app/administration/src/module/sw-product/page/index.vue"
        )
        == Area.ADMINISTRATION
    )


def test_checkout_classifies_before_storefront_and_core():
    assert classify("src/Core/Checkout/Cart/CartCalculator.php") == Area.CHECKOUT
    assert (
        classify("src/Storefront/Resources/views/storefront/page/checkout/cart/index.html.twig")
        == Area.CHECKOUT
    )
    assert (
        classify(
            "src/Storefront/Resources/views/storefront/component/checkout/offcanvas-cart.html.twig"
        )
        == Area.CHECKOUT
    )


def test_flow_classifies():
    assert classify("src/Core/Content/Flow/Dispatching/FlowExecutor.php") == Area.FLOW
    assert (
        classify(
            "src/Administration/Resources/app/administration/src/module/sw-flow/page/index.vue"
        )
        == Area.FLOW
    )


def test_changelog_paths_classify():
    assert classify("changelog/release-6-7-0-0/2024-01-01-feature-x.md") == Area.CHANGES
    assert classify("UPGRADE-6.7.md") == Area.CHANGES


def test_language_detection():
    assert language_of("src/Core/Foo.php") == "php"
    assert language_of("foo/bar.html.twig") == "twig"
    assert language_of("a.vue") == "vue"
    assert language_of("b.scss") == "scss"
    assert language_of("nope.exe") is None


def test_excludes_tests_vendor_dist():
    assert not is_ingest_candidate("src/Core/Framework/Test/Foo.php")
    assert not is_ingest_candidate("vendor/symfony/console/Application.php")
    assert not is_ingest_candidate("src/Storefront/Resources/public/dist/styles/some.css")
    assert not is_ingest_candidate("foo.spec.js")


def test_included_php():
    assert is_ingest_candidate("src/Core/Framework/DataAbstractionLayer/EntityRepository.php")
