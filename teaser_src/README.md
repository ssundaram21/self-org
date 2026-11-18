# Teaser video source

`index.html` is a hand-timed animation (1920×1240). `capture.py` steps it frame by frame in headless
Chromium and encodes `../figs/teaser.mp4` (+ `teaser_poster.png`).

- **Text / narration:** edit `narration.js` (intro, narration bar, thought bubbles, goal).
- **Speed:** `SPEED` in `index.html` (per-segment slow-down).
- **File arrows:** `FILE_ARROWS` in `index.html`.
- `data.js` holds the game replays and timeline data.

Render: `python3 capture.py video ../figs/teaser.mp4`
Spot-check frames: `python3 capture.py snap OUT_DIR 10 40.5` (video seconds)
Preview in a browser on this machine: `index.html?play=1&debug=1`. The fonts load from local `file://` paths.
