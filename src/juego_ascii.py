"""Offline horizontal playground backed by LEMC Studio's ASCII renderer."""
from math import cos, pi, sin
from time import perf_counter
import tkinter as tk
from tkinter import ttk

import numpy as np
from PIL import Image, ImageTk

from locomocion_ecuestre import DT, Mount, damp
import retrato_jinete
import mundos_ascii

SIZE=(960,540)
COLS,ROWS=160,90
CELL=6
Y,X=np.mgrid[:ROWS,:COLS].astype('float32')
GLYPHS=" .,:;~=-_/\\|ox*#%@+"
RAMP=" .,:;=+x*#%@"
AREAS=('Bosque de la lluvia','Vado de la luna','Puerta de las brasas')
ARMORS=('Acero y carmesí','Latón y verde','Hierro azulado')
METERS=5.


class World:
    def __init__(self,font,atlas,area=1):
        self.atlas=atlas(font('consola.ttf',6),GLYPHS,CELL,CELL).astype('uint8')
        self.puppet_atlas=atlas(font('consola.ttf',5),retrato_jinete.ATLAS_CHARS,3,4)
        self.ramp=np.array([GLYPHS.index(c) for c in RAMP])
        self.palette=np.array([GLYPHS.index(c) for c in '.:;/\\|'])
        self.maps={}
        self.flashes=[]
        self.rng=np.random.default_rng(914)
        self.drops=self.rng.random((150,4))
        self.armor=0
        self.inspection=False
        self.angle=-.24
        self.zoom=1.62
        self.night=self.target_night=.37
        self.weather=self.target_weather=1.
        self.set_area(area)

    def set_area(self,index):
        if index not in self.maps:
            self.maps[index]=mundos_ascii.Terrain(index)
        self.area=index
        self.map=self.maps[index]
        spawn=((20.4,30),(13.2,25.2),(21,26))
        self.mount=Mount(*spawn[index])
        self.mount.heading=(-.65,-.42,-.74)[index]
        self.mount.reset_feet()
        self.camera=self.mount.position.copy()
        self.flashes.clear()

    def step(self,drive=0,steer=0):
        if self.inspection:
            self.angle+=steer*DT*.97
            return
        self.night=damp(self.night,self.target_night,3.4,DT)
        self.weather=damp(self.weather,self.target_weather,3.6,DT)
        self.mount.step(DT,drive,steer)
        lead=np.array((cos(self.mount.heading),sin(self.mount.heading)))*self.mount.speed*.71
        self.camera=damp(self.camera,self.mount.position+lead,3.25,DT)
        for x,y in self.mount.contacts:
            xx,yy=round(x*METERS),round(y*METERS)
            layer=self.map.mat[min(232,max(0,yy)),min(209,max(0,xx))]
            ttl=.68 if layer==mundos_ascii.WATER else .26
            self.flashes.append((x,y,self.mount.time,ttl,layer))
        self.flashes=[p for p in self.flashes if self.mount.time-p[2]<p[3]]

    def image(self):
        if self.inspection:
            return self.profile()
        t=self.mount.time
        cam_x,cam_y=self.camera*METERS
        wx=np.clip((X-COLS*.5)/self.zoom+cam_x,0,mundos_ascii.WORLD_W-1)
        wy=np.clip((Y-ROWS*.52)/self.zoom+cam_y,0,mundos_ascii.WORLD_H-1)
        ix,iy=wx.astype('intp'),wy.astype('intp')
        nx,ny=np.minimum(ix+1,mundos_ascii.WORLD_W-1),np.minimum(iy+1,mundos_ascii.WORLD_H-1)
        u,v=(wx-ix.astype('float32'))[...,None],(wy-iy.astype('float32'))[...,None]
        rgb=self.map.rgb
        low=rgb[iy,ix]*(1-u)+rgb[iy,nx]*u
        high=rgb[ny,ix]*(1-u)+rgb[ny,nx]*u
        rgb=low*(1-v)+high*v
        material=self.map.mat[iy,ix]
        water=material==mundos_ascii.WATER
        growth=(material==mundos_ascii.LEAF)|(material==mundos_ascii.GRASS)
        rain=self.weather
        night=self.night
        wind=.44*sin(t*1.45)+.21*sin(t*3.8)
        waves=mundos_ascii.silvery_water(t,wx,wy)
        grass=np.sin(wx*.83+wy*.27+t*1.86+wind*.42)
        grain=.50+.17*np.sin(wx*3.1+wy*7.7)+.19*np.cos(wx*5.1-wy*2.6)
        rain_seed=((ix//4*37 ^ iy//4*71)&127)/127
        age=np.mod(rain_seed+t*(.80+rain_seed*.57),1).astype('float32')
        radius=np.hypot(wx%4-2,wy%4-2)
        rings=water*np.clip(1-abs(radius-age*3.8)/.32,0,1)*np.clip(1-age/.62,0,1)
        ground=(~growth & ~water)*np.clip(1-age/.12,0,1)*np.clip(1-radius/.65,0,1)
        mist=.5+.5*np.sin(wx*.064+wy*.118-t*.64+np.sin(wy*.034)*2)
        ink=rgb*(.95+grain*.30+grass*growth*.22+water*waves*.24)[...,None]
        shading=.20*(1-night*.7)*np.exp(-((wx-95+np.sin(wy*.17)*9)**2)/420)
        ink=ink*(1-night*.40)+night*np.array((4,11,22))+shading[...,None]*np.array((94,98,65))
        ink+=(mist*.20)[...,None]*np.array((20,44,56))
        ink+=rain*(rings+ground)[...,None]*np.array((110,151,166))
        density=grain+.14*growth*grass+.12*water*waves
        index=(density*len(self.ramp)).astype('intp').clip(0,len(self.ramp)-1)
        glyph=self.ramp[index]
        grass_index=((grass+1)*2.7).astype('intp').clip(0,len(self.palette)-1)
        glyph[growth]=self.palette[grass_index[growth]]
        leaves=material==mundos_ascii.LEAF
        edge=leaves&~np.roll(leaves,1,axis=0)
        glyph[edge]=GLYPHS.index('x')
        ink[edge]*=1.24
        crest=water & (waves>.26)
        glyph[crest]=GLYPHS.index('~')
        glyph[(rings*rain)>.34]=GLYPHS.index('o')
        glyph[(ground*rain)>.37]=GLYPHS.index('+')
        if self.area==2:
            for ax,ay in ((81,85),(126,82),(90,108),(117,106)):
                glow=np.exp(-((wx-ax)**2+(wy-ay)**2)/43)*(.9+.1*sin(t*11+ax))
                ink+=glow[...,None]*np.array((193,113,45))
                gx,gy=round((ax-cam_x)*self.zoom+COLS*.5),round((ay-cam_y)*self.zoom+ROWS*.52)
                if 0<=gx<COLS and 0<=gy<ROWS:
                    ink[gy,gx]=(255,199,91)
                    glyph[gy,gx]=GLYPHS.index('*')
        if self.area==1:
            shine=np.exp(-((wx-56+waves*1.4)**2)/54)
            ink+=(water*shine*(.29+.13*waves))[...,None]*np.array((91,131,175))

        for hx,hy,start,ttl,surface in self.flashes:
            sx=(hx*METERS-cam_x)*self.zoom+COLS*.5
            sy=(hy*METERS-cam_y)*self.zoom+ROWS*.52
            age=(t-start)/ttl
            rr=np.hypot(X-sx,(Y-sy)*1.58)
            ripple=np.clip(1-abs(rr-2.5*age)/1.15,0,1)*(1-age)
            impact=ripple*(water if surface==mundos_ascii.WATER else ~water)
            ink+=impact[...,None]*np.array((88,129,150))
            glyph[impact>.30]=GLYPHS.index('o' if surface==mundos_ascii.WATER else '+')

        sx,sy=(self.mount.position-self.camera)*METERS*self.zoom+np.array((COLS*.5,ROWS*.52))
        width=max(27,min(round(35+self.zoom*9),round(sy*.94)))
        height=round(width*.95)
        left=round(sx-width*.50)
        top=round(sy-height*.95)
        shadow=np.exp(-((X-sx)**2/(.17*width)**2+(Y-sy)**2/10))*.27
        right=cos(self.mount.heading)>=0
        for _,index,_,_,source_foot in retrato_jinete.LEGS:
            foot=self.mount.feet[index].local
            base=-.86 if index in (0,2) else .79
            x=source_foot[0]*retrato_jinete.SOURCE_SCALE
            lifted=min(1,max(0,(foot[2]-.075)/.19))
            x=(x+np.clip((foot[0]-base)*62,-29,29))/retrato_jinete.SIZE[0]
            ax=left+width*(x if right else 1-x)
            ay=top+height*source_foot[1]*retrato_jinete.SOURCE_SCALE/retrato_jinete.SIZE[1]
            shadow+=np.exp(-((X-ax)**2/5+(Y-ay)**2/1.8))*(1-lifted)*.28
        ink*=1-np.minimum(shadow,.68)[...,None]
        portrait=retrato_jinete.character_canvas(self.mount,wind,self.mount.heading,self.armor,width*2,
                                                  round(height*1.5))
        source=portrait.resize((width,height),Image.Resampling.BILINEAR)
        actor=Image.new('RGBA',(COLS,ROWS))
        actor.alpha_composite(source,(left,top))
        rgba=np.asarray(actor)
        rx=(X+np.sin(Y*.52+t*3.1)*1.46).astype('intp').clip(0,COLS-1)
        ry=(2*sy-Y+np.cos(X*.37+t*3.6)*1.14).astype('intp').clip(0,ROWS-1)
        reflected=rgba[ry,rx]
        reflection=water & (Y>sy) & (reflected[:,:,3]>95)
        ink[reflection]=ink[reflection]*.67+reflected[:,:,:3][reflection]*.33
        glyph[reflection]=GLYPHS.index('~')
        if rain:
            x,y,s,d=self.drops.T
            within=d<rain*.77
            dx=((x-t*(.072+.029*s)+wind*.022)%1*COLS).astype('intp')[within]
            dy=((y+t*(.37+.32*s))%1*ROWS).astype('intp')[within]
            glyph[dy,dx]=GLYPHS.index('/')
            ink[dy,dx]+=s[within,None]*np.array((58,88,112))
        color=np.clip(ink,0,255).astype('uint8')
        bg=(np.array((4,8,12))+.24*color).astype('uint8')
        image=self.compose(glyph,color,bg).convert('RGBA')
        foreground=retrato_jinete.ascii_layer(portrait,self.puppet_atlas,1.19-night*.32)
        image.alpha_composite(foreground,(left*CELL,top*CELL))
        return image.convert('RGB')

    def profile(self):
        # The supplied side view is the art source, with a controlled preview pan.
        double_width=round(151+8*cos(self.angle))
        height=round(double_width*.776)
        actor=retrato_jinete.character_canvas(None,0,0,self.armor,double_width,height)
        foreground=retrato_jinete.ascii_layer(actor,self.puppet_atlas,1.21)
        image=Image.new('RGBA',SIZE,(14,16,20,255))
        left=round((SIZE[0]-foreground.width)/2+sin(self.angle)*45)
        image.alpha_composite(foreground,(left,22))
        return image.convert('RGB')

    def compose(self,glyph,color,bg,atlas=None):
        tile=(self.atlas if atlas is None else atlas)[glyph]
        mask=Image.fromarray(tile.transpose(0,2,1,3).reshape(SIZE[1],SIZE[0]))
        foreground=Image.fromarray(color).resize(SIZE,Image.Resampling.NEAREST)
        background=Image.fromarray(bg).resize(SIZE,Image.Resampling.NEAREST)
        return Image.composite(foreground,background,mask)


def open_window(parent,font,atlas,area=1,light='Automática',weather='Del escenario',particles=True):
    window=tk.Toplevel(parent)
    window.title('Mundos ASCII · Campo de práctica')
    window.configure(bg='#111820')
    window.geometry('1024x648')
    window.minsize(680,430)
    world=World(font,atlas,area)
    world.night=world.target_night={'Día':.12,'Noche':.82}.get(light,.37)
    world.weather=world.target_weather=0. if not particles or weather=='Despejado' else 1.
    active=set()
    toolbar=ttk.Frame(window,padding=(10,5))
    toolbar.pack(fill='x')
    scene=tk.StringVar(window,AREAS[area])
    equipment=tk.StringVar(window,ARMORS[0])
    area_ui=ttk.Combobox(toolbar,values=AREAS,textvariable=scene,state='readonly',width=22)
    armor_ui=ttk.Combobox(toolbar,values=ARMORS,textvariable=equipment,state='readonly',width=19)
    area_ui.pack(side='left',padx=(0,7))
    armor_ui.pack(side='left',padx=(0,8))
    ttk.Button(toolbar,text='Día / noche',command=lambda:toggle('n')).pack(side='left',padx=(0,5))
    ttk.Button(toolbar,text='Lluvia',command=lambda:toggle('r')).pack(side='left',padx=(0,5))
    inspection_button=ttk.Button(toolbar,text='Inspeccionar modelo',command=lambda:toggle('v'))
    inspection_button.pack(side='left')
    canvas=tk.Canvas(window,background='#090e13',borderwidth=0,highlightthickness=0)
    canvas.pack(fill='both',expand=True)
    picture=canvas.create_image(0,0,anchor='center')
    ttk.Label(window,text='W / ↑ avanzar    S / ↓ frenar    A D / ← → girar    + / − zoom    V inspeccionar    Esc cerrar',
              padding=(8,5),anchor='center').pack(fill='x')

    def pick(event):
        if event.widget is area_ui:
            world.set_area(AREAS.index(scene.get()))
        else:
            world.armor=ARMORS.index(equipment.get())
        canvas.focus_set()

    def toggle(key):
        if key=='v':
            world.inspection=not world.inspection
            inspection_button.configure(text='Volver al mundo' if world.inspection else 'Inspeccionar modelo')
        elif key=='n':
            world.target_night=.12 if world.target_night>.45 else .83
        elif key=='r':
            world.target_weather=1-world.target_weather
        elif key in ('plus','equal','kp_add'):
            world.zoom=min(2.45,world.zoom+.22)
        elif key in ('minus','kp_subtract'):
            world.zoom=max(1.22,world.zoom-.22)
        elif key in ('1','2','3'):
            world.armor=int(key)-1
            equipment.set(ARMORS[world.armor])
        canvas.focus_set()

    def press(event):
        key=event.keysym.lower()
        if key=='escape':
            close()
            return 'break'
        if key not in active:
            toggle(key)
        active.add(key)

    def release(event):
        active.discard(event.keysym.lower())

    area_ui.bind('<<ComboboxSelected>>',pick)
    armor_ui.bind('<<ComboboxSelected>>',pick)
    canvas.bind('<KeyPress>',press)
    canvas.bind('<KeyRelease>',release)
    canvas.bind('<FocusOut>',lambda event:active.clear())
    canvas.bind('<Button-1>',lambda event:canvas.focus_set())
    canvas.focus_set()
    last=perf_counter()
    remainder=0.
    job=None

    def tick():
        nonlocal last,remainder,job
        now=perf_counter()
        remainder+=min(now-last,.10)
        last=now
        drive=-1 if active & {'s','down'} else int(bool(active & {'w','up'}))
        steer=int(bool(active & {'d','right'}))-int(bool(active & {'a','left'}))
        while remainder>=DT:
            world.step(drive,steer)
            remainder-=DT
        image=world.image()
        width,height=max(2,canvas.winfo_width()),max(2,canvas.winfo_height())
        factor=min(width/SIZE[0],height/SIZE[1])
        drawn=image.resize((max(1,round(960*factor)),max(1,round(540*factor))),Image.Resampling.BILINEAR)
        canvas.rendered=ImageTk.PhotoImage(drawn,master=window)
        canvas.itemconfigure(picture,image=canvas.rendered)
        canvas.coords(picture,width*.5,height*.5)
        job=window.after(1,tick)

    def close():
        if job is not None:
            window.after_cancel(job)
        window.destroy()

    window.protocol('WM_DELETE_WINDOW',close)
    tick()
    return window
