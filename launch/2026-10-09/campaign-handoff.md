# StoryVocabs campaign draft and remaining acceptance work

Status verified 9 October 2026. The campaign is a draft and is off. No new advertising spend has been enabled.

## Draft already saved in Ads Manager

Ad account: `578417129494002`, BDT. Campaign: `120253830077980572`, “StoryVocabs | Puja Pro | 10–12 Oct 2026 | DRAFT”. Ad set: `120253830077990572`, “BD | Adults 18+ | Website Purchase | 3 days”. One placeholder ad exists, `120253830078000572`; the reviewed two-ad setup still needs completion.

Sales objective; Website conversion location; maximize conversions. The website dataset cannot yet be selected because it is not connected to this ad account. Purchase must be selected and verified before launch.

Bangladesh, age 18+, all genders, no restrictive language filter; broad targeting. Start 10 October 2026 at 12:00 AM, end 12 October 2026 at 11:59 PM, account timezone GMT+6. Lifetime media budget saved at ৳1,250. There is no automatic renewal or increase.

The billing page showed roughly 15% estimated tax on the older unpaid balance. If the same rate applies, ৳1,250 media plus ৳187.50 tax leaves ৳62.50 within the ৳1,500 total cap for other fees. This is provisional: confirm actual fees before publishing. The older unpaid balance, ৳709.35 plus ৳106.40 estimated tax and any fees, is separate from the new campaign budget and requires the owner to resolve it.

Facebook Feed, Stories and Reels are the intended placements. Meta's current ad-set placement editor showed a changing placements notice. Platforms and placement controls still need inspection; do not change account-wide exclusions that affect other campaigns.

## Ad A — Lifetime static

Use `assets/offer-feed.png`, with `offer-square.png` or `offer-story.png` for their corresponding placement previews. Verify every preview's crop.

Headline: StoryVocabs Pro Lifetime ৳২,০০০

Primary text:

গল্প পড়ো। শব্দে tap করো। বাংলা meaning দেখো। তারপর practice করো।

DU/IBA, BCS, Bank ও IELTS vocabulary practice-এর জন্য StoryVocabs Pro। ৮১টি Word Pack, ৪০৫টি গল্প ও ১,৬০৮টি শব্দ—সাথে flashcards, games ও review tools।

পূজা অফারে Pro Lifetime ৳৪,০০০ → ৳২,০০০। ৫০% ছাড়, একবারের পেমেন্ট। কম খরচে শুরু করতে ১ মাসের Pro ৳২২৫।

আগে দেখে নিতে চাও? ৩টি Word Pack ফ্রি। অফার ২১ অক্টোবর ২০২৬ রাত ১১:৫৯ পর্যন্ত (ঢাকা সময়)। কোনো auto-renewal নেই। Lifetime access service commercially available থাকা পর্যন্ত। পূর্ণ শর্ত website-এ দেখো।

Destination:
https://storyvocabs.com/?utm_source=facebook&utm_medium=paid_social&utm_campaign=puja_pro_20261010&utm_content=lifetime_static

CTA: Learn More.

## Ad B — actual product demo

Use the revised `assets/product-demo.mp4`. Use the same offer details and headline, with this opening:

StoryVocabs-এ vocabulary practice কীভাবে করবে? ৩০ সেকেন্ডে আসল interface দেখে নাও: গল্প → বাংলা meaning → flashcard practice → saved শব্দ review।

Destination:
https://storyvocabs.com/?utm_source=facebook&utm_medium=paid_social&utm_campaign=puja_pro_20261010&utm_content=product_demo

## Pending owner and browser steps

1. Restore Chrome connection in the kmap.2030@gmail.com profile. The cover and introduction image are already corrected live; revised video and FAQ artwork still need attachment replacement and public verification. The seven daily posts are prepared, not scheduled.
2. Complete the prepared campaign-access request in Business Suite's “Choose the role” dialog if the owner accepts Meta's Commercial Terms. Partial campaign access is selected; full control of finances and permissions is off. Then connect dataset `29351877324501546` to the BDT ad account.
3. Approve generation and installation of the dataset's direct CAPI token in the production server's private environment. No token has been generated and server delivery remains disabled. Do not put credentials in Git, chat, frontend code or posts.
4. Resolve the older ad-account balance directly in Billing & payments.
5. Verify browser events and server-confirmed Purchase acceptance/deduplication in Events Manager. Avoid invented Purchase test events that look like real revenue.
6. Owner completes a controlled mobile payment from a tagged ad destination, separately from the ad budget. Verify invoice amount, approval, Pro access, status page, receipt, attribution, internal report revenue and one Meta Purchase. Pending, failed, cancelled and wrong-amount submissions must create no Purchase.
7. Owner verifies incoming support email and a successful reply.
8. Finish placement previews and two ads, confirm total fees within cap, and launch only after these checks pass. Pause immediately for checkout, price or activation failures; stop at the three-day endpoint or cap.

## Production code and verification

Product PR #47 and queue/content-safety PR #20 were merged. Production health reports database OK and release `38ed0ed6a30a89076a22f3d171efb8160a8458a0`. The live pricing catalogue was rechecked: ৳225 / ৳600 / ৳1,125 / ৳2,000 and offer expiry `2026-10-21T17:59:59Z`, which is 11:59:59 PM Dhaka.

Website: https://storyvocabs.com/api/health
Catalogue: https://storyvocabs.com/api/native/catalog
Product implementation: https://github.com/abdullahprobal/StoryVocabs.com/pull/47
Queue safety: https://github.com/abdullahprobal/StoryVocabs-social/pull/20

Website verification previously passed 170 tests, lint, build and the 81-pack/405-story/1,608-word content audit. Social queue/editorial checks previously passed 67 tests. Creative repair separately passed all ten layout checks and a portable rebuild produced identical PNG hashes. The revised video is 30 seconds, 1080×1920, 30 fps. None of those replaces the pending real mobile checkout and Meta acceptance checks.
