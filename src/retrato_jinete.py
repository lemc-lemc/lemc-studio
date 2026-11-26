"""Photo-derived ASCII puppet with world-driven hoof contacts."""
from dataclasses import dataclass
from functools import lru_cache
from math import cos, sin, tau
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from locomocion_ecuestre import smooth

SIZE=(309,319)
SOURCE_SCALE=.25
ATLAS_CHARS=" .,:;irsXA253hMHGS#9B&@"
OUTLINE=((37,1000),(33,920),(39,803),(51,715),(67,639),(94,570),(139,518),(205,491),
         (244,467),(256,457),(316,438),(370,434),(412,386),(430,297),(432,249),
         (430,228),(440,212),(443,177),(480,153),(491,137),(476,133),(483,116),
         (492,97),(487,77),(488,58),(496,35),(510,20),(521,14),(546,18),
         (571,28),(591,47),(599,61),(617,87),(601,116),(590,147),(575,143),
         (573,157),(586,172),(597,200),(608,241),(615,287),(612,317),(604,337),
         (626,349),(656,345),(672,354),(687,365),(713,368),(724,385),(735,410),
         (747,410),(775,376),(819,333),(864,291),(912,255),(969,224),(1023,205),
         (1070,199),(1094,192),(1126,155),(1122,177),(1138,157),(1139,170),(1131,207),
         (1152,233),(1160,271),(1176,315),(1189,355),(1200,384),(1205,414),(1217,457),
         (1210,478),(1198,494),(1179,495),(1164,501),(1144,495),(1136,476),
         (1114,475),(1089,491),(1041,505),(988,505),(973,547),(952,626),
         (948,681),(927,735),(895,779),(863,815),(860,851),(852,902),
         (845,937),(843,980),(834,1030),(828,1065),(830,1109),(854,1145),
         (857,1169),(877,1202),(869,1212),(799,1212),(793,1200),(783,1197),
         (711,1201),(703,1191),(700,1164),(690,1143),(695,1115),(695,1091),
         (708,1049),(717,1001),(722,951),(720,906),(725,858),(725,814),(716,811),
         (678,824),(637,829),(602,831),(571,818),(549,813),(495,809),
         (448,802),(410,788),(383,770),(363,747),(348,743),(333,778),(309,802),
         (293,837),(282,868),(275,898),(269,936),(266,967),(273,1001),(290,1048),
         (310,1093),(325,1122),(342,1146),(364,1166),(387,1187),(387,1199),
         (312,1208),(301,1194),(291,1169),(281,1147),(267,1117),(256,1087),
         (244,1054),(237,1028),(227,994),(219,951),(218,924),(228,891),
         (242,862),(249,824),(220,847),(202,885),(182,916),(173,945),
         (158,981),(153,1015),(147,1051),(148,1085),(155,1112),(165,1139),
         (184,1174),(199,1202),(198,1213),(115,1216),(104,1200),(104,1180),
         (92,1150),(87,1118),(94,1092),(100,1069),(91,1056),(75,1062),
         (59,1046),(45,1046))
REIN_OPEN=((978,501),(1043,496),(1090,487),(1138,465),(1144,455),(1127,446),
           (1110,435),(1092,410),(1062,399),(1029,390),(1011,414),(998,450))
TAIL=((140,526),(219,494),(162,595),(146,687),(138,753),(137,839),(119,915),
      (99,1005),(95,1093),(24,1080),(19,692),(84,555))
HEAD=((1014,224),(1081,180),(1144,143),(1226,360),(1233,518),(1087,527),
      (1000,515),(973,566),(980,475),(969,382))
CLOAK=((430,204),(477,148),(550,150),(565,173),(520,208),(500,247),(494,320),
       (476,398),(440,498),(378,555),(287,604),(247,470),(326,436),(375,423),
       (412,369),(427,267))
TORSO_LEG_CUTS=(((122,701),(270,733),(275,834),(218,916),(176,1056),(225,1230),(65,1230),(78,1040),(97,844)),
                ((276,728),(355,751),(357,843),(315,916),(307,1010),(362,1122),(416,1214),(232,1230),(234,1117),(195,969),(215,821)),
                ((684,750),(816,761),(807,849),(796,911),(792,1004),(823,1220),(650,1220),(661,1048),(690,878)),
                ((790,706),(947,692),(930,790),(893,868),(865,976),(861,1075),(907,1231),(753,1231),(740,1110),(754,971),(762,846)))
# Each attached profile is listed back to front with hip, knee and hoof landmarks.
LEGS=((1,0,(296,741),(265,931),(344,1184)),
      (2,1,(759,764),(757,930),(742,1185)),
      (0,2,(205,736),(146,934),(151,1198)),
      (3,3,(840,732),(815,935),(839,1198)))


def mask(points):
    out=Image.new('L',SIZE)
    ImageDraw.Draw(out).polygon([(x*SOURCE_SCALE,y*SOURCE_SCALE) for x,y in points],fill=255)
    return np.asarray(out)>0


def pair(point):
    return np.asarray(point,dtype=float)*SOURCE_SCALE


@dataclass(frozen=True)
class Layer:
    image: Image.Image
    box: tuple


def crop_layer(rgb, region):
    alpha=Image.fromarray((255*region).astype('uint8'))
    sprite=rgb.copy()
    sprite.putalpha(alpha)
    box=alpha.getbbox()
    return Layer(sprite.crop(box),box)


@lru_cache(maxsize=1)
def build():
    source=Image.open(Path(__file__).with_name('jinete_referencia.png')).convert('RGBA')
    rgb=source.resize(SIZE,Image.Resampling.LANCZOS)
    person=mask(OUTLINE) & ~mask(REIN_OPEN)
    pixels=np.asarray(rgb)
    y=np.arange(SIZE[1])[:,None]
    x=np.arange(SIZE[0])[None,:]
    # Suppress the light studio floor between the four legs without touching silver armor.
    clean=(y>211)&((x<113)|(x>174))&(pixels[:,:,0]>144)&(pixels[:,:,1]>138)&(pixels[:,:,2]>125)
    boundary=person & ~np.asarray(Image.fromarray((person*255).astype('uint8')).filter(ImageFilter.MinFilter(3)),dtype=bool)
    studio=(pixels[:,:,0]>158)&(pixels[:,:,1]>146)&(pixels[:,:,2]>130)
    person &= ~(clean | (boundary&studio))
    stand=crop_layer(rgb,person)
    leg_masks=[mask(contour)&person for contour in TORSO_LEG_CUTS]
    # The near pair owns pixels that overlap the far pair.
    leg_masks[1]&=~leg_masks[0]
    leg_masks[2]&=~leg_masks[3]
    tail=mask(TAIL)&person
    head=mask(HEAD)&person
    cloak=mask(CLOAK)&person
    legs=[]
    for i,index,hip,joint,hoof in LEGS:
        area=leg_masks[i]&~tail
        legs.append((index,pair(hip),pair(joint),pair(hoof),crop_layer(rgb,area)))
    body=person & ~(np.logical_or.reduce(leg_masks)|tail|head|cloak)
    # Preserve a narrow overlap around the shoulder, saddle and cape attachment.
    body|=person&((mask(((146,683),(242,680),(363,682),(369,745),(285,777),(152,765))))|
                  mask(((682,703),(937,663),(930,753),(804,817),(723,800)))|
                  mask(((989,321),(1019,327),(1036,357),(1023,420),(1001,465),(975,480))))
    return stand,crop_layer(rgb,body),crop_layer(rgb,tail),crop_layer(rgb,head),crop_layer(rgb,cloak),legs


def place(target,layer,offset=(0,0)):
    target.alpha_composite(layer.image,(round(layer.box[0]+offset[0]),round(layer.box[1]+offset[1])))


def warp(target,layer,start,end,a,b):
    delta=(end-start).astype(float)
    goal=b-a
    den=float(delta@delta)
    c=float(goal@delta)/den
    s=float(delta[0]*goal[1]-delta[1]*goal[0])/den
    matrix=np.array(((c,-s),(s,c)))
    translation=a-matrix@start
    x0,y0,x1,y1=layer.box
    corners=np.array(((x0,y0),(x1,y0),(x0,y1),(x1,y1)))@matrix.T+translation
    left,top=np.floor(corners.min(axis=0)).astype(int)
    right,bottom=np.ceil(corners.max(axis=0)).astype(int)+1
    inv=np.linalg.inv(matrix)
    origin=inv@(np.array((left,top))-translation)-np.array((x0,y0))
    data=(inv[0,0],inv[0,1],origin[0],inv[1,0],inv[1,1],origin[1])
    tiled=layer.image.transform((right-left,bottom-top),Image.Transform.AFFINE,data,Image.Resampling.BILINEAR)
    target.alpha_composite(tiled,(int(left),int(top)))


def rotate(target,layer,anchor,angle,offset):
    pivot=pair(anchor)
    tip=pivot+np.array((0.,65.))
    aim=tip+np.array((-65*sin(angle),65*(cos(angle)-1)))
    warp(target,layer,pivot,tip,pivot+offset,aim+offset)


def deform_leg(canvas,layer,hip,knee,foot,slide,lift,bob):
    """Warp each leg continuously from shoulder to hoof, with no cut at the joint."""
    ys=np.array((layer.box[1]-4,hip[1],knee[1],foot[1],layer.box[3]+4),dtype=float)
    # Edge rows of the crop can lie inside a landmark; extend the support beyond both.
    ys[0]=min(ys[0],ys[1]-2)
    ys[-1]=max(ys[-1],ys[-2]+2)
    xs=np.array((0,0,slide*.43+lift*.13,slide,slide))
    vertical=np.array((bob,bob,bob*.47-lift*.36,-lift,-lift))
    y0=int(np.floor(np.min(ys+vertical)))
    y1=int(np.ceil(np.max(ys+vertical)))+1
    x0=int(np.floor(layer.box[0]+xs.min()))-1
    x1=int(np.ceil(layer.box[2]+xs.max()))+1

    # Smoothly interpolate the shear in the source rows. Use one mesh for the
    # entire leg so coat, hock and fetlock remain continuous as the hoof lifts.
    source_edges=np.linspace(ys[0],ys[-1],17)
    segment=np.clip(np.searchsorted(ys,source_edges,side='right')-1,0,len(ys)-2)
    fraction=(source_edges-ys[segment])/(ys[segment+1]-ys[segment])
    weight=fraction*fraction*(3-2*fraction)
    dx=xs[segment]+(xs[segment+1]-xs[segment])*weight
    dy=vertical[segment]+(vertical[segment+1]-vertical[segment])*weight
    warped_edges=source_edges+dy
    boundaries=np.unique(np.clip(np.rint(warped_edges).astype(int),y0,y1))
    boundaries=np.unique(np.r_[y0,boundaries,y1])
    tiles=[]
    for lo,hi in zip(boundaries,boundaries[1:]):
        src_lo,src_hi=np.interp((lo,hi),warped_edges,source_edges)
        offset_lo,offset_hi=np.interp((lo,hi),warped_edges,dx)
        left_lo=x0-offset_lo-layer.box[0]
        left_hi=x0-offset_hi-layer.box[0]
        top,bottom=src_lo-layer.box[1],src_hi-layer.box[1]
        quad=(left_lo,top,left_hi,bottom,left_hi+x1-x0,bottom,left_lo+x1-x0,top)
        tiles.append(((0,int(lo-y0),x1-x0,int(hi-y0)),quad))
    warped=layer.image.transform((x1-x0,y1-y0),Image.Transform.MESH,tiles,Image.Resampling.BILINEAR)
    canvas.alpha_composite(warped,(x0,y0))


def sprite(pose=None,wind=0):
    stand,body,tail,head,cloak,legs=build()
    canvas=Image.new('RGBA',SIZE)
    if pose is None:
        place(canvas,stand)
        return canvas
    t=pose.time
    activity=smooth(pose.speed/.58)
    breathing=.55*sin(t*2.1)
    bob=np.array((0.,-pose.bob*57+breathing))
    rotate(canvas,tail,(197,530),.025*sin(t*4.5)+wind*.072,bob)
    for flag in (False,True):
        if flag:
            place(canvas,body,bob)
            nod=(.046*sin(tau*pose.phase-.72)-pose.pitch*.52)*activity+.011*sin(t*1.82)
            rotate(canvas,head,(1016,402),nod,bob)
            rotate(canvas,cloak,(503,169),wind*.051+.015*sin(t*4.8),bob)
        for n,(index,hip,knee,foot,layer) in enumerate(legs):
            if (n>=2)!=flag:
                continue
            local=pose.feet[index].local
            base=(-.86 if index in (0,2) else .79)
            slide=float(np.clip((local[0]-base)*62,-29,29))*activity
            lift=float(np.clip((local[2]-.075)*91,0,22))*activity
            deform_leg(canvas,layer,hip,knee,foot,slide,lift,bob[1])
    return canvas


def grade(source,armor):
    if armor==0:
        return source
    rgba=np.array(source)
    rgb=rgba[:,:,:3].astype('float32')
    y,x=np.mgrid[:rgba.shape[0],:rgba.shape[1]]
    garment=(x>95)&(x<186)&(y<209)&(rgb[:,:,0]>rgb[:,:,2]*1.10)
    tint=(.78,1.15,.84) if armor==1 else (.89,.92,1.25)
    rgb[garment]*=np.asarray(tint)
    rgba[:,:,:3]=rgb.clip(0,255).astype('uint8')
    return Image.fromarray(rgba)


def character_canvas(pose,wind,heading,armor,width,height):
    actor=grade(sprite(pose,wind),armor)
    facing=cos(heading)>=0
    if not facing:
        actor=ImageOps.mirror(actor)
    return actor.resize((width,height),Image.Resampling.LANCZOS)


def ascii_layer(actor,atlas,light=1):
    """Compose only text glyphs over a transparent background."""
    rgba=np.asarray(actor)
    rgb=rgba[:,:,:3].astype('float32')
    alpha=rgba[:,:,3]
    contrast=(rgb@np.array((.23,.65,.12)))/255
    density=(.31+.68*contrast)*(len(ATLAS_CHARS)-1)
    weights=atlas[np.clip(density.astype('intp'),1,len(ATLAS_CHARS)-1)]
    rows,cols=alpha.shape
    h,w=atlas.shape[1:]
    size=(cols*w,rows*h)
    mask_grid=weights.transpose(0,2,1,3).reshape(size[1],size[0])
    mask_image=Image.fromarray(mask_grid)
    lit=(np.power(rgb/255.,.79)*255*(1.45*light)+13).clip(0,255).astype('uint8')
    tint=Image.fromarray(lit).resize(size,Image.Resampling.NEAREST)
    backing=Image.fromarray((lit*.19).astype('uint8')).resize(size,Image.Resampling.NEAREST)
    layer=Image.composite(tint,backing,mask_image).convert('RGBA')
    layer.putalpha(Image.fromarray(alpha).resize(size,Image.Resampling.BILINEAR))
    return layer
