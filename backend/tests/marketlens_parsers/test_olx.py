"""Synthetic OLX HTML used only with a mock transport."""

import sys
from datetime import UTC
from json import loads

import httpx
import pytest
from pydantic import TypeAdapter

from app.marketlens import import_listings
from app.marketlens.contracts import CollectionRequest, Listing, ListingParser
from app.marketlens.parsers.collect_olx import main as export_olx
from app.marketlens.parsers.olx import CATEGORY, CATEGORY_URL, OLXParser, OLXSourceError


def synthetic_card(href, title="", price=""):
    return f"""
    <div data-cy="l-card">
      <a href="{href}"><img src="/synthetic.png"></a>
      <a href="{href}"><h6>{title}</h6></a>
      <p data-testid="ad-price">{price}</p>
    </div>
    """


@pytest.fixture
def synthetic_category():
    return (
        synthetic_card(
            "/d/obyavlenie/test-IDTest1.html?tracking=1",
            "Учебный <b>телефон</b>",
            "85&nbsp;<span>000</span> тг.",
        )
        + synthetic_card("/d/obyavlenie/renamed-IDTest1.html", "Дубликат", "1 тг.")
        + synthetic_card("/d/obyavlenie/test-IDTest2.html", "Фикстура без цены", "Договорная")
        + synthetic_card("/d/obyavlenie/test-IDTest3.html", "Фикстура с валютой", "12 USD")
        + synthetic_card("/d/obyavlenie/test-IDTest4.html", price="1 тг.")
        + synthetic_card("https://other.example/d/obyavlenie/test-IDTest5.html", "Чужой URL")
    )


def html(body):
    return httpx.Response(200, text=body, headers={"Content-Type": "text/html; charset=utf-8"})


def test_repeated_collection_deduplicates_and_retains_partial_cards(synthetic_category):
    requests = []

    def respond(request):
        requests.append(str(request.url))
        return html(synthetic_category)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        parser: ListingParser = OLXParser(client, authorized=True)
        collected = parser.collect(CollectionRequest(category=CATEGORY))
        first = list(collected)
        second = list(parser.collect(CollectionRequest(category=CATEGORY)))
        limited = list(parser.collect(CollectionRequest(category=CATEGORY, limit=2)))

    assert requests == [CATEGORY_URL] * 3
    assert (
        [row.id for row in first]
        == [row.id for row in second]
        == ["olx:Test1", "olx:Test2", "olx:Test3"]
    )
    assert [row.id for row in limited] == ["olx:Test1", "olx:Test2"]
    assert second[0].scraped_at >= first[0].scraped_at
    assert first[0].scraped_at.tzinfo is UTC
    assert first[0].title == "Учебный телефон"
    assert str(first[0].url) == "https://www.olx.kz/d/obyavlenie/test-IDTest1.html"
    assert first[0].price == 85000
    assert first[0].currency == "KZT"
    for row in first[1:]:
        assert row.price is row.currency is row.city is row.published_at is row.seller_id is None
        assert row.images == []
        assert row.attributes == {}


def test_cli_output_matches_import_schema_and_import_rejects_marked_fixtures(
    synthetic_category, monkeypatch, capsys, tmp_path
):
    client = httpx.Client(transport=httpx.MockTransport(lambda request: html(synthetic_category)))
    monkeypatch.setattr("app.marketlens.parsers.collect_olx.httpx.Client", lambda: client)
    monkeypatch.setattr(sys, "argv", ["collect_olx", "--authorized", "--limit", "2"])
    export_olx()
    output = capsys.readouterr().out
    adapter = TypeAdapter(list[Listing])
    assert loads(output)[0]["externalId"] == "Test1"
    rows = adapter.validate_json(output)
    assert len(rows) == 2

    fixtures = []
    for row in rows:
        fixture_id = f"fixture-{row.external_id}"
        fixtures.append(
            row.model_copy(
                update={"id": f"olx:{fixture_id}", "external_id": fixture_id, "dataset": "fixture"}
            )
        )
    path = tmp_path / "synthetic-fixtures.json"
    path.write_bytes(adapter.dump_json(fixtures, by_alias=True))
    monkeypatch.setattr(sys, "argv", ["import_listings", str(path)])
    with pytest.raises(SystemExit) as failure:
        import_listings.main()
    assert failure.value.code == 2
    assert "Fixture records cannot be imported here" in capsys.readouterr().err


def test_collect_requires_authorization_and_supported_category():
    def unexpected_request(request):
        pytest.fail("Must validate the request before accessing OLX")

    with httpx.Client(transport=httpx.MockTransport(unexpected_request)) as client:
        parser = OLXParser(client)
        with pytest.raises(ValueError, match="electronics"):
            parser.collect(CollectionRequest(category="cars"))
        with pytest.raises(OLXSourceError, match="разрешение"):
            parser.collect(CollectionRequest(category=CATEGORY))


@pytest.mark.parametrize("status", [302, 403, 429, 503])
def test_source_http_failure(status):
    transport = httpx.MockTransport(lambda request: httpx.Response(status))
    with (
        httpx.Client(transport=transport) as client,
        pytest.raises(OLXSourceError, match=f"HTTP {status}"),
    ):
        OLXParser(client, authorized=True).collect(CollectionRequest(category=CATEGORY))


@pytest.mark.parametrize("error", [httpx.ProxyError, httpx.ReadTimeout])
def test_source_connection_failure(error):
    def fail(request):
        raise error("test")

    with (
        httpx.Client(transport=httpx.MockTransport(fail)) as client,
        pytest.raises(OLXSourceError, match="OLX:"),
    ):
        OLXParser(client, authorized=True).collect(CollectionRequest(category=CATEGORY))


@pytest.mark.parametrize("body", ["<html>Access denied</html>", synthetic_card("/bad", "Test")])
def test_unrecognized_page_is_a_source_failure(body):
    with (
        httpx.Client(transport=httpx.MockTransport(lambda request: html(body))) as client,
        pytest.raises(OLXSourceError, match="не найдены"),
    ):
        OLXParser(client, authorized=True).collect(CollectionRequest(category=CATEGORY))


def test_explicit_empty_category():
    response = html('<div data-testid="listing-empty-state"></div>')
    with httpx.Client(transport=httpx.MockTransport(lambda request: response)) as client:
        assert (
            OLXParser(client, authorized=True).collect(CollectionRequest(category=CATEGORY)) == []
        )


def test_cli_source_failure_does_not_emit_listing_json(monkeypatch, capsys):
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(403)))
    monkeypatch.setattr("app.marketlens.parsers.collect_olx.httpx.Client", lambda: client)
    monkeypatch.setattr(sys, "argv", ["collect_olx", "--authorized"])
    with pytest.raises(SystemExit) as failure:
        export_olx()
    assert failure.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "HTTP 403" in captured.err
