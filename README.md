# Pripper — A Pinterest Ripper 🪄📌
> ⚠️ **Note:** This project (including this README) was put together quickly with the help of AI.  
> It’s not perfect by any means — expect rough edges, and feel free to improve it!

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB.svg?logo=python&logoColor=white)](#)
[![Selenium](https://img.shields.io/badge/Selenium-Automation-43B02A.svg?logo=selenium&logoColor=white)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](#license)
![Platforms](https://img.shields.io/badge/Windows%20|%20macOS%20|%20Linux-0A66C2)

**Pripper** is a fast Pinterest media ripper that grabs images and videos, skips avatars, de-duplicates, and **cleans your haul** with smart filters (delete tiny images, remove screenshots/text/QR, and **auto-sort by color vs. greyscale**). It runs headless or with a visible browser and names files **incrementally** across runs (`image_1.jpg`, `image_2.jpg`, …), never overwriting your existing files.

> ⚠️ Use responsibly. Respect site Terms of Service and creator copyrights. This tool is provided for personal/archival/educational use only.

---

## ✨ Features

- **Basic vs Advanced modes**
    - *Basic:* blazing fast; downloads as you scroll.
    - *Advanced:* opens each pin to fetch highest-quality media (incl. videos).
- **Headless or visible** Chrome.
- **Concurrent downloads** with robust content-type/extension detection.
- **Avatar skipping** & **exact duplicate** detection (SHA-256).
- **Smart cleanup**
    - Delete tiny thumbnails.
    - Remove screenshots / text / QR (OpenCV + optional Tesseract).
    - **Color sorting:** color vs greyscale into folders.
    - Move videos to `videos/` and GIFs to `gifs/` (folders only created if needed).
- **Incremental filenames** across runs (no clobbering).

---

## 📦 Installation

> Single `requirements.txt`.

```bash
git clone https://github.com/LalisaTM/Pripper.git
cd pripper

# (Recommended) create a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install all dependencies
pip install -r requirements.txt
```

### Optional: Tesseract OCR (for stronger text/screenshot detection)

- **Windows:** Install Tesseract from https://github.com/UB-Mannheim/tesseract/wiki, then ensure the installer adds it to PATH (or restart your terminal).
- **macOS:** `brew install tesseract`
- **Linux (Debian/Ubuntu):** `sudo apt-get install tesseract-ocr`

Pripper works without Tesseract; you just get slightly weaker text-detection.

---

## 🚀 Usage

From the repo root:

```bash
# Preferred (module entry point)
python -m pripper

# If your shell needs it, you can also run the main file directly:
python -m pripper.main
```

You’ll be prompted for:
- **Headless mode** (faster) or visible browser (good for debugging).
- **Fast/Normal mode** (page load strategy & concurrency).
- **Target directory** (where downloads go).
- **ZIP after downloads** (optional).
- A **Pinterest URL** to rip.
- **Advanced mode** (deeper, higher quality) or **Basic** (faster).

After downloading, you’ll see a **filter menu** (multi-select):
1. Delete small images (likely thumbnails/icons)
2. Delete exact duplicates (images/gifs/videos)
3. Filter by color (sort → `color_images/` & `greyscale_images/`)
4. Delete text/QR/screenshot-like images (images only)
6. Move MP4/WebM/MOV/M4V to `videos/` and GIF to `gifs/`
5. **EVERYTHING:** 1 → 2 → 4 → 3 → 6 → cleanup

> Folders for `videos/` and `gifs/` are only created if something is actually moved there; empty ones are removed at the end.

---

## 📁 Output layout

```
<your-target-folder>/
├─ color_images/
├─ greyscale_images/
├─ videos/            # only if any were moved
├─ gifs/              # only if any were moved
└─ image_123.jpg      # (leftover images are auto-moved/renumbered)
```

- Files are named `image_<N>.<ext>` and continue counting across runs.
- During color sorting, collisions are resolved by auto-incrementing the filename **in the destination folder** (no overwrites).

---

## 🧠 Advanced mode (what it does)

- Loads your URL and **scrolls** to collect visible media.
- Additionally **extracts per-pin pages** and tries to fetch the **highest quality** image (e.g. `/originals/`) and any **video** sources found.
- De-duplicates media by filename preference and content hash.

Advanced mode is slower but yields more + higher-quality files.

---

## ⚙️ Configuration (quick knobs)

Edit `pripper/config.py`:

```python
SCROLL_PAUSE = 0.8      # time between scrolls (Basic mode)
MAX_SCROLLS = 50        # how deep to scroll
ADVANCED_DELAY = 1.2    # delay between per-pin fetches (Advanced)
MAX_WORKERS = 6         # concurrent downloader threads
MIN_IMAGE_BYTES = 1000  # minimum payload size to accept
```

---

## ❓ FAQ / Troubleshooting

**ChromeDriver version mismatch?**  
We use `webdriver-manager`, which auto-installs a compatible driver. If Chrome just updated, re-run Pripper and it will fetch a matching driver. If problems persist, try:
```bash
pip install -U webdriver-manager selenium
```

**Tesseract not found / OCR errors?**  
Install Tesseract (see above). On Windows, ensure its install folder is on your PATH and restart your terminal.

**Color sorting feels off?**  
Color detection uses multiple signals (HSV saturation, LAB chroma, Hasler-Süsstrunk colorfulness). You can loosen/tighten thresholds in `_is_greyish()` in `filters.py` (documented in code).

**Does it overwrite files?**  
No. Downloads, moves, and sorts use **incremental renaming** to avoid collisions.

---

## 🛡️ Legal

This project is for personal/educational use. You’re responsible for how you use it. Always respect Pinterest’s Terms of Service and copyright laws in your jurisdiction.

---

## 🤝 Contributing

PRs welcome! Bug fixes, selectors, new filters, performance tweaks—bring ’em on. Please:
1. Open an issue describing the change.
2. Keep PRs focused and well-commented.
3. Run `ruff`/`black` (if you use them) for style, and test on at least one Pinterest URL.

---

## 📜 License

MIT — see [LICENSE](LICENSE) for details.

---

## 💙 Support

If this saved you time, a ⭐ on the repo helps others find it. Happy ripping!
