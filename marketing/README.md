# Shoe Shopper — Promotional Videos

Two cuts built from the app's real logo, palette, and the core flow:
**AR scan → AI measurement → fit-ranked recommendations** (with the
paper-photo method mentioned as the no-AR fallback). The scanned foot is
drawn wearing a sock, and the scan copy tells users to wear the socks they
plan to wear with the shoes (thick for boots, thin for runners) — keep both;
sock thickness genuinely affects fit and it avoids bare-foot imagery. The recommendations
scene plays out like a real session: a finger swipes the featured shoe's
colorway carousel (swatch pills + colorway name follow, matching the real
RecommendationsScreen), then taps the heart to save it — filling the heart
and popping a "Saved to wishlist" toast over a bottom tab bar.

**Consumer cut** (`promo.html` → `ShoeShopper_Promo.mp4`, ~29s): product only.

**Investor/cofounder cut** (`promo_pitch.html` → `ShoeShopper_Pitch.mp4`, ~62s):
wraps the product scenes with pitch beats sourced from the CSE 115C deck —
the 18% return-rate stat (Capital One Shopping Research, 2025), why current
fixes fail, an affiliate buy-through scene (on screen the retailer is a generic
"partner retailer" since GOAT is just the first integration; its product URLs
in `active_listings.json` are already affiliate links), a business-model scene
(affiliate commerce / brand partnerships / anonymized retail fit insights,
each with an honest status tag), the fit-data flywheel, the status-tagged
roadmap (virtual try-on in development / partnerships / launch), and a team
close (Alyssa Pagaduan · Or Zait-Givon · Tyler Weng). All claims were
fact-checked against the codebase and cited sources on 2026-07-09 — keep it
that way when editing (e.g. tolerance learning is global, not per-brand).

## Files
| File | Purpose |
|---|---|
| `ShoeShopper_Promo.mp4` | Consumer video — 1920×1080, 30fps, 29s. |
| `ShoeShopper_Pitch.mp4` | Investor video — 1920×1080, 30fps, 57s. |
| `promo.html` / `promo_pitch.html` | Source animations. Open in a browser to preview (auto-loops). Fully standalone — images are embedded as data URIs, and the 1280×720 stage scales to fit any viewport. |
| `inline-assets.js` | Embeds `assets/*.webp` into an HTML file (`node inline-assets.js [file]`). |
| `render.js` | Headless-Chrome frame capture (`node render.js [file]` → `frames/`). |
| `build.ps1` | One command: inline assets + capture frames + encode MP4 + clean up. |

## Rebuild after editing a source HTML file
```powershell
powershell -ExecutionPolicy Bypass -File build.ps1                                   # consumer cut
powershell -ExecutionPolicy Bypass -File build.ps1 promo_pitch.html ShoeShopper_Pitch.mp4   # pitch cut
```
Requirements (already installed): Chrome, `ffmpeg` (winget `Gyan.FFmpeg`),
and `puppeteer-core` (`npm install` in this folder).

## Notes
- The animation timeline is deterministic and seekable (`window.__seek(ms)`),
  so every frame is captured exactly — no dropped frames or jitter.
- To change resolution/fps, edit the `W`, `H`, `SCALE`, `FPS` constants in
  `render.js` (layout is 1280×720; `SCALE=1.5` renders at 1920×1080).
- Recommendation cards use **real product photos** in `assets/` (Nike Air Max 1,
  New Balance 550, Adidas Samba), pulled from `active_listings.json` (GOAT CDN).
  The colorway carousel swipes between three real Air Max 1 colorways from the
  same data: Crepe - Soft Grey, Black, and Escape (`am1_*.webp`).
  To swap products: put a WebP in `assets/`, add it to `FILES` in
  `inline-assets.js`, update the `.card` markup (`data-asset="<key>"`), rebuild.
- The logo is a downscaled WebP copy of `frontend/assets/ShoeShopper Logo.png`
  (`assets/logo.webp`); regenerate with ffmpeg if the brand asset changes.
