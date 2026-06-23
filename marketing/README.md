# Shoe Shopper — Promotional Video

A 26-second branded promo built from the app's real logo, palette, and the
core flow: **photo scan → AI measurement → fit-ranked recommendations**.

## Files
| File | Purpose |
|---|---|
| `ShoeShopper_Promo.mp4` | The final video — 1280×720, 30fps, 26s. Share this. |
| `promo.html` | The source animation. Open in a browser to preview (auto-loops). Uses the real `frontend/assets/ShoeShopper Logo.png`. |
| `render.js` | Headless-Chrome frame capture (`promo.html?capture=1` → `frames/`). |
| `build.ps1` | One command: capture frames + encode MP4 + clean up. |

## Rebuild after editing promo.html
```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```
Requirements (already installed): Chrome, `ffmpeg` (winget `Gyan.FFmpeg`),
and `puppeteer-core` (`npm install` in this folder).

## Notes
- The animation timeline is deterministic and seekable (`window.__seek(ms)`),
  so every frame is captured exactly — no dropped frames or jitter.
- To change resolution/fps, edit the `W`, `H`, `FPS` constants in `render.js`.
- Recommendation cards use **real product photos** in `assets/` (Nike Air Max 1,
  New Balance 550, Adidas Samba), pulled from `active_listings.json` (GOAT CDN).
  To swap products: download new images into `assets/`, update the `.card`
  markup in `promo.html`, and rebuild.
