"""Reshape Noto Sans Mongolian for horizontal (left-to-right) reading.

Moves the stem so that its centre sits at RATIO of the glyph height below
the top, optionally slants the glyphs, and keeps advance widths and stroke
thickness.

Usage: python3 horiz.py SRC.ttf DST.ttf [SLANT] [FAMILY] [RATIO] [MODE]
  SLANT   degrees, positive = top leans left, negative = right (default 0)
  FAMILY  family name written to the name table (default 'NSM Horizontal Test')
  RATIO   stem-centre depth from the top in units of glyph height
          (default: golden section 0.382)
  MODE    0 = stretch below / compress above, total height kept
          1 = as 0, but ring letters (o/u/oe/ue) are not stretched below
          2 = nothing below the stem changes; only the part above is
              compressed (total height shrinks)
"""
import sys, math
from fontTools.ttLib import TTFont
from fontTools.subset import Subsetter, Options

SRC, DST = sys.argv[1], sys.argv[2]
STEM_LO, STEM_HI = 364, 444          # stem band in the source font
TOP, BOT = 1059, -266                # global extent of Mongolian glyphs
H = TOP - BOT
RATIO = float(sys.argv[5]) if len(sys.argv) > 5 else (3 - 5 ** 0.5) / 2  # stem centre depth from top, in units of H (default: golden section)
MODE = sys.argv[6] if len(sys.argv) > 6 else '0'
C0 = (STEM_LO + STEM_HI) / 2
if MODE == '2':
    TOP_NEW = (C0 - RATIO * BOT) / (1 - RATIO)   # solves (TOP_NEW - C0) = RATIO * (TOP_NEW - BOT)
    new_c = C0
else:
    TOP_NEW = TOP
    new_c = TOP - H * RATIO              # target stem centre
shift = new_c - C0
NLO, NHI = STEM_LO + shift, STEM_HI + shift
SLANT = float(sys.argv[3]) if len(sys.argv) > 3 else 0  # degrees, positive = top leans left
K = math.tan(math.radians(SLANT))
Y0 = (NLO + NHI) / 2                 # shear pivot on the stem centre line

def sx(x, y):
    """Horizontal shear about the stem centre; joins on the stem stay exact."""
    return x - K * (y - Y0)

def f(y):
    """Piecewise-linear vertical map. Modes 0/1: stretch below the stem,
    rigid stem band, compress above, TOP/BOT fixed. Mode 2: identity up to
    the stem top, compress above."""
    if MODE == '2':
        if y <= STEM_HI:
            return y
        return STEM_HI + (y - STEM_HI) * (TOP_NEW - STEM_HI) / (TOP - STEM_HI)
    if y < STEM_LO:
        return BOT + (y - BOT) * (NLO - BOT) / (STEM_LO - BOT)
    if y <= STEM_HI:
        return y + shift
    return NHI + (y - STEM_HI) * (TOP - NHI) / (TOP - STEM_HI)

def f_ring(y):
    """Map for ring (o/u/oe/ue) glyphs: the part below the stem is only
    translated with the stem, the part above is compressed as usual."""
    return y + shift if y <= STEM_HI else f(y)

KEEP_RING = MODE == '1'

font = TTFont(SRC)
glyf = font['glyf']

# Collect all Mongolian glyphs (cmap + GSUB closure)
cps = [c for c in font.getBestCmap() if 0x1800 <= c <= 0x18AF or 0x11660 <= c <= 0x1167F]
opts = Options(); opts.layout_features = ['*']; opts.glyph_names = True; opts.notdef_outline = True
ss = Subsetter(opts); ss.populate(unicodes=cps)
tmp = TTFont(SRC); ss.subset(tmp)
mong = {g for g in tmp.getGlyphOrder() if g not in ('.notdef', 'space', 'uni00A0')}

def closure(cps):
    t = TTFont(SRC); s_ = Subsetter(opts); s_.populate(unicodes=cps); s_.subset(t)
    return set(t.getGlyphOrder())

# Glyphs of the ring letters o, u, oe, ue (traditional and Todo), plus any
# composite that reuses one of them (e.g. medial/final forms of other letters)
ring = set()
if KEEP_RING:
    base0 = closure([])
    for cp in (0x1823, 0x1824, 0x1825, 0x1826, 0x1846, 0x1847, 0x1848, 0x1849):
        ring |= closure([cp]) - base0
    ring &= mong
    for n in mong:
        g = font['glyf'][n]
        if g.isComposite() and any(c.glyphName in ring for c in g.components):
            ring.add(n)

def flatten(coords, ends):
    """Approximate the outline as line segments (on- and off-curve points as a polygon)."""
    segs, s = [], 0
    for e in ends:
        pts = coords[s:e + 1]
        for i in range(len(pts)):
            segs.append((pts[i], pts[(i + 1) % len(pts)]))
        s = e + 1
    return segs

def ray_hit(p, d, segs, maxd=200):
    """Distance from p along direction d to the nearest outline segment."""
    best = None
    for (a, b) in segs:
        ex, ey = b[0] - a[0], b[1] - a[1]
        den = d[0] * ey - d[1] * ex
        if abs(den) < 1e-9: continue
        wx, wy = a[0] - p[0], a[1] - p[1]
        t = (wx * ey - wy * ex) / den
        u = (wx * d[1] - wy * d[0]) / den
        if 1.0 < t < maxd and 0 <= u <= 1:
            best = t if best is None or t < best else best
    return best

def transform(name):
    fm = f_ring if name in ring else f
    g = glyf[name]
    if g.numberOfContours <= 0: return
    coords = list(g.coordinates); ends = g.endPtsOfContours
    segs = flatten(coords, ends)
    # orientation: TrueType outer contours are clockwise -> inward normal is right-hand
    new, s = [], 0
    for e in ends:
        pts = coords[s:e + 1]; n = len(pts)
        for i, (x, y) in enumerate(pts):
            px, py = pts[i - 1]; nx, ny = pts[(i + 1) % n]
            tx, ty = nx - px, ny - py; L = math.hypot(tx, ty) or 1
            inward = (ty / L, -tx / L)
            d = ray_hit((x, y), inward, segs)
            if d is None:
                yc = y
            else:
                yc = y + inward[1] * d / 2      # stroke centre (y component)
            ny_ = fm(yc) + (y - yc)
            new.append((round(sx(x, ny_)), round(ny_)))
        s = e + 1
    for i, c in enumerate(new): g.coordinates[i] = c
    g.recalcBounds(glyf)

for name in mong:
    if not glyf[name].isComposite(): transform(name)
for name in mong:
    g = glyf[name]
    if g.isComposite():
        for c in g.components:
            c.y = round(f(c.y + STEM_LO) - f(STEM_LO)) if c.y else 0
            c.x = round(c.x - K * c.y)
        g.recalcBounds(glyf)

# Sync hmtx left side bearings with the new xMin; renderers position the
# outline by lsb, so a stale lsb shifts sheared glyphs and breaks the joins
hmtx = font['hmtx']
for name in mong:
    adv, _ = hmtx[name]
    g = glyf[name]
    hmtx[name] = (adv, g.xMin if g.numberOfContours != 0 else 0)

# Map GPOS anchors of Mongolian glyphs
def fix_anchor(a, gn=None):
    if a is not None:
        a.YCoordinate = round((f_ring if gn in ring else f)(a.YCoordinate))
        a.XCoordinate = round(sx(a.XCoordinate, a.YCoordinate))
for lk in font['GPOS'].table.LookupList.Lookup:
    for st in lk.SubTable:
        if lk.LookupType == 9: st = st.ExtSubTable
        t = st.LookupType if hasattr(st, 'LookupType') else lk.LookupType
        if t in (4, 6):
            marks = st.MarkCoverage.glyphs if t == 4 else st.Mark1Coverage.glyphs
            for gn, rec in zip(marks, st.MarkArray.MarkRecord):
                if gn in mong: fix_anchor(rec.MarkAnchor, gn)
            if t == 4:
                for gn, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                    if gn in mong:
                        for a in rec.BaseAnchor: fix_anchor(a, gn)
            else:
                for gn, rec in zip(st.Mark2Coverage.glyphs, st.Mark2Array.Mark2Record):
                    if gn in mong:
                        for a in rec.Mark2Anchor: fix_anchor(a, gn)
        elif t == 3:
            for gn, rec in zip(st.Coverage.glyphs, st.EntryExitRecord):
                if gn in mong: fix_anchor(rec.EntryAnchor, gn); fix_anchor(rec.ExitAnchor, gn)

# Drop TrueType hinting (instructions refer to old outlines)
for n in glyf.keys():
    gg = glyf[n]
    if hasattr(gg, 'program'): gg.program.fromBytecode(b'')
for t in ('fpgm', 'prep', 'cvt '):
    if t in font: del font[t]
# post.italicAngle: counter-clockwise from vertical, so left lean is positive
font['post'].italicAngle = SLANT
fam = sys.argv[4] if len(sys.argv) > 4 else 'NSM Horizontal Test'
nt = font['name']
for pid, eid, lid in [(3, 1, 0x409), (1, 0, 0)]:
    nt.setName(fam, 1, pid, eid, lid); nt.setName('Regular', 2, pid, eid, lid)
    nt.setName(fam + ' Regular', 4, pid, eid, lid)
    nt.setName(fam.replace(' ', '') + '-Regular', 6, pid, eid, lid)
for i in (16, 17): nt.removeNames(nameID=i)
font.save(DST)
print('mode', MODE, 'top', round(TOP_NEW), 'glyphs transformed:', len(mong), 'ring glyphs:', len(ring), 'stem ->', NLO, NHI)
