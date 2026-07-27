const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const FPS = 30;
const W = 1280, H = 720;   // CSS layout size; SCALE=1.5 → 1920x1080 output
const SCALE = 1.5;
const HTML = process.argv[2] || 'promo.html';   // e.g. `node render.js promo_pitch.html`
const OUT = path.join(__dirname, 'frames');
const PAGE = 'file://' + path.join(__dirname, HTML).replace(/\\/g, '/') + '?capture=1';

(async () => {
  if (fs.existsSync(OUT)) fs.rmSync(OUT, { recursive: true, force: true });
  fs.mkdirSync(OUT);

  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--force-color-profile=srgb', '--hide-scrollbars', '--disable-gpu']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: W, height: H, deviceScaleFactor: SCALE });
  await page.goto(PAGE, { waitUntil: 'networkidle0' });
  await page.evaluate(async () => { await document.fonts.ready; });
  await new Promise(r => setTimeout(r, 400));

  const total = await page.evaluate(() => window.__TOTAL);
  const nFrames = Math.ceil((total / 1000) * FPS);
  console.log(`Total ${total}ms -> ${nFrames} frames @ ${FPS}fps`);

  for (let i = 0; i < nFrames; i++) {
    const t = (i / FPS) * 1000;
    await page.evaluate((tt) => window.__seek(tt), t);
    const name = path.join(OUT, 'f' + String(i).padStart(5, '0') + '.png');
    await page.screenshot({ path: name, clip: { x: 0, y: 0, width: W, height: H } });
    if (i % 30 === 0) process.stdout.write(`\r  frame ${i}/${nFrames}`);
  }
  console.log(`\r  frame ${nFrames}/${nFrames}  done`);
  await browser.close();
})();
