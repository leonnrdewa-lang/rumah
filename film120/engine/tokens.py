"""Design tokens: canvas, palette, type, safe zones. One source of truth for the whole film."""
import os

W, H, FPS = 1080, 1920, 30
TOTAL_S = 120.0
TOTAL_FRAMES = int(round(TOTAL_S * FPS))          # 3600

# palette (RGB)
CHARCOAL = (15, 16, 18)
CHAR2 = (26, 27, 30)         # raised surface
WHITE = (244, 239, 228)      # warm white
GREY = (138, 135, 128)
VOLT = (210, 255, 60)        # the single vivid accent: "locked / now / verified"
BLACK = (0, 0, 0)

# safe zones for Reels / TikTok chrome
MARGIN = 64
SAFE_TOP = 210
SAFE_BOTTOM = 1500
SUB_Y = 1290                 # subtitle baseline band 1250-1420
SPINE_Y = 200                # decorative hairline
YEARS_Y = 248                # year labels under the spine

FONT_DIRS = [d for d in os.environ.get('FONT_DIR', '').split(':') if d] + ['/home/user/fonts', '/tmp/fonts2/all']
FONT_FILES = dict(
    display='anton-latin-400-normal.woff',
    serif='instrument-serif-latin-400-normal.woff',
    serif_i='instrument-serif-latin-400-italic.woff',
    mono='jetbrains-mono-latin-700-normal.woff',
    monor='jetbrains-mono-latin-500-normal.woff',
    ui='inter-latin-700-normal.woff',
    ui_xb='inter-latin-800-normal.woff',
    cond='archivo-narrow-latin-700-normal.woff',
)
