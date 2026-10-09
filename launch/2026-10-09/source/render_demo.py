"""Editable captioned product demo using authentic responsive app captures.
No product screen is generated or redrawn. Run with Python/Playwright and ffmpeg.
"""
from pathlib import Path
import base64
import subprocess
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT.parent.parent / 'render/assets/fonts'
if not FONTS.exists():
    FONTS = Path('P:/Storyvocabs Socials/render/assets/fonts')

def data(path):
    mime = 'font/woff2' if path.suffix == '.woff2' else 'image/png'
    return f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode()

fonts = ''
for family, filename, weight in [('Hind','HindSiliguri-400-bengali.woff2',400),('Hind','HindSiliguri-700-bengali.woff2',700),('DM','DMSans-700-latin.woff2',700)]:
    fonts += f"@font-face{{font-family:{family};src:url('{data(FONTS/filename)}');font-weight:{weight};}}"

scenes = [
    ('story', 5, 'গল্প পড়ো', 'Highlighted শব্দগুলো খেয়াল করো', 'demo-story.png'),
    ('meaning', 7, 'শব্দে tap করো', 'বাংলা meaning, example ও pronunciation', 'demo-meaning.png'),
    ('flashcard', 6, 'Flashcard-এ practice করো', 'কার্ড flip করে meaning মিলিয়ে নাও', 'demo-flashcard.png'),
    ('review', 5, 'Saved শব্দ review করো', 'Bookmark করে পরে আবার দেখো', 'demo-review.png'),
]
with sync_playwright() as p:
    browser = p.chromium.launch()
    for name, seconds, title, subtitle, screenshot in scenes:
        html = f'''<!doctype html><html lang="bn"><meta charset="utf-8"><style>{fonts}
        *{{box-sizing:border-box}}html,body{{margin:0;width:1080px;height:1920px;background:#EAF0FF;color:#0F172A;font-family:Hind,DM,sans-serif}}
        main{{position:relative;width:1080px;height:1920px;overflow:hidden}}
        .brand{{position:absolute;left:100px;top:200px;display:flex;align-items:center;gap:18px;font:700 36px DM}}.brand img{{width:64px;height:64px;border-radius:16px}}
        h1{{position:absolute;left:100px;right:140px;top:280px;margin:0;font-size:54px;line-height:1.2;color:#1D4ED8}}
        .screen{{position:absolute;top:380px;left:290px;width:450px;height:auto;border:3px solid white;border-radius:18px}}
        .caption{{position:absolute;top:1385px;left:100px;right:140px;font-size:36px;line-height:1.35;text-align:center;font-weight:700;margin:0}}
        .domain{{position:absolute;top:1480px;left:100px;right:140px;text-align:center;font:700 29px/1.3 DM;color:#1D4ED8;margin:0}}
        </style><main><div class="brand" data-check="brand"><img src="{data(ROOT/'assets/profile-generated.png')}">StoryVocabs</div>
        <h1 data-check="headline">{title}</h1><img data-check="screen" class="screen" src="{data(ROOT/'assets'/screenshot)}"><p data-check="caption" class="caption">{subtitle}</p><p data-check="domain" class="domain">storyvocabs.com</p></main></html>'''
        (ROOT/'source'/f'demo-{name}.html').write_text(html,encoding='utf-8')
        page=browser.new_page(viewport={'width':1080,'height':1920},device_scale_factor=1)
        page.set_content(html)
        page.evaluate('document.fonts.ready')
        problems=page.evaluate('''() => {
          const els=[...document.querySelectorAll('[data-check]')];const issues=[];
          for(const el of els){const r=el.getBoundingClientRect();if(r.left<100||r.right>940||r.top<190||r.bottom>1536)issues.push('Unsafe caption region: '+el.dataset.check);if(el.scrollWidth>el.clientWidth+2)issues.push('Text overflow: '+el.dataset.check);}
          for(let i=0;i<els.length;i++)for(let j=i+1;j<els.length;j++){const a=els[i].getBoundingClientRect(),b=els[j].getBoundingClientRect();if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1)issues.push('Overlap: '+els[i].dataset.check+' / '+els[j].dataset.check);}
          return issues;
        }''')
        if problems:
            raise SystemExit(f'{name}: rejected: {problems}')
        page.screenshot(path=str(ROOT/'assets'/f'demo-frame-{name}.png'))
        page.close()
    browser.close()

timeline = [(f'demo-frame-{name}.png',seconds) for name,seconds,*_ in scenes] + [('offer-story.png',7)]
concat = ''.join(f"file '{(ROOT/'assets'/filename).as_posix()}'\nduration {seconds}\n" for filename,seconds in timeline)
concat += f"file '{(ROOT/'assets'/timeline[-1][0]).as_posix()}'\n"
(ROOT/'source'/'demo-timeline.txt').write_text(concat,encoding='utf-8')
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(ROOT/'source'/'demo-timeline.txt'),'-vf','fps=30,format=yuv420p','-t','30','-c:v','libx264','-preset','medium','-crf','20','-movflags','+faststart',str(ROOT/'assets'/'product-demo.mp4')],check=True)
(ROOT/'assets'/'product-demo.srt').write_text('''1
00:00:00,000 --> 00:00:05,000
গল্প পড়ো। Highlighted শব্দগুলো খেয়াল করো।

2
00:00:05,000 --> 00:00:12,000
শব্দে tap করো। বাংলা meaning, example ও pronunciation দেখো।

3
00:00:12,000 --> 00:00:18,000
Flashcard-এ practice করো। কার্ড flip করে meaning মিলিয়ে নাও।

4
00:00:18,000 --> 00:00:23,000
Bookmark করে saved শব্দগুলো পরে review করো।

5
00:00:23,000 --> 00:00:30,000
পূজা অফারে Pro Lifetime ৳২,০০০। ৫০% ছাড়।
২১ অক্টোবর ২০২৬ রাত ১১:৫৯ পর্যন্ত। ৩টি Word Pack ফ্রি।
storyvocabs.com
''',encoding='utf-8')
print('Exported 30-second 1080x1920 captioned product demonstration and SRT.')

