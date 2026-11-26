"""Reusable ASCII world renderer with terrain, animated surfaces and a camera."""
from dataclasses import dataclass
from functools import lru_cache
from math import pi, sin
import os

import numpy as np
from PIL import Image, ImageDraw

from caballero_del_faro import SIZE, Scene as Panel, ease
import modelo_jinete

NAMES = ('La ruta del vigía', 'Bosque de la lluvia', 'Vado de la luna', 'Puerta de las brasas')
LIGHTING = ('Automática', 'Día', 'Noche')
WEATHER = ('Del escenario', 'Lluvia', 'Despejado')
COLS, ROWS = 135,160
CELL_W,CELL_H=4,6
WORLD_W,WORLD_H=210,233
Y,X=np.mgrid[:ROWS,:COLS]
GLYPHS=" .,:;~=-_+/\\()[]<>iox*#%O@|"
SOIL,GRASS,STONE,WATER,WOOD,LEAF,FLAME=range(7)

@dataclass(frozen=True)
class Biome:
    base: tuple
    path: tuple
    leaf: tuple
    water: tuple
    night: float
    rain: float
    entry: float
    exit: float

BIOMES=(
    Biome((33,65,46),(112,102,75),(54,106,72),(55,104,114),.28,1, -1.15,-.33),
    Biome((36,64,63),(101,112,116),(43,86,89),(51,116,150),.84,.12,-.40,.46),
    Biome((68,55,53),(130,107,90),(96,79,57),(68,84,94),.60,.53,.46,.18),
)

def path_x(y, chapter):
    return 104 + 16*np.sin(y*.026+chapter*.58) - 8*np.cos(y*.055)


def silvery_water(t, x, y):
    return np.sin(y*.48-t*3.3+np.sin(x*.17)) + .42*np.sin(y*.93+x*.16-t*4.1)


class Terrain:
    def __init__(self, chapter):
        self.chapter=chapter
        self.settings=BIOMES[chapter]
        self.rng=np.random.default_rng(294+chapter*931)
        self.color=Image.new('RGB',(WORLD_W,WORLD_H))
        self.types=Image.new('L', self.color.size)
        yy,xx=np.mgrid[:WORLD_H,:WORLD_W]
        self.rng_noise=self.rng.random(self.color.size[::-1])
        soil=self.settings.base
        trail=np.abs(xx-path_x(yy,chapter))<(17 if chapter!=2 else 24)
        river=np.abs(xx-75+26*np.sin(yy*.019+.8))<27
        mat=np.where(trail,SOIL,GRASS)
        if chapter==1:
            mat=np.where(river,WATER,mat)
            crossing=np.abs(yy-102)<10+2*np.sin(xx*.087)
            mat=np.where(crossing & river,STONE,mat)
        table=np.array((self.settings.path,soil,(129,141,151),self.settings.water))
        lighting=(.68+.15*np.sin(xx*.11+yy*.06)+.11*np.cos(yy*.17-xx*.08)+.28*self.rng_noise)
        self.color=Image.fromarray((table[mat]*lighting[...,None]).clip(0,255).astype('uint8'))
        self.types=Image.fromarray(mat.astype('uint8'))
        self.paint=ImageDraw.Draw(self.color)
        self.masks=ImageDraw.Draw(self.types)
        self.populate()
        self.rgb=np.asarray(self.color)
        self.mat=np.asarray(self.types)

    def poly(self, points, color, material):
        self.paint.polygon(points,fill=color)
        self.masks.polygon(points,fill=material)

    def ellipse(self, box, color, material):
        self.paint.ellipse(box,fill=color)
        self.masks.ellipse(box,fill=material)

    def tree(self,x,y,s):
        self.ellipse((x-7*s,y-3*s,x+23*s,y+9*s),(22,35,29),GRASS)
        self.poly([(x-3*s,y+5*s),(x+2*s,y-35*s),(x+7*s,y-33*s),(x+3*s,y+5*s)],
                  (82,65,49),WOOD)
        for dx,dy,r in ((2,-21,9),(-8,-24,8),(10,-29,10),(-2,-34,10),(5,-41,7),
                        (-9,-38,6),(15,-24,6),(0,-49,5)):
            dx,dy,r=dx*s,dy*s,r*s
            color=tuple(round(c*self.rng.uniform(.64,1.27)) for c in self.settings.leaf)
            self.ellipse((x+dx-r,y+dy-r,x+dx+r,y+dy+r*.8),color,LEAF)
        for _ in range(round(28*s)):
            dx=self.rng.uniform(-13,15)*s
            dy=self.rng.uniform(-47,-19)*s
            if ((dx/s)/15)**2+((dy/s+33)/15)**2<1:
                self.ellipse((x+dx,y+dy,x+dx+1.8*s,y+dy+1.1*s),tuple(int(c*1.26) for c in self.settings.leaf),LEAF)

    def rock(self,x,y,s):
        self.poly(((x-7*s,y+4*s),(x-9*s,y-2*s),(x-3*s,y-9*s),
                   (x+5*s,y-8*s),(x+9*s,y),(x+5*s,y+6*s)),(75,88,93),STONE)
        self.poly(((x-8*s,y-1*s),(x-3*s,y-9*s),(x+5*s,y-8*s),(x+7*s,y-4*s),
                   (x,y),(x-4*s,y+1*s)),(137,147,155),STONE)

    def gate(self):
        # Two masonry towers and a recessed central arch.
        self.poly(((56,83),(77,34),(139,34),(157,93),(140,122),(76,121)),(45,42,48),STONE)
        for x in (72,134):
            self.poly(((x-12,92),(x-12,46),(x+9,41),(x+13,87),(x+5,95)),(126,119,119),STONE)
            self.poly(((x+7,47),(x+13,45),(x+16,86),(x+5,96),(x+5,66)),(74,70,80),STONE)
            y=44
            for dx in (-12,-3,6):
                self.poly(((x+dx,y),(x+dx,y-8),(x+dx+6,y-8),(x+dx+6,y)),(169,151,141),STONE)
            for row in range(50,89,5):
                for i in range(3):
                    l=x-11+i*7+(row%2)
                    self.poly(((l,row),(l+6,row),(l+5,row+2),(l,row+2)),
                              (99+(i+row)%22,91+(i+row)%17,99),STONE)
            self.poly(((x-5,65),(x-5,55),(x-2,52),(x+1,55),(x+1,65)),(33,33,42),STONE)
        self.poly(((82,67),(124,63),(123,89),(116,89),(116,73),(108,66),
                   (98,68),(92,76),(92,94),(83,93)),(134,124,119),STONE)
        self.poly(((94,92),(94,78),(99,72),(108,69),(115,76),(115,90)),(24,24,35),STONE)
        for y in range(94,136,5):
            self.poly(((87,y),(121,y-2),(121,y),(87,y+2)),(96,91,91),STONE)

    def populate(self):
        if self.chapter==2:
            self.gate()
        tree_data=[]
        for i in range(230):
            x,y=self.rng.uniform(3,WORLD_W-4),self.rng.uniform(8,WORLD_H)
            if self.chapter==2 and 51<x<159 and 28<y<142:
                continue
            terrain=self.types.getpixel((int(x),int(y)))
            margin=abs(x-path_x(y,self.chapter))
            if terrain in (GRASS,SOIL) and margin>25 and i%3:
                tree_data.append((x,y,self.rng.uniform(.49,1.06) if self.chapter==0 else self.rng.uniform(.38,.80)))
            elif i%3==0 and terrain!=WATER and (margin>17 or i%7==0):
                self.rock(x,y,self.rng.uniform(.22,.77))
        for tree in sorted(tree_data,key=lambda p:p[1]):
            self.tree(*tree)


@lru_cache(maxsize=4)
def prepare(font, atlas):
    return WorldSequence(font,atlas)


class WorldSequence(Panel):
    def __init__(self,font,atlas):
        self.heading=font('consola.ttf',16)
        self.caption=font('consola.ttf',12)
        self.signature=font('seguisym.ttf' if os.name=='nt' else 'georgia.ttf',15)
        self.excerpt=('phase = (cycle+shift+offset)%1',
                      'swing = ease((phase-.59)/.41)',
                      'radius = .10 + age*.91')
        self.atlas=atlas(font('consola.ttf',6), GLYPHS, CELL_W,CELL_H).astype('uint16')
        self.ramps=np.array([[GLYPHS.index(c) for c in row]
                            for row in (" .,:;+=*#@", " .,;i/\\|x#", " .:=-+*#%@", "  .,~=-_+o",
                                        " .:;|/x#%@", " .,:;iox#%", " .,~+x*#%@")])
        self.dense=np.array([GLYPHS.index(c) for c in " .,:;+=x*#%@"])
        self.maps=[Terrain(chapter) for chapter in range(3)]
        self.particles=np.random.default_rng(7721).random((320,5))

    def frame(self,time,data):
        mode=NAMES.index(data['figura'])
        if mode==0:
            progress=time*3/data['duracion']
            chapter=min(2,int(progress))
            elapsed=(progress-chapter)*12
        else:
            chapter=mode-1
            elapsed=time*12/data['duracion']
        ink,glyph,night=self.shot(chapter,elapsed,data)
        tile=self.atlas[glyph]
        color=ink.clip(0,255).astype('uint16')
        backdrop=(np.array((8,13,19))+.24*color).astype('uint16')[:,:,None,None,:]
        pixels=(tile[...,None]*color[:,:,None,None,:]+(255-tile[...,None])*backdrop)//255
        image=Image.fromarray(pixels.transpose(0,2,1,3,4).reshape(SIZE[1],SIZE[0],3).astype('uint8'))
        if data['codigo']:
            self.panel(image,data,1-night,time)
        return image

    def shot(self,chapter,t,data):
        terrain=self.maps[chapter]
        biome=terrain.settings
        travel=ease(t/12)
        cam_y=132-73*travel if chapter<2 else 135-63*travel
        cam_x=105+7*sin(t*.22+chapter)
        wx=np.clip(X+cam_x-COLS*.50,0,WORLD_W-1)
        wy=np.clip(Y+cam_y-ROWS*.55,0,WORLD_H-1)
        ix,iy=wx.astype('intp'),wy.astype('intp')
        nx,ny=np.minimum(ix+1,WORLD_W-1),np.minimum(iy+1,WORLD_H-1)
        u,v=(wx-ix)[...,None],(wy-iy)[...,None]
        lower=terrain.rgb[iy,ix]*(1-u)+terrain.rgb[iy,nx]*u
        upper=terrain.rgb[ny,ix]*(1-u)+terrain.rgb[ny,nx]*u
        color=lower*(1-v)+upper*v
        material=terrain.mat[iy,ix]
        night={'Día':.07,'Noche':.91}.get(data['mundo_luz'],biome.night+.19*ease(t/11))
        rain={'Lluvia':1,'Despejado':0}.get(data['mundo_clima'],biome.rain)
        rain*=data['particulas']
        trees=(material==LEAF)|(material==GRASS)
        water=material==WATER
        wind=.42*sin(t*1.6)+.27*sin(t*3.3)
        waves=silvery_water(t,wx,wy)
        sway=np.sin(wx*.43+wy*.28+t*1.9+wind)
        edge=(np.roll(material,1,axis=0)!=material)
        grain=.44+.23*np.sin(wx*2.91+wy*3.82)+.13*np.cos(wy*8.2-wx*2.1)
        density=grain+.11*trees*sway+.10*water*waves+.16*edge
        mist=.5+.5*np.sin(wx*.076+wy*.10-t*.42+np.sin(wy*.031)*2)
        ink=color*(.91+.16*grain+.18*trees*sway+.17*water*waves)[...,None]
        ink=ink*(1.17-night*.38)+night*np.array((3,15,31))
        shaft=.29*np.exp(-((wx-105+np.sin(wy*.06)*17)**2)/650)
        ink+=shaft[...,None]*np.array((61,83,66))*(1-night*.36)
        torches=0
        if chapter==2:
            for x,y in ((81,85),(126,82),(90,108),(117,106)):
                glow=(.86+.14*sin(t*13+x))*np.exp(-((wx-x)**2+(wy-y)**2)/93)
                torches=torches+glow
            ink+=torches[...,None]*np.array((229,135,47))
        if chapter==1:
            reflection=np.exp(-((wx-53+np.sin(wy*.26+t*2)*2.4)**2)/77)
            ink+=(water*reflection*(.45+.27*waves))[...,None]*np.array((79,125,175))
        ink+=((mist*.17+.10)*night)[...,None]*np.array((25,56,74))
        if rain:
            seed=((np.floor(wx*.29).astype('intp')*173 ^ np.floor(wy*.29).astype('intp')*271)&127)/127
            age=np.mod(seed+t*(.79+seed*.56),1)
            distance=np.hypot(np.mod(wx*.29,1)-.5,np.mod(wy*.29,1)-.5)
            radius = .10 + age*.91
            ripple=np.maximum(0,1-abs(distance-radius)/.11)*np.maximum(0,1-age/.49)
            spatter=np.maximum(0,1-age/.12)*np.maximum(0,1-distance/.32)
            impact=ripple*water + spatter*(~trees)
            ink+=(impact*rain)[...,None]*np.array((87,144,165))

        # Camera-relative aiming and foot contact remain consistent across environments.
        horse_y=122-66*travel if chapter<2 else 135-47*travel
        horse_x=float(path_x(horse_y,chapter)) + (10*sin(t*.29) if chapter==1 else 3*sin(t*.31))
        sx,sy=horse_x-cam_x+COLS*.5,horse_y-cam_y+ROWS*.55
        angle=biome.entry+(biome.exit-biome.entry)*travel
        gait=ease(t/.62)*(1-ease((t-9.1)/2.7)) if chapter==2 else .82+.18*sin(pi*travel)
        shadow=np.exp(-((X-sx)**2/290+(Y-sy)**2/27))
        ink*=1-shadow[...,None]*.42
        light=.48+(.57*ease((t-6)/3) if chapter==2 else .16)
        actor,visible=modelo_jinete.draw(t,gait,wind,angle,12.2+1.4*sin(pi*travel),sx,sy,(ROWS,COLS),light)
        if chapter==1:
            reflected_y=(2*sy-Y+np.sin(X*.18+t*3)*2).astype('intp').clip(0,ROWS-1)
            reflection_x=(X+np.sin(Y*.35+t*2)*2).astype('intp').clip(0,COLS-1)
            reflected=water&(Y>sy)&visible[reflected_y,reflection_x]
            ink[reflected]=.71*ink[reflected]+.29*actor[reflected_y,reflection_x][reflected]
        rim=(~visible)&(np.roll(visible,1,axis=0)|np.roll(visible,-1,axis=0)|
                       np.roll(visible,1,axis=1)|np.roll(visible,-1,axis=1))
        ink[rim]*=.42
        ink[visible]=actor[visible]
        glyph=self.ramps[material,np.clip((density*10).astype('intp'),0,9)]
        glyph[visible]=self.dense[np.clip((np.mean(actor[visible],axis=1)/19).astype('intp'),2,11)]
        if rain:
            glyph[(impact*rain>.30)&(~visible)]=GLYPHS.index('o')
            px,py,depth,seed,_=self.particles.T
            visible_rain=(seed<rain*.84)
            rx=((px+t*(-.12+.025*depth)+wind*.014) % 1*COLS).astype('intp')
            ry=((py+t*(.34+.53*depth)) % 1*ROWS).astype('intp')
            rx,ry,depth=rx[visible_rain],ry[visible_rain],depth[visible_rain]
            glyph[ry,rx]=GLYPHS.index('/')
            ink[ry,rx]+=depth[:,None]*np.array((49,75,97))
        if chapter==2:
            for fire_x,fire_y in ((81,85),(126,82),(90,108),(117,106)):
                x=round(fire_x-cam_x+COLS*.5)
                y=round(fire_y-cam_y+ROWS*.55)
                if 2<=x<COLS-2 and 4<=y<ROWS and not visible[y,x]:
                    for k in range(4):
                        tip=x+round(k*wind*.9+sin(t*15+k)*.5)
                        if not visible[y-k,tip]:
                            glyph[y-k,tip]=GLYPHS.index('*' if k<2 else '+')
                            ink[y-k,tip]=np.array((255,215-26*k,105-14*k))
        if data['particulas'] and chapter in (1,2):
            for px,py,depth,seed,_ in self.particles[:42]:
                age=(seed+t*(.29+.25*depth))%1
                if chapter==1:
                    x=round((px*COLS+sin(t+seed*9)*7)%COLS)
                    y=round((py*ROWS+t*1.52)%ROWS)
                else:
                    base_x,base_y=((81,85),(126,82),(90,108),(117,106))[int(px*4)]
                    x=round(base_x-cam_x+COLS*.5+wind*age*8)
                    y=round(base_y-cam_y+ROWS*.55-age*(4+depth*18))
                if 0<=x<COLS and 0<=y<ROWS and not visible[y,x]:
                    ink[y,x]+=(1-age)*np.array((180,154,71))
                    glyph[y,x]=GLYPHS.index('*' if age<.25 else '.')
        transition=min(ease((t+.5)/.55),ease((12.52-t)/.59)) if data['figura']==NAMES[0] else 1
        ink*=transition
        return ink,glyph,night
