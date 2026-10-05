"""Preview fonts on a column grid; words are separated by one column (Latin space).

Usage: python3 preview_mono.py OUT.png 'LABEL|FONT.ttf[:grid]' ...
"""
import sys, uharfbuzz as hb, freetype, numpy as np
from PIL import Image, ImageDraw, ImageFont

TEXT = ['ᠮᠣᠩᠭᠣᠯ ᠥᠪᠥᠷ ᠤᠰᠤ ᠦᠨᠡᠨ', 'ᡐᡆᡑᡆ ᡆᡕᡅᠷᠠᡑ ᡔᡇᡏᡇ ᡑᡈᡋᡈᠨ']
COL = 600

def render_cols(path, lines, px=60, W=1300, H=230, grid=False):
    face = freetype.Face(path); face.set_char_size(px * 64); s = px / face.units_per_EM
    font = hb.Font(hb.Face(hb.Blob.from_file_path(path)))
    img = np.full((H, W), 255, np.uint8); lh = int(1.6 * px)
    for r, L in enumerate(lines):
        x = 20.0; base = 20 + r * lh + int(1.15 * px)
        for wi, word in enumerate(L.split(' ')):
            if wi: x += COL * s
            b = hb.Buffer(); b.add_str(word); b.guess_segment_properties(); hb.shape(font, b)
            for i, p in zip(b.glyph_infos, b.glyph_positions):
                face.load_glyph(i.codepoint, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING)
                g = face.glyph; bm = g.bitmap
                if bm.rows:
                    a = np.array(bm.buffer, np.uint8).reshape(bm.rows, bm.pitch)[:, :bm.width]
                    X = int(round(x + p.x_offset * s)) + g.bitmap_left
                    Y = base - int(round(p.y_offset * s)) - g.bitmap_top
                    x0, y0 = max(X, 0), max(Y, 0); x1, y1 = min(X + bm.width, W), min(Y + bm.rows, H)
                    if x1 > x0 and y1 > y0:
                        sub = img[y0:y1, x0:x1]; sub[:] = np.minimum(sub, 255 - a[y0 - Y:y1 - Y, x0 - X:x1 - X])
                x += p.x_advance * s
    im = Image.new('RGB', (W, H), (255, 255, 255)); d = ImageDraw.Draw(im)
    if grid:
        col = COL * s
        for i in range(int(W / col) + 1): d.line([(20 + i * col, 0), (20 + i * col, H)], fill=(160, 190, 255))
    im.paste((0, 0, 0), mask=Image.fromarray(255 - img))
    return im

if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    lf = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 30)
    ims = []
    for arg in sys.argv[2:]:
        lab, spec = arg.split('|', 1)
        path, _, g = spec.partition(':')
        im = render_cols(path, TEXT, grid=(g == 'grid')); d = ImageDraw.Draw(im)
        w = d.textlength(lab, font=lf); d.text((im.width - w - 12, 8), lab, fill=(200, 0, 0), font=lf)
        ims.append(im)
    out = Image.new('RGB', (ims[0].width, len(ims) * 240), (200, 200, 200))
    for k, i in enumerate(ims): out.paste(i, (0, k * 240))
    out.save(sys.argv[1])
