/**
 * US men's shoe sizing utilities.
 *
 * Formula (Brannock device): size = 3 × foot_length_in − 22
 * Inverse:                   foot_length_in = (size + 22) / 3
 *
 * getSizeRange accounts for ~0.5" measurement deviation from CV scan.
 */

const DEVIATION = 0.5; // inches

// All US men's half-sizes we support
const US_SIZES = [
  '6', '6.5', '7', '7.5', '8', '8.5', '9', '9.5',
  '10', '10.5', '11', '11.5', '12', '12.5', '13', '14', '15',
];

/** Ideal foot length (inches) for a given US men's size string. */
function sizeToLength(size) {
  return (parseFloat(size) + 22) / 3;
}

/**
 * Given a measured foot length in inches, returns all US men's sizes
 * whose ideal foot length falls within [lengthIn - 0.5, lengthIn + 0.5].
 *
 * @param {number} lengthIn  Foot length in inches from CV scan.
 * @returns {string[]}       Array of US size strings, e.g. ['8.5', '9', '9.5']
 */
export function getSizeRange(lengthIn) {
  const lo = lengthIn - DEVIATION;
  const hi = lengthIn + DEVIATION;
  return US_SIZES.filter((size) => {
    const ideal = sizeToLength(size);
    return ideal >= lo && ideal <= hi;
  });
}

/**
 * Returns the single closest US men's size for a foot length.
 *
 * @param {number} lengthIn
 * @returns {string}
 */
export function getBestSize(lengthIn) {
  let bestSize = US_SIZES[0];
  let bestDiff = Infinity;
  for (const size of US_SIZES) {
    const diff = Math.abs(sizeToLength(size) - lengthIn);
    if (diff < bestDiff) {
      bestDiff = diff;
      bestSize = size;
    }
  }
  return bestSize;
}
