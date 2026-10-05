"""Empirically determine how many width-1 characters each glyph stands for."""
import itertools, uharfbuzz as hb, sys, json
from fontTools.ttLib import TTFont
from collections import defaultdict, Counter
P = sys.argv[1]
f = TTFont(P); order = f.getGlyphOrder(); cmap = f.getBestCmap(); hm = f['hmtx']
font = hb.Font(hb.Face(hb.Blob.from_file_path(P)))
ZERO = {0x180B, 0x180C, 0x180D, 0x180E, 0x180F, 0x200C, 0x200D}
letters = [c for c in cmap if 0x1820 <= c <= 0x1878 or 0x1880 <= c <= 0x18AA]
fvs = [0x180B, 0x180C, 0x180D, 0x180F]
import unicodedata
def width(c): return 0 if c in ZERO or unicodedata.category(chr(c)) in ("Mn", "Me", "Cf") else 1
ks = defaultdict(Counter)
def shape(cps):
    b = hb.Buffer(); b.add_codepoints(cps); b.guess_segment_properties()
    b.cluster_level = hb.BufferClusterLevel.CHARACTERS
    hb.shape(font, b)
    infos = b.glyph_infos
    # advancing glyphs in order; each owns chars from its cluster up to the next one's
    adv = [(i.cluster, order[i.codepoint]) for i in infos if hm[order[i.codepoint]][0] > 0]
    for k, (c0, g) in enumerate(adv):
        if g.startswith(('fvs', 'mvs')): continue
        if k > 0 and adv[k - 1][0] == c0:          # extra glyph of the same cluster
            ks[g][0] += 1; continue
        nxt = [c for c, _ in adv[k + 1:] if c > c0]
        c1 = nxt[0] if nxt else len(cps)
        nchar = sum(width(cps[j]) for j in range(c0, c1))
        ks[g][nchar] += 1
seqs = 0
for a in letters:
    for v in [[]] + [[x] for x in fvs]:
        for pos in range(4):
            ctx = {0: [], 1: [0x1820], 2: [], 3: [0x1820]}[pos]
            post = {0: [], 1: [0x1820], 2: [0x1820], 3: []}[pos]
            shape(ctx + [a] + v + post); seqs += 1
for a, b in itertools.product(letters, repeat=2):
    for pre in ([], [0x1820]):
        for post in ([], [0x1820]):
            shape(pre + [a, b] + post); seqs += 1
# random words catch ligatures that need wider context (vowel harmony etc.)
import random
random.seed(0)
core = [c for c in letters if c <= 0x1842]; todo = [c for c in letters if 0x1843 <= c <= 0x185C]
for _ in range(100000):
    pool = core if random.random() < .7 else todo + [0x1820, 0x1821, 0x1828, 0x182F, 0x1837]
    shape([random.choice(pool) for _ in range(random.randint(2, 8))]); seqs += 1
print('sequences', seqs)
multi = {g: dict(c) for g, c in ks.items() if len(c) > 1 or isinstance(g, tuple)}
print('inconsistent/multi-glyph clusters:', len(multi)); print(list(multi.items())[:20])
k = {g: c.most_common(1)[0][0] for g, c in ks.items() if isinstance(g, str)}
print(Counter(k.values()))
json.dump(k, open('k.json', 'w'))
