from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
from time import sleep
import os
import re
import time

# ------------------------------------------------------------------
# WebDriver Setup
# ------------------------------------------------------------------

def setup_edge_driver():
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.use_chromium = True

    try:
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        driver = webdriver.Edge(
            service=Service(EdgeChromiumDriverManager().install()),
            options=options
        )
        return driver
    except Exception:
        return webdriver.Edge(options=options)


def wait_for_driver_ready(driver, timeout=20):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def click_and_handle_new_tab(click_fn, driver, timeout=10):
    original = driver.current_window_handle
    before = set(driver.window_handles)

    click_fn()

    WebDriverWait(driver, timeout).until(
        lambda d: len(d.window_handles) >= len(before)
    )

    after = set(driver.window_handles)
    new_tabs = after - before

    if new_tabs:
        driver.switch_to.window(new_tabs.pop())
        wait_for_driver_ready(driver)
        return True

    return False


def close_extra_tabs(driver, keep_handle):
    for handle in list(driver.window_handles):
        if handle != keep_handle:
            driver.switch_to.window(handle)
            driver.close()
    driver.switch_to.window(keep_handle)

# ------------------------------------------------------------------
# Paths / XPaths
# ------------------------------------------------------------------

file_path = 'rewards_log.txt'

card_base_xpath = '/html/body/div[1]/div[2]/main/div/ui-view/mee-rewards-dashboard/main/div/mee-rewards-daily-set-section/div/mee-card-group[1]/div/mee-card[{}]/div/card-content/mee-rewards-daily-set-item-content/div/a'
base_points_xpath = '/html/body/div[1]/div[2]/main/div/ui-view/mee-rewards-dashboard/main/div/mee-rewards-daily-set-section/div/mee-card-group[1]/div/mee-card[{}]/div/card-content/mee-rewards-daily-set-item-content/div/a/mee-rewards-points/div/div/span[1]'
alt_base_xpath = '//*[@id="more-activities"]/div/mee-card[{}]/div/card-content/mee-rewards-more-activities-card-item/div/a'
alt_points_xpath = '//*[@id="more-activities"]/div/mee-card[{}]/div/card-content/mee-rewards-more-activities-card-item/div/a/mee-rewards-points/div/div/span[1]'

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------

def log_to_file(message):
    now = datetime.now().strftime('%H:%M')
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(f'{now} - {message}\n')
    print(message)

# ------------------------------------------------------------------
# Card Logic
# ------------------------------------------------------------------

def collecting_points(card_xpath, card_number):
    try:
        root = driver.current_window_handle

        card = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, card_xpath))
        )

        aria = card.get_attribute('aria-label') or ""
        href = card.get_attribute('href')

        log_to_file(f'Processing card {card_number}: {aria}')

        if "Redeem now" in aria:
            log_to_file("Skipping redeem card.")
            return

        opened = click_and_handle_new_tab(lambda: card.click(), driver)

        sleep(2)

        if opened:
            driver.close()
            driver.switch_to.window(root)
        else:
            driver.refresh()
            wait_for_driver_ready(driver)

        close_extra_tabs(driver, root)

    except Exception as e:
        log_to_file(f'Error collecting points on card {card_number}: {e}')


def card_status_check(card_number, kind):
    xpath = base_points_xpath.format(card_number)
    if kind == "Activities":
        xpath = alt_points_xpath.format(card_number)

    el = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )

    cls = el.get_attribute('class')
    log_to_file(f"Card {card_number} status class: {cls}")

    today = datetime.now().strftime('%B %d, %Y')

    if 'SkypeCircleCheck' in cls:
        return f"Collected - {today}"
    elif 'AddMedium' in cls:
        return cls
    return "Unknown"


def get_card_state(card_number, kind):
    status = card_status_check(card_number, kind)
    today = datetime.now().strftime('%B %d, %Y')

    if status == f"Collected - {today}":
        log_to_file(f"{kind} card {card_number} already collected.")
        return status

    xpath = card_base_xpath.format(card_number)
    if kind == "Activities":
        xpath = alt_base_xpath.format(card_number)

    collecting_points(xpath, card_number)
    sleep(2)
    return status

# ------------------------------------------------------------------
# Streak
# ------------------------------------------------------------------

def get_streak_count():
    try:
        streak_xpath = '//mee-rewards-streak'
        el = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, streak_xpath))
        )
        label = el.get_attribute('aria-label')
        m = re.search(r"(\d+), Current day streak", label)
        return int(m.group(1)) if m else 0
    except Exception as e:
        log_to_file(f"Streak error: {e}")
        return 0

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    global driver

    driver = setup_edge_driver()
    driver.get('https://rewards.microsoft.com/')
    wait_for_driver_ready(driver)
    sleep(2)
    driver.refresh()
    wait_for_driver_ready(driver)

    root = driver.current_window_handle

    today = datetime.now().strftime('%B %d, %Y')
    log_to_file("Starting rewards run.")

    initial = get_streak_count()

    for i in range(1, 4):
        get_card_state(i, "Daily Set")
        close_extra_tabs(driver, root)

    for i in range(2, 20):
        get_card_state(i, "Activities")
        close_extra_tabs(driver, root)

    final = get_streak_count()
    log_to_file(f"Streak: {initial} → {final}")

    driver.quit()
    log_to_file("WebDriver closed.")

# ------------------------------------------------------------------

if __name__ == '__main__':
    main()
