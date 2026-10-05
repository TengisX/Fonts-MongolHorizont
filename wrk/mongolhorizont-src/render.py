"""Render a text preview of a font with HarfBuzz shaping.

Usage: python3 render.py FONT.ttf OUT.png [TEXT_LINE ...]
"""
import sys, uharfbuzz as hb, freetype, numpy as np
from PIL import Image, ImageDraw
def render(path,lines,out,px=72,guides=None):
    face=freetype.Face(path); face.set_char_size(px*64); upem=face.units_per_EM; s=px/upem
    font=hb.Font(hb.Face(hb.Blob.from_file_path(path)))
    lh=int(1.6*px); W=1200; img=np.full((len(lines)*lh+40,W),255,np.uint8)
    for r,L in enumerate(lines):
        b=hb.Buffer();b.add_str(L);b.guess_segment_properties();hb.shape(font,b)
        x=20; base=20+r*lh+int(1.15*px)
        for i,p in zip(b.glyph_infos,b.glyph_positions):
            face.load_glyph(i.codepoint, freetype.FT_LOAD_RENDER|freetype.FT_LOAD_NO_HINTING)
            g=face.glyph; bm=g.bitmap
            if bm.rows:
                a=np.array(bm.buffer,np.uint8).reshape(bm.rows,bm.pitch)[:,:bm.width]
                X=int(round(x+p.x_offset*s))+g.bitmap_left; Y=base-g.bitmap_top
                sub=img[Y:Y+bm.rows,X:X+bm.width]; sub[:]=np.minimum(sub,255-a[:sub.shape[0],:sub.shape[1]])
            x+=p.x_advance*s
    im=Image.fromarray(img).convert('RGB')
    if guides:
        d=ImageDraw.Draw(im)
        for r in range(len(lines)):
            base=20+r*lh+int(1.15*px)
            for gy,col in guides: d.line([(0,base-gy*s),(W,base-gy*s)],fill=col)
    im.save(out)
TEXT=["ᠮᠣᠩᠭᠣᠯ ᠪᠢᠴᠢᠭ","ᠬᠡᠪᠲᠡᠭᠡ ᠤᠰᠤᠭ ᠰᠣᠨᠢᠨ","ᠥᠪᠥᠷ ᠮᠣᠩᠭᠣᠯ ᠤᠨ ᠶᠡᠬᠡ ᠰᠤᠷᠭᠠᠭᠤᠯᠢ"]
if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    render(sys.argv[1], sys.argv[3:] or TEXT, sys.argv[2])
