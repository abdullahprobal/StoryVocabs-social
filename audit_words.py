import re, json

with open(r'C:\Users\DELL\.antigravity\Story-Vocabulary app\frontend\src\data\wordPacks.js', 'r', encoding='utf-8') as f:
    content = f.read()

start = content.find('[')
depth = 0
for i, ch in enumerate(content[start:], start):
    if ch == '[': depth += 1
    elif ch == ']':
        depth -= 1
        if depth == 0: break

json_str = content[start:i+1]
json_str = re.sub(r',\s*}', '}', json_str)
json_str = re.sub(r',\s*]', ']', json_str)
packs = json.loads(json_str)

lines = []
lines.append("=== Pack 1 Words ===")
for pack in packs:
    if pack['id'] == 1:
        for w in pack['words']:
            lines.append(f"  {w['word']:15s} | {w['bangla']:25s} | POS: {w.get('partOfSpeech',''):10s} | Meaning: {w['meaning'][:80]}")

with open(r'C:\Users\DELL\.antigravity\StoryVocabs-social\word_pack_audit.txt', 'w', encoding='utf-8') as f:
    f.write("\n".join(lines))

print("Done - wrote to word_pack_audit.txt")
