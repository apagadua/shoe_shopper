// Embed the promo's images into promo.html as base64 data URIs, so the file
// renders standalone (preview panels, file://, headless capture) with no
// dependency on relative paths. Idempotent: replaces the ASSETS block in place.
const fs = require('fs');
const path = require('path');

const FILES = {
  logo: 'assets/logo.webp',
  am1grey: 'assets/am1_grey.webp',     // Air Max 1 "Crepe - Soft Grey"
  am1black: 'assets/am1_black.webp',   // Air Max 1 "Black"
  am1escape: 'assets/am1_escape.webp', // Air Max 1 "Escape"
  nb550: 'assets/nb550.webp',
  samba: 'assets/samba.webp',
};

const entries = Object.entries(FILES).map(([key, rel]) => {
  const b64 = fs.readFileSync(path.join(__dirname, rel)).toString('base64');
  return `    ${key}:"data:image/webp;base64,${b64}"`;
});

const htmlPath = path.join(__dirname, process.argv[2] || 'promo.html');
const html = fs.readFileSync(htmlPath, 'utf8');
const block = `/*ASSETS_START*/\n  var ASSETS={\n${entries.join(',\n')}\n  };\n  /*ASSETS_END*/`;
if (!html.includes('/*ASSETS_START*/') || !html.includes('/*ASSETS_END*/')) {
  throw new Error('ASSETS markers not found in promo.html');
}
const out = html.replace(/\/\*ASSETS_START\*\/[\s\S]*?\/\*ASSETS_END\*\//, block);
if (out === html) {
  console.log('Assets already up to date in promo.html');
} else {
  fs.writeFileSync(htmlPath, out);
  console.log(`Inlined ${Object.keys(FILES).length} assets -> promo.html (${Math.round(out.length / 1024)} KB)`);
}
