# StoryVocabs creative correction, 9 October 2026

The earlier plan-comparison graphic allowed the terms to overlap Lifetime's discount label. It was unsuitable for publication. The current version uses document flow, explicit table columns and a separate terms block. Lifetime has its own navy band, with the price and discount emphasized in yellow. Price figures use DM Sans; the Bangladeshi currency symbol uses Hind Siliguri. Bengali headings use Tiro Bangla and body copy uses Hind Siliguri.

All ten revised layouts were inspected at export size and as 390px reading previews. The render audit passes with no block collisions, clipped content, overflowing price columns or unloaded images. Those checks supplement visual inspection; they do not certify Facebook's crop or the readability of all miniature text in product screens.

The old story-reader composite showed a different, inaccurate Recant meaning. Revised cover and offers use the authentic screenshots captured for the product demo: “প্রকাশ্যে মত প্রত্যাহার করা, আগের কথা ফিরিয়ে নেওয়া”. No product screen is generated or redrawn.

## Release files

- `../assets/plans-feed.png`: reviewed price comparison.
- `../assets/offer-feed.png`, `offer-square.png`, `offer-story.png`: reviewed offer adaptations.
- `../assets/cover-v3.png`: reviewed replacement cover.
- `../assets/faq-feed.png`, `lesson-recant.png`, `lesson-pluralism.png`, `founder-feed.png`, `flashcard-feed.png`: reviewed supporting feed images.
- `../assets/product-demo.mp4`: re-rendered 30-second video with the corrected offer end card.
- `../source/render_launch_v3.py`: editable layout source with mandatory collision checks.
- `../source/render_demo.py`: editable demo source.

`../source/render_launch.py` is obsolete and retained only for rollback. Do not use it to regenerate publication assets. Originals are retained in `../rollback/before-quality-repair/`. Correcting local files does not itself update an already published Facebook attachment; replacement must be verified in the Page.

## Required review for every future export

1. Use server-verified prices, dates and catalogue counts.
2. Render with loaded local fonts. Fail export if any layout check fails.
3. Inspect the entire image at full size, including the bottom edge and Lifetime row.
4. Inspect a phone-size reading preview for headline, price, terms and domain.
5. Inspect Facebook's actual placement previews before publication or advertising.
6. Verify the saved public image after publication. Retain its URL and proof screenshot.

An export is not approved merely because rendering completed successfully.
