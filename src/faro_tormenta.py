"""An oblique ASCII world with surface-specific weather and an articulated knight."""
import os
from math import atan2, cos, pi, sin
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw

from caballero_del_faro import Scene as Panel, SIZE, ease
import caballero_montado

NAME = 'El caballero del faro - La tormenta'
COLS, ROWS = 108, 120
CELL_W, CELL_H = 5, 8
Y, X = np.mgrid[:ROWS, :COLS]
GLYPHS = " .`',:;!+=-~_/\\|()[]{}<>x*#%oO@&^v"
SEA, GRASS, ROAD, ROCK, STONE, ROOF, LEAVES, WOOD, STEEL, CLOTH, GOLD, DARK, FIRE = range(13)
MATERIALS = (
    ((58, 129, 156), "   .,:~=-_"),
    ((67, 136, 104), " .`',;!/\\|"),
    ((122, 150, 164), " .:;=-+#%"),
    ((119, 130, 145), " .:/\\+#%"),
    ((155, 174, 184), " .:;=-+#%"),
    ((85, 114, 131), " .:-=/\\|"),
    ((70, 135, 106), " .:;/\\x*#"),
    ((97, 79, 71), " .:'=-|%"),
    ((225, 245, 255), " :=+x#%@@"),
    ((219, 69, 88), " :;/x#%@@"),
    ((221, 180, 112), ".:=+*#%@"),
    ((39, 53, 66), " .:;=-#"),
    ((255, 199, 87), "+*x#%@@"),
)
PATH = ((-10, 21, .5), (-8, 14, .5), (-6, 8, .5), (-2, 4, .5),
        (3, 1, .5), (6, -4, .55), (9, -7, 1), (9, -11, 2.8))
KEYS = (0, 4, 8, 11, 14, 17, 19, 20)
BEACON = (9, -12, 6.4)


TRACK = np.array(PATH)
INTERVALS = np.diff(KEYS)
SLOPES = np.diff(TRACK, axis=0) / INTERVALS[:, None]
TANGENTS = np.zeros_like(TRACK, dtype=float)
same_direction = SLOPES[:-1] * SLOPES[1:] > 0
np.divide(2*SLOPES[:-1]*SLOPES[1:], SLOPES[:-1]+SLOPES[1:],
          out=TANGENTS[1:-1], where=same_direction)


def route(time):
    """Interpolate the path with continuous velocity through the bends."""
    index = int(np.clip(np.searchsorted(KEYS, time, side='right')-1, 0, len(KEYS)-2))
    interval = INTERVALS[index]
    u = float(np.clip((time-KEYS[index])/interval, 0, 1))
    return ((1-ease(u))*TRACK[index] + ease(u)*TRACK[index+1]
            + interval*(u*(1-u)**2*TANGENTS[index] - u*u*(1-u)*TANGENTS[index+1]))


def gust(time):
    return .36*sin(time*1.55) + .18*sin(time*3.32+.9) + .11*sin(time*6.5)


def land_edge(y):
    return 3.6 + np.sin(y*.29)*2.1 + np.cos(y*.63)*.8


def face(center, dimensions, material, yaw=0):
    x, y, z = center
    w, d, h = np.asarray(dimensions)/2
    c, s = cos(yaw), sin(yaw)
    corners = [(x+u*c-v*s, y+u*s+v*c, z+k) for k in (-h, h)
               for u, v in ((-w,-d), (w,-d), (w,d), (-w,d))]
    return [(tuple(corners[i] for i in ids), material, shade)
            for ids, shade in (((0, 1, 5, 4), .38), ((1, 2, 6, 5), .59),
                               ((2, 3, 7, 6), .81), ((3, 0, 4, 7), .46),
                               ((4, 5, 6, 7), 1.25))]


def strip(a, b, width, material):
    x, y, z = a
    u, v, w = b
    angle = atan2(v-y, u-x)
    dx, dy = -sin(angle)*width/2, cos(angle)*width/2
    top = ((x+dx,y+dy,z), (u+dx,v+dy,w), (u-dx,v-dy,w), (x-dx,y-dy,z))
    side = tuple((p[0],p[1],p[2]-.58) for p in top)
    return [(top, material, 1.13), ((top[0],top[1],side[1],side[0]), STONE, .62),
            ((top[2],top[3],side[3],side[2]), ROCK, .77)]


@lru_cache(maxsize=3)
def prepare(font, atlas):
    return Scene(font, atlas)


class Scene(Panel):
    def __init__(self, font, atlas):
        self.heading = font('consola.ttf', 16)
        self.caption = font('consola.ttf', 12)
        self.signature = font('seguisym.ttf' if os.name == 'nt' else 'georgia.ttf', 15)
        self.atlas = atlas(font('consola.ttf', 8), GLYPHS, CELL_W, CELL_H).astype('uint16')
        self.tables = np.array([[GLYPHS.index(ramp[min(len(ramp)-1, int(i*len(ramp)/64))])
                                 for i in range(64)] for _, ramp in MATERIALS])
        self.colors = np.asarray([color for color, _ in MATERIALS], dtype=np.float32)
        self.excerpt = (
            'phase = (stride+offset)%1',
            'lift = 13*sin(pi*swing)*moving',
            'radius = .045 + age*.88',
        )
        rng = np.random.default_rng(9903)
        self.drops = rng.random((340, 4))
        self.world = self.build(rng)
        bounds = []
        for points, _, _ in self.world:
            u = [x-.27*y for x,y,z in points]
            v = [.65*y-z for x,y,z in points]
            bounds.append((min(u),max(u),min(v),max(v)))
        self.bounds = np.array(bounds).T

    def build(self, rng):
        mesh = []
        for a, b in zip(PATH[:6], PATH[1:6]):
            mesh.extend(strip(a, b, 3.2, ROAD))
            for t in (.13, .40, .68, .94):
                p = np.asarray(a)*(1-t)+np.asarray(b)*t
                angle = atan2(b[1]-a[1], b[0]-a[0])
                for side in (-1, 1):
                    q = p + np.array((-sin(angle)*1.54*side, cos(angle)*1.54*side, .21))
                    mesh.extend(face(q, (.63, .28, .45), STONE, angle))
        for i in range(12):
            mesh.extend(face((9, -6.9-i*.38, .28+i*.194), (2.55,.52,.56), STONE))
        for x in (7.08, 10.92):
            mesh.extend(face((x,-10.75,3.28), (.65,1.05,4.05), STONE))
            for height in (2.15, 3.05, 4.1, 4.95):
                mesh.extend(face((x, -10.73, height), (.8, 1.2, .135), STONE))
        mesh.extend(face((9,-11.15,5.15), (4.5,1.25,.62), STONE))
        mesh.extend(face((9,-12.55,2.36), (5.25,5.5,.82), ROCK))
        mesh.extend(face((9,-12.95,5.72), (4.9,4.8,.5), STONE))
        mesh.extend(face((9,-13.55,5.18), (4.4,2.55,.72), STONE))
        for i in range(6):
            x = 6.8 + i*.88
            mesh.extend(face((x,-14.95,6.16), (.46,.55,.7), STONE))
            if i in (0, 1, 4, 5):
                mesh.extend(face((x,-10.75,6.16), (.46,.55,.7), STONE))
        for x in (6.66, 11.32):
            mesh.extend(face((x,-12.65,3.89), (.8,3.1,3.2), STONE))
        mesh.extend(face((9,-12,6.09), (1.06,.91,.34), GOLD))
        for _ in range(78):
            y = rng.uniform(-24,25)
            x = land_edge(y)+rng.uniform(.15,13)
            if abs(x-9) < 3 and -16 < y < -5:
                continue
            h = rng.uniform(.28,1.9)
            mesh.extend(face((x,y,h*.26), (h*rng.uniform(.8,1.6),h,h*.53), ROCK, rng.uniform(-pi,pi)))
        for x, y, h in ((-12,23,4),(1,9,3.7),(7,8,4.7),(11,3,5.4),(14,-4,5),
                        (2,-8,3.6),(4,-16,4.2),(14,-17,5),(5,0,4),(13,-23,4.9)):
            mesh.extend(face((x,y,h*.25), (.28,.28,h*.5), WOOD))
            for i in range(6):
                z = h*(.34+i*.115)
                size = h*(.45-i*.06)
                mesh.extend(face((x+.14*sin(i*2),y,z), (size,size*.66,.35*h), LEAVES, .32*i))
        for x,y in ((-16,16),(-17,13),(-18,18),(-15,22),(-18,21),(-11,24)):
            for i in range(5):
                span = 1.7 - i*.26
                mesh.extend(face((x,y,i*.63+.6), (span,span*.76,1.13), LEAVES, i*.55))
        for x,y,w in ((-11.3,13.3,1.1),(-3.9,11.3,.9),(-8,1.3,1.9),(-3.5,-4,2.3),(-12.4,-12,1.65)):
            mesh.extend(face((x,y,.18), (w,w*.56,.56), ROCK, .61))
        for y in (-13.85, -12.97, -12.09):
            mesh.extend(face((6.22,y,3.74), (.21,.39,2.8), STONE))
        for z in (2.95,3.49,4.36,5.65):
            for x in (6.35, 11.65):
                mesh.extend(face((x,-12.83,z), (.51,4.12,.11), STONE))
        return mesh

    def camera(self, time):
        x, y, z = route(time+.45)
        look = ease((time-18.7)/2.5)
        reveal = ease((time-20)/10.5)
        scale = 10.5 - 1.4*ease(time/8) + 1.55*ease((time-7)/8)
        tracking = np.array((x+.55, y-2.45, z+.18, scale))
        beacon = np.array((8.6-4.1*reveal, -11.65+5.15*reveal, 3.05-2.28*reveal, 9.8-4.7*reveal))
        camera = tracking*(1-look) + beacon*look
        _, cy, cz, scale = camera
        foot = route(time)
        projected_row = ROWS*.51+scale*((foot[1]-cy)*.65-(foot[2]-cz))
        overshoot = max(0, projected_row-89)
        camera[1] += overshoot**2/(overshoot+2)/(.65*scale)
        return camera

    def mount(self, time, x, y, scale):
        sprite, hand = caballero_montado.frame(time, gust(time))
        width = round(30 + scale*1.65)
        height = round(width*caballero_montado.HEIGHT*CELL_W/(caballero_montado.WIDTH*CELL_H))
        field = Image.new('RGBA', (COLS,ROWS))
        left, top = round(x-width*.53), round(y-height*.94)
        field.paste(sprite.resize((width,height),Image.Resampling.LANCZOS),(left,top))
        torch = (left+(hand[0]+3)*width/sprite.width, top+(hand[1]-13)*height/sprite.height)
        return np.asarray(field), torch

    def paint(self, project, materials, tones, mesh):
        colors, shade = ImageDraw.Draw(materials), ImageDraw.Draw(tones)
        def depth(item):
            points = item[0]
            return sum(y+.67*z+.19*x for x,y,z in points)/len(points)

        for points, material, tone in sorted(mesh, key=depth):
            polygon = [project(*p) for p in points]
            if (max(p[0] for p in polygon)<0 or min(p[0] for p in polygon)>=COLS or
                    max(p[1] for p in polygon)<0 or min(p[1] for p in polygon)>=ROWS):
                continue
            ax, ay = polygon[0]
            bx, by = polygon[1]
            cx, cy = polygon[2]
            if abs((bx-ax)*(cy-ay)-(by-ay)*(cx-ax)) < .45:
                continue
            colors.polygon(polygon, fill=material)
            shade.polygon(polygon, fill=round(tone*120))

    def frame(self, time, data):
        t = time*35/data['duracion']
        position = route(t)
        cx,cy,cz,scale = self.camera(t)
        def project(x,y,z):
            return (COLS*.5+scale*((x-cx)-.27*(y-cy)), ROWS*.51+scale*((y-cy)*.65-(z-cz)))

        wy = (Y-ROWS*.51)/(.65*scale)+cy-cz/.65
        wx = (X-COLS*.5)/scale+cx+.27*(wy-cy)
        edge = land_edge(wy)
        land = wx > edge
        cape = -14.7 + 2.4*np.cos(wy*.33) + 2.2*np.sin(wy*.16)
        land |= (wx < cape) & (wy > 5)
        dry = (wx > edge+.82) | ((wx < cape-.9) & (wy > 5.6))
        initial = np.where(dry, GRASS, np.where(land, ROCK, SEA)).astype('uint8')
        surfaces = Image.fromarray(initial)
        tones = Image.new('L', (COLS,ROWS), 115)
        ship_x = -10.1 + 8.4*ease((t-20)/15)
        ship_y = -16 + 7.2*ease((t-20)/15)
        ship = face((ship_x,ship_y,.24+.09*sin(t*3)), (1.72,3.52,.59), WOOD,.15)
        ship += face((ship_x,ship_y,1.32), (.10,.12,2.56), WOOD)
        ship += [(((ship_x,ship_y,2.70),(ship_x-1.52,ship_y-.45,.44),
                   (ship_x+.39,ship_y+.51,.65)), GOLD, .72+.47*ease((t-20)/6))]
        ship += face((ship_x,ship_y+1.18,.49), (.23,.22,.30), GOLD)
        light = ease((t-20)/1.05)
        flame = face((9,-12,6.37), (.47,.45,.52+.14*sin(t*17)), FIRE)
        left, top = cx-.27*cy-COLS*.5/scale, .65*cy-cz-ROWS*.51/scale
        x0,x1,y0,y1 = self.bounds
        visible = (x1>=left) & (x0<left+COLS/scale) & (y1>=top) & (y0<top+ROWS/scale)
        nearby = [self.world[index] for index in np.flatnonzero(visible)]
        self.paint(project, surfaces, tones, nearby+ship+(flame if light else []))
        material = np.asarray(surfaces)
        shade = np.asarray(tones)/120
        wet = (material == SEA)
        leaves = (material == LEAVES) | (material == GRASS)
        stone = (material == STONE) | (material == ROAD)
        wave = np.sin(wy*4.1+np.sin(wx*1.1)+t*3) + .44*np.sin(wx*2.8+wy*2-t*4.4)
        grain = .52+.24*np.sin(wx*11+np.cos(wy*7))+.17*np.cos(wy*14-wx*8)
        grain += .07*np.cos(wy*21+wx*19)
        air = gust(t)
        blade = np.sin(wx*2.1+wy*.8+t*1.9+air) * np.cos(wx*.4-wy*1.4+t*.81)
        rain_wake = np.sin((wx-ship_x)*15-(wy-ship_y)*4+t*2)
        wake = wet*np.exp(-((wx-ship_x)/(1.1+.32*abs(wy-ship_y)))**2)
        wake *= np.exp(-abs(wy-ship_y)*.44) * (wy < ship_y) * ease((t-19)/9)
        wave += .51*wake*rain_wake
        blocks = np.cos(wy*10 + .8*np.sin(wx*4))*np.cos(wx*5+np.floor(wy*3)*pi)
        density = .39+.42*grain + wet*(.16*wave-.21) + leaves*.15*blade + stone*.10*blocks
        material_light = (.43+.62*grain)*shade + wet*.145*wave + leaves*.17*blade + stone*.13*blocks
        actor = (material == STEEL) | (material == CLOTH)
        road = (material == ROAD)
        material_light += actor*.5
        coast = (abs(wx-edge) < 1.09) | ((abs(wx-cape) < .9) & (wy > 5))
        foam = wet & (wave > .64) & coast
        road_edge = road & ((np.roll(material,1,axis=1) != ROAD) | (np.roll(material,-1,axis=1) != ROAD))
        boundary = material != np.roll(material,1,axis=0)
        pavers = np.abs(np.sin(wy*7.7))<.15
        joints = np.abs(np.sin(wx*6.2 + np.floor(wy*2.45)*pi*.5))<.14
        mortar = stone & (pavers | joints)
        material_light = np.where(mortar,material_light*.54,material_light)
        material_light += road_edge*.37 + foam*.53 + boundary*(~wet)*.28
        source_x,source_y = project(*BEACON)
        dx = X-source_x
        offset = (Y-source_y-dx*(.10+.24*sin((t-20)*.83))) / (2.2+abs(dx)*.155)
        beam = light * np.exp(-offset**2) * (dx < 0) * np.maximum(0, 1-abs(dx)/145)
        orange = 1.25*light*np.exp(-((X-source_x)**2+(Y-source_y)**2)/430)
        orange += wet*light*np.exp(-((wx-6+wy*.32)**2)/7)*np.clip(.45+wave*.4,0,1)*.7
        lightning = sum(max(0,1-abs(t-cue)/width)*power for cue,width,power
                        in ((1.05,.16,.61),(9.15,.18,.44),(17.45,.23,.68),(17.80,.095,.38)))
        px, py = project(*position)
        mount, (tx, ty) = self.mount(t, px, py, scale)
        lantern = (.12+.48*ease((t-17.7)/1.35)-.28*light)*np.exp(-((X-tx)**2+(Y-ty)**2)/70)
        contact = np.exp(-((X-px)**2/145+(Y-py)**2/8))
        separation = np.exp(-((X-px)**2/490+(Y-py+13)**2/520))
        material_light *= (1-contact*.42)*(1-separation*.38)
        fog = .5+.5*np.sin(wy*.22+wx*.25+.3*t+1.3*np.sin(wx*.13-t*.18))
        ink = self.colors[material]*material_light[...,None] + np.array([94,114,142])*lightning
        ink += (orange+beam*.97+lantern)[...,None]*np.array([160,96,36])
        ink += (fog*.15 + foam*.16+wake*.24)[...,None]*np.array([50,95,128])
        if data['particulas']:
            grid_x, grid_y = wx*1.13, wy*1.13
            cell_x, cell_y = np.floor(grid_x), np.floor(grid_y)
            seed = ((cell_x.astype('int32')*15391 ^ cell_y.astype('int32')*35729) & 127)/127
            age = np.mod(seed*5.37+t*(.64+seed*.49),1)
            distance = np.hypot(np.mod(grid_x,1)-.5,np.mod(grid_y,1)-.5)
            radius = .045 + age*.88
            pulse = np.maximum(0,1-abs(distance-radius)/.083) * np.maximum(0,1-age/.47)**1.3
            rings = wet*pulse*(seed>.31)
            splash = (stone | (material==ROCK))*np.maximum(0,1-age/.13)
            splash *= np.maximum(0,1-distance/.24)*(seed>.47)
            rustle = leaves*pulse*.15*(seed>.68)
            ink += (rings*.95+splash*1.15+rustle)[...,None]*np.array([91,121,139])
        glyph = self.tables[material, np.clip((density*64).astype('intp'),0,63)]
        crest = wet & (wave>.85) & (grain>.28)
        glyph[crest] = GLYPHS.index('~')
        glyph[foam & (grain>.29)] = GLYPHS.index('=')
        glyph[road_edge] = GLYPHS.index(':')
        glyph[boundary & (material == STEEL)] = GLYPHS.index('#')
        glyph[wet & (beam > .42) & (grain>.58)] = GLYPHS.index('.')
        glyph[leaves & (blade>.40)] = GLYPHS.index('/')
        glyph[leaves & (blade<-.40)] = GLYPHS.index('\\')
        if data['particulas']:
            glyph[(rings>.26) & (age<.16)] = GLYPHS.index('o')
            glyph[(rings>.16) & (age>=.16)] = GLYPHS.index('~')
            glyph[splash>.29] = GLYPHS.index('+')
            drop_x,drop_y,velocity,depth = self.drops.T
            streak_x = (drop_x - t*(.067+.031*velocity) + air*.012 - cx*.019*(1+depth)) % 1 * COLS
            streak_y = (drop_y + t*(.28+.48*velocity) - cy*.016*(1+depth)) % 1 * ROWS
            near = depth > .29+.21*ease((t-19)/4)
            for ox, oy, strength in ((0,0,.9),(-1,1,.42)):
                rain_x = (streak_x[near].astype('intp')+ox)%COLS
                rain_y = (streak_y[near].astype('intp')+oy)%ROWS
                brightness = (depth[near]*(1-(streak_y[near]%1)*.55)*strength)
                ink[rain_y,rain_x] += brightness[:,None]*np.array([55,79,95])
                glyph[rain_y[brightness>.42],rain_x[brightness>.42]] = GLYPHS.index('/')
        fuse = ease((t-19.38)/.62)
        if 19.38 < t < 20.42:
            fade = 1-ease((t-20)/.42)
            for i in range(12):
                progress = max(0,fuse-i*.025)
                tip_x = round(tx+(source_x-tx)*progress+sin(i*.92+t*13)*i*.11)
                tip_y = round(ty+(source_y-ty)*progress)
                if 0<=tip_x<COLS and 0<=tip_y<ROWS:
                    glyph[tip_y,tip_x] = GLYPHS.index('*' if i<3 else '.')
                    ink[tip_y,tip_x] += np.array([203,113,43])*fade*(1-i/14)
        if light:
            sparks = self.drops[:50]
            for a,b,c,_ in sparks:
                age = (a+t*(.6+b))%1
                x = round(source_x+age*(c-1.4)*20)
                y = round(source_y-age*(2+b*11))
                if 0<=x<COLS and 0<=y<ROWS:
                    glyph[y,x] = GLYPHS.index('*' if age < .25 else '.')
                    ink[y,x] += np.asarray([220,124,47])*(1-age)
        hue = mount[:,:,:3].astype('float32')
        alpha = mount[:,:,3]/255
        rim = np.maximum.reduce((np.roll(alpha,1,axis=0), np.roll(alpha,-1,axis=0),
                                 np.roll(alpha,1,axis=1), np.roll(alpha,-1,axis=1)))
        outline = (alpha<.23) & (rim>.55)
        ink[outline] *= .43
        front = alpha>.24
        luminance = hue @ np.array((.22,.70,.08),dtype='float32')
        details = np.array([GLYPHS.index(ch) for ch in ".:;-=+x#%@"])
        facets = np.clip((luminance/27+.64*np.sin(X*2.4+Y*1.9)).astype('intp'),0,9)
        glyph[front] = details[facets[front]]
        exposed = (hue+lightning*np.array([52,66,74])+lantern[...,None]*np.array([38,22,10])).clip(0,255)
        ink[front] = exposed[front]*alpha[front,None]+ink[front]*(1-alpha[front,None])
        texture = self.atlas[glyph]
        dark = np.array([5,11,18]) + ink.clip(0,255)*np.where(wet,.101,.159)[...,None]
        dark += (beam*.24+lightning*.11)[...,None]*np.array([112,77,49])
        dark[outline] *= .40
        dark[front] = (dark[front]*.24+exposed[front]*.43)*alpha[front,None]+dark[front]*(1-alpha[front,None])
        color = ink.clip(0,255).astype('uint16')
        backdrop = dark.clip(0,255).astype('uint16')[:,:,None,None,:]
        pixels = (texture[...,None]*color[:,:,None,None,:] + (255-texture[...,None])*backdrop)//255
        image = Image.fromarray(pixels.transpose(0,2,1,3,4).reshape(SIZE[1],SIZE[0],3).astype('uint8'))
        if data['codigo']:
            self.panel(image, data, light, time)
        return image
