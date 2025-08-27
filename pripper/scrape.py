# pripper/scrape.py
import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .config import (
    ADVANCED_DELAY,
    VIDEO_EXTS,
    MAX_SCROLLS,
    SCROLL_PAUSE,
)
from .browser import is_avatar_image, scroll_page
from .utils import print_info, print_success, print_warning, print_error
from .files import get_next_index
from .net import download_images_concurrent

def scroll_and_download_realtime(driver, target_dir):
    """Scroll page and download media per scroll in batches (concurrent)."""
    os.makedirs(target_dir, exist_ok=True)

    # dedupe by content hashes of existing files
    import hashlib
    existing_hashes = set()
    if os.path.exists(target_dir):
        for fname in os.listdir(target_dir):
            path = os.path.join(target_dir, fname)
            if os.path.isfile(path):
                try:
                    with open(path, 'rb') as f:
                        existing_hashes.add(hashlib.sha256(f.read()).hexdigest())
                except Exception:
                    pass

    next_idx = get_next_index(target_dir)
    downloaded_count = 0
    avatar_count = 0
    processed_urls = set()

    last_height = driver.execute_script("return document.body.scrollHeight")

    for i in range(MAX_SCROLLS):
        print_info(f"Scroll {i+1}/{MAX_SCROLLS} - Collecting media...")

        all_images = driver.find_elements(By.TAG_NAME, 'img')
        scroll_avatars = 0
        batch_urls = []

        for img in all_images:
            try:
                src = img.get_attribute('src') or ''
                if not src or 'pinimg.com' not in src or src in processed_urls:
                    continue
                processed_urls.add(src)

                if is_avatar_image(img, driver):
                    avatar_count += 1
                    scroll_avatars += 1
                    continue

                high = (src.replace('/236x/', '/736x/')
                        .replace('/474x/', '/736x/'))
                batch_urls.append(high)
            except Exception:
                continue

        # ALSO collect <video> sources
        try:
            videos = driver.find_elements(By.TAG_NAME, 'video')
            for v in videos:
                vsrc = (v.get_attribute('src') or '').strip()
                if not vsrc:
                    for s in v.find_elements(By.TAG_NAME, 'source'):
                        vsrc = (s.get_attribute('src') or '').strip()
                        if vsrc:
                            break
                if not vsrc:
                    continue
                if vsrc in processed_urls:
                    continue
                if ('pinimg.com' not in vsrc) and (not any(vsrc.lower().endswith(e) for e in VIDEO_EXTS)):
                    continue
                processed_urls.add(vsrc)
                batch_urls.append(vsrc)
        except Exception:
            pass

        # Download batch concurrently
        if batch_urls:
            got, skipped, next_idx = download_images_concurrent(batch_urls, target_dir, existing_hashes, next_idx)
            downloaded_count += got
            if got or scroll_avatars:
                print_info(f"  This scroll: {got} downloaded, {scroll_avatars} avatars skipped")

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE)

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            print_info("Reached end of page")
            break
        last_height = new_height

        if i % 3 == 2:
            driver.execute_script("window.scrollBy(0, -200);")
            time.sleep(0.2)
            driver.execute_script("window.scrollBy(0, 400);")
            time.sleep(0.2)

    print_success("Real-time download complete!")
    print_info(f"  Total files downloaded: {downloaded_count}")
    print_info(f"  Avatars filtered out: {avatar_count}")
    return downloaded_count


def extract_pin_links(driver):
    pin_links = set()
    selectors = [
        'a[href*="/pin/"]:not([href*="/search/pins/"])',
        '[data-test-id="pin"] a[href*="/pin/"]:not([href*="/search/"])',
        '.pinWrapper a[href*="/pin/"]:not([href*="/search/"])',
        '.Pin a[href*="/pin/"]:not([href*="/search/"])',
        '[data-test-id="pinrep"] a[href*="/pin/"]:not([href*="/search/"])',
        '.pinImageWrapper a[href*="/pin/"]:not([href*="/search/"])'
    ]
    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            print_info(f"Found {len(elements)} pin links with selector: {selector}")
            for el in elements:
                href = el.get_attribute('href')
                if href and '/pin/' in href:
                    if any(skip in href for skip in ['/search/', 'rs=srs', 'view_parameter_type']):
                        continue
                    try:
                        parent_html = el.get_attribute('outerHTML')
                        if 'discover-bubble' in parent_html:
                            continue
                    except Exception:
                        pass
                    clean = href.split('?')[0].split('#')[0]
                    pin_links.add(clean)
        except Exception as e:
            print_warning(f"Selector {selector} failed: {e}")
    return list(pin_links)


def extract_image_from_pin_page(driver, pin_url):
    try:
        driver.get(pin_url)
        wait = WebDriverWait(driver, 10)
        selectors = [
            'img[alt*="Pin"]',
            'img[elementtiming*="MainPinImage"]',
            '.hCL',
            'img[src*="pinimg.com"]',
            '.mainContainer img',
            '.pinImageWrapper img',
            'img[fetchpriority="high"]'
        ]
        for sel in selectors:
            try:
                img_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                src = img_el.get_attribute('src')
                if src and 'pinimg.com' in src:
                    return (src.replace('/236x/', '/originals/')
                            .replace('/474x/', '/originals/')
                            .replace('/736x/', '/originals/'))
            except Exception:
                continue
    except Exception as e:
        print_error(f"Error processing pin {pin_url}: {e}")
    return None


def extract_video_from_pin_page(driver):
    """Try to get a video URL (mp4/webm/mov) from the current pin page."""
    try:
        vids = driver.find_elements(By.TAG_NAME, 'video')
        for v in vids:
            cand = (v.get_attribute('src') or '').strip()
            if cand and any(cand.lower().endswith(e) for e in ('.mp4', '.webm', '.mov', '.m4v')):
                return cand
            for s in v.find_elements(By.TAG_NAME, 'source'):
                cand = (s.get_attribute('src') or '').strip()
                if cand and any(cand.lower().endswith(e) for e in ('.mp4', '.webm', '.mov', '.m4v')):
                    return cand
    except Exception:
        pass
    try:
        metas = driver.find_elements(By.CSS_SELECTOR, 'meta[property="og:video"],meta[itemprop="contentUrl"]')
        for m in metas:
            cand = (m.get_attribute('content') or '').strip()
            if cand and any(cand.lower().endswith(e) for e in ('.mp4', '.webm', '.mov', '.m4v')):
                return cand
    except Exception:
        pass
    try:
        links = driver.find_elements(By.CSS_SELECTOR, 'link[itemprop="contentUrl"]')
        for l in links:
            cand = (l.get_attribute('href') or '').strip()
            if cand and any(cand.lower().endswith(e) for e in ('.mp4', '.webm', '.mov', '.m4v')):
                return cand
    except Exception:
        pass
    return None


def extract_image_urls_basic(driver):
    urls = set()
    for img in driver.find_elements(By.CSS_SELECTOR, 'img[src*="pinimg.com"]'):
        try:
            src = img.get_attribute('src') or ''
            if not src:
                continue
            high = src.replace('/236x/', '/736x/').replace('/474x/', '/736x/')
            urls.add(high.split('?')[0])
        except Exception:
            continue
    return list(urls)


def extract_image_urls_advanced(driver, original_url):
    print_info("Advanced mode: Starting comprehensive extraction...")
    driver.get(original_url)
    time.sleep(2.5)
    scroll_page(driver)

    print_info("Phase 1: Extracting basic images...")
    basic_urls = extract_image_urls_basic(driver)
    print_success(f"Basic extraction: {len(basic_urls)} images found")

    print_info("Phase 2: Extracting pin links...")
    pin_links = extract_pin_links(driver)
    print_info(f"Found {len(pin_links)} individual pins")

    all_urls = set(basic_urls)

    if pin_links:
        print_info("Phase 3: Processing individual pins for high-quality media...")
        for i, pin_url in enumerate(pin_links):
            print_info(f"Processing pin {i+1}/{len(pin_links)}: {os.path.basename(pin_url)}")

            image_url = extract_image_from_pin_page(driver, pin_url)
            if image_url:
                all_urls.add(image_url)
                print_success(f"Found high-quality image: {os.path.basename(image_url)}")
            else:
                print_warning(f"No main image found for pin: {pin_url}")

            try:
                video_url = extract_video_from_pin_page(driver)
                if video_url:
                    all_urls.add(video_url)
                    print_success(f"Found video: {os.path.basename(video_url)}")
            except Exception:
                pass

            time.sleep(ADVANCED_DELAY)

    final_urls = {}
    for url in all_urls:
        filename = os.path.basename(url.split('?')[0])
        if filename not in final_urls or '/originals/' in url:
            final_urls[filename] = url

    result_urls = list(final_urls.values())
    print_success(f"Advanced extraction complete: {len(result_urls)} total unique media found")
    return result_urls
