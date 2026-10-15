"""One-off public DBIQ index-document discovery in a headless browser.

Public GET and UI clicks on index.db.com only. No auth bypass, bearer
cookies, broker network, PDF publishing or licensed-data redistribution.
The CI run retains only document discovery *statuses* and source URLs,
never private PDF bytes or undocumented index contract choices.

This is separate from deterministic C3G source-data validation.
"""
from __future__ import annotations

import asyncio
import json
import re
from urllib.parse import urlparse

INDEX_URL = "https://index.db.com/dbiq-web/indices/95400"
DOCUMENTS = (
    "DBIQ Optimum Yield Diversified Commodity Index Guide 2025.pdf",
    "Diversified Commodity Index Weights for November 2025.pdf",
)


def approved_url(url: str) -> bool:
    p = urlparse(url)
    return (
        p.scheme == "https"
        and p.hostname is not None
        and (p.hostname == "db.com" or p.hostname.endswith(".db.com"))
    )


async def attempt() -> dict:
    from playwright.async_api import async_playwright

    results = {
        "schema": "FUND100_C3G_PUBLIC_ISSUER_DOCUMENT_DISCOVERY_V1",
        "scope": "PUBLIC_DOCUMENT_ACCESS_PROBE_NO_BROKER",
        "approved_issuer_page": INDEX_URL,
        "source_document_bodies_acquired": False,
        "pdf_contents_verified": False,
        "actual_issuer_index_roll_contracts_extracted": False,
        "paper_or_live_orders": 0,
        "documents": [],
    }
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(accept_downloads=False)
            page = await context.new_page()
            observed = []
            page.on(
                "response",
                lambda response: observed.append({
                    "url": response.url,
                    "status": response.status,
                    "content_type": response.headers.get("content-type", ""),
                }) if approved_url(response.url) and (
                    "pdf" in response.url.lower() or
                    "document" in response.url.lower() or
                    "application/pdf" in response.headers.get("content-type", "").lower()
                ) else None,
            )
            try:
                response = await page.goto(INDEX_URL, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(5500)
                results["http_status"] = response.status if response else None
                results["rendered_title"] = (await page.title())[:180]
                text = await page.locator("body").inner_text(timeout=5000)
                results["index_page_contains_dbiq_ticker"] = "DBLCDBCE" in text
                results["index_page_contains_document_listing"] = (
                    "DBIQ Optimum Yield Diversified Commodity Index Guide 2025" in text
                )
            except Exception as exc:
                results["page_error_type"] = type(exc).__name__
            for label in DOCUMENTS:
                item = {"title": label, "direct_pdf_url_verified": False,
                        "official_pdf_bytes_acquired": False}
                try:
                    locator = page.get_by_text(label, exact=True)
                    count = await locator.count()
                    item["rendered_exact_title_matches"] = count
                    if count:
                        node = locator.first
                        href = await node.get_attribute("href")
                        if not href:
                            href = await node.evaluate(
                                "(node) => node.closest('a')?.href || null"
                            )
                        if href and approved_url(href) and ".pdf" in href.lower():
                            item["candidate_pdf_url"] = href
                            item["direct_pdf_url_verified"] = True
                        # Click only a displayed original issuer document.
                        # Browsers may open native PDF viewer/download; the
                        # no-download context deliberately blocks retention.
                        try:
                            await node.click(timeout=4000)
                            await page.wait_for_timeout(1500)
                            item["clicked_issuer_document"] = True
                        except Exception as exc:
                            item["click_result"] = type(exc).__name__
                except Exception as exc:
                    item["locator_result"] = type(exc).__name__
                results["documents"].append(item)
            results["official_http_document_response_candidates"] = [
                response for response in observed[:30]
                if approved_url(response["url"])
            ]
        finally:
            await browser.close()
    return results


def main() -> None:
    payload = asyncio.run(attempt())
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["source_document_bodies_acquired"]:
        print("INDEX METHODOLOGY PDF BYTES NOT ACQUIRED: still evidence-gated.")
    print("C3G provider-indexed contracts are research only, not futures P&L.")


if __name__ == "__main__":
    main()
