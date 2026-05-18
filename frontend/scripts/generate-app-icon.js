/**
 * Builds a 1024×1024 app icon with the wordmark scaled to fit the Android
 * adaptive-icon safe zone (~66% center) so it isn't clipped by the launcher circle.
 */
const path = require('path');
const sharp = require('sharp');

const ROOT = path.join(__dirname, '..');
const INPUT = path.join(ROOT, 'assets', 'ShoeShopper Logo.png');
const OUTPUT = path.join(ROOT, 'assets', 'app-icon.png');

const CANVAS = 1024;
/** Logo max width as fraction of canvas — keeps full wordmark inside circular masks. */
const LOGO_SCALE = 0.58;
const BG = { r: 255, g: 248, b: 240, alpha: 1 }; // #FFF8F0

async function main() {
  const logoMaxWidth = Math.round(CANVAS * LOGO_SCALE);

  const resized = await sharp(INPUT)
    .resize({ width: logoMaxWidth, fit: 'inside' })
    .png()
    .toBuffer();

  await sharp({
    create: {
      width: CANVAS,
      height: CANVAS,
      channels: 4,
      background: BG,
    },
  })
    .composite([{ input: resized, gravity: 'center' }])
    .png()
    .toFile(OUTPUT);

  const meta = await sharp(OUTPUT).metadata();
  console.log(`Wrote ${OUTPUT} (${meta.width}×${meta.height}), logo max width ${logoMaxWidth}px`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
