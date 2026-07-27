# Try-On Quality Spike — Qwen-Image-Edit on the 3060

**Goal of this doc:** stand up the shared local GPU environment (ComfyUI) and run
**one** Qwen-Image-Edit-2509 generation on a real foot photo + one of our shoe
colorways. The output of that single test decides whether we build the Phase 1
"try it on" backend or pivot to the Phase 2 3D viewer. **Do not build the
`/api/tryon/` endpoint until this spike passes.**

This runs entirely on your machine (mobile RTX 3060, 6GB VRAM, ~16GB RAM). It is
free — no service or API key.

---

## 0. Reality check (read first)

- 6GB VRAM is below the comfortable range for this model. It **will work** via
  GGUF quantization + CPU/RAM offload, but expect **~2–5 min per image** and
  heavy RAM use. That's fine for a spike and for a demo app; it is *not* fast.
- The model + text encoder downloads total **~20–25 GB**. Make sure you have
  disk space before starting.
- If your machine has less than 16GB RAM this will thrash; close other apps.

---

## 1. Install ComfyUI + the GGUF node

```bash
# Pick a folder OUTSIDE this repo (e.g. C:\AI\ComfyUI) — do not put models in shoe_shopper_dev
git clone https://github.com/comfyanonymous/ComfyUI
cd ComfyUI
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt

# GGUF loader support (city96)
cd custom_nodes
git clone https://github.com/city96/ComfyUI-GGUF
cd ComfyUI-GGUF
pip install -r requirements.txt
cd ..\..
```

Also install **ComfyUI-Manager** (makes missing-node installs one click later):
```bash
cd custom_nodes
git clone https://github.com/ltdrdata/ComfyUI-Manager
cd ..
```

---

## 2. Download the model files

Source repo: **QuantStack/Qwen-Image-Edit-2509-GGUF** on Hugging Face. Place each
file in the exact folder shown.

| File | Goes in | Notes |
|---|---|---|
| `Qwen-Image-Edit-2509-Q4_K_M.gguf` | `ComfyUI/models/diffusion_models/` | Primary. If you hit out-of-memory, swap to `Q3_K_M`. |
| `qwen_2.5_vl_7b_fp8_scaled.safetensors` | `ComfyUI/models/text_encoders/` | The text/vision encoder (~9GB, offloaded to RAM). |
| `qwen_image_vae.safetensors` | `ComfyUI/models/vae/` | VAE. |
| `Qwen-Image-Lightning-4steps-V1.0.safetensors` *(optional)* | `ComfyUI/models/loras/` | 4-step LoRA — cuts gen time a lot. Get this if you want faster iteration. |

The text encoder + VAE are the standard Qwen-Image ones (also on the
`Comfy-Org/Qwen-Image_ComfyUI` repo if QuantStack doesn't host them).

---

## 3. Prepare the two test inputs

Drop both into `ComfyUI/input/`:

1. **`foot_photo.jpg`** — a real photo of feet/lower legs in an outfit, shoes
   visible, taken roughly how a user would (standing, phone height, decent
   light). Use your own — this is the realistic case.
2. **`shoe_ref.png`** — download one of these clean side-profile shots (all are
   confirmed multi-angle colorways in our DB):

   - Adidas Samba White/Black/Gum: `https://image.goat.com/1000/attachments/product_template_pictures/images/070/577/101/original/437050_00.png.png`
   - Nike Air Max 1 Black: `https://image.goat.com/1000/attachments/product_template_pictures/images/098/838/550/original/1277524_00.png.png`
   - New Balance 550 White/Grey: `https://image.goat.com/1000/attachments/product_template_pictures/images/067/269/013/original/731742_00.png.png`

   Start with the **Samba** — clean low-top, simple shape, easiest case. If that
   works, retry with the Air Max (chunkier sole) to stress-test.

---

## 4. Build the workflow

Easiest path: load a prebuilt **Qwen-Image-Edit-2509 GGUF** workflow JSON
(search the ComfyUI templates, the ComfyUI-Wiki Qwen page, or Civitai
"Qwen Image and Edit 2509 GGUF Beginner Friendly"), then swap its loaders for the
GGUF node. The graph you want:

```
Unet Loader (GGUF)  ── Qwen-Image-Edit-2509-Q4_K_M.gguf
CLIP Loader (GGUF or standard) ── qwen_2.5_vl_7b_fp8_scaled.safetensors  (type: qwen_image)
VAE Loader ── qwen_image_vae.safetensors
Load Image ×2 ── foot_photo.jpg  AND  shoe_ref.png
        └─► TextEncodeQwenImageEdit (takes both images + the prompt)
                 └─► KSampler ──► VAE Decode ──► Save Image
```

If a node is missing/red, open ComfyUI-Manager → "Install Missing Custom Nodes."

**Launch with low-VRAM offload:**
```bash
python main.py --lowvram
# if you still OOM:  python main.py --novram   (slower, more aggressive offload)
```

---

## 5. Prompt + settings

**Prompt (starting point):**
```
Replace the shoes the person is wearing with the shoes from the second image.
Keep the person, pose, legs, socks, background, and lighting exactly the same.
Match the new shoes to the foot position, angle, and perspective. Photorealistic,
natural shadows where the shoe meets the ground.
```

**Settings:**
- Steps: **20** (or **4** if using the Lightning LoRA)
- CFG: **2.5–4.0** (Qwen-Edit likes low CFG; start at 3.0)
- Sampler: `euler` / scheduler `simple`
- Denoise: **1.0** (it's an edit conditioned on the input image)
- Resolution: keep near the foot photo's aspect; ~1024px long side

Run it. First run is slow (model load). Generate 3–4 times with different seeds —
quality varies run to run, and you're judging the *best* achievable, not the
first.

---

## 6. How to judge it (the decision gate)

Score the best-of-4 output against these. **Pass = the shoe is recognizably the
right model, correctly placed, without obvious melting.**

| Criterion | Pass looks like |
|---|---|
| **Identity** | It's clearly *that* shoe — silhouette, colorway, key details (Samba's gum sole / 3 stripes) survive. |
| **Placement** | Shoe sits on the actual foot, right scale, follows the leg angle. Not floating, not a second pair. |
| **Occlusion** | Pant hem / sock overlaps the shoe naturally instead of the shoe painting over them. |
| **No melt** | Laces, sole, toe box aren't smeared or fused. Five-ish lace rows, not abstract goo. |
| **Background intact** | Person, pose, floor, lighting unchanged outside the shoe region. |

**Outcomes:**
- **Clear pass** → green-light Phase 1. Next step: I write the `tryon-02` spec for
  the async `/api/tryon/` endpoint (Measurement-style job, ComfyUI called via its
  local `/prompt` API, mocked in tests).
- **Borderline** → try the Lightning LoRA off (more steps), tune CFG/prompt, test
  a second shoe. If still meh, treat as fail.
- **Fail (melted/wrong/ignored shoe)** → don't sink more into Phase 1. Pivot to
  **Phase 2 (3D viewer)**, which uses the multi-angle galleries we already loaded
  and carries far less risk. The ComfyUI install isn't wasted — Hunyuan3D runs in
  the same environment.

---

## 7. Report back

Save the best output and tell me which shoe + how it scored on the table above
(a screenshot is ideal). I'll turn that into either the Phase 1 endpoint spec or
the Phase 2 batch-3D plan.
