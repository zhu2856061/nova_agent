#!/usr/bin/env python3
"""
Builtin Browser Example

This example demonstrates how to use Crawl4AI's builtin browser feature,
which simplifies the browser management process. With builtin mode:

- No need to manually start or connect to a browser
- No need to manage CDP URLs or browser processes
- Automatically connects to an existing browser or launches one if needed
- Browser persists between script runs, reducing startup time
- No explicit cleanup or close() calls needed

The example also demonstrates "auto-starting" where you don't need to explicitly
call start() method on the crawler.
"""

import asyncio
import time

from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig


async def crawl_with_builtin_browser():
    """
    Simple example of crawling with the builtin browser.

    Key features:
    1. browser_mode="builtin" in BrowserConfig
    2. No explicit start() call needed
    3. No explicit close() needed
    """
    print("\n=== Crawl4AI Builtin Browser Example ===\n")

    # Create a browser configuration with builtin mode
    browser_config = BrowserConfig(
        # browser_mode="builtin",  # This is the key setting!
        headless=True,  # Can run headless for background operation
        viewport={
            "width": 800,
            "height": 600,
        },  # Smaller viewport for better performance
    )

    # Create crawler run configuration
    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,  # Skip cache for this demo
        screenshot=True,  # Take a screenshot
        verbose=True,  # Show verbose logging
    )

    # Create the crawler instance
    # Note: We don't need to use "async with" context manager

    async def fetch_content(url):
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=crawler_config)
            return result

    # Start crawling several URLs - no explicit start() needed!
    # The crawler will automatically connect to the builtin browser
    print("\n➡️ Crawling first URL...")
    t0 = time.time()
    result1 = await fetch_content(url="https://crawl4ai.com")
    t1 = time.time()
    print(f"✅ First URL crawled in {t1 - t0:.2f} seconds")
    print(f"   Got {len(result1.markdown.raw_markdown)} characters of content")
    print(f"   Title: {result1.metadata.get('title', 'No title')}")


async def main():
    """Run the example"""
    await crawl_with_builtin_browser()


if __name__ == "__main__":
    asyncio.run(main())
