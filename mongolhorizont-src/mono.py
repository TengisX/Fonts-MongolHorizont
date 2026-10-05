"""Make an unslanted horiz.py output (mode 2) monospaced, then slant it.

Every Mongolian glyph gets an advance of k * W, where k is the number of
width-1 characters the glyph stands for (1 for most letters, 2 for
ligatures such as BA+A); k comes from k.json, produced by probe_k.py.

Per glyph, in the source design space:
  A. bring the advance to k * WC by lengthening or trimming the stem at both
     ends; glyphs that cannot be trimmed enough, or have no stem ends, are
     centred or compressed horizontally (stroke thickness kept);
  B. scale everything by S = W / WC about the Han ideographic centre line,
     again keeping stroke thickness;
  C. shear by SLANT degrees about the stem centre line.

Usage: python3 mono.py SRC.ttf DST.ttf K.json W WC SLANT
  W      final column width in font units (600 = most Latin monospace fonts)
  WC     common width the glyphs are first equalised to (W <= WC)
  SLANT  degrees, positive = top leans left, negative = right
"""
import sys, json, math
from fontTools.ttLib import TTFont
from fontTools.subset import Subsetter, Options
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

SRC, DST, KJSON = sys.argv[1:4]
W, WC, SLANT = float(sys.argv[4]), float(sys.argv[5]), float(sys.argv[6])
S = W / WC
STEM_LO, STEM_HI = 364, 444          # stem band of the mode-2 source
STEM_C = (STEM_LO + STEM_HI) / 2
YC = 380                             # Han ideographic centre (Noto Sans CJK: -120..880)
TRIM_MARGIN = 20                     # stem stub left in place when trimming
K = math.tan(math.radians(SLANT))
Y0 = YC + S * (STEM_C - YC)          # stem centre after scaling = shear pivot

font = TTFont(SRC)
glyf, hmtx = font['glyf'], font['hmtx']
kmap = json.load(open(KJSON))

# Mongolian glyphs: cmap + GSUB closure
cps = [c for c in font.getBestCmap() if 0x1800 <= c <= 0x18AF or 0x11660 <= c <= 0x1167F]
opts = Options(); opts.layout_features = ['*']; opts.glyph_names = True; opts.notdef_outline = True
ss = Subsetter(opts); ss.populate(unicodes=cps); tmp = TTFont(SRC); ss.subset(tmp)
mong = {g for g in tmp.getGlyphOrder() if g not in ('.notdef', 'space', 'uni00A0')}

# Decompose composites so each glyph can be reshaped independently
gs = font.getGlyphSet()
for n in sorted(mong):
    if glyf[n].isComposite():
        rec = DecomposingRecordingPen(gs); gs[n].draw(rec)
        pen = TTGlyphPen(None); rec.replay(pen); glyf[n] = pen.glyph()

def contours(g):
    out, s = [], 0
    for e in g.endPtsOfContours:
        out.append(list(g.coordinates[s:e + 1])); s = e + 1
    return out

def segments(cs):
    return [(c[i], c[(i + 1) % len(c)]) for c in cs for i in range(len(c))]

def ray_hit(p, d, segs, maxd=200):
    best = None
    for a, b in segs:
        ex, ey = b[0] - a[0], b[1] - a[1]
        den = d[0] * ey - d[1] * ex
        if abs(den) < 1e-9: continue
        wx, wy = a[0] - p[0], a[1] - p[1]
        t = (wx * ey - wy * ex) / den; u = (wx * d[1] - wy * d[0]) / den
        if 1.0 < t < maxd and 0 <= u <= 1 and (best is None or t < best): best = t
    return best

def centres(cs):
    """Stroke centre for every point: half way to the opposite edge along the inward normal."""
    segs, out = segments(cs), []
    for c in cs:
        n = len(c)
        for i, (x, y) in enumerate(c):
            (px, py), (nx, ny) = c[i - 1], c[(i + 1) % n]
            tx, ty = nx - px, ny - py; L = math.hypot(tx, ty) or 1
            d = (ty / L, -tx / L)
            h = ray_hit((x, y), d, segs)
            out.append((x, y) if h is None else (x + d[0] * h / 2, y + d[1] * h / 2))
    return out

def in_band(y): return STEM_LO - 1 <= y <= STEM_HI + 1

def stem_ends(pts, adv):
    """Indices of points on the left / right stem ends."""
    band = [x for x, y in pts if in_band(y)]
    if not band: return set(), set()
    bl, br = min(band), max(band)
    # leftmost band points at or left of the origin (stems may overlap leftwards),
    # rightmost band points at or beyond the advance
    L = {i for i, (x, y) in enumerate(pts) if in_band(y) and x <= 2 and x <= bl + 2}
    R = {i for i, (x, y) in enumerate(pts) if in_band(y) and x >= adv - 2 and x >= br - 2} - L
    return L, R

def split_band_edges(cs, flags, adv):
    """Split vertical outline edges at the outer stem ends where they cross the
    stem edges (e.g. a ring whose side runs straight up into the stem), so
    the stem end gets its own corner points."""
    band = [x for c in cs for x, y in c if in_band(y)]
    if not band: return cs, flags
    bl, br = min(band), max(band)
    out_c, out_f = [], []
    for c, fl in zip(cs, flags):
        n = len(c); nc, nf = [], []
        for i in range(n):
            p, q = c[i], c[(i + 1) % n]
            nc.append(p); nf.append(fl[i])
            if not (fl[i] and fl[(i + 1) % n]) or p[0] != q[0]: continue
            x = p[0]
            if not (abs(x - bl) <= 2 and x <= 2 or abs(x - br) <= 2 and x >= adv - 2): continue
            ys = [Y for Y in (STEM_LO, STEM_HI) if min(p[1], q[1]) < Y < max(p[1], q[1])]
            for Y in (ys if q[1] > p[1] else ys[::-1]):
                nc.append((x, Y)); nf.append(1)
        out_c.append(nc); out_f.append(nf)
    return out_c, out_f

def split_corners(cs, flags, L, R):
    """Where a stem-end point also starts a non-horizontal edge (a tooth flush
    with the glyph edge), duplicate it: one copy stays on the stem end, the
    other moves with the tooth, so the stem is lengthened horizontally."""
    out_c, out_f, roles, idx = [], [], [], 0
    for c, fl in zip(cs, flags):
        n = len(c); nc, nf = [], []
        for i, p in enumerate(c):
            gi = idx + i
            role = 'L' if gi in L else 'R' if gi in R else 'I'
            if role == 'I':
                nc.append(p); nf.append(fl[i]); roles.append('I'); continue
            prv, nxt = c[i - 1], c[(i + 1) % n]
            pi, ni = idx + (i - 1) % n, idx + (i + 1) % n
            pre = pi not in L and pi not in R and prv[1] != p[1]
            post = ni not in L and ni not in R and nxt[1] != p[1]
            if pre: nc.append(p); nf.append(1); roles.append('I')
            nc.append(p); nf.append(fl[i]); roles.append(role)
            if post: nc.append(p); nf.append(1); roles.append('I')
        idx += n; out_c.append(nc); out_f.append(nf)
    return out_c, out_f, roles

def plan_x(name, pts, adv, k, L, R):
    """Return (L, R, plain x-map for interior points, new advance in WC units)."""
    T = k * WC
    xs = [x for x, _ in pts]
    xr = max(xs)
    inner = [x for i, (x, _) in enumerate(pts) if i not in L and i not in R]
    if not inner:                                  # pure stem piece
        L, R = set(), set(); inner = xs
    lo, hi = min(inner), max(inner)
    d = T - adv
    if not L and not R:                            # no stem ends: centre or compress
        if d >= 0:
            return L, R, (lambda x: x + d / 2), T
        r = T / adv
        return L, R, (lambda x: x * r), T
    if d >= 0:                                     # lengthen the stem
        if L and R: sh = d / 2
        elif L: sh = d
        else: sh = 0
        return L, R, (lambda x: x + sh), T
    t = -d                                         # trim the stem, both ends
    tl = max(0, lo - TRIM_MARGIN) if L else 0
    tr = max(0, xr - hi - TRIM_MARGIN) if R else 0
    tL = min(tl, t / 2); tR = min(tr, t - tL); tL = min(tl, t - tR)
    rest = t - tL - tR
    if rest <= 0:
        return L, R, (lambda x: x - tL), T
    # still too wide: compress the inner part into the space left
    a0, a1 = lo - tL, hi - tL                       # inner span after trimming
    b0 = a0 if L else 0                             # keep left edge position
    span = (a1 - a0); target_span = span - rest
    r = target_span / span if span > 0 else 1
    return L, R, (lambda x: b0 + (x - tL - a0) * r), T

def write_contour(pen, pts, on):
    """Replay a TrueType contour (on/off-curve flags) into a pen."""
    n = len(pts)
    start = next((i for i in range(n) if on[i]), None)
    if start is None:                              # all off-curve: implied on-curve points
        pen.qCurveTo(*pts, None); return
    pts = pts[start:] + pts[:start]; on = on[start:] + on[:start]
    pen.moveTo(pts[0]); buf = []
    for p, o in zip(pts[1:] + [pts[0]], on[1:] + [1]):
        if o:
            if buf: pen.qCurveTo(*buf, p); buf = []
            else: pen.lineTo(p)
        else: buf.append(p)
    pen.closePath()

anchor_x = {}                                      # plain x-map per glyph for GPOS anchors

def process(name):
    g = glyf[name]
    adv = hmtx[name][0]
    k = kmap.get(name, 1 if adv > 0 else 0)
    anchor_x[name] = lambda x: x
    if name.startswith('mvs') or name == 'nnbsp':  # gaps: one empty column
        glyf[name] = TTGlyphPen(None).glyph(); hmtx[name] = (round(W), 0); return
    if name == 'nirugu.extend' or name.startswith('fvs'):
        k = 0                                      # stem extensions / stray FVS boxes
    newadv = round(k * W)
    if k == 0 and adv > 0:
        glyf[name] = TTGlyphPen(None).glyph(); hmtx[name] = (0, 0); return
    if g.numberOfContours <= 0:
        hmtx[name] = (newadv, 0); return
    cs = contours(g)
    flags, s0 = [], 0
    for e in g.endPtsOfContours:
        flags.append([g.flags[j] & 1 for j in range(s0, e + 1)]); s0 = e + 1
    pts = [p for c in cs for p in c]

    # A. equalise width to k * WC (skipped for zero-advance marks)
    edge = set()
    if adv > 0:
        T = k * WC
        L0, R0 = stem_ends(pts, adv)
        if T >= adv and (L0 or R0):
            # Lengthen: move the glyph and bridge the gaps with stem pieces,
            # which also works for joins that are curves rather than flat stem ends
            d = T - adv
            sh = d / 2 if L0 and R0 else d if L0 else 0
            cs = [[(x + sh, y) for x, y in c] for c in cs]
            OV = 25                                 # overlap of the bridge into the glyph
            if L0 and sh > 0:
                x0 = min(pts[i][0] for i in L0)
                cs.append([(x0, STEM_LO), (x0, STEM_HI), (x0 + sh + OV, STEM_HI), (x0 + sh + OV, STEM_LO)])
                flags.append([1, 1, 1, 1])
            if R0 and d - sh > 0:
                x1 = max(pts[i][0] for i in R0)
                cs.append([(x1 + sh - OV, STEM_LO), (x1 + sh - OV, STEM_HI), (x1 + d, STEM_HI), (x1 + d, STEM_LO)])
                flags.append([1, 1, 1, 1])
            pts = [p for c in cs for p in c]
            n_old = sum(len(c) for c in cs) - 4 * (int(bool(L0) and sh > 0) + int(bool(R0) and d - sh > 0))
            edge = set(range(n_old, len(pts)))      # bridge corners stay exact
            anchor_x[name] = lambda x, sh=sh: x + sh
        else:
            cs, flags = split_band_edges(cs, flags, adv)
            pts = [p for c in cs for p in c]
            L0, R0 = stem_ends(pts, adv)
            cs, flags, roles = split_corners(cs, flags, L0, R0)
            pts = [p for c in cs for p in c]
            L = {i for i, r in enumerate(roles) if r == 'L'}
            R = {i for i, r in enumerate(roles) if r == 'R'}
            L, R, fx, T = plan_x(name, pts, adv, k, L, R)
            cen = centres(cs)
            new = []
            for i, ((x, y), (cx, cy)) in enumerate(zip(pts, cen)):
                if i in L: nx = x
                elif i in R: nx = T + (x - adv)
                else: nx = fx(cx) + (x - cx)
                new.append((nx, y))
            anchor_x[name] = fx
            cs, j = [], 0
            for c in flags:
                cs.append(new[j:j + len(c)]); j += len(c)
            pts = new
            edge = L | R

    # B. scale by S about (0, YC), keeping stroke thickness; C. shear
    cen = centres(cs)
    out = []
    for i, ((x, y), (cx, cy)) in enumerate(zip(pts, cen)):
        if i in edge:                              # stem ends: exact, on the stem centre line
            cx, cy = x, STEM_C
        elif abs(y - STEM_LO) <= 1 or abs(y - STEM_HI) <= 1:
            cy = STEM_C                            # keep stem edges straight and 80 units apart
        nx = S * cx + (x - cx)
        ny = YC + S * (cy - YC) + (y - cy)
        out.append((round(nx - K * (ny - Y0)), round(ny)))
    pen = TTGlyphPen(None); j = 0
    for c, fl in zip(cs, flags):
        seg = out[j:j + len(c)]; j += len(c)
        write_contour(pen, seg, fl)
    ng = pen.glyph(); glyf[name] = ng; g = ng
    g.recalcBounds(glyf)
    hmtx[name] = (newadv, g.xMin)

for n in sorted(mong):
    process(n)

def fix_anchor(a, gn):
    if a is None: return
    x = anchor_x.get(gn, lambda v: v)(a.XCoordinate)
    y = YC + S * (a.YCoordinate - YC)
    x = S * x
    a.XCoordinate, a.YCoordinate = round(x - K * (y - Y0)), round(y)

for lk in font['GPOS'].table.LookupList.Lookup:
    for st in lk.SubTable:
        if lk.LookupType == 9: st = st.ExtSubTable
        t = st.LookupType if hasattr(st, 'LookupType') else lk.LookupType
        if t in (4, 6):
            marks = st.MarkCoverage.glyphs if t == 4 else st.Mark1Coverage.glyphs
            for gn, rec in zip(marks, st.MarkArray.MarkRecord):
                if gn in mong: fix_anchor(rec.MarkAnchor, gn)
            bases = (zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord) if t == 4 else
                     zip(st.Mark2Coverage.glyphs, st.Mark2Array.Mark2Record))
            for gn, rec in bases:
                if gn in mong:
                    for a in (rec.BaseAnchor if t == 4 else rec.Mark2Anchor): fix_anchor(a, gn)
        elif t == 3:
            for gn, rec in zip(st.Coverage.glyphs, st.EntryExitRecord):
                if gn in mong: fix_anchor(rec.EntryAnchor, gn); fix_anchor(rec.ExitAnchor, gn)

font['post'].italicAngle = SLANT
font['post'].isFixedPitch = 0                      # Latin glyphs in the font stay proportional
font.save(DST)
print(DST, 'W', W, 'WC', WC, 'scale', round(S, 3), 'slant', SLANT)
