"""Plate typography, profile circle and same-pixel Facebook crop."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

path,kind,mode = sys.argv[1:]
path=Path(path)
directory=path.parent
fonts=directory.parents[2]/'assets/fonts'
ed=directory.parent.name=='di-belakang-tabir'
plate=Image.open(path).convert('RGBA')
W,H=plate.size
if kind=='logo':
    base=Image.new('RGBA',plate.size,'#142b35' if ed else '#1b343e')
    d=ImageDraw.Draw(base)
    d.ellipse((0,0,W-1,H-1),fill='#18313C' if ed else '#213E4B')
    base.alpha_composite(plate)
    master=base.convert('RGB')
    master.save(directory/('logo.png' if mode=='final' else '.logo-proof.png'))
    if mode=='final':
        board=Image.new('RGB',(420,220),'#f1f3f5')
        for x,n in [(19,48),(87,96),(214,180)]:
            small=master.resize((n,n),Image.Resampling.LANCZOS)
            mask=Image.new('L',(n*4,n*4))
            ImageDraw.Draw(mask).ellipse((0,0,n*4-1,n*4-1),fill=255)
            mask=mask.resize((n,n),Image.Resampling.LANCZOS)
            board.paste(small,(x,(220-n)//2),mask)
            if n==48:
                thumb=small.convert('RGBA')
                thumb.putalpha(mask)
                thumb.save(directory/'logo_48.png')
        board.save(directory/'logo_check.png')
else:
    master=plate.convert('RGB')
    draw=ImageDraw.Draw(master)
    factor=W/1640
    def letters(words, family, size, cx, cy, colour):
        font=ImageFont.truetype(str(fonts/(family+'-Bold.ttf')),round(size*factor))
        draw.text((cx*factor,cy*factor),words,font=font,fill=colour,anchor='mm',stroke_width=0)
    if ed:
        letters('Di Belakang Tabir','Montserrat',70,963,152,'#FAF8EF')
        letters('Dalam Benda','Montserrat',28,963,220,'#FAF8EF')
    else:
        letters('Kita Buat Dia','Oswald',74,909,211,'#FFF4DB')
        letters('Bengkel Bar','Montserrat',27,909,282,'#FFF4DB')
    master.save(directory/('cover.png' if mode=='final' else '.cover-proof.png'))
    if mode=='final':
        master.crop((0,48,1640,672)).save(directory/'cover_fb_1640x624.png')
