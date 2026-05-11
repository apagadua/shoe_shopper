import { supabase, isSupabaseConfigured } from '../config/supabase';

const CHUNK_SIZE = 100;

/** @param {unknown} v */
function trimUrl(v) {
  if (v == null) return null;
  const s = String(v).trim();
  return s.length ? s : null;
}

function normalizeSizeRow(row) {
  return {
    us_size: row.us_size ?? null,
    price_usd: row.price_usd ?? null,
    is_available: row.is_available ?? null,
  };
}

function normalizeColorwayRow(row, sizes) {
  return {
    goat_id: row.goat_id != null && String(row.goat_id).trim() !== '' ? String(row.goat_id).trim() : String(row.id),
    sku: row.sku ?? null,
    name: row.name ?? row.colorway_name ?? null,
    image_url: trimUrl(row.image_url ?? row.image ?? null),
    product_url: trimUrl(row.product_url ?? row.url ?? null),
    sizes,
  };
}

function colorwayMergeKey(row) {
  const goat = row.goat_id != null && String(row.goat_id).trim() !== '' ? String(row.goat_id).trim() : '';
  if (goat) return `goat:${goat}`;
  const sku = row.sku != null && String(row.sku).trim() !== '' ? String(row.sku).trim() : '';
  if (sku) return `sku:${sku}`;
  return `id:${row.id}`;
}

function scoreColorwayRow(r) {
  const img = trimUrl(r.image_url ?? r.image ?? null) ? 2 : 0;
  const name = trimUrl(r.name ?? r.colorway_name ?? null) ? 1 : 0;
  return img + name;
}

/** @param {ReturnType<typeof normalizeSizeRow>[][]} sizeLists */
function mergeSizeLists(sizeLists) {
  const out = [];
  const seen = new Set();
  for (const list of sizeLists) {
    for (const s of list || []) {
      const k = `${s.us_size}`;
      if (seen.has(k)) continue;
      seen.add(k);
      out.push(s);
    }
  }
  return out;
}

/**
 * Loads `shoe` + `shoe_colorway` + `shoe_colorway_size` for recommendation card IDs.
 * @param {number[]} shoeIds — same as `item.id` from `/api/recommendations/`
 * @returns {Promise<Map<number, { shoe_id: number, catalog_shoe_image_url: string|null, catalog_shoe_product_url: string|null, colorways: ReturnType<typeof normalizeColorwayRow>[] }>>}
 */
export async function fetchShoeCardPayloadsByIds(shoeIds) {
  const map = new Map();
  if (!shoeIds?.length) return map;

  if (!isSupabaseConfigured || !supabase) {
    if (__DEV__) {
      console.warn(
        '[shoeCardPayloads] Supabase URL/key missing. Set EXPO_PUBLIC_SUPABASE_URL and EXPO_PUBLIC_SUPABASE_ANON_KEY '
        + 'in frontend/.env or repo-root .env (see app.config.js), then restart Metro with: npx expo start --clear'
      );
    }
    return map;
  }

  const uniq = [...new Set(shoeIds.filter((id) => id != null).map(Number))];

  try {
    for (let i = 0; i < uniq.length; i += CHUNK_SIZE) {
      const chunk = uniq.slice(i, i + CHUNK_SIZE);

      const { data: shoeRows, error: shoeErr } = await supabase
        .from('shoe')
        .select('id, shoe_image_url, product_url')
        .in('id', chunk);

      if (shoeErr && __DEV__) console.warn('[shoeCardPayloads] shoe', shoeErr.message);

      /** @type {Map<number, { shoe_image_url: string|null, product_url: string|null }>} */
      const shoeRowById = new Map();
      for (const s of shoeRows || []) {
        const sid = Number(s.id);
        shoeRowById.set(sid, {
          shoe_image_url: trimUrl(s.shoe_image_url),
          product_url: trimUrl(s.product_url),
        });
      }

      const { data: colorwayRows, error: colorwayErr } = await supabase
        .from('shoe_colorway')
        .select('id, shoe_id, goat_id, sku, name, image_url, product_url')
        .in('shoe_id', chunk);

      if (colorwayErr) {
        if (__DEV__) console.warn('[shoeCardPayloads]', colorwayErr.message);
        continue;
      }

      const colorwaysByShoeId = new Map();
      const colorwayIds = [];

      for (const row of colorwayRows || []) {
        const shoeId = Number(row.shoe_id);
        const list = colorwaysByShoeId.get(shoeId) || [];
        list.push(row);
        colorwaysByShoeId.set(shoeId, list);
        if (row.id != null) colorwayIds.push(row.id);
      }

      let sizesByColorwayId = new Map();
      if (colorwayIds.length) {
        const { data: sizeRows, error: sizeErr } = await supabase
          .from('shoe_colorway_size')
          .select('colorway_id, us_size, price_usd, is_available')
          .in('colorway_id', colorwayIds);

        if (sizeErr) {
          if (__DEV__) console.warn('[shoeCardPayloads]', sizeErr.message);
        } else {
          for (const s of sizeRows || []) {
            const cwId = s.colorway_id;
            if (cwId == null) continue;
            const list = sizesByColorwayId.get(cwId) || [];
            list.push(normalizeSizeRow(s));
            sizesByColorwayId.set(cwId, list);
          }
        }
      }

      for (const shoeId of chunk) {
        const sid = Number(shoeId);
        const rows = colorwaysByShoeId.get(sid) || [];
        /** @type {Map<string, typeof rows>} */
        const groups = new Map();
        for (const r of rows) {
          const k = colorwayMergeKey(r);
          const g = groups.get(k) || [];
          g.push(r);
          groups.set(k, g);
        }
        const normalized = [];
        for (const group of groups.values()) {
          if (group.length === 1) {
            const r0 = group[0];
            normalized.push(normalizeColorwayRow(r0, sizesByColorwayId.get(r0.id) || []));
            continue;
          }
          const best = [...group].sort((a, b) => scoreColorwayRow(b) - scoreColorwayRow(a))[0];
          const sizeLists = group.map((r) => sizesByColorwayId.get(r.id) || []);
          normalized.push(normalizeColorwayRow(best, mergeSizeLists(sizeLists)));
        }
        normalized.sort((a, b) => String(a.goat_id).localeCompare(String(b.goat_id), undefined, { numeric: true }));

        const shoeMeta = shoeRowById.get(sid);
        map.set(sid, {
          shoe_id: sid,
          catalog_shoe_image_url: shoeMeta?.shoe_image_url ?? null,
          catalog_shoe_product_url: shoeMeta?.product_url ?? null,
          colorways: normalized,
        });
      }
    }
  } catch (e) {
    if (__DEV__) console.warn('[shoeCardPayloads]', e?.message || e);
  }

  return map;
}
