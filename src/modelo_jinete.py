"""Articulated rider and horse for the ASCII world scenes."""
from math import cos, hypot, pi, sin, sqrt, tau

import numpy as np

from caballero_del_faro import ease
from locomocion_ecuestre import FEET, knee_between

COAT = (110,73,62)
HIGHLIGHT = (135,94,77)
MANE = (34,29,37)
HOOF = (51,48,55)
STEEL = (164,179,191)
BLADE = (207,234,243)
ARMOR = (78,110,139)
CLOAK = (68,28,43)
GOLD = (221,168,83)
LEATHER = (68,45,40)


def rig(time, gait, wind, pose=None, armor=0):
    """Return ellipsoids with longitudinal, transverse and vertical axes."""
    cycle = time*1.34
    bob = gait*(.055*cos(tau*cycle*2))+.018*sin(time*2.3)
    nod = .10*gait*sin(tau*cycle-.7)+.045*sin(time*2.2)
    parts=[]
    def part(a,b,r,s,color):
        parts.append((a,b,r,s,color))
    roll, pitch = (pose.roll,pose.pitch) if pose else (0,0)
    if pose:
        bob=pose.bob+.012*sin(time*1.8)
        nod=.098*min(1,pose.speed)*sin(tau*pose.phase-.84)+.022*sin(time*1.6)
    for i,(forward,lateral) in enumerate(FEET):
        rear=forward<0
        if pose:
            x,y,z=pose.feet[i].local
            lift=max(0,z-.075)
        else:
            phase=(cycle+.25*i)%1
            swing=ease((phase-.61)/.39)
            stride=.39-.78*phase/.61 if phase<.61 else -.39+.78*swing
            x=forward+stride*gait+(-.15 if i==2 else .14 if i==0 else -.12 if i==1 else .06)
            y,z=lateral,.075+.20*sin(pi*swing)*gait
            lift=z-.075
        upper=np.array((forward-(.08 if rear else .04),lateral*.79,
                        1.32+bob+forward*pitch+lateral*roll))
        pastern=np.array((x-.068,y,z+.087))
        if rear:
            stifle=np.array((forward+.22+(x-forward)*.16,y*.91,1.02+bob+lift*.20))
            hock=knee_between(stifle,pastern,.515,.469,-1)
            part(upper,stifle,.163,.176,COAT)
            part(stifle,hock,.093,.109,COAT)
            part(hock+np.array((-.026,0,.058)),hock,.055,.071,MANE)
            part(hock,pastern,.044,.051,MANE)
        else:
            elbow=np.array((forward-.105+(x-forward)*.18,y*.86,1.025+bob+lift*.30))
            knee=knee_between(elbow,pastern,.455,.487,1)
            part(upper,elbow,.130,.149,COAT)
            part(elbow,knee,.083,.092,COAT)
            part(knee,pastern,.046,.050,MANE)
        coronet=(x+.024,y,z-.006)
        part(pastern,coronet,.045,.052,MANE)
        part((x-.061,y,z-.027),(x+.088,y,z-.030),.070,.049,HOOF)
    for side in (-1,1):
        part((1.447,.142*side,2.131+bob+nod),(1.514,.145*side,2.105+bob+nod),.021,.026,MANE)
        part((1.50,.14*side,2.229+bob+nod),(1.646,.105*side,1.877+bob+nod),.017,.024,LEATHER)
        part((1.566,.102*side,1.915+bob+nod),(1.668,.103*side,1.864+bob+nod),.019,.022,LEATHER)
    tail=(-1.44,wind*.14,.91+bob)
    part((-1.16,0,1.53+bob),tail,.091,.109,MANE)
    part(tail,(-1.47,wind*.24,.35+bob+.09*sin(time*3.1)),.064,.099,MANE)
    part((-.66,0,1.64+bob),(.06,0,1.69+bob),.31,.085,LEATHER)
    for side in (-1,1):
        hip=(-.35,side*.30,1.71+bob)
        knee=(-.015,side*.43,1.37+bob)
        ankle=(-.056,side*.431,.95+bob)
        part(hip,knee,.131,.118,ARMOR)
        part((knee[0]-.047,knee[1],knee[2]-.046),(knee[0]+.048,knee[1],knee[2]+.042),.083,.076,STEEL)
        part(knee,ankle,.081,.075,STEEL)
        part(ankle,(.110,ankle[1],.93+bob),.060,.059,LEATHER)
        part((.098,side*.463,.92+bob),(-.070,side*.463,.92+bob),.014,.017,GOLD)
    sway=roll*3
    lean=pitch*3
    for side in (-1,1):
        shoulder=(-.34+lean,.218*side+sway,2.41+bob)
        elbow=(-.46+lean,.247*side+sway,2.15+bob)
        hand=(-.037+lean,.171*side+sway,2.128+bob)
        part(shoulder,elbow,.084,.079,STEEL)
        part(elbow,hand,.070,.061,ARMOR)
        part(hand,(hand[0]+.067,hand[1],hand[2]-.013),.055,.050,LEATHER)
        bit=(1.58,.112*side,1.89+bob+nod)
        slack=(.78,.205*side,1.87+bob+nod*.32)
        part(hand,slack,.009,.013,LEATHER)
        part(slack,bit,.009,.013,LEATHER)

    if armor:
        palettes=(
            {STEEL:(168,155,109),ARMOR:(89,98,87),CLOAK:(57,113,95),BLADE:(240,222,165),GOLD:(237,185,90)},
            {STEEL:(117,135,161),ARMOR:(51,62,87),CLOAK:(95,71,146),BLADE:(176,213,232),GOLD:(174,188,202)},
        )
        palette=palettes[armor-1]
        parts=[(a,b,r,s,palette.get(color,color)) for a,b,r,s,color in parts]
    return parts


RING=tuple((cos(tau*i/8),sin(tau*i/8)) for i in range(8))
SIDE_SHADE=(.56,.82,1.13,1.28,1.14,.97,.76,.53)


def loft(sections,color,vertical=False):
    """Join shaped cross-sections. Each section defines width and depth independently."""
    rings=[]
    for x,y,z,width,depth in sections:
        if vertical:
            rings.append([(x+u*depth,y+v*width,z) for u,v in RING])
        else:
            rings.append([(x,y-u*width,z+v*depth) for u,v in RING])
    result=[]
    for row,(a,b) in enumerate(zip(rings,rings[1:])):
        for i,shade in enumerate(SIDE_SHADE):
            j=(i+1)%8
            tint=tuple(c*shade*(.95+.055*(row%3)) for c in color)
            result.extend(((a[i],a[j],b[j],tint),(a[i],b[j],b[i],tint)))
    return result


def sculpted_forms(time, gait, armor, pose):
    bob=pose.bob+.012*sin(time*1.8) if pose else gait*.055*cos(tau*time*2.68)+.018*sin(time*2.3)
    nod=(.098*min(1,pose.speed)*sin(tau*pose.phase-.84)+.022*sin(time*1.6)
         if pose else .10*gait*sin(tau*time*1.34-.7)+.045*sin(time*2.2))
    lean=pose.pitch*3 if pose else 0
    sway=pose.roll*3 if pose else 0
    torso=[(-1.31,0,1.29,.035,.055),(-1.13,0,1.34,.34,.32),
           (-.81,0,1.32,.36,.39),(-.39,0,1.26,.405,.42),
           (.20,0,1.31,.40,.42),(.67,0,1.40,.305,.39),(.98,0,1.53,.055,.18)]
    horse=loft([(x,y,z+bob,w,d) for x,y,z,w,d in torso],COAT)
    neck=[(.40,0,1.48,.196,.243),(.62,0,1.63,.295,.362),
          (.85,0,1.80,.251,.39),(1.035,0,1.995+nod*.52,.203,.342),
          (1.22,0,2.16+nod*.85,.159,.235),(1.38,0,2.23+nod,.103,.121)]
    horse+=loft([(x,y,z+bob,w,d) for x,y,z,w,d in neck],COAT)
    head=[(1.602,0,1.794+nod,.076,.076),(1.627,0,1.852+nod,.104,.112),
          (1.566,0,1.989+nod,.122,.145),(1.502,0,2.124+nod,.151,.182),
          (1.448,0,2.226+nod,.134,.153),(1.354,0,2.301+nod,.060,.066)]
    horse+=loft([(x,y,z+bob,w,d) for x,y,z,w,d in head],HIGHLIGHT,True)
    for sign in (-1,1):
        heel=(1.362,sign*.071,2.239+nod+bob)
        base=(1.472,sign*.112,2.254+nod+bob)
        tip=(1.423,sign*.143,2.451+nod+bob)
        inside=(1.435,sign*.132,2.301+nod+bob)
        horse.extend(((heel,base,tip,COAT),(base,inside,tip,MANE)))
    horse+=loft([(x,0,z+bob+nod*k,w,d) for x,z,k,w,d in
                ((.421,1.82,0,.044,.102),(.66,1.98,.17,.064,.14),
                 (.92,2.199,.54,.052,.117),(1.19,2.332,.83,.041,.076),
                 (1.42,2.332,1,.028,.051))],MANE)
    finish=((170,181,194),(172,152,98),(112,139,153))[armor]
    chest=[(-.34,0,1.65,.191,.109),(-.34,0,1.83,.143,.120),(-.32,0,2.08,.176,.149),
           (-.318,0,2.36,.218,.133),(-.30,0,2.45,.088,.091)]
    rider=loft([(x+lean,y+sway,z+bob,w,d) for x,y,z,w,d in chest],finish,True)
    for z,w in ((1.93,.237),(2.01,.213),(2.10,.190)):
        rider+=loft([(-.33+lean,sway,z+bob,w,.135),(-.30+lean,sway,z+bob+.043,w*.94,.142)],finish,True)
    helm=[(-.265,0,2.423,.094,.119),(-.255,0,2.50,.118,.160),
          (-.255,0,2.638,.121,.177),(-.275,0,2.735,.105,.122),(-.296,0,2.806,.023,.038)]
    rider+=loft([(x+lean,y+sway,z+bob,w,d) for x,y,z,w,d in helm],finish,True)
    visor=[(-.162+lean,sway-.102,2.609+bob),(-.095+lean,sway-.039,2.608+bob),
           (-.097+lean,sway+.038,2.632+bob),(-.164+lean,sway-.104,2.633+bob)]
    rider.extend(((visor[0],visor[1],visor[2],MANE),(visor[0],visor[2],visor[3],MANE)))
    return horse+rider


def equipment_mesh(t, wind, armor, pose):
    bob=pose.bob+.012*sin(t*1.8) if pose else .018*sin(t*2.3)
    colors=((ARMOR,GOLD,CLOAK),( (89,98,87),(237,185,90),(57,113,95)),
            ((51,62,87),(174,188,202),(95,71,146)))
    steel,rim,cloth=colors[armor]
    faces=[]
    # Surcoat folds open toward the back; each row lags the row above.
    def fabric(u,v):
        wave=sin(t*3.3-v*1.9+u*3.7)
        return (-.46-.25*v-.12*v*v, u*(.19+v*.13)+wind*v*.17,
                2.40-.96*v+wave*.075*v+bob)
    columns=(-1,-.50,0,.5,1)
    rows=(0,.26,.51,.76,1)
    for i,(top,bottom) in enumerate(zip(rows,rows[1:])):
        for j,(left,right) in enumerate(zip(columns,columns[1:])):
            a,b,c,d=fabric(left,top),fabric(right,top),fabric(right,bottom),fabric(left,bottom)
            shade=.67+.24*(j%2)+.13*sin(t*2.1+i)
            tint=tuple(c*shade for c in cloth)
            faces.extend(((a,b,c,tint),(a,c,d,tint)))
    # The shield hangs from the near saddle strap and follows its sway.
    shape=((-0.68,2.11),(-.25,2.10),(-.26,1.87),(-.43,1.56),(-.62,1.76))
    if armor==1:
        shape=((-0.69,2.06),(-.48,2.16),(-.25,2.08),(-.25,1.85),(-.45,1.59),(-.65,1.77))
    swing=.025*sin(t*2.8)+(pose.roll*.28 if pose else 0)
    outer=[(x,.466+swing,z+bob) for x,z in shape]
    inner=[(-.47+(x+.47)*.87,.493+swing,1.88+(z-1.88)*.89+bob) for x,z in shape]
    peak=(-.47,.556+swing,1.87+bob)
    for i in range(len(shape)):
        j=(i+1)%len(shape)
        faces.extend(((outer[i],outer[j],inner[j],rim),(outer[i],inner[j],inner[i],rim),
                      (inner[i],inner[j],peak,tuple(c*(1.10 if i<3 else .68) for c in steel))))
    emblem=[(-.47,.559+swing,1.99+bob),(-.416,.559+swing,1.88+bob),
            (-.47,.560+swing,1.76+bob),(-.523,.559+swing,1.88+bob)]
    faces.extend(((emblem[0],emblem[1],emblem[2],rim),(emblem[0],emblem[2],emblem[3],rim)))
    return faces


def draw_mesh(faces, transform, scale, cx, cy, source, depth, light):
    rows, cols=depth.shape
    points=np.asarray([face[:3] for face in faces])@transform.T
    screen=points[:,:,:2]*scale+(cx,cy)
    lower=np.maximum(0,np.floor(screen.min(axis=1)).astype(int))
    upper=np.minimum((cols,rows),np.ceil(screen.max(axis=1)).astype(int)+1)
    a=screen[:,1]-screen[:,0]
    b=screen[:,2]-screen[:,0]
    determinants=a[:,0]*b[:,1]-b[:,0]*a[:,1]
    indices=np.flatnonzero((upper>lower).all(axis=1)&(np.abs(determinants)>=.001))
    for i in indices:
        p,xy,color=points[i],screen[i],faces[i][3]
        x0,y0=lower[i]
        x1,y1=upper[i]
        av,bv,det=a[i],b[i],determinants[i]
        gx=np.arange(x0,x1)[None,:]-xy[0,0]
        gy=np.arange(y0,y1)[:,None]-xy[0,1]
        u=(gx*bv[1]-gy*bv[0])/det
        v=(gy*av[0]-gx*av[1])/det
        z=-(p[0,2]+u*(p[1,2]-p[0,2])+v*(p[2,2]-p[0,2]))
        target=depth[y0:y1,x0:x1]
        mask=(u>=0)&(v>=0)&(u+v<=1)&(z>target)
        target[mask]=z[mask]
        source[y0:y1,x0:x1][mask]=np.asarray(color)*(.73+.36*light)


def draw(time, gait, wind, yaw, scale, cx, cy, shape, light, pose=None, armor=0, tilt=.54):
    """Project each rounded volume with a depth buffer and diffuse light."""
    rows,cols=shape
    source=np.zeros((rows,cols,3),dtype='float32')
    depth=np.full(shape,-np.inf,dtype='float32')
    rotation=np.array(((cos(yaw),-sin(yaw),0),(sin(yaw),cos(yaw),0),(0,0,1)))
    normal=(1-tilt**2)**.5
    camera=np.array(((1,0,0),(0,tilt,-normal),(0,-normal,-tilt)))
    transform=camera@rotation
    illumination=np.array((-.42,-.69,-.59))
    for a,b,r,s,color in rig(time,gait,wind,pose,armor):
        a,b=np.asarray(a),np.asarray(b)
        axis=b-a
        length=sqrt(axis@axis)
        axis=axis/length
        vx,vy,vz=axis
        horizontal=hypot(vx,vy)
        sx,sy=(-vy/horizontal,vx/horizontal) if horizontal>.03 else (0,1)
        end=length*.5+.05
        basis=transform@np.array(((vx*end,sx*r,-vz*sy*s),
                                  (vy*end,sy*r,vz*sx*s),
                                  (vz*end,0,(vx*sy-vy*sx)*s)))
        covariance=basis@basis.T
        center=transform@((a+b)*.5)
        extent=np.sqrt(np.diag(covariance))
        x,y=cx+scale*center[0],cy+scale*center[1]
        x0,x1=max(0,int(x-extent[0]*scale)),min(cols,int(x+extent[0]*scale)+2)
        y0,y1=max(0,int(y-extent[1]*scale)),min(rows,int(y+extent[1]*scale)+2)
        if x1<=x0 or y1<=y0:
            continue
        gx=(np.arange(x0,x1)[None,:]-x)/scale
        gy=(np.arange(y0,y1)[:,None]-y)/scale
        aa,ab,bb=covariance[0,0],covariance[0,1],covariance[1,1]
        det=aa*bb-ab*ab
        nx=(bb*gx-ab*gy)/det
        ny=(aa*gy-ab*gx)/det
        radius=gx*nx+gy*ny
        zx,zy=covariance[:2,2]
        height=np.sqrt(np.maximum(0,1-radius))
        variance=covariance[2,2]-(bb*zx*zx-2*ab*zx*zy+aa*zy*zy)/det
        surface=center[2]+nx*zx+ny*zy-height*sqrt(max(1e-6,variance))
        # Smaller camera depth means nearer.
        target=depth[y0:y1,x0:x1]
        mask=(radius<1)&(-surface>target)
        if not mask.any():
            continue
        target[mask]=-surface[mask]
        diffuse=np.clip(nx*illumination[0]*extent[0]+ny*illumination[1]*extent[1]+height*.69,0,1)
        glint=np.maximum(0,1-abs(nx*extent[0]+.25))**5
        metal=color in (STEEL,BLADE,ARMOR,GOLD) or color in ((168,155,109),(117,135,161),(240,222,165),(176,213,232))
        bright=(.28+.78*diffuse+light*.23)+(1-height)**2*.17+glint*height*(.25 if metal else .07)
        tinted=np.asarray(color)*bright[...,None]+light*np.array((32,16,4))
        source[y0:y1,x0:x1][mask]=tinted[mask]
    faces=sculpted_forms(time,gait,armor,pose)+equipment_mesh(time,wind,armor,pose)
    draw_mesh(faces,transform,scale,cx,cy,source,depth,light)
    return source,np.isfinite(depth)
