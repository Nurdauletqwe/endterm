import math, subprocess, wave, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

S = "static"; B = "static/before"
os.makedirs(B, exist_ok=True)
NAVY = (11, 61, 145)

DOC = '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M9.5 12h6M9.5 16h6"/>'
open(f"{S}/logo.svg", "w", encoding="utf-8").write(
 '<svg xmlns="http://www.w3.org/2000/svg" width="168" height="40" viewBox="0 0 168 40" role="img" aria-label="DocRequest">'
 '<rect x="2" y="2" width="36" height="36" rx="9" fill="#0B3D91"/>'
 '<g transform="translate(7 7) scale(1.1)" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + DOC + '</g>'
 '<text x="46" y="27" font-family="Segoe UI, Roboto, Arial, sans-serif" font-size="22" font-weight="700" fill="#0B3D91">DocRequest</text></svg>')
open(f"{S}/favicon.svg", "w", encoding="utf-8").write(
 '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40"><rect x="2" y="2" width="36" height="36" rx="9" fill="#0B3D91"/>'
 '<g transform="translate(7 7) scale(1.1)" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + DOC + '</g></svg>')

SS = 8
def bez(p0, p1, p2, p3, n=24):
    return [tuple((1-t)**3*a + 3*(1-t)**2*t*b + 3*(1-t)*t**2*c + t**3*d for a, b, c, d in zip(p0, p1, p2, p3))
            for t in [i/n for i in range(n+1)]]
ICONS = {
 "i-doc":    {"lines": [[(7,3),(14,3),(18,7),(18,21),(7,21),(7,3)], [(14,3),(14,7),(18,7)], [(9.5,12),(15.5,12)], [(9.5,16),(15.5,16)]], "circles": []},
 "i-send":   {"lines": [[(21,3),(3,10.5),(10,13),(12.5,20),(21,3)], [(10,13),(21,3)]], "circles": []},
 "i-pending":{"lines": [[(12,7),(12,12),(15,14)]], "circles": [(12,12,9)]},
 "i-check":  {"lines": [[(8,12.5),(11,15.5),(16,9.5)]], "circles": [(12,12,9)]},
 "i-cancel": {"lines": [[(9,9),(15,15)], [(15,9),(9,15)]], "circles": [(12,12,9)]},
 "i-user":   {"lines": [bez((4,21),(4,16.6),(7.6,14),(12,14)) + bez((12,14),(16.4,14),(20,16.6),(20,21))], "circles": [(12,8,4)]},
}
def draw_icon(spec, size, color, width=2.0, offset=(0, 0), img=None):
    k = size * SS / 24
    im = img or Image.new("RGBA", (size*SS, size*SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im); w = max(1, int(width*k))
    ox, oy = offset
    for pts in spec["lines"]:
        P = [((x*k)+ox, (y*k)+oy) for x, y in pts]
        d.line(P, fill=color, width=w, joint="curve")
        for x, y in (P[0], P[-1]):
            d.ellipse([x-w/2, y-w/2, x+w/2, y+w/2], fill=color)
    for cx, cy, r in spec["circles"]:
        d.ellipse([cx*k-r*k+ox, cy*k-r*k+oy, cx*k+r*k+ox, cy*k+r*k+oy], outline=color, width=w)
    return im
for name, spec in ICONS.items():
    draw_icon(spec, 36, (33, 37, 41, 255)).resize((36, 36), Image.LANCZOS).save(f"{B}/{name}.png", optimize=True)

W, H = 336, 80
im = Image.new("RGBA", (W*SS//4, H*SS//4), (0, 0, 0, 0)); sc = SS/4
d = ImageDraw.Draw(im)
d.rounded_rectangle([4*sc, 4*sc, 76*sc, 76*sc], radius=18*sc, fill=NAVY + (255,))
draw_icon(ICONS["i-doc"], 1, (255,255,255,255))  # no-op guard
k = 2.2 * sc
for pts in ICONS["i-doc"]["lines"]:
    P = [(14*sc + x*k, 14*sc + y*k) for x, y in pts]
    d.line(P, fill=(255,255,255,255), width=int(2*k), joint="curve")
    for x, y in (P[0], P[-1]): d.ellipse([x-k, y-k, x+k, y+k], fill=(255,255,255,255))
font = None
for f in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"]:
    if os.path.exists(f):
        size = int(40*sc)
        while size > 10 and ImageFont.truetype(f, size).getlength("DocRequest") > (W*SS//4 - 92*sc - 6*sc): size -= 2
        font = ImageFont.truetype(f, size); break
d.text((92*sc, 40*sc), "DocRequest", font=font or ImageFont.load_default(), fill=NAVY + (255,), anchor="lm")
im.resize((W, H), Image.LANCZOS).save(f"{B}/logo.png", optimize=True)

HW, HH = 2400, 1350
yy, xx = np.mgrid[0:HH, 0:HW].astype(np.float32)
t = (xx/HW*0.6 + yy/HH*0.4)[..., None]
c0, c1 = np.array([10, 38, 96], np.float32), np.array([29, 95, 184], np.float32)
hero = Image.fromarray((c0*(1-t) + c1*t).astype(np.uint8)).convert("RGBA")
def layer(): return Image.new("RGBA", (HW, HH), (0, 0, 0, 0))
L = layer(); d = ImageDraw.Draw(L)
d.ellipse([1500, -300, 2700, 900], fill=(255, 255, 255, 22)); d.ellipse([-300, 800, 700, 1700], fill=(255, 255, 255, 16))
hero = Image.alpha_composite(hero, L)
def shadow(box, r, blur_alpha=70, off=22):
    Ls = layer(); ImageDraw.Draw(Ls).rounded_rectangle([box[0]+off//2, box[1]+off, box[2]+off//2, box[3]+off], radius=r, fill=(0, 0, 0, blur_alpha))
    return Ls
PILLS = [((255, 243, 205), (102, 77, 3)), ((207, 226, 255), (8, 66, 152)), ((209, 231, 221), (10, 54, 34))]
hero = Image.alpha_composite(hero, shadow([1060, 850, 2380, 925], 22))
L = layer(); d = ImageDraw.Draw(L)
d.rounded_rectangle([1060, 850, 2380, 925], radius=22, fill=(226, 232, 242, 255))
d.rounded_rectangle([1560, 850, 1880, 880], radius=12, fill=(186, 196, 214, 255))
hero = Image.alpha_composite(hero, shadow([1180, 200, 2260, 860], 40))
L2 = layer(); d = ImageDraw.Draw(L2)
d.rounded_rectangle([1180, 200, 2260, 860], radius=40, fill=(15, 27, 51, 255))
d.rounded_rectangle([1214, 234, 2226, 826], radius=18, fill=(255, 255, 255, 255))
d.rectangle([1214, 234, 2226, 300], fill=NAVY + (255,))
d.rounded_rectangle([1236, 249, 1272, 285], radius=9, fill=(255, 255, 255, 255))
d.rounded_rectangle([1288, 258, 1470, 276], radius=8, fill=(255, 255, 255, 235))
for j in range(5):
    y0 = 330 + j*98
    d.line([(1236, y0+78), (2204, y0+78)], fill=(222, 226, 233, 255), width=3)
    d.rounded_rectangle([1236, y0+14, 1236+300-(j % 3)*50, y0+34], radius=9, fill=(33, 37, 41, 255))
    d.rounded_rectangle([1236, y0+44, 1236+200+(j % 2)*60, y0+60], radius=8, fill=(190, 198, 212, 255))
    bg, fg = PILLS[(j*2) % 3 if j < 3 else j % 3]
    d.rounded_rectangle([1900, y0+14, 2204, y0+62], radius=24, fill=bg + (255,))
    d.ellipse([1918, y0+26, 1942, y0+50], fill=fg + (255,))
    d.rounded_rectangle([1954, y0+30, 2080, y0+46], radius=8, fill=fg + (255,))
hero = Image.alpha_composite(hero, L); hero = Image.alpha_composite(hero, L2)
hero = Image.alpha_composite(hero, shadow([1930, 560, 2290, 1290], 56, 90, 26))
L = layer(); d = ImageDraw.Draw(L)
d.rounded_rectangle([1930, 560, 2290, 1290], radius=56, fill=(15, 27, 51, 255))
d.rounded_rectangle([1950, 585, 2270, 1265], radius=40, fill=(255, 255, 255, 255))
d.rectangle([1950, 585, 2270, 640], fill=NAVY + (255,))
for k, (yy0, ww) in enumerate([(670, 190), (790, 150), (910, 80)]):
    d.rounded_rectangle([1972, yy0, 1972+ww, yy0+16], radius=8, fill=(33, 37, 41, 255))
    d.rounded_rectangle([1972, yy0+30, 2248, yy0+86], radius=12, fill=(244, 246, 250, 255), outline=(190, 198, 212, 255), width=3)
d.rounded_rectangle([1972, 1030, 2248, 1092], radius=14, fill=(13, 110, 253, 255))
d.rounded_rectangle([2060, 1053, 2160, 1069], radius=8, fill=(255, 255, 255, 255))
d.rounded_rectangle([1972, 1126, 2248, 1230], radius=16, fill=(209, 231, 221, 255), outline=(163, 207, 187, 255), width=3)
d.ellipse([1990, 1152, 2038, 1200], fill=(25, 135, 84, 255))
d.line([(2002, 1177), (2012, 1187), (2028, 1166)], fill=(255, 255, 255, 255), width=7, joint="curve")
d.rounded_rectangle([2054, 1158, 2226, 1174], radius=8, fill=(10, 54, 34, 255))
d.rounded_rectangle([2054, 1186, 2190, 1200], radius=7, fill=(60, 120, 90, 255))
hero = Image.alpha_composite(hero, L).convert("RGB")
hero.save(f"{B}/hero-original.png", optimize=True)
hero.resize((640, 360), Image.LANCZOS).save(f"{S}/hero-640.webp", quality=80, method=6)
hero.resize((1280, 720), Image.LANCZOS).save(f"{S}/hero-1280.webp", quality=80, method=6)
hero.resize((640, 360), Image.LANCZOS).save(f"{S}/hero-640.jpg", quality=80, optimize=True, progressive=True)

a = hero.resize((640, 360)); px = np.asarray(a, np.float32)
def lin(c): c = c/255; return np.where(c <= 0.03928, c/12.92, ((c+0.055)/1.055)**2.4)
worst = 99.0
for xi in range(0, int(640*0.60)):
    al = 0.86 + (0.60-0.86)*xi/639
    for yi in range(int(360*0.25), int(360*0.80)):
        rgb = px[yi, xi]*(1-al) + np.array([10, 25, 50])*al
        Lm = (0.2126*lin(rgb[0]) + 0.7152*lin(rgb[1]) + 0.0722*lin(rgb[2]))
        worst = min(worst, 1.05/(Lm+0.05))
print(f"worst-case contrast white text / hero text area: {worst:.1f}:1")

sr = 44100; notes = [(880, 0.0), (1318.5, 0.16)]; n = int(sr*0.75)
sig = np.zeros(n)
for f, start in notes:
    i0 = int(start*sr); m = n - i0; tt = np.arange(m)/sr
    sig[i0:] += np.sin(2*np.pi*f*tt) * np.exp(-5.5*tt) * np.minimum(1, tt*400)
sig = (sig/np.abs(sig).max()*0.6*32767).astype(np.int16)
with wave.open("notification.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(sig.tobytes())
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "notification.wav", "-codec:a", "libmp3lame", "-b:a", "128k", f"{S}/notification.mp3"], check=True)
for root in (S, B, "."):
    for f in sorted(os.listdir(root)):
        p = os.path.join(root, f)
        if os.path.isfile(p) and f.split(".")[-1] in ("svg", "png", "webp", "jpg", "mp3", "wav"):
            print(f"{p:36s}{os.path.getsize(p)/1024:9.1f} KB")
