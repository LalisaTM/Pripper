# pripper/filters.py
import os
from .utils import print_info, print_success, print_warning, print_error
from .config import IMAGE_EXTS, VIDEO_EXTS, GIF_EXTS, ALL_EXTS
from .files import move_with_increment

# --------- Text/QR detection helpers ---------
def _has_qr_cv2(filepath):
    """True if a QR is detected (OpenCV)."""
    try:
        import cv2
        img = cv2.imread(filepath)
        if img is None:
            return False
        det = cv2.QRCodeDetector()
        data, pts, _ = det.detectAndDecode(img)
        return pts is not None and pts.any()
    except Exception:
        return False

def _ocr_letters(filepath):
    """Return alnum char count via pytesseract, or None if unavailable."""
    try:
        from PIL import Image
        import pytesseract
        txt = pytesseract.image_to_string(Image.open(filepath))
        return sum(ch.isalnum() for ch in txt)
    except Exception:
        return None

def _textlike_score_cv2(filepath, resize_to=900):
    """
    Heuristic score (0..1) for 'text/screenshot-like' using OpenCV only:
    combines edge density + many small components + large white background.
    """
    try:
        import cv2, numpy as np
        img = cv2.imread(filepath)
        if img is None:
            return 0.0
        h, w = img.shape[:2]
        s = min(1.0, float(resize_to) / max(h, w)) if max(h, w) > resize_to else 1.0
        if s < 1.0:
            img = cv2.resize(img, (int(w*s), int(h*s)), interpolation=cv2.INTER_AREA)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(cv2.GaussianBlur(gray, (3,3), 0), 80, 160)
        edge_density = float((edges > 0).mean())

        thr = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY_INV, 25, 10)
        kernel = np.ones((3,3), np.uint8)
        opened = cv2.morphologyEx(thr, cv2.MORPH_OPEN, kernel, iterations=1)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(opened, 8)
        areas = stats[1:, cv2.CC_STAT_AREA].astype(np.float32) if n > 1 else np.array([])
        img_area = float(opened.shape[0] * opened.shape[1])
        small = ((areas > img_area*0.0002) & (areas < img_area*0.02)).sum()
        small_ratio = small / max(len(areas), 1)

        white_bg_ratio = float((gray >= 240).mean())
        score = 0.45*small_ratio + 0.35*edge_density + 0.20*white_bg_ratio
        return max(0.0, min(1.0, float(score)))
    except Exception:
        return 0.0

# --------- Color classification ----------
def _is_greyish(
        filepath,
        sat_low=0.22,           # pixel considered low-saturation if S<0.22
        sat_px_fraction=0.85,   # need ≥85% low-sat pixels
        sat_p90_max=0.35,       # 90th percentile of S must be ≤0.35
        colorfulness_thresh=18.0,   # Hasler–Süsstrunk: lower = greyer
        mean_chroma_thresh=8.0,     # LAB mean chroma
        resize_to=256
):
    """
    Return True if image is greyscale/greyish (low saturation & low colorfulness).
    Returns None if Pillow is missing; any file error => None (treated as COLOR by caller).
    """
    try:
        from PIL import Image, ImageFile
        ImageFile.LOAD_TRUNCATED_IMAGES = True
    except ImportError:
        return None

    try:
        import numpy as np
        NP = True
    except ImportError:
        NP = False

    try:
        with Image.open(filepath) as im:
            im.load()
            im = im.convert('RGB')
            if resize_to:
                im.thumbnail((resize_to, resize_to), Image.BILINEAR)

            hsv = im.convert('HSV')
            _, s, v = hsv.split()
            s_data = list(s.getdata())
            v_data = list(v.getdata())
            mid_mask = [20 <= vv <= 245 for vv in v_data]
            s_mid = [sv for sv, keep in zip(s_data, mid_mask) if keep] or s_data

            if NP:
                s_arr = __import__('numpy').array(s_mid, dtype='float32') / 255.0
                p90 = float(__import__('numpy').percentile(s_arr, 90))
                frac_low = float((s_arr < sat_low).mean())
            else:
                s_arr = [sv / 255.0 for sv in s_mid]
                s_sorted = sorted(s_arr)
                n = len(s_sorted)
                def percentile(p):
                    if n == 0: return 0.0
                    k = (p/100) * (n-1)
                    f = int(k)
                    c = min(f+1, n-1)
                    return s_sorted[f] + (k-f) * (s_sorted[c]-s_sorted[f]) if n > 1 else s_sorted[0]
                p90 = percentile(90)
                frac_low = (sum(1 for sv in s_arr if sv < sat_low) / n) if n else 1.0

            greyish_by_sat = (frac_low >= sat_px_fraction) and (p90 <= sat_p90_max)

            px = list(im.getdata())
            if NP:
                arr = __import__('numpy').array(px, dtype='float32')
                R, G, B = arr[:, 0], arr[:, 1], arr[:, 2]
                rg = R - G
                yb = 0.5 * (R + G) - B
                c_var  = float((__import__('numpy').var(rg) + __import__('numpy').var(yb)) ** 0.5)
                mrg, myb = float(rg.mean()), float(yb.mean())
                c_mean = float((mrg**2 + myb**2) ** 0.5)
                colorfulness = c_var + 0.3 * c_mean
            else:
                R = [p[0] for p in px]; G = [p[1] for p in px]; B = [p[2] for p in px]
                rg = [r-g for r,g in zip(R,G)]
                yb = [0.5*(r+g)-b for r,g,b in zip(R,G,B)]
                def mean(lst): return sum(lst)/len(lst) if lst else 0.0
                def var(lst):
                    m = mean(lst)
                    return (sum((x-m)*(x-m) for x in lst)/len(lst)) if lst else 0.0
                c_var = (var(rg) + var(yb)) ** 0.5
                mrg, myb = mean(rg), mean(yb)
                c_mean = (mrg*mrg + myb*myb) ** 0.5
                colorfulness = c_var + 0.3 * c_mean

            lab = im.convert('LAB')
            _, A, Bc = lab.split()
            a_data = list(A.getdata()); b_data = list(Bc.getdata())
            if NP:
                np = __import__('numpy')
                a_arr = np.array(a_data, dtype=np.float32) - 128.0
                b_arr = np.array(b_data, dtype=np.float32) - 128.0
                chroma_mean = float(np.sqrt(a_arr*a_arr + b_arr*b_arr).mean())
            else:
                chroma_mean = (
                    sum(((ad-128.0)**2 + (bd-128.0)**2) ** 0.5 for ad, bd in zip(a_data, b_data)) / len(a_data)
                    if a_data else 0.0
                )

            greyish_by_colorfulness = (colorfulness <= colorfulness_thresh) and (chroma_mean <= mean_chroma_thresh)
            return bool(greyish_by_sat or greyish_by_colorfulness)

    except Exception:
        return None

# --------- Filter actions (delete/move/sort) ----------
def filter_small_images(target_dir, image_files, min_pixels=300, fallback_bytes=25_000):
    """Delete small images."""
    print_info("Deleting small images...")
    try:
        from PIL import Image
        PIL_AVAILABLE = True
    except ImportError:
        PIL_AVAILABLE = False
        print_warning("Pillow not installed; falling back to file-size threshold. (pip install pillow)")
    deleted = 0

    if not PIL_AVAILABLE:
        for filename in image_files:
            p = os.path.join(target_dir, filename)
            try:
                if os.path.getsize(p) < fallback_bytes:
                    os.remove(p); deleted += 1
                    print_info(f"Deleted small file: {filename}")
            except Exception as e:
                print_warning(f"Could not check {filename}: {e}")
        print_success(f"Deleted {deleted} small images.")
        return

    from PIL import Image
    for filename in image_files:
        p = os.path.join(target_dir, filename)
        try:
            with Image.open(p) as img:
                w, h = img.size
            if w < min_pixels or h < min_pixels:
                os.remove(p); deleted += 1
                print_info(f"Deleted small image: {filename} ({w}x{h})")
        except Exception as e:
            print_warning(f"Could not check {filename}: {e}")
    print_success(f"Deleted {deleted} small images.")

def filter_duplicates(target_dir, files_all_media):
    """Delete exact duplicates (byte-identical) across images/gifs/videos)."""
    print_info("Deleting exact duplicates...")
    import hashlib
    seen = {}
    deleted = 0
    for filename in files_all_media:
        p = os.path.join(target_dir, filename)
        try:
            with open(p, 'rb') as f:
                h = hashlib.sha256(f.read()).hexdigest()
            if h in seen:
                os.remove(p); deleted += 1
                print_info(f"Deleted duplicate: {filename} (duplicate of {seen[h]})")
            else:
                seen[h] = filename
        except Exception as e:
            print_warning(f"Could not hash {filename}: {e}")
    print_success(f"Deleted {deleted} duplicates.")

def filter_textlike_images(target_dir, image_files, score_threshold=0.42, ocr_letters_min=16):
    """Delete images that look like text/QR/screenshots."""
    print_info("Deleting text/QR/screenshot-like images...")
    deleted_qr = 0
    deleted_txt = 0
    for filename in image_files:
        path = os.path.join(target_dir, filename)
        if not os.path.isfile(path):
            continue

        if _has_qr_cv2(path):
            try:
                os.remove(path); deleted_qr += 1
                print_info(f"Deleted QR: {filename}")
            except Exception as e:
                print_warning(f"Could not delete {filename}: {e}")
            continue

        score = _textlike_score_cv2(path)
        letters = _ocr_letters(path)  # may be None
        is_textlike = (score >= score_threshold) or (letters is not None and letters >= ocr_letters_min)
        if is_textlike:
            try:
                os.remove(path); deleted_txt += 1
                why = f"score={score:.2f}" + (f", ocr={letters}" if letters is not None else "")
                print_info(f"Deleted text-like: {filename} ({why})")
            except Exception as e:
                print_warning(f"Could not delete {filename}: {e}")
    print_success(f"Text/QR deletion done. Deleted {deleted_txt} text-like and {deleted_qr} QR images.")

def filter_by_color(target_dir, image_files):
    """
    Sort by color:
      - (b) both -> move color to 'color_images/' and greyish to 'greyscale_images/' (default)
      - (c) keep color in main, move greys to 'greyscale_images/'
      - (g) keep greys in main, move color to 'color_images/'
    Unknown/unanalyzable files are treated as COLOR to be safe.
    """
    from colorama import Fore
    print_info("Filter by color")
    mode = input(
        Fore.YELLOW + "Choose: (b) sort both [default], (c) keep color in main, (g) keep greyish in main: "
    ).strip().lower() or 'b'

    color_dir = os.path.join(target_dir, "color_images")
    grey_dir  = os.path.join(target_dir, "greyscale_images")
    os.makedirs(color_dir, exist_ok=True)
    os.makedirs(grey_dir,  exist_ok=True)

    try:
        import PIL  # noqa: F401
        PIL_AVAILABLE = True
    except ImportError:
        PIL_AVAILABLE = False
        print_warning("Pillow not installed; using fallback heuristic. Install with: python -m pip install pillow")

    moved = 0
    for filename in image_files:
        src_path = os.path.join(target_dir, filename)
        if not os.path.isfile(src_path):
            continue

        if PIL_AVAILABLE:
            greyish = _is_greyish(src_path)
            if greyish is None:
                greyish = False  # treat unanalyzable as COLOR to be safe
        else:
            greyish = False

        dest_dir = None
        if mode == 'b':
            dest_dir = grey_dir if greyish else color_dir
        elif mode == 'c' and greyish:
            dest_dir = grey_dir
        elif mode == 'g' and not greyish:
            dest_dir = color_dir
        elif mode not in ('b', 'c', 'g'):
            dest_dir = grey_dir if greyish else color_dir

        if dest_dir:
            try:
                final_dest = move_with_increment(src_path, dest_dir)
                moved += 1
                print_info(f"Moved {filename} -> {final_dest}")
            except Exception as e:
                print_warning(f"Could not move {filename}: {e}")

    print_success(f"Color filtering complete. Moved {moved} images.")

def move_media_types(target_dir):
    """Move MP4/WebM/MOV/M4V into videos/, GIF into gifs/.
    Folders are only created if at least one file is moved."""
    videos_dir = None
    gifs_dir = None
    moved_vid = 0
    moved_gif = 0

    for fname in list(os.listdir(target_dir)):
        p = os.path.join(target_dir, fname)
        if not os.path.isfile(p):
            continue
        low = fname.lower()

        if low.endswith(VIDEO_EXTS):
            if videos_dir is None:
                videos_dir = os.path.join(target_dir, "videos")
            try:
                move_with_increment(p, videos_dir)
                moved_vid += 1
            except Exception as e:
                print_warning(f"Could not move video {fname}: {e}")

        elif low.endswith(GIF_EXTS):
            if gifs_dir is None:
                gifs_dir = os.path.join(target_dir, "gifs")
            try:
                move_with_increment(p, gifs_dir)
                moved_gif += 1
            except Exception as e:
                print_warning(f"Could not move GIF {fname}: {e}")

    print_success(f"Media move complete (videos: {moved_vid}, gifs: {moved_gif}).")

def finalize_color_only(target_dir):
    """
    Keep only:
      - color_images/
      - greyscale_images/
      - videos/ (only if contains files)
      - gifs/   (only if contains files)
    Remove temp folders. Leftover images in root are MOVED to color_images.
    """
    import shutil

    for d in ("small_images", "duplicates", "qr_codes", "rejected_text_ui",
              "size_small", "size_medium", "size_large"):
        dp = os.path.join(target_dir, d)
        if os.path.isdir(dp):
            try:
                shutil.rmtree(dp)
                print_info(f"Removed folder: {dp}")
            except Exception as e:
                print_warning(f"Could not remove {dp}: {e}")

    color_dir = os.path.join(target_dir, "color_images")
    grey_dir  = os.path.join(target_dir, "greyscale_images")
    os.makedirs(color_dir, exist_ok=True)
    os.makedirs(grey_dir,  exist_ok=True)

    # Move leftover images in root -> color_images (renumbering if needed)
    for fname in list(os.listdir(target_dir)):
        p = os.path.join(target_dir, fname)
        if not os.path.isfile(p):
            continue
        low = fname.lower()
        if low.endswith(IMAGE_EXTS):
            try:
                move_with_increment(p, color_dir)
            except Exception as e:
                print_warning(f"Could not move leftover {fname}: {e}")

    # If videos/gifs folders exist but are empty, remove them
    for d in ("videos", "gifs"):
        dp = os.path.join(target_dir, d)
        if os.path.isdir(dp):
            try:
                has_files = any(os.path.isfile(os.path.join(dp, f)) for f in os.listdir(dp))
                if not has_files:
                    shutil.rmtree(dp)
                    print_info(f"Removed empty folder: {dp}")
            except Exception as e:
                print_warning(f"Could not inspect/remove {dp}: {e}")

def filter_downloaded_images(target_dir):
    """Run one or many filters. Accepts comma/space separated choices."""
    if not os.path.exists(target_dir):
        print_warning("No images to filter!")
        return

    def list_images():
        return [f for f in os.listdir(target_dir) if f.lower().endswith(('.jpg','.jpeg','.png','.webp','.gif'))]

    def list_all_media():
        return [f for f in os.listdir(target_dir) if f.lower().endswith(ALL_EXTS)]

    image_files = list_images()
    if not image_files:
        print_warning("No image files found to filter!")
        return

    from colorama import Fore
    print_info(f"Found {len(image_files)} downloaded images")
    print_info("Image filtering options (multi-select allowed, e.g. 1,3,4):")
    print(Fore.CYAN + "1. Delete small images (likely thumbnails/icons)")
    print(Fore.CYAN + "2. Delete exact duplicates (images/gifs/videos)")
    print(Fore.CYAN + "3. Filter by color (sort -> color_images / greyscale_images)")
    print(Fore.CYAN + "4. Delete text/QR/screenshot-like images (images only)")
    print(Fore.CYAN + "6. Move MP4/WebM to videos/ and GIF to gifs/")
    print(Fore.CYAN + "5. EVERYTHING: 1 -> 2 -> 4 -> 3 -> 6 -> cleanup")

    raw = input(Fore.YELLOW + "Choose (e.g. 1 3 4 | 1,3,4 | 5): ").strip().lower()
    if not raw:
        print_info("Skipping image filtering")
        return

    if raw in ("5", "all"):
        seq = ["1", "2", "4", "3", "6"]
    else:
        import re
        tokens = [t for t in re.split(r"[,\s]+", raw) if t]
        seen = set()
        seq = [t for t in tokens if t in {"1","2","3","4","6"} and not (t in seen or seen.add(t))]

    apply_selected_filters(seq, target_dir)

def apply_selected_filters(seq, target_dir):
    """Apply a sequence like ['1','3','4'] with state refreshed between steps."""
    def list_images():
        return [f for f in os.listdir(target_dir) if f.lower().endswith(('.jpg','.jpeg','.png','.webp','.gif'))]
    def list_all_media():
        return [f for f in os.listdir(target_dir) if f.lower().endswith(ALL_EXTS)]

    actions = {
        "1": lambda: filter_small_images(target_dir, list_images()),
        "2": lambda: filter_duplicates(target_dir, list_all_media()),
        "3": lambda: filter_by_color(target_dir, list_images()),
        "4": lambda: filter_textlike_images(target_dir, list_images()),
        "6": lambda: move_media_types(target_dir),
    }

    ran_any = False
    for code in seq:
        if code not in actions:
            print_warning(f"Unknown option '{code}' — skipping")
            continue
        print_info(f"Running filter {code} ...")
        try:
            actions[code]()
            ran_any = True
        except Exception as e:
            print_error(f"Filter {code} failed: {e}")

    if ran_any:
        finalize_color_only(target_dir)
        print_success("Filters complete and cleaned up.")
    else:
        print_info("No valid filters selected.")
