# /sync-shoes

Browser-based shoe data sync. For every shoe in the work queue, finds it on
GOAT (or falls back to Google → reputable retailer), enumerates all available
colorways, captures per-colorway price + availability for each measured size,
and writes the results to a payload file for `apply_shoe_sync` to commit.

---

## Setup

Before running this command:
1. Run: `python manage.py export_shoes_for_sync --output queue.json`
2. Confirm `queue.json` exists and has records.
3. Initialize an empty results array: create `payload.json` containing `[]`

---

## For each shoe in queue.json

Work through the list sequentially. For each shoe, follow these steps in order.

### Step A — Decide where to start

If `shoe.existing_goat_url` is set:
- Go directly to that URL (skip the search step — faster and avoids mismatches)
- Note: this lands on one colorway's page; you will enumerate all colorways from there

If `shoe.existing_goat_url` is null:
- Go to `https://www.goat.com/search?query={brand}+{model}` (URL-encode the query)

---

### Step B — GOAT search (only when no existing URL)

1. Navigate to the search URL
2. Call `read_network_requests` — GOAT is a React SPA and fires internal API
   calls when the page loads. Look for XHR/fetch requests containing product
   data (URLs like `/api/v1/product_templates` or similar). The JSON response
   contains: id, slug, name, brand, colorway, image_url.
3. Scan the results for a match:
   - Brand matches (case-insensitive, partial OK: "Nike" in "Nike Sportswear")
   - Model name appears in the result name, or vice versa
   - If multiple candidates: take the top result (GOAT's own ranking)
   - If ambiguous: take a screenshot to visually confirm before proceeding
4. If a confident match is found → note the product slug and navigate to the
   product page: `https://www.goat.com/sneakers/{slug}`
5. If no confident match after the first results page → try page 2 by appending
   `&p=2` to the search URL and repeating step 2
6. If still no match after two pages → fall through to **Step D (Google fallback)**

---

### Step C — GOAT product page: enumerate all colorways

You are now on a GOAT product page (either from existing_goat_url or from search).

**Intercept the network to get structured data:**

1. Call `read_network_requests` — look for API calls that return colorway/variant
   data. GOAT typically fires calls like:
   - `/api/v1/product_templates?product_template_id=...` — colorway list
   - `/api/v1/selling_variants?...` — per-size pricing and availability
   These responses contain structured JSON with all the data you need.

2. From the colorway list response, collect for each colorway:
   - `goat_id` (the product's unique ID from GOAT's API)
   - `name` (colorway name / nickname)
   - `image_url`
   - `product_url` (construct as `https://www.goat.com/sneakers/{slug}`)

3. From the variants/selling response, for each colorway and each of the shoe's
   `measured_sizes`, collect:
   - `price_usd` (lowest ask / buy now price for that size)
   - `is_available` (true if there is inventory at that size)

4. **Only keep colorways that have at least one of our measured sizes available.**
   Colorways with zero available inventory in any of our sizes are excluded from
   the payload entirely.

**If the network calls don't expose what you need:**

Fall back to DOM extraction:
- Find the color swatch selector on the page (usually a row of thumbnail images
  or color circles near the product title)
- Count how many swatches there are
- For each swatch:
  a. Click the swatch
  b. Wait for the page to update
  c. Note the updated URL (each GOAT colorway has its own slug URL)
  d. Call `get_page_text` or `javascript_tool` to extract:
     - Page title / colorway name
     - Main product image URL
     - For each measured size: find the size selector, check if that size shows
       a price (available) or is greyed out / missing (unavailable)
  e. Take a screenshot to visually confirm the colorway and price before recording

Build the colorway array and append the full shoe record to payload.json with
`"status": "found_goat"`.

---

### Step D — Google fallback (GOAT search returned nothing)

1. Navigate to `https://www.google.com`
2. Search for: `"{brand}" "{model}" buy`
3. Call `get_page_text` or `read_page` to read the search result URLs and titles
4. Collect the first 8–10 result URLs and classify each domain:

**Reputable retailers (proceed to Step E):**
- Brand sites: nike.com, adidas.com, newbalance.com, asics.com, brooks.com,
  saucony.com, hoka.com, on.com, salomon.com, vans.com, converse.com,
  reebok.com, puma.com, underarmour.com, skechers.com
- Chain retailers: footlocker.com, finishline.com, zappos.com, nordstrom.com,
  dsw.com, dickssportinggoods.com, eastbay.com, jdsports.com, academy.com,
  famousfootwear.com

**Discontinued signals (mark inactive):**
- ebay.com, poshmark.com, grailed.com, depop.com, mercari.com, thredup.com,
  stockx.com (resale-only aftermarket — treat same as eBay for our purposes)

**Decision:**
- If ANY result is from the reputable list → take the first reputable URL → **Step E**
- If results exist but ALL are from the discontinued list → **Step F (discontinued)**
- If no shopping results at all (only reviews/articles) → **Step F (discontinued)**

---

### Step E — Retailer page: enumerate all colorways

You are now on a non-GOAT retailer product page.

**Synthetic ID scheme** — use the retailer's own per-colorway identifier so
re-runs are idempotent:
- nike.com: extract the style code from the URL (e.g. `CW2288-111`) → ID = `nike_CW2288-111`
- footlocker.com: extract the product number from the URL (e.g. `42819325`) → ID = `footlocker_42819325`
- adidas.com: extract the product ID from the URL → ID = `adidas_{product_id}`
- Any other site: use `web_{first 16 chars of sha256 of the colorway's canonical URL}`

**Enumeration steps:**

1. Take a screenshot to confirm you landed on the right shoe
2. Find the color swatch selector on the page. Most retailer PDPs have a row of
   color options near the product image.
3. Count the swatches. Note the current (default) colorway.
4. For each swatch (including the default):
   a. Click the swatch
   b. Wait for page update (URL change or image swap — check both)
   c. Extract:
      - Colorway name (swatch aria-label, or page title suffix after "—" or "|",
        or the text label next to the swatch)
      - Current page URL (the canonical URL for this colorway)
      - Main product image URL (og:image meta tag is most reliable — use
        `javascript_tool` to read `document.querySelector('meta[property="og:image"]').content`)
      - Synthetic ID (from URL per scheme above)
   d. For each of the shoe's `measured_sizes`:
      - Find the size grid/selector on the page
      - Check if that size is present and selectable (not greyed out / crossed out)
      - If selectable: click it, then read the displayed price
      - Record: `{ us_size, price_usd, is_available }`
   e. Screenshot to confirm before recording this colorway

5. After all swatches, build the colorway array. Only include colorways that
   have at least one of our measured sizes available.

6. Append to payload.json with `"status": "found_retailer"`, `"source"` set to
   the domain (e.g. `"footlocker.com"`), `"source_url"` set to the retailer's
   product page URL.

---

### Step F — Mark discontinued

Append to payload.json:
```json
{
  "shoe_id": <id>,
  "status": "discontinued",
  "source": null,
  "source_url": null,
  "colorways": [],
  "notes": "<brief reason: 'Only eBay results on Google' / 'No results found' / etc.>"
}
```

---

### Step G — Error handling

If the browser throws an error, the page fails to load, or you cannot extract
the required data after reasonable retries:

Append to payload.json:
```json
{
  "shoe_id": <id>,
  "status": "error",
  "source": null,
  "source_url": null,
  "colorways": [],
  "notes": "<description of what failed>"
}
```

Then continue to the next shoe — do not stop the whole run.

---

## Payload record format (reference)

```json
{
  "shoe_id": 12,
  "status": "found_goat",
  "source": "goat",
  "source_url": "https://www.goat.com/sneakers/air-force-1-07",
  "colorways": [
    {
      "goat_id": "abc-def-123",
      "name": "White / White",
      "image_url": "https://...",
      "product_url": "https://www.goat.com/sneakers/air-force-1-07-white",
      "sizes": [
        { "us_size": 10.0, "price_usd": 89.00, "is_available": true },
        { "us_size": 10.5, "price_usd": 95.00, "is_available": false }
      ]
    }
  ],
  "notes": "3 colorways found, 2 available in size 10.0"
}
```

---

## After all shoes are processed

Print a summary table:
- Total shoes processed
- found_goat / found_retailer / discontinued / error counts
- Total colorways collected
- Total available size+colorway combinations

Then stop. Do NOT run apply_shoe_sync. Do NOT write anything to the database.

The payload.json file is the deliverable for this run. The user will review it
and decide when to apply it by running:

    python manage.py apply_shoe_sync --input payload.json --dry-run
    python manage.py apply_shoe_sync --input payload.json
