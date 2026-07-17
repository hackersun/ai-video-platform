#!/usr/bin/env python3
from __future__ import annotations
import argparse, signal, tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from PIL import Image, ImageDraw

def build(path: Path):
    w,h=1536,1024; image=Image.new('RGB',(w,h),'#e8e2d6'); draw=ImageDraw.Draw(image); split=int(w*.60); pw=split//3
    for i in range(3):
        x=i*pw; draw.rectangle((x+8,8,x+pw-8,h-8),fill=(220-i*8,230,235+i*5),outline='#203040',width=5); cx=x+pw//2+(i-1)*12
        draw.ellipse((cx-55,120,cx+55,230),fill='#d8ad8b',outline='#182838',width=8); draw.polygon(((cx-90,250),(cx+90,250),(cx+125-i*15,760),(cx-110+i*12,760)),fill='#243a59',outline='#102030')
        draw.line((cx-60,360,cx-135+i*20,590),fill='#102030',width=22); draw.line((cx+60,360,cx+135-i*20,590),fill='#102030',width=22)
    draw.rectangle((split,0,w-1,h-1),fill='#162334',outline='#e0c080',width=6)
    for y in range(60,620,45): draw.line((split+35,y,w-35,y+(y%90)-30),fill=(65+y%80,90,120),width=7)
    colors=['#1b2a41','#406080','#c08a52','#e0c9a6','#7f3448']; sw=(w-split-80)//len(colors)
    for i,color in enumerate(colors):
        x=split+40+i*sw; draw.rectangle((x,700,x+sw-12,930),fill=color,outline='white',width=4)
    image.save(path,'PNG')

def main():
    p=argparse.ArgumentParser(); p.add_argument('--port',type=int,required=True); args=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='ai-video-reference-') as directory:
        root=Path(directory); build(root/'valid-composite.png')
        handler=lambda *a,**kw: SimpleHTTPRequestHandler(*a,directory=str(root),**kw)
        server=ThreadingHTTPServer(('127.0.0.1',args.port),handler); signal.signal(signal.SIGTERM,lambda *_: server.shutdown())
        print(f'reference fixture ready on 127.0.0.1:{args.port}',flush=True); server.serve_forever()
if __name__=='__main__': main()
