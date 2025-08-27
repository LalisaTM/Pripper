# pripper/browser.py
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from .utils import print_info
from .config import SCROLL_PAUSE, MAX_SCROLLS

def get_driver(headless: bool = True, fast: bool = True):
    options = Options()
    if headless:
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        print_info("Running in headless mode (no browser window)")
    else:
        print_info("Running in visible mode (browser window will open)")

    if fast:
        try:
            options.page_load_strategy = 'eager'  # stop after DOMContentLoaded
        except Exception:
            pass
        for arg in [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-extensions',
            '--disable-notifications',
            '--disable-background-networking',
            '--disable-sync',
            '--window-size=1920,1080'
        ]:
            options.add_argument(arg)
    else:
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.implicitly_wait(2)
    return driver


def scroll_page(driver):
    last_height = driver.execute_script("return document.body.scrollHeight")
    images_found_count = []

    for i in range(MAX_SCROLLS):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE)
        time.sleep(0.4)

        from .utils import print_info as _pi  # avoid import loop
        current_images = len(driver.find_elements(By.CSS_SELECTOR, 'img[src*="pinimg.com"]'))
        images_found_count.append(current_images)

        new_height = driver.execute_script("return document.body.scrollHeight")
        _pi(f"Scrolling... ({i+1}/{MAX_SCROLLS}) - Height: {new_height}, Images: {current_images}")

        if new_height == last_height:
            if len(images_found_count) >= 3:
                a, b, c = images_found_count[-3:]
                if a == b == c:
                    _pi("No new images loading, reached end")
                    break

        last_height = new_height

        if i % 5 == 4:
            driver.execute_script("window.scrollBy(0, -200);")
            time.sleep(0.2)
            driver.execute_script("window.scrollBy(0, 400);")
            time.sleep(0.2)


def is_avatar_image(img, driver):
    """Return True if likely an avatar."""
    try:
        src = img.get_attribute('src') or ''
        alt_text = img.get_attribute('alt') or ''
        classes = img.get_attribute('class') or ''

        try:
            width = int(img.get_attribute('width') or '0')
            height = int(img.get_attribute('height') or '0')
            natural_width = driver.execute_script("return arguments[0].naturalWidth;", img)
            natural_height = driver.execute_script("return arguments[0].naturalHeight;", img)
            if ((width > 0 and height > 0 and max(width, height) < 80) or
                (natural_width > 0 and natural_height > 0 and max(natural_width, natural_height) < 80)):
                return True
        except Exception:
            pass

        avatar_indicators = ['avatar', 'profile', 'user-image', 'creator', 'author', 'uploader', 'poster']
        for indicator in avatar_indicators:
            if any(indicator in (x or '').lower() for x in (alt_text, classes, src)):
                return True

        try:
            for _ in range(3):
                parent = img.find_element(By.XPATH, './..')
                if not parent:
                    break
                parent_attrs = [
                    parent.get_attribute('class') or '',
                    parent.get_attribute('data-test-id') or '',
                    parent.get_attribute('id') or ''
                ]
                for attr_value in parent_attrs:
                    if any(p in attr_value.lower() for p in ['creator-avatar','user-avatar','profile','avatar']):
                        return True
                img = parent
        except Exception:
            pass
        return False
    except Exception:
        return False
