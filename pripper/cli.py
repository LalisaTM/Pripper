# pripper/cli.py
import os
import time
from colorama import Fore
from .utils import print_info, print_success, print_warning, print_error
from .browser import get_driver
from .scrape import scroll_and_download_realtime, extract_image_urls_advanced
from .files import get_next_index, create_zip_file
from .net import download_images_concurrent

def main():
    print_info("Starting Enhanced Pinterest Ripper 🚀")
    print_info("=" * 50)

    print(Fore.CYAN + "Choose browser mode:")
    print(Fore.CYAN + "  y = Headless (no browser window, faster)")
    print(Fore.CYAN + "  n = Visible (show browser window, good for debugging)")
    headless_choice = input(Fore.YELLOW + "Run in headless mode? (y/n): ").strip().lower()
    headless_mode = headless_choice == 'y'

    print(Fore.CYAN + "Performance mode:")
    print(Fore.CYAN + "  y = Fast (less waiting, concurrent downloads)")
    print(Fore.CYAN + "  n = Normal")
    fast_choice = input(Fore.YELLOW + "Use fast mode? (y/n): ").strip().lower()
    fast_mode = fast_choice == 'y'

    if headless_mode:
        print_success("Selected: Headless mode (no browser window)")
    else:
        print_success("Selected: Visible mode (browser window will open)")

    target = input(Fore.YELLOW + "Target directory (one-time setup): ").strip()
    if not target:
        target = "pinterest_downloads"
        print_info(f"Using default directory: {target}")

    zip_choice = input(Fore.YELLOW + "Create ZIP file after downloads? (y/n): ").strip().lower() == 'y'

    while True:
        print(Fore.CYAN + "\n" + "="*50)
        url = input(Fore.YELLOW + "Enter Pinterest URL (or ENTER to quit): ").strip()
        if not url:
            print_info("Exiting Pinterest Ripper. Goodbye!")
            break

        advanced_mode = input(
            Fore.YELLOW + "Advanced Mode? (y/n) [Takes longer but better quality + more images]: "
        ).strip().lower() == 'y'

        print_info(f"Mode: {'Advanced (High Quality + Complete)' if advanced_mode else 'Basic (Fast)'}")
        print_info("Starting browser...")

        driver = get_driver(headless=headless_mode, fast=fast_mode)

        try:
            driver.get(url)
            if not headless_mode:
                print_success("Browser opened! You can see what's happening now...")
                print_warning("Watch the browser window to see the scraping process...")
            time.sleep(2.0 if fast_mode else 3.0)

            if advanced_mode:
                print_warning("Advanced Mode may take several minutes...")
                urls = extract_image_urls_advanced(driver, url)
                print_info(f"Media found: {len(urls)}")
                if urls:
                    import hashlib
                    existing_hashes = set()
                    for fname in os.listdir(target):
                        p = os.path.join(target, fname)
                        if os.path.isfile(p):
                            try:
                                with open(p, 'rb') as f:
                                    existing_hashes.add(hashlib.sha256(f.read()).hexdigest())
                            except Exception:
                                pass
                    next_idx = get_next_index(target)
                    count, skipped, _ = download_images_concurrent(urls, target, existing_hashes, next_idx)
                    print_success(f"Complete! {count} new files downloaded, {skipped} skipped.")
                    if zip_choice and count > 0:
                        create_zip_file(target)
                else:
                    print_warning("No media found!")
            else:
                print_info("Loading page and downloading media in real-time (concurrent batches)...")
                scroll_and_download_realtime(driver, target)

            # Post-download filter menu
            from .filters import filter_downloaded_images
            filter_downloaded_images(target)

        except Exception as e:
            print_error(f"Error processing page: {e}")
        finally:
            if not headless_mode:
                input(Fore.YELLOW + "\nPress ENTER to close browser and continue...")
            driver.quit()
