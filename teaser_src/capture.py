"""Render the teaser animation (index.html) to video, or snapshot single frames.

  python capture.py video ../figs/teaser.mp4      # also writes ../figs/teaser_poster.png
  python capture.py snap OUT_DIR 10 25.5 40      # PNGs at those *video* seconds

Needs playwright + imageio-ffmpeg. They were installed into a scratch dir (PYLIB below);
if that's gone: pip install --target <dir> playwright imageio-ffmpeg numpy pillow, and set PYLIB.
"""
import glob, io, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PYLIB = os.environ.get('PYLIB', '/tmp/claude-26817/-data-vision-phillipi-self-improvement-self-org-learning-game-changer/'
                                 '47742deb-c099-45f5-918c-3d03bfcdb909/scratchpad/pylib')
sys.path.insert(0, PYLIB)
import imageio_ffmpeg
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

W, H, FPS = 1920, 1240, 30
exe = glob.glob('/data/vision/phillipi/self-improvement/.cache/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell')[0]
mode = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe, args=['--allow-file-access-from-files'])
    pg = b.new_page(viewport={'width': W, 'height': H})
    pg.on('console', lambda m: print('console:', m.text))
    pg.on('pageerror', lambda e: print('pageerror:', e))
    pg.goto('file://' + os.path.join(HERE, 'index.html'))
    pg.wait_for_timeout(800)
    if mode == 'snap':
        out = sys.argv[2]
        os.makedirs(out, exist_ok=True)
        for t in sys.argv[3:]:
            pg.evaluate(f'seek({t})')
            pg.screenshot(path=os.path.join(out, f'snap_{t}.png'))
    else:
        out = sys.argv[2]
        end = pg.evaluate('END')
        poster = round(pg.evaluate('POSTER') * FPS)
        gen = imageio_ffmpeg.write_frames(out, (W, H), fps=FPS, pix_fmt_out='yuv420p', codec='libx264', macro_block_size=8,
                                          output_params=['-crf', '20', '-movflags', '+faststart'])
        gen.send(None)
        for i in range(int(end * FPS) + 1):
            pg.evaluate(f'seek({i / FPS})')
            im = Image.open(io.BytesIO(pg.screenshot())).convert('RGB')
            if i == poster:
                im.save(out.replace('.mp4', '_poster.png'))
            gen.send(np.asarray(im).tobytes())
        gen.close()
    b.close()
