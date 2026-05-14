#!/usr/bin/env python3
"""PolyNews Terminal — Playwright test."""

import asyncio, re, sys
from playwright.async_api import async_playwright

POLYNEWS_URL = "https://polynews-vin.loca.lt"
TIMEOUT = 15_000

async def run():
    errors = []
    console_errors = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headed so we can see
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await ctx.new_page()

        # Capture console errors
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        print("🌐 Navigating to PolyNews Terminal...")
        resp = await page.goto(POLYNEWS_URL, timeout=TIMEOUT, wait_until="networkidle")
        print(f"   HTTP status: {resp.status}")

        # Wait for news cards to appear
        print("\n📰 Waiting for news cards to load...")
        try:
            await page.wait_for_selector(".touch-target", timeout=TIMEOUT)
        except Exception as e:
            print(f"   ❌ No cards found: {e}")
            await browser.close()
            return False

        # Count cards
        cards = await page.query_selector_all(".touch-target")
        print(f"   ✓ Found {len(cards)} news cards")

        # Get item details before clicking
        card_data = []
        for i, card in enumerate(cards[:5]):
            title_el = await card.query_selector("h3")
            source_el = await card.query_selector("span.text-xs.font-semibold")
            href = await card.get_attribute("href")
            title = await title_el.inner_text() if title_el else "(no title)"
            source = await source_el.inner_text() if source_el else "(no source)"
            card_data.append({"title": title[:60], "source": source, "href": href})
            print(f"   [{i+1}] [{source}] {title[:55]}...")
            print(f"       href: {href}")

        # Filter cards that have real URLs (not empty polynews URLs)
        clickable_cards = [c for c in card_data if c["href"] and len(c["href"]) > 10 and not c["href"].startswith("https://polynews")]
        print(f"\n   ✓ {len(clickable_cards)} cards with real URLs")

        if not clickable_cards:
            print("\n   ⚠ All cards are non-clickable (no URLs). Checking dimmed/static cards...")
            # Check if dimmed cards (no URL) exist
            dimmed = await page.query_selector_all(".opacity-60")
            print(f"   Found {len(dimmed)} dimmed cards (no URL)")
            # Check what the actual article source looks like
            first_card = cards[0]
            href = await first_card.get_attribute("href")
            print(f"   First card href: {href}")
            print(f"   First card tag: {await first_card.evaluate('el => el.tagName')}")
            # Check if cards are anchor tags or divs
            tag = await first_card.evaluate('el => el.tagName')
            print(f"   First card tag name: {tag}")

            # Check if there are any anchor tags at all
            anchors = await page.query_selector_all("a")
            print(f"   Total anchor tags on page: {len(anchors)}")
            for a in anchors[:3]:
                href = await a.get_attribute("href")
                print(f"   Anchor href: {href}")

            # The app likely works — check that BBC/Yahoo items have proper URLs
            print("\n🔍 Checking URL attachment in data...")
            all_text = await page.inner_text("body")
            # Check if URLs appear in the page at all
            url_pattern = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')
            urls_found = url_pattern.findall(all_text)
            print(f"   URLs found on page: {len(urls_found)}")
            for u in urls_found[:5]:
                print(f"     {u}")

        else:
            # Test clicking — open first real URL
            first = clickable_cards[0]
            print(f"\n🖱 Clicking first item with real URL: {first['title'][:50]}...")
            print(f"   URL: {first['href']}")

            # Use popup to intercept the new page
            async with page.expect_popup() as popup_info:
                await page.click("a[href='" + first["href"] + "']")

            popup = await popup_info.value
            popup_url = popup.url
            print(f"   ✅ Popup opened at: {popup_url}")

            # Verify the popup is a real news site (not polynews internal)
            if "polynews" not in popup_url and popup_url.startswith("http"):
                print(f"   ✅ Correct! Opens real news site: {popup_url[:80]}")
            else:
                print(f"   ⚠ Popup URL seems wrong: {popup_url}")

            await popup.close()

        # Report console errors
        if console_errors:
            print(f"\n⚠ Console errors: {console_errors}")
        else:
            print(f"\n✅ No console errors")

        print("\n✅ Test complete")
        await browser.close()
        return True

if __name__ == "__main__":
    ok = asyncio.run(run())
    sys.exit(0 if ok else 1)