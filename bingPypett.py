
import asyncio
import os
import json
from datetime import datetime
from pyppeteer import launch

# File Paths
cookie_file = "cookies.json"
file_path = "rewards_log.txt"

# URL for Microsoft Rewards
rewards_url = "https://rewards.microsoft.com/"

def log_to_file(message):
    """Log messages to a file."""
    now = datetime.now().strftime('%H:%M')
    with open(file_path, 'a', encoding='utf-8') as file:
        file.write(f'{now} - {message}\n')
    print(f"{message}\n")

async def save_cookies(page):
    """Save cookies after login."""
    cookies = await page.cookies()
    with open(cookie_file, "w") as f:
        json.dump(cookies, f)
    log_to_file("Cookies saved.")

async def load_cookies(page):
    """Load cookies if available."""
    if os.path.exists(cookie_file):
        with open(cookie_file, "r") as f:
            cookies = json.load(f)
        await page.setCookie(*cookies)
        log_to_file("Loaded saved cookies.")

async def login_if_needed(page):
    """Check if login is required, and if so, wait for user login."""
    await page.goto(rewards_url)
    await page.waitForSelector("body")

    # Check if already logged in
    if "Sign in" not in await page.content():
        log_to_file("Already logged in.")
        return

    log_to_file("Login required. Please log in manually.")
    await asyncio.sleep(20)  # Give user time to log in

    await save_cookies(page)

async def collect_rewards(page):
    """Automate clicking on daily rewards."""
    log_to_file("Collecting daily rewards...")

    # Open the rewards page
    await page.goto(rewards_url)
    await page.waitForSelector("body")

    # Find all clickable reward links
    reward_links = await page.evaluate('''() => {
        return Array.from(document.querySelectorAll('a[href*="rewards"]'))
            .map(a => a.href);
    }''')

    log_to_file(f"Found {len(reward_links)} rewards to process.")

    # Click each reward link
    for link in reward_links:
        log_to_file(f"Opening: {link}")
        new_page = await page.browser.newPage()
        await new_page.goto(link)
        await asyncio.sleep(5)  # Wait for action to complete
        await new_page.close()

    log_to_file("All rewards processed.")

async def main():
    """Main function to launch the browser and run automation."""
    browser = await launch(headless=False, executablePath="/usr/bin/chromium")  # Use system Chromium
    page = await browser.newPage()

    await load_cookies(page)
    await login_if_needed(page)
    await collect_rewards(page)

    await browser.close()
    log_to_file("Script completed.")

if __name__ == "__main__":
    asyncio.run(main())
