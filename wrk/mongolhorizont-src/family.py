"""Turn horiz.py output into a member of the MongolHorizont family:
set family/style names, style flags and Han-compatible vertical metrics.

Usage: python3 family.py SRC.ttf DST.ttf Regular|Italic
"""
import sys
from fontTools.ttLib import TTFont

FAMILY = 'MongolHorizont'
# Vertical metrics copied from Noto Sans CJK so mixed lines keep the Han line height
ASC, DSC = 1160, -288

def set_style(src, dst, style):
    f = TTFont(src)
    italic = style == 'Italic'
    ps = f'{FAMILY}-{style}'
    nt = f['name']
    for pid, eid, lid in [(3, 1, 0x409), (1, 0, 0)]:
        nt.setName(FAMILY, 1, pid, eid, lid)
        nt.setName(style, 2, pid, eid, lid)
        nt.setName(f'1.000;{ps}', 3, pid, eid, lid)
        nt.setName(f'{FAMILY} {style}', 4, pid, eid, lid)
        nt.setName(ps, 6, pid, eid, lid)
    for i in (16, 17, 21, 22):
        nt.removeNames(nameID=i)
    os2 = f['OS/2']
    os2.usWeightClass = 400
    sel = os2.fsSelection & ~((1 << 0) | (1 << 5) | (1 << 6))   # clear ITALIC, BOLD, REGULAR
    os2.fsSelection = sel | ((1 << 0) if italic else (1 << 6))
    mac = f['head'].macStyle & ~0b11                              # clear bold, italic
    f['head'].macStyle = mac | (0b10 if italic else 0)
    hh = f['hhea']; hh.ascent, hh.descent, hh.lineGap = ASC, DSC, 0
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = ASC, DSC, 0
    os2.usWinAscent, os2.usWinDescent = ASC, -DSC
    f.save(dst)
    print(dst, 'italicAngle', f['post'].italicAngle)

if __name__ == '__main__':
    if len(sys.argv) != 4 or sys.argv[3] not in ('Regular', 'Italic'):
        sys.exit(__doc__)
    set_style(*sys.argv[1:4])
