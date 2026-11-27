"""Verify the populated local MarketLens API through the Firebase Auth emulator."""

import argparse
import json
from getpass import getpass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


local_http = build_opener(ProxyHandler({}), NoRedirect())


def request(url, *, token=None, payload=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    data = json.dumps(payload).encode() if payload is not None else None
    with local_http.open(Request(url, data=data, headers=headers), timeout=15) as response:
        return json.load(response)


def check(api_port, auth_port, email, password):
    auth = f"http://127.0.0.1:{auth_port}/identitytoolkit.googleapis.com/v1"
    token = request(
        f"{auth}/accounts:signInWithPassword?key=local-demo",
        payload={"email": email, "password": password, "returnSecureToken": True},
    )["idToken"]
    base = f"http://127.0.0.1:{api_port}/api/v1/market"
    catalog = request(f"{base}/listings?limit=100&sort=price_asc", token=token)["items"]
    if not catalog or not all(item["analysis"] for item in catalog):
        raise ValueError("Import listings and run the analytics refresh before the check.")
    prices = [
        item["listing"]["price"]
        for item in catalog
        if item["listing"]["currency"] == "KZT" and item["listing"]["price"] is not None
    ]
    if not prices or prices != sorted(prices):
        raise ValueError("Expected known KZT prices sorted in ascending order.")
    groups = request(f"{base}/stats", token=token)["items"]
    if not groups or any(
        sum(bin_["count"] for bin_ in group["histogram"]) != group["sampleSize"] for group in groups
    ):
        raise ValueError("Market groups or histogram counts are missing or inconsistent.")
    listing = catalog[0]["listing"]
    detail = f"{base}/listings/{quote(listing['id'], safe='')}"
    snapshots = request(f"{detail}/history", token=token)["items"]
    if not snapshots or snapshots[0]["price"] != listing["price"]:
        raise ValueError("The latest observed price does not match the catalog.")
    explanation = request(f"{detail}/explanation", token=token, payload={})
    if explanation["provider"] != "local":
        raise ValueError("Use an API instance with Gemini disabled for this check.")
    return {
        "checkedListings": len(catalog),
        "checkedGroups": len(groups),
        "history": len(snapshots),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default="tester@example.test")
    parser.add_argument("--api-port", type=int, default=8010)
    parser.add_argument("--auth-port", type=int, default=9199)
    args = parser.parse_args()
    try:
        result = check(args.api_port, args.auth_port, args.email, getpass("Local password: "))
    except HTTPError as error:
        parser.exit(1, f"Local MarketLens check received HTTP {error.code}.\n")
    except (URLError, KeyError, ValueError) as error:
        parser.exit(1, f"Local MarketLens check failed: {error}\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
