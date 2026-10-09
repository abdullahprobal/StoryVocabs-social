# StoryVocabs launch assets

This folder contains manually reviewed creative assets and prepared captions. Its files do not publish or schedule posts automatically. The generic queue remains paused for 9–16 October 2026.

Use `assets/cover-v3.png` as the current cover. `cover-v2.png` is superseded. The three `offer-*.png` files, plan comparison, FAQ, lessons, founder workflow and flashcard image are from the corrected layout source. `product-demo.mp4` is a 30-second captioned sequence of authentic product captures with a corrected offer end card.

## Rebuild and review

Requirements: Python, Playwright Chromium and ffmpeg. Fonts are already checked into the repository in `render/assets/fonts`.

```powershell
python launch/2026-10-09/source/render_launch_v3.py
```

The renderer writes candidates into `launch/2026-10-09/revised/` and phone reading previews into its `phone-previews/` subfolder. It rejects overlapping blocks, overflowing price columns and clipping. Inspect every full export and phone preview before copying reviewed candidates into `assets/`. A passing geometry audit alone is insufficient.

After promoting the reviewed offer Story image:

```powershell
python launch/2026-10-09/source/render_demo.py
```

The demo renderer also rejects collisions and places its text inside a conservative Reel-safe region. Verify actual Facebook placement previews separately.

## Current publication state

On 9 October, the corrected cover was saved and the existing introduction's image was replaced and verified in Facebook's public photo viewer. The caption and original post remained intact. The plan comparison has not been published. The revised video and FAQ image still need their Facebook replacement step; browser access became unavailable before those actions.

Introduction: https://www.facebook.com/StoryVocabs/posts/122131032254846512

FAQ: https://www.facebook.com/StoryVocabs/posts/122131084262846512

Old video, awaiting replacement: https://www.facebook.com/StoryVocabs/posts/122131084940846512

`launch-content.md` contains prepared daily captions for 10–16 October and support replies; these are not yet scheduled. `qa/` retains the local layout audit, asset hashes and review notes. Rollback for earlier tracked artwork is available in Git; local original files are also preserved in the working artifact's rollback folder.

The Sales campaign remains unpublished and off. Dataset/account connection, CAPI credentials, verified Purchase acceptance, billing resolution and an owner-controlled mobile payment still need completion before advertising spend.
