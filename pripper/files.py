# pripper/files.py
import os
import re
from .config import ALL_EXTS, IMAGE_EXTS

def get_next_index(target_dir):
    max_idx = 0
    pattern = re.compile(r"image_(\d+)\.(?:jpg|png|jpeg|webp|gif|mp4|m4v|webm|mov)$", re.IGNORECASE)
    if os.path.exists(target_dir):
        for fname in os.listdir(target_dir):
            m = pattern.match(fname)
            if m:
                idx = int(m.group(1))
                if idx > max_idx:
                    max_idx = idx
    return max_idx + 1

def get_next_index_in(dir_path):
    """
    Return next index N for a filename like image_N.ext in `dir_path`
    (counts images, gifs, and videos).
    """
    max_idx = 0
    pattern = re.compile(r"image_(\d+)\.(?:jpg|jpeg|png|webp|gif|mp4|webm|mov|m4v)$", re.IGNORECASE)
    if os.path.isdir(dir_path):
        for fname in os.listdir(dir_path):
            m = pattern.match(fname)
            if m:
                idx = int(m.group(1))
                if idx > max_idx:
                    max_idx = idx
    return max_idx + 1

def move_with_increment(src_path, dest_dir):
    """
    Move `src_path` into `dest_dir`. If a same-name file exists, rename to the
    next image_{N}.ext in that folder. Returns final destination path.
    """
    os.makedirs(dest_dir, exist_ok=True)
    base = os.path.basename(src_path)
    dest_path = os.path.join(dest_dir, base)

    # Fast path: no collision
    if not os.path.exists(dest_path):
        os.rename(src_path, dest_path)
        return dest_path

    # Collision -> bump to next index
    _, ext = os.path.splitext(base)
    next_idx = get_next_index_in(dest_dir)
    new_name = f"image_{next_idx}{ext.lower()}"
    dest_path = os.path.join(dest_dir, new_name)
    os.rename(src_path, dest_path)
    return dest_path

def _move_to_dir(src_path, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    base = os.path.basename(src_path)
    name, ext = os.path.splitext(base)
    dest = os.path.join(dest_dir, base)
    i = 1
    while os.path.exists(dest):
        dest = os.path.join(dest_dir, f"{name}_{i}{ext}")
        i += 1
    os.rename(src_path, dest)
    return dest

def create_zip_file(target_dir):
    """Create ZIP file from downloaded images/videos (keeps structure)."""
    import zipfile
    zip_path = target_dir.rstrip('/\\') + '.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(target_dir):
            for fname in files:
                if fname.lower().endswith(ALL_EXTS):
                    full = os.path.join(root, fname)
                    arcname = os.path.relpath(full, start=os.path.dirname(target_dir))
                    zf.write(full, arcname)
    from .utils import print_success
    print_success(f"ZIP created: {zip_path}")
