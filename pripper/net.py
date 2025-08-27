# pripper/net.py
import os
import hashlib
import requests
import concurrent.futures

from .utils import print_success
from .config import MIN_IMAGE_BYTES, ALL_EXTS, MAX_WORKERS

def _requests_session():
    s = requests.Session()
    s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    return s

def _fetch_bytes(url, session, timeout=12):
    try:
        r = session.get(url, timeout=timeout)
        if r.status_code != 200:
            return None, None
        data = r.content
        if not data or len(data) < MIN_IMAGE_BYTES:
            return None, None
        ctype = r.headers.get('content-type', '')
        return data, ctype
    except Exception:
        return None, None

def _ext_from_ctype_or_url(ctype, url):
    if ctype:
        ctype = ctype.lower()
        if 'image/jpeg' in ctype or 'jpeg' in ctype or 'jpg' in ctype: return '.jpg'
        if 'image/png'  in ctype or 'png'  in ctype:                    return '.png'
        if 'image/webp' in ctype or 'webp' in ctype:                    return '.webp'
        if 'image/gif'  in ctype or 'gif'  in ctype:                    return '.gif'
        if 'video/mp4'  in ctype or 'mp4'  in ctype:                    return '.mp4'
        if 'video/webm' in ctype or 'webm' in ctype:                    return '.webm'
        if 'video/quicktime' in ctype or 'mov' in ctype:                return '.mov'
    ext = os.path.splitext(url.split('?')[0].split('#')[0])[1].lower()
    if ext in ALL_EXTS:
        return ext
    return '.jpg'

def download_images_concurrent(urls, target_dir, existing_hashes, start_idx, max_workers=MAX_WORKERS):
    """Fetch multiple media concurrently, write sequential filenames in main thread."""
    if not urls:
        return 0, 0, start_idx

    session = _requests_session()
    count = 0
    skipped = 0
    results = []

    def worker(url):
        data, ctype = _fetch_bytes(url, session)
        if not data:
            return (url, None, None, None)
        h = hashlib.sha256(data).hexdigest()
        return (url, data, ctype, h)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for url, data, ctype, h in ex.map(worker, urls):
            if not data:
                skipped += 1
                continue
            if h in existing_hashes:
                skipped += 1
                continue
            results.append((url, data, ctype, h))

    next_idx = start_idx
    os.makedirs(target_dir, exist_ok=True)
    for url, data, ctype, h in results:
        ext = _ext_from_ctype_or_url(ctype, url)
        fname = f"image_{next_idx}{ext}"
        out_path = os.path.join(target_dir, fname)
        with open(out_path, 'wb') as f:
            f.write(data)
        existing_hashes.add(h)
        print_success(f"Downloaded: {fname} ({len(data)} bytes)")
        next_idx += 1
        count += 1

    return count, skipped, next_idx
