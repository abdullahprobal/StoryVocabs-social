"""StoryVocabs launch artwork: editable type, real screens, checked layout.

Run this source, then inspect the full exports and phone previews before promotion.
Content occupies normal document flow. Export fails for collisions or clipping.
The earlier render_launch.py is retained only as a rollback record.
"""
from pathlib import Path
from itertools import combinations
import base64
import json
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'revised'
OUT.mkdir(exist_ok=True)
PREVIEWS = OUT / 'phone-previews'
PREVIEWS.mkdir(exist_ok=True)
FONTS = ROOT.parent.parent / 'render/assets/fonts'
if not FONTS.exists():
    FONTS = Path('P:/Storyvocabs Socials/render/assets/fonts')

def data(path):
    mime = 'font/woff2' if path.suffix == '.woff2' else 'image/png'
    return f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode()

fonts = ''
for family, filename, weight in [
    ('Tiro', 'TiroBangla-400-bengali.woff2', 400),
    ('Hind', 'HindSiliguri-400-bengali.woff2', 400),
    ('Hind', 'HindSiliguri-600-bengali.woff2', 600),
    ('Hind', 'HindSiliguri-700-bengali.woff2', 700),
    ('DM', 'DMSans-700-latin.woff2', 700),
    ('DM', 'DMSans-400-latin.woff2', 400),
]:
    fonts += f"@font-face{{font-family:{family};src:url('{data(FONTS/filename)}');font-weight:{weight};}}"

logo = data(ROOT / 'assets/profile-generated.png')
screens = {name: data(ROOT / 'assets' / f'demo-{name}.png')
           for name in ['story', 'meaning', 'flashcard', 'review']}

def check(tag, name, content, classes=''):
    return f'<{tag} data-check="{name}" class="{classes}">{content}</{tag}>'

def brand():
    return check('header', 'brand', f'<img src="{logo}" alt=""><span>StoryVocabs</span>', 'brand')

def money(value, cls=''):
    return f'<span class="money {cls}"><span class="currency">৳</span><span class="digits">{value}</span></span>'

def footer(offer=False):
    line = '২১ অক্টোবর ২০২৬ · রাত ১১:৫৯ পর্যন্ত (ঢাকা সময়)' if offer else '৩টি Word Pack দিয়ে ফ্রি শুরু করো'
    return check('footer', 'footer', f'<p>{line}</p><div class="footer-row"><b>storyvocabs.com</b><span>গল্প পড়ো · শব্দ শেখো · practice করো</span></div>', 'footer')

base = fonts + '''
*{box-sizing:border-box}html,body{margin:0;padding:0}
body{background:#F8FAFC;color:#0F172A;font-family:Hind,DM,sans-serif}
.canvas{width:100vw;height:100vh;overflow:hidden;display:flex;flex-direction:column;padding:52px 64px 48px;position:relative}
h1,h2,h3,p{margin:0}.brand{display:flex;align-items:center;gap:18px;font:700 34px DM;flex-shrink:0;min-height:72px}
.brand img{width:72px;height:72px;border-radius:18px}
h1{font:400 65px/1.25 Tiro,DM,Hind,serif}h1 .en{font-family:DM;font-size:.9em;font-weight:400}
.blue{color:#2563EB}.muted{color:#475569}.en{font-family:DM,Hind,sans-serif}
.title{margin-top:42px;flex-shrink:0}.context{font-size:32px;line-height:1.4;margin-top:18px;color:#475569}
.money{display:inline-flex;align-items:baseline;gap:7px;white-space:nowrap;line-height:1.12;letter-spacing:-1px}
.currency{font-family:Hind,sans-serif;font-weight:700;font-size:.78em;letter-spacing:0}
.digits{font-family:DM,sans-serif;font-weight:700;font-variant-numeric:tabular-nums}
.footer{margin-top:auto;padding-top:22px;border-top:2px solid #CBD5E1;flex-shrink:0;font-size:32px;line-height:1.5}
.footer-row{display:flex;align-items:baseline;justify-content:space-between;gap:20px;margin-top:9px}
.footer b{font:700 34px/1.3 DM;color:#1D4ED8}.footer-row span{font-size:25px;color:#475569}
.promo{margin-top:35px;display:flex;align-items:center;justify-content:space-between;font-size:30px;font-weight:700}
.discount{background:#FFE58A;color:#0F172A;padding:7px 18px;font-size:30px}
.shot{display:block;border:2px solid #CBD5E1;border-radius:14px;height:auto}
'''

layouts = {}
rows = ''
for label, price, regular, percent in [
    ('১ মাস', '225', '300', '২৫%'), ('৩ মাস', '600', '800', '২৫%'),
    ('৬ মাস', '1,125', '1,500', '২৫%'), ('Lifetime', '2,000', '4,000', '৫০%'),
]:
    lifetime = label == 'Lifetime'
    rows += f'''<section class="plan-row {'lifetime' if lifetime else ''}">
    <div data-row-check="{label} label" class="plan-name"><b>{label}</b><small>{percent} ছাড়</small></div>
    <div data-row-check="{label} price" class="plan-price">{money(price)}</div>
    <div data-row-check="{label} regular" class="plan-regular"><s>{money(regular)}</s></div></section>'''
plans = brand() + check('div', 'headline', '<h1>নিজের সময় অনুযায়ী<br><span class="blue"><span class="en">Pro plan</span> বেছে নাও</span></h1><p class="context">পূজা অফার · সব plan-এ একই Pro access</p>', 'title')
plans += check('div', 'plan table', '<div class="plan-head"><span>মেয়াদ</span><span>অফার মূল্য</span><span>নিয়মিত মূল্য</span></div>' + rows, 'plans')
plans += check('p', 'terms', 'কোনো auto-renewal নেই।<br>Lifetime-এর পূর্ণ শর্ত website-এ দেখো।', 'terms') + footer(True)
layouts['plans-feed'] = (1080, 1350, plans, '''
.title{margin-top:38px}h1{font-size:62px}.plans{margin-top:28px;flex-shrink:0}
.plan-head,.plan-row{display:grid;grid-template-columns:34% 37% 29%;align-items:center;column-gap:0}
.plan-head{height:48px;font-size:26px;color:#475569;padding:0 24px}
.plan-head span:nth-child(2),.plan-head span:nth-child(3){text-align:right}
.plan-row{min-height:136px;padding:15px 24px;border-top:2px solid #CBD5E1}
.plan-name b{font:700 37px/1.35 Hind,DM}.plan-name small{display:block;font-size:28px;line-height:1.4;margin-top:4px;color:#475569}
.plan-price{text-align:right;font-size:56px;color:#1D4ED8;white-space:nowrap}
.plan-regular{text-align:right;font-size:33px;color:#64748B;white-space:nowrap}.plan-regular .digits{text-decoration:line-through}
.lifetime{background:#0F172A;color:#F8FAFC;border:0;min-height:144px;margin-top:8px}
.lifetime .plan-name b{font-family:DM}.lifetime .plan-name small{color:#FFE58A}
.lifetime .plan-price{color:#FFE58A}.lifetime .plan-regular{color:#CBD5E1}
.terms{font-size:29px;line-height:1.42;color:#475569;margin:26px 0 20px;flex-shrink:0}
.footer{font-size:31px}.footer-row span{display:none}
''')

def offer_body():
    body = brand() + check('div', 'promotion', '<span>পূজা অফার</span><span class="discount">৫০% ছাড়</span>', 'promo')
    body += check('div', 'headline', '<h1>গল্পে শেখো।<br><span class="blue"><span class="en">Pro</span>-তে practice করো।</span></h1>', 'title')
    body += check('div', 'lifetime offer', '<h2>Pro Lifetime</h2>' + money('2,000', 'hero-price') + '<p class="regular">নিয়মিত ' + money('4,000') + ' · একবারের পেমেন্ট</p>', 'hero')
    body += check('div', 'product proof', f'<div class="benefits"><p><b>৮১টি</b> Word Pack</p><p>৪০৫টি গল্প · ১,৬০৮টি শব্দ</p><p class="muted">Flashcards · Games · Review</p><p class="free">৩টি Word Pack ফ্রি</p></div><img class="shot" src="{screens["meaning"]}" alt="Real Recant word panel">', 'proof')
    return body + footer(True)

offer_css = '''
.title{margin-top:24px}h1{font-size:61px}.hero{margin-top:25px;flex-shrink:0}
.hero h2{font:700 31px/1.3 DM}.hero-price{font-size:132px;color:#1D4ED8;margin-top:12px}
.regular{margin-top:10px;font-size:30px;line-height:1.4}.regular .money{font-size:30px;letter-spacing:0}.regular .digits{font-weight:400}
.proof{display:flex;justify-content:space-between;align-items:center;gap:38px;margin:30px 0 26px;min-height:0;flex:1}
.proof .shot{width:200px;max-height:100%;object-fit:contain;flex-shrink:0}.benefits{font-size:32px;line-height:1.55}.benefits p+p{margin-top:17px}.benefits b{color:#1D4ED8}
.free{font-weight:700;background:#FFE58A;display:inline-block;padding:10px 18px;margin-top:30px!important}
.footer-row span{display:none}
'''
layouts['offer-feed'] = (1080, 1350, offer_body(), offer_css)
layouts['offer-square'] = (1080, 1080, offer_body(), offer_css + '''
.canvas{padding:42px 64px 38px}.brand{min-height:64px}.brand img{width:64px;height:64px}
.promo{margin-top:22px;font-size:28px}.discount{font-size:28px;padding:3px 16px}
.title{margin-top:17px}h1{font-size:52px;line-height:1.21}.hero{margin-top:17px}.hero h2{font-size:28px}
.hero-price{font-size:106px;margin-top:8px}.regular{font-size:28px;margin-top:4px}.regular .money{font-size:28px}
.proof{margin:20px 0 18px;gap:28px}.proof .shot{width:150px}.benefits{font-size:30px;line-height:1.3}
.benefits p+p{margin-top:11px}.free{margin-top:19px!important;font-size:29px}.footer{padding-top:14px;font-size:30px}.footer b{font-size:31px}
''')
layouts['offer-story'] = (1080, 1920, offer_body(), offer_css + '''
.canvas{padding:200px 140px 400px 100px}.brand img{width:68px;height:68px}.brand{font-size:34px}
.promo{margin-top:30px}.title{margin-top:24px}h1{font-size:62px}.hero{margin-top:24px}.hero-price{font-size:134px}
.proof{margin:28px 0 25px;gap:30px}.proof .shot{width:220px}.benefits{font-size:31px;line-height:1.4}
.benefits p+p{margin-top:16px}.footer{font-size:31px}.footer b{font-size:34px}
''')

faq = brand() + check('div', 'headline', '<h1>কেনার আগে<br><span class="blue">জেনে নাও</span></h1><p class="context">Payment, activation ও support</p>', 'title')
faq += check('div', 'answers', '''<section><h2>আগে ফ্রি দেখো</h2><p>৩টি Word Pack · ১৫টি গল্প</p></section><section><h2>নিজের সময় অনুযায়ী Pro নাও</h2><p>১ / ৩ / ৬ মাস অথবা Lifetime<br>কোনো auto-renewal নেই</p></section><section><h2>Verified payment → Pro activation</h2><p>bKash · Nagad · Rocket<br>ZiniPay hosted checkout</p></section>''', 'answers')
faq += check('div', 'support', '<p>পেমেন্টের পর সমস্যা হলে</p><b>support@storyvocabs.com</b>', 'support')
faq += footer() + ''
layouts['faq-feed'] = (1080, 1350, faq, '''
.title{margin-top:34px}h1{font-size:65px}.answers{margin-top:35px;flex-shrink:0}
.answers section{padding:19px 0;border-top:2px solid #CBD5E1}.answers h2{font-size:34px;line-height:1.4;color:#1D4ED8}
.answers p{font-size:30px;line-height:1.5;margin-top:7px}.support{margin:25px 0 24px;flex-shrink:0;font-size:30px;line-height:1.5}
.support b{font:700 34px/1.5 DM}.footer-row span{font-size:23px}
''')

for name, word, pos, meaning, quote in [
    ('lesson-recant', 'Recant', 'verb', 'প্রকাশ্যে মত প্রত্যাহার করা,<br>আগের কথা ফিরিয়ে নেওয়া', 'He would not <b>recant</b> his earlier public threats against the opposition.'),
    ('lesson-pluralism', 'Pluralism', 'noun', 'বহুত্ববাদ<br>নানা গোষ্ঠী ও মতের সহাবস্থান', 'The new charter demanded genuine <b>pluralism</b> in the upcoming parliament.'),
]:
    body = brand() + check('div', 'word', f'<h1>{word}</h1><p>{pos}</p>', 'word')
    body += check('p', 'meaning', meaning, 'meaning')
    body += check('blockquote', 'example', f'<p>“{quote}”</p>', 'example')
    body += check('p', 'source', 'Word Pack 1 · Geopolitics<br>The Ink That Broke the Siege', 'source') + footer()
    layouts[name] = (1080, 1350, body, '''
.word{margin-top:58px}.word h1{font:700 106px/1.1 DM}.word p{font:400 29px/1.4 DM;color:#64748B;margin-top:18px}
.meaning{font-size:46px;font-weight:700;line-height:1.5;color:#1D4ED8;margin-top:46px}
.example{margin:46px 0 0;padding:35px 32px;background:#EAF0FF;font:400 37px/1.5 DM}
.source{font:400 29px/1.6 DM;margin-top:29px;color:#475569}
.footer-row span{display:none}
''')

founder = brand() + check('div', 'headline', '<h1>গল্পের context থেকে<br><span class="blue">শব্দের practice পর্যন্ত</span></h1>', 'title')
founder += check('div', 'workflow', '<p><span>01</span>গল্প পড়ো</p><p><span>02</span>শব্দের meaning দেখো</p><p><span>03</span>Flashcards ও games</p><p><span>04</span>Saved শব্দ review করো</p>', 'workflow')
founder += check('div', 'founder fact', '<b>Founded by a University of Dhaka student.</b><p>শেখার অভিজ্ঞতা দেখে নিজের সিদ্ধান্ত নাও।</p>', 'founder') + footer()
layouts['founder-feed'] = (1080, 1350, founder, '''
h1{font-size:61px}.workflow{margin-top:47px;background:#EAF0FF;padding:20px 34px}
.workflow p{display:flex;align-items:center;gap:34px;font-size:40px;font-weight:700;line-height:1.4;padding:26px 0}
.workflow p+p{border-top:2px solid #CBD5E1}.workflow span{font:700 30px/1.4 DM;color:#1D4ED8}
.founder{margin-top:40px;font-size:31px;line-height:1.5}.founder b{font:700 28px/1.5 DM}.founder p{margin-top:16px}
.footer-row span{display:none}
''')

flash = brand() + check('div', 'headline', '<h1>কার্ড flip করো।<br><span class="blue">Meaning মিলিয়ে নাও।</span></h1>', 'title')
flash += check('div', 'flashcard demo', f'<div class="flash-copy"><h2>Recant</h2><p>গল্পে পড়া শব্দটি<br>এবার flashcard-এ<br>practice করো।</p><p class="muted">Word Pack 1</p></div><img class="shot" src="{screens["flashcard"]}" alt="Real flashcard">', 'flash-demo') + footer()
layouts['flashcard-feed'] = (1080, 1350, flash, '''
h1{font-size:61px}.flash-demo{display:flex;justify-content:space-between;align-items:center;gap:50px;margin:40px 0 35px;flex:1;min-height:0}
.flash-demo .shot{width:310px;flex-shrink:0}.flash-copy{font-size:36px;line-height:1.55}.flash-copy h2{font:700 63px/1.2 DM;color:#1D4ED8}
.flash-copy p{margin-top:32px}.footer-row span{display:none}
''')

cover = f'''<aside class="cover-shot left"><img src="{screens['story']}" alt="Real story"></aside>
<div class="cover-main">{brand()}
{check('div', 'cover headline', '<h1>গল্পে গল্পে<br><span class="blue">পরীক্ষার <span class="en">vocabulary</span></span></h1>', 'cover-title')}
{check('p', 'exam audiences', 'DU/IBA · BCS · Bank · IELTS', 'exams')}
{check('div', 'free and domain', '<b>৩টি Word Pack দিয়ে ফ্রি শুরু করো</b><p>storyvocabs.com</p>', 'cover-cta')}
{check('p', 'cover workflow', 'গল্প পড়ো → শব্দে tap করো → practice করো', 'cover-workflow')}
</div><aside class="cover-shot right"><img src="{screens['meaning']}" alt="Real Bangla meaning"></aside>'''
layouts['cover-v3'] = (1640, 720, cover, '''
.canvas{padding:0;background:#EAF0FF;border-top:14px solid #2563EB;border-bottom:14px solid #1D4ED8}
.cover-main{position:absolute;left:405px;right:405px;top:50px;bottom:45px;display:flex;flex-direction:column;align-items:center}
.cover-main .brand{font-size:29px;min-height:60px}.cover-main .brand img{width:60px;height:60px;border-radius:14px}
.cover-title{margin-top:25px;text-align:center}h1{font-size:66px;line-height:1.24}.cover-title .en{font-size:56px;font-weight:400}
.exams{font:400 27px/1.4 DM;color:#475569;margin-top:23px}
.cover-cta{font-size:31px;line-height:1.4;text-align:center;margin-top:24px}.cover-cta p{font:700 28px/1.5 DM;color:#1D4ED8;margin-top:10px}
.cover-workflow{margin-top:auto;background:#0F172A;color:#F8FAFC;padding:14px 23px;font-size:28px;line-height:1.4;white-space:nowrap}
.cover-shot{position:absolute;top:50px;width:320px;overflow:hidden;border:3px solid white;border-radius:15px;background:white}
.cover-shot img{display:block;width:100%;height:auto}.cover-shot.left{left:55px}.cover-shot.right{right:55px}
''')

audit_js = '''() => {
  const issues=[];
  const canvas=document.querySelector('.canvas').getBoundingClientRect();
  const nodes=[...document.querySelectorAll('[data-check]')];
  const rect=(e)=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height}};
  const overlap=(a,b)=>Math.min(a.right,b.right)-Math.max(a.x,b.x)>1 && Math.min(a.bottom,b.bottom)-Math.max(a.y,b.y)>1;
  for(const e of nodes){const r=rect(e);
    if(r.x<canvas.x-1||r.y<canvas.y-1||r.right>canvas.right+1||r.bottom>canvas.bottom+1)issues.push(`Outside canvas: ${e.dataset.check}`);
  }
  for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){
    if(!nodes[i].contains(nodes[j])&&!nodes[j].contains(nodes[i])&&overlap(rect(nodes[i]),rect(nodes[j])))issues.push(`Overlap: ${nodes[i].dataset.check} / ${nodes[j].dataset.check}`);
  }
  for(const row of document.querySelectorAll('.plan-row')){
    const cells=[...row.querySelectorAll('[data-row-check]')];
    for(let i=0;i<cells.length;i++)for(let j=i+1;j<cells.length;j++)if(overlap(rect(cells[i]),rect(cells[j])))issues.push(`Price column overlap: ${cells[i].dataset.rowCheck}`);
  }
  for(const e of document.querySelectorAll('p,h1,h2,h3,small,.plan-name,.plan-price,.plan-regular,.footer-row,.regular,.benefits')){
    if(e.scrollWidth>e.clientWidth+2)issues.push(`Horizontal overflow: ${e.textContent.trim().slice(0,70)}`);
  }
  for(const e of document.querySelectorAll('.proof,.flash-demo')){
    if(e.scrollHeight>e.clientHeight+2)issues.push(`Content clipped: ${e.className}`);
  }
  const unloaded=[...document.images].filter(i=>!i.complete||i.naturalWidth===0).length;
  if(unloaded)issues.push(`Unloaded images: ${unloaded}`);
  return {issues,blocks:nodes.map(e=>({name:e.dataset.check,...rect(e)})),fontStatus:document.fonts.status};
}'''

reports = {}
with sync_playwright() as p:
    browser = p.chromium.launch()
    for name, (w, h, body, css) in layouts.items():
        html = f'<!doctype html><html lang="bn"><meta charset="utf-8"><style>{base}{css}</style><body><main class="canvas">{body}</main></body></html>'
        (OUT / f'{name}.html').write_text(html, encoding='utf-8')
        page = browser.new_page(viewport={'width':w,'height':h}, device_scale_factor=1)
        page.set_content(html)
        page.evaluate('document.fonts.ready')
        report = page.evaluate(audit_js)
        reports[name] = report
        if report['issues']:
            print(name + ': ' + '; '.join(report['issues']))
        else:
            page.screenshot(path=str(OUT / f'{name}.png'))
            # A phone-size reading preview, not a claim of Facebook's device crop.
            preview = browser.new_page(viewport={'width':390,'height':round(h * 390 / w)},device_scale_factor=1)
            preview.set_content(f'<html><style>html,body{{margin:0}}img{{display:block;width:390px}}</style><img src="{data(OUT / f"{name}.png")}">')
            preview.screenshot(path=str(PREVIEWS / f'{name}.png'))
            preview.close()
        page.close()
    browser.close()
(OUT / 'layout-audit.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
errors = sum(len(r['issues']) for r in reports.values())
if errors:
    raise SystemExit(f'REJECTED: {errors} layout errors. No affected PNG exported.')
print(f'PASS: {len(reports)} layouts. No block overlaps, clipped content, overflowing price columns or unloaded images. Visual review still required.')
