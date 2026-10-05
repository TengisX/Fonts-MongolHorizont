"""Check that shaped Mongolian text advances by W per width-1 character."""
import sys, random, unicodedata, uharfbuzz as hb
from fontTools.ttLib import TTFont
P, W = sys.argv[1], int(sys.argv[2])
f = TTFont(P); cmap = f.getBestCmap()
font = hb.Font(hb.Face(hb.Blob.from_file_path(P)))
letters = [c for c in cmap if 0x1820 <= c <= 0x1842]          # core Mongolian letters
todo = [c for c in cmap if 0x1843 <= c <= 0x185C]
extra = [0x180B, 0x180C, 0x180D, 0x180E]
def width(c):
    if c == 0x180E: return 1                      # MVS is drawn as a one-column gap
    return 0 if unicodedata.category(chr(c)) in ('Mn', 'Me', 'Cf') else 1
random.seed(1); bad = 0; N = 20000; examples = []
for _ in range(N):
    pool = letters if random.random() < .7 else todo + [0x1820, 0x1821, 0x1828, 0x182F, 0x1837]
    w = [random.choice(pool) for _ in range(random.randint(1, 8))]
    if random.random() < .15: w.insert(random.randint(1, len(w)), random.choice(extra))
    b = hb.Buffer(); b.add_codepoints(w); b.guess_segment_properties(); hb.shape(font, b)
    tot = sum(p.x_advance for p in b.glyph_positions); exp = W * sum(width(c) for c in w)
    if tot != exp:
        bad += 1
        if len(examples) < 8: examples.append((''.join(map(chr, w)), [hex(c) for c in w], tot, exp))
print(f'{P}: {bad}/{N} words off-grid')
for e in examples: print(' ', e)
