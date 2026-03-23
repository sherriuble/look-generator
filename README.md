# Wardrobe Generator (Figma-synced)

This project was bootstrapped from your Figma file and contains:

- `data/items.json`: all extracted wardrobe items
- `data/clusters.json`: grouped top clusters
- `data/top_matches.json`: prebuilt look match logic by weather + occasion
- `src/generate_outfit.py`: outfit generator CLI

## Re-run Figma extraction

Put a fresh Figma file JSON in `figma_raw.json` and run:

```bash
python3 scripts/extract_figma_wardrobe.py
```

## Export images from Figma

Run:

```bash
FIGMA_TOKEN=your_token_here python3 scripts/export_figma_images.py
```

This downloads:

- `assets/thumbs/<item_id>.png`
- `assets/full/<item_id>.png`

And writes lookup metadata to:

- `data/image_map.json`

## Generate an outfit

```bash
python3 src/generate_outfit.py --weather hot_warm --occasion casual
python3 src/generate_outfit.py --weather pleasant_chilly --occasion sport
python3 src/generate_outfit.py --weather cold --occasion work
```

## Run web generator

```bash
python3 src/web_app.py
```

Open: `http://127.0.0.1:8787`

The page calls `/api/generate` and shows each slot with item images from `assets/thumbs` / `assets/full`.

## Publish (Render quick setup)

1. Push this folder to a GitHub repo.
2. In [Render](https://render.com/), create a new **Web Service** from that repo.
3. Configure:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `python3 src/web_app.py`
4. Add env vars:
   - `HOST=0.0.0.0`
   - `PORT=10000` (Render injects one too; this app supports env `PORT`)
5. Deploy and open your public URL.

## Publish on Netlify (Free, easiest)

This project now runs as a static app (no backend needed in production).

1. Push your project to GitHub.
2. Go to [Netlify](https://www.netlify.com/) and click **Add new site** -> **Import an existing project**.
3. Connect your GitHub repo.
4. Build settings:
   - **Build command:** (leave empty)
   - **Publish directory:** `.`
5. Deploy.

`netlify.toml` is already included and routes `/` to `web/index.html`.

After deploy, your app URL will be something like:
- `https://your-site-name.netlify.app`

Allowed weather values:

- `hot_warm`
- `pleasant_chilly`
- `cold`

Allowed occasions:

- `sport`
- `casual`
- `work`
- `nice`
