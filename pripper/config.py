# pripper/config.py

# Timing & performance
SCROLL_PAUSE   = 0.8        # slightly faster default
MAX_SCROLLS    = 50
ADVANCED_DELAY = 1.2        # wait between pin opens in Advanced
MAX_WORKERS    = 6          # parallel download workers (tune 4-8)
MIN_IMAGE_BYTES = 1000

# File type groups
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp')
GIF_EXTS   = ('.gif',)
VIDEO_EXTS = ('.mp4', '.m4v', '.webm', '.mov')
ALL_EXTS   = IMAGE_EXTS + GIF_EXTS + VIDEO_EXTS
