#!/usr/bin/env python3
"""
PolyNews Terminal v3 — Real-time news aggregator for Polymarket trading decisions.
No APIs. HTTP + Playwright browser scraping only.
"""

import argparse
import asyncio
import re
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import warnings

# Suppress BeautifulSoup XML warning (Google News RSS returns XML but we parse as HTML)
from bs4 import XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


async def fetch(url: str, headers: dict = None, timeout: int = 20) -> Optional[str]:
    default = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
    }
    if headers:
        default.update(headers)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            r = await client.get(url, headers=default)
            return r.text if r.status_code < 400 else None
    except Exception:
        return None


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or "", "html.parser")


# ─── SOURCE 1: HACKER NEWS ────────────────────────────────────────────────────

async def scrape_hn(limit: int = 20, category: str = "news") -> list[dict]:
    """Scrape HN with proper score/comments extraction."""
    html = await fetch(f"https://news.ycombinator.com/{category}")
    sp = soup(html)
    results = []
    items = sp.select("tr.athing")
    for item in items[:limit]:
        title_el = item.select_one("span.titleline > a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        url = title_el.get("href", "")
        # Score is in the NEXT sibling tr after .athing
        next_row = item.find_next_sibling("tr")
        score = 0
        comments = 0
        if next_row:
            score_el = next_row.select_one("span.score")
            if score_el:
                m = re.search(r"(\d+)", score_el.get_text())
                if m:
                    score = int(m.group(1))
            # Comments in same row as "N comments"
            cmts_el = next_row.select_one("a[href*=comments]")
            if cmts_el:
                m = re.search(r"(\d+)", cmts_el.get_text())
                if m:
                    comments = int(m.group(1))
        results.append({"title": title, "url": url, "score": score, "comments": comments})
    return results


# ─── SOURCE 2: BBC NEWS ────────────────────────────────────────────────────────

async def scrape_bbc(limit: int = 15) -> list[dict]:
    html = await fetch("https://www.bbc.com/news/")
    sp = soup(html)
    results = []
    seen = set()
    for a in sp.select("a[href]"):
        t = a.get_text(strip=True)
        href = a.get("href", "")
        if not t or len(t) < 25 or t in seen:
            continue
        if "/news/" in href and ("bbc.com" in href or href.startswith("/")):
            if href.startswith("/"):
                href = "https://www.bbc.com" + href
            if "bbc.com/news" not in href:
                continue
            seen.add(t)
            results.append({"title": t, "url": href})
            if len(results) >= limit:
                break
    return results


# ─── SOURCE 3: YAHOO FINANCE ──────────────────────────────────────────────────

async def scrape_yahoo_finance(limit: int = 15) -> list[dict]:
    html = await fetch("https://finance.yahoo.com/")
    sp = soup(html)
    results = []
    seen = set()
    # Look for market data symbols
    for el in sp.select("fin-streamer, [data-testid='quote']"):
        sym = el.get("data-symbol", "")
        if sym:
            price = el.get("data-value", el.get_text(strip=True))
            results.append({"title": f"{sym}: {price}", "url": f"https://finance.yahoo.com/quote/{sym}"})
            seen.add(sym)
    # Fallback: find links with news articles
    if not results:
        for a in sp.select("a[href]"):
            t = a.get_text(strip=True)
            href = a.get("href", "")
            if not t or len(t) < 20 or t in seen:
                continue
            if "/news/" in href or "/quote/" in href:
                if href.startswith("/"):
                    href = "https://finance.yahoo.com" + href
                seen.add(t)
                results.append({"title": t, "url": href})
                if len(results) >= limit:
                    break
    return results[:limit]


# ─── SOURCE 4: COINDESK ────────────────────────────────────────────────────────

async def scrape_coindesk(limit: int = 15) -> list[dict]:
    html = await fetch("https://www.coindesk.com/news/")
    sp = soup(html)
    results = []
    seen = set()
    for a in sp.select("a[href]"):
        t = a.get_text(strip=True)
        href = a.get("href", "")
        if not t or len(t) < 20 or t in seen:
            continue
        if "/news/" in href:
            if href.startswith("/"):
                href = "https://www.coindesk.com" + href
            seen.add(t)
            results.append({"title": t, "url": href})
            if len(results) >= limit:
                break
    return results


# ─── SOURCE 5: THE BLOCK ───────────────────────────────────────────────────────

async def scrape_theblock(limit: int = 12) -> list[dict]:
    html = await fetch("https://www.theblock.co/latest")
    sp = soup(html)
    results = []
    seen = set()
    for a in sp.select("a[href]"):
        t = a.get_text(strip=True)
        href = a.get("href", "")
        if not t or len(t) < 20 or t in seen:
            continue
        if "/post/" in href or "/latest/" in href or any(k in href for k in ["/crypto/", "/news/"]):
            if not href.startswith("http"):
                href = "https://www.theblock.co" + href
            seen.add(t)
            results.append({"title": t, "url": href})
            if len(results) >= limit:
                break
    return results


# ─── SOURCE 6: POLYMARKET ───────────────────────────────────────────────────────

async def scrape_polymarket() -> list[dict]:
    """Get trending markets via web scraping."""
    html = await fetch("https://polymarket.com/markets")
    sp = soup(html)
    results = []

    # Strategy 1: look for market YES/YES% patterns in text
    for el in sp.select("span, div"):
        text = el.get_text(strip=True)
        # Match patterns like "76% Yes" or "YES 0.68" or probability patterns
        m = re.search(r"(\d+(?:\.\d+)?)\s*%.*?(YES|Yes|yes|NO|No|no|\$|¢)", text)
        title = text
        if 10 < len(title) < 100 and m and title not in [r.get("title","") for r in results]:
            prob = re.search(r"(\d+(?:\.\d+)?)\s*%", title)
            if prob:
                results.append({
                    "title": title,
                    "url": "",
                })

    # Strategy 2: find market list items
    for a in sp.select("a[href*='/market/']"):
        t = a.get_text(strip=True)
        href = a.get("href", "")
        if t and len(t) > 15 and len(t) < 120:
            results.append({
                "title": t,
                "url": f"https://polymarket.com{href}" if href else "",
            })

    # Deduplicate by title
    seen = set()
    deduped = []
    for r in results:
        if r["title"] not in seen:
            seen.add(r["title"])
            deduped.append(r)

    return deduped[:12]


# ─── SOURCE 7: NITTER (Twitter scraping without API) ─────────────────────────

NITTER_INSTANCES = [
    "nitter.privacydev.io",
    "nitter.poast.org",
    "nitter.kylrth.com",
]


async def scrape_nitter_user(username: str, limit: int = 8) -> list[dict]:
    for instance in NITTER_INSTANCES:
        html = await fetch(f"https://{instance}/{username}")
        if not html:
            continue
        sp = soup(html)
        tweets = []
        for item in sp.select("div.timeline-item")[:limit]:
            content = item.select_one(".tweet-content")
            date_el = item.select_one(".tweet-date a")
            if content:
                text = content.get_text(strip=True)
                link = date_el.get("href", "") if date_el else ""
                tweets.append({
                    "title": text[:150],
                    "url": f"https://twitter.com{link}" if link else "",
                    "time": date_el.get_text(strip=True) if date_el else "",
                })
        if tweets:
            return tweets
    return []


async def search_nitter(query: str, limit: int = 8) -> list[dict]:
    encoded = query.replace(" ", "%20")
    for instance in NITTER_INSTANCES:
        html = await fetch(f"https://{instance}/search?f=tweets&q={encoded}")
        if not html:
            continue
        sp = soup(html)
        tweets = []
        for item in sp.select("div.timeline-item")[:limit]:
            content = item.select_one(".tweet-content")
            date_el = item.select_one(".tweet-date a")
            if content:
                text = content.get_text(strip=True)
                link = date_el.get("href", "") if date_el else ""
                tweets.append({
                    "title": text[:150],
                    "url": f"https://twitter.com{link}" if link else "",
                    "time": date_el.get_text(strip=True) if date_el else "",
                })
        if tweets:
            return tweets
    return []


_twitter_browser = None
_twitter_context = None


async def get_twitter_browser():
    global _twitter_browser, _twitter_context
    if _twitter_browser is None:
        p = await async_playwright().start()
        _twitter_browser = await p.chromium.launch()
        _twitter_context = await _twitter_browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            viewport={"width": 1280, "height": 720},
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
        )
    return _twitter_browser, _twitter_context


async def scrape_twitter_user(username: str, limit: int = 8) -> list[dict]:
    """Scrape tweets from a Twitter/X user profile page via Playwright."""
    try:
        browser, context = await get_twitter_browser()
        page = await context.new_page()
        await page.goto(f"https://twitter.com/{username}", timeout=20000, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        await page.mouse.wheel(0, 300)
        await asyncio.sleep(0.5)

        tweets_data = await page.evaluate(
            """(limit) => {
            const articles = document.querySelectorAll("article");
            const results = [];
            for (const art of articles) {
                const textEl = art.querySelector('[data-testid="tweetText"]');
                const timeEl = art.querySelector("time");
                const linkEl = art.querySelector('a[href*="/status/"]');
                if (textEl) {
                    results.push({
                        text: textEl.innerText.trim(),
                        time: timeEl ? timeEl.getAttribute("datetime") : null,
                        href: linkEl ? linkEl.getAttribute("href") : null
                    });
                }
                if (results.length >= limit) break;
            }
            return results;
            }""",
            limit,
        )

        await page.close()
        return [
            {"title": t["text"][:150], "url": f"https://twitter.com{t['href']}" if t["href"] else "", "time": t["time"] or ""}
            for t in tweets_data
        ]
    except Exception:
        return []


async def search_twitter(query: str, limit: int = 8) -> list[dict]:
    """Search Twitter/X via Playwright. Falls back gracefully when logged-out."""
    try:
        browser, context = await get_twitter_browser()
        page = await context.new_page()
        encoded_q = query.replace(" ", "%20")
        await page.goto(
            f"https://twitter.com/search?q={encoded_q}&src=typed_query&f=live",
            timeout=20000,
            wait_until="domcontentloaded"
        )
        await asyncio.sleep(3)

        # Detect login wall
        body_text = (await page.inner_text("body"))[:100].lower()
        if "sign in to x" in body_text or "sign in with apple" in body_text:
            await page.close()
            return []

        # Scroll to load results
        await page.mouse.wheel(0, 300)
        await asyncio.sleep(0.5)

        tweets_data = await page.evaluate(
            """(limit) => {
            const articles = document.querySelectorAll("article");
            const results = [];
            for (const art of articles) {
                const textEl = art.querySelector('[data-testid="tweetText"]');
                const timeEl = art.querySelector("time");
                const linkEl = art.querySelector('a[href*="/status/"]');
                if (textEl) {
                    results.push({
                        text: textEl.innerText.trim(),
                        time: timeEl ? timeEl.getAttribute("datetime") : null,
                        href: linkEl ? linkEl.getAttribute("href") : null
                    });
                }
                if (results.length >= limit) break;
            }
            return results;
            }""",
            limit,
        )

        await page.close()
        if not tweets_data:
            return []
        return [
            {"title": t["text"][:150], "url": f"https://twitter.com{t['href']}" if t["href"] else "", "time": t["time"] or ""}
            for t in tweets_data
        ]
    except Exception:
        return []


# ─── SOURCE 8: GOOGLE NEWS RSS ─────────────────────────────────────────────────

async def scrape_google_news(query: str, limit: int = 10) -> list[dict]:
    encoded = query.replace(" ", "%20").replace(" OR ", "%20OR%20")
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    html = await fetch(url)
    if not html:
        return []
    sp = soup(html)
    results = []
    for item in sp.select("item")[:limit]:
        title_el = item.select_one("title")
        link_el = item.select_one("link")
        pub_el = item.select_one("pubDate")
        results.append({
            "title": title_el.get_text(strip=True) if title_el else "",
            "url": link_el.get_text(strip=True) if link_el else "",
            "time": pub_el.get_text(strip=True) if pub_el else "",
        })
    return results


# ─── SOURCE 9: REDDIT (via Playwright headless) ─────────────────────────────────

_reddit_browser = None
_reddit_context = None


async def get_reddit_browser():
    global _reddit_browser, _reddit_context
    if _reddit_browser is None:
        p = await async_playwright().start()
        _reddit_browser = await p.chromium.launch()
        _reddit_context = await _reddit_browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
        )
    return _reddit_browser, _reddit_context


async def close_reddit_browser():
    global _reddit_browser, _reddit_context
    if _reddit_browser:
        await _reddit_browser.close()
        _reddit_browser = None
        _reddit_context = None


async def scrape_reddit(sub: str, limit: int = 10) -> list[dict]:
    """Scrape Reddit via headless Playwright on old.reddit.com."""
    try:
        browser, context = await get_reddit_browser()
        page = await context.new_page()
        await page.goto(f"https://old.reddit.com/r/{sub}/", timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        posts = await page.evaluate(
            """(limit) => {
            const results = [];
            const items = document.querySelectorAll('div[data-type="link"]');
            items.forEach(item => {
                const titleEl = item.querySelector('a.title');
                const scoreEl = item.querySelector('.score');
                const comEl = item.querySelector('a[href*="comments"]');
                if (titleEl) {
                    const scoreText = scoreEl ? scoreEl.getAttribute('title') : '0';
                    const score = parseInt(scoreText) || 0;
                    const comments = comEl ? parseInt(comEl.textContent.replace(/[^0-9]/g,'')) || 0 : 0;
                    results.push({
                        title: titleEl.textContent.trim(),
                        score: score,
                        comments: comments,
                    });
                    if (results.length >= limit) return;
                }
            });
            return results;
            }""",
            limit,
        )
        await page.close()
        return posts[:limit]
    except Exception as e:
        return []


# ─── COLLECT ALL ──────────────────────────────────────────────────────────────

async def collect() -> dict:
    tasks = {
        # Hacker News
        "hn": scrape_hn(20, "news"),
        "hn_best": scrape_hn(10, "best"),
        "hn_show": scrape_hn(10, "show"),
        # Mainstream news
        "bbc": scrape_bbc(12),
        "yahoo_finance": scrape_yahoo_finance(12),
        "coindesk": scrape_coindesk(10),
        "theblock": scrape_theblock(10),
        # Polymarket
        "polymarket": scrape_polymarket(),
        # Reddit (no auth required)
        "reddit_wsb": scrape_reddit("wallstreetbets", 8),
        "reddit_news": scrape_reddit("news", 8),
        "reddit_crypto": scrape_reddit("cryptocurrency", 8),
        "reddit_stocks": scrape_reddit("stocks", 8),
        "reddit_economy": scrape_reddit("economy", 8),
        "reddit_worldnews": scrape_reddit("worldnews", 8),
        # Google News via RSS
        "g_economy": scrape_google_news("stock market OR economy OR GDP", 6),
        "g_crypto": scrape_google_news("bitcoin OR cryptocurrency", 6),
        "g_fed": scrape_google_news("federal reserve OR interest rates", 6),
        "g_polymarket": scrape_google_news("polymarket OR prediction market", 6),
        "g_geopolitics": scrape_google_news("war OR military OR china OR russia", 6),
        # Twitter/X searches via Playwright
        "twitter_pm": search_twitter("polymarket", 5),
        "twitter_btc": search_twitter("bitcoin", 5),
        "twitter_fed": search_twitter("fed rates", 5),
        "twitter_election": search_twitter("election 2026", 5),
        "twitter_trade": search_twitter("trading", 5),
    }

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    output = {}
    for key, val in zip(tasks.keys(), results):
        if isinstance(val, Exception):
            output[key] = []
        else:
            output[key] = val
    return output


# ─── DISPLAY ──────────────────────────────────────────────────────────────────

def print_div(label: str):
    console.print(f"\n[bold yellow]▸ {label}[/]")


def display_hn(data: list, label: str = "Hacker News"):
    if not data:
        return
    print_div(label)
    t = Table(box=None, border_style=None, pad_edge=False)
    t.add_column("Pts", justify="right", style="dim", width=5)
    t.add_column("Cmts", justify="right", style="dim", width=5)
    t.add_column("Title", style="white")
    for item in data[:15]:
        title = item["title"][:78]
        if len(item["title"]) > 78:
            title += "..."
        t.add_row(str(item.get("score", 0)), str(item.get("comments", 0)), title)
    console.print(t)


def display_reddit(data: list, sub: str):
    if not data:
        return
    print_div(f"r/{sub}")
    t = Table(box=None, border_style=None, pad_edge=False)
    t.add_column("Score", justify="right", style="dim", width=6)
    t.add_column("Title", style="white")
    for item in data[:10]:
        title = item["title"][:78]
        if len(item["title"]) > 78:
            title += "..."
        t.add_row(str(item.get("score", 0)), title)
    console.print(t)


def display_news(data: list, source: str):
    if not data:
        return
    print_div(source)
    seen = set()
    for item in data:
        title = item.get("title", "")[:95]
        url = item.get("url", "")
        if not title or title in seen:
            continue
        seen.add(title)
        console.print(f"  • {title}")
        if url:
            domain = ""
            if "//" in url:
                domain = url.split("//")[1].split("/")[0][:40]
            console.print(f"    [dim cyan]{domain}[/]")


def display_polymarket(data: list):
    if not data:
        return
    print_div("POLYMARKET TRENDING")
    seen = set()
    for item in data:
        title = item.get("title", "")[:100]
        url = item.get("url", "")
        if not title or title in seen:
            continue
        seen.add(title)
        console.print(f"  [yellow]▸[/] {title}")
        if url:
            console.print(f"    [dim cyan]{url[:60]}[/]")


def display_twitter(data: list, label: str):
    if not data:
        return
    print_div(f"Twitter/X: #{label}")
    for item in data[:5]:
        console.print(f"  [magenta]@[/] {item.get('title','')[:110]}")


def display_google(data: list, label: str):
    if not data:
        return
    print_div(f"Google News: {label}")
    for item in data[:6]:
        console.print(f"  [green]•[/] {item.get('title','')[:90]}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

async def run(live: bool = False, interval: int = 120):
    console.print(Panel(
        "[bold yellow]PolyNews Terminal v3[/]\n"
        "[dim]HN · BBC · Yahoo Finance · CoinDesk · The Block · Polymarket · Reddit · Google News · Nitter[/]\n"
        f"[dim]No APIs | Auto-refresh every {interval}s | Ctrl+C to quit[/]",
        border_style="yellow",
        expand=False,
    ))

    count = 0
    while True:
        count += 1
        ts = datetime.now().strftime("%H:%M:%S")
        console.print(f"\n[dim]══ #{count} — {ts} ══[/]")

        try:
            data = await collect()
        except Exception as e:
            console.print(f"[red]Collection error: {e}[/]")
            if live:
                await asyncio.sleep(interval)
                continue
            break

        # Hacker News
        display_hn(data.get("hn", []), "Hacker News")
        display_hn(data.get("hn_best", []), "HN Best")
        display_hn(data.get("hn_show", []), "HN Show")

        # News feeds
        display_news(data.get("bbc", []), "BBC News")
        display_news(data.get("yahoo_finance", []), "Yahoo Finance")
        display_news(data.get("coindesk", []), "CoinDesk")
        display_news(data.get("theblock", []), "The Block")

        # Polymarket
        display_polymarket(data.get("polymarket", []))

        # Reddit
        for sub in ["wallstreetbets", "cryptocurrency", "stocks", "news", "economy", "worldnews"]:
            display_reddit(data.get(f"reddit_{sub}", []), sub)

        # Twitter/X searches
        console.print(f"\n[dim]── Twitter/X ──[/]")
        for term in ["polymarket", "bitcoin", "fed rates", "election 2026", "trading"]:
            display_twitter(data.get(f"twitter_{term.replace(' ', '_')}", []), term)

        # Google News
        console.print(f"\n[dim]── Google News ──[/]")
        google_labels = {
            "g_economy": "Economy/Stocks",
            "g_crypto": "Crypto",
            "g_fed": "Fed/Rates",
            "g_polymarket": "Polymarket",
            "g_geopolitics": "Geopolitics",
        }
        for key, label in google_labels.items():
            display_google(data.get(key, []), label)

        if not live:
            break

        console.print(f"\n[dim]Next refresh in {interval}s...[/]")
        await asyncio.sleep(interval)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--live", action="store_true")
    p.add_argument("--interval", type=int, default=120)
    args = p.parse_args()
    asyncio.run(run(live=args.live, interval=args.interval))