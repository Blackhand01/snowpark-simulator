"""Review sheets from actual Blender PNGs, without retouching their content."""
import argparse,json,hashlib
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();out=a.output.resolve()
    from PIL import Image,ImageDraw,ImageFont,__version__
    font_path=Path('/System/Library/Fonts/Helvetica.ttc')
    font=ImageFont.truetype(str(font_path),24) if font_path.exists() else ImageFont.load_default()
    small=ImageFont.truetype(str(font_path),18) if font_path.exists() else ImageFont.load_default()
    pair=json.loads((out/'appearance-comparison.json').read_text())
    panel=Image.new('RGB',(1600,870),'#f4f6f8');draw=ImageDraw.Draw(panel)
    for i,name in enumerate(['before','after']):
        label='PRIMA' if i==0 else 'DOPO'
        draw.text((i*800+20,12),label,font=font,fill='#172432')
        draw.text((i*800+20,44),'Stessa camera, luce e impostazioni; sola rifinitura atleta',font=small,fill='#43556a')
        panel.paste(Image.open(out/(name+'.png')).convert('RGB').resize((800,800),Image.Resampling.LANCZOS),(i*800,70))
    panel.save(out/'before-after.png')
    panel=Image.new('RGB',(1600,1710),'#f4f6f8');draw=ImageDraw.Draw(panel)
    for i,(name,label) in enumerate([('portrait.png','ATLETA'),('back.png','RETRO / SILHOUETTE'),('face.png','CASCO / MASCHERA'),('equipment.png','SCARPONI / ATTACCHI')]):
        x=(i%2)*800;y=(i//2)*855
        draw.text((x+20,y+14),label,font=font,fill='#172432')
        panel.paste(Image.open(out/name).convert('RGB').resize((800,800),Image.Resampling.LANCZOS),(x,y+55))
    panel.save(out/'presentation-sheet.png')
    files={f.name:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in out.iterdir()
           if f.is_file() and f.suffix in ['.png','.blend','.toml']}
    (out/'artifact-manifest.json').write_text(json.dumps(dict(files=files,pillow=__version__,image_processing='Layout and proportional resizing only; no retouching'),indent=2)+'\n')
    print('REVIEW_SHEETS_WRITTEN',len(files))


if __name__=='__main__':main()
