"""Fixed-step mounted locomotion with ground contacts in world coordinates."""
from dataclasses import dataclass, field
from math import atan2, cos, exp, hypot, pi, sin, tau

import numpy as np

FEET = ((-.86,-.31),(.79,-.31),(-.86,.31),(.79,.31))
STANCE = .64
DT = 1/120


def smooth(t):
    t = min(1,max(0,t))
    return t*t*(3-2*t)


def damp(value,target,rate,dt):
    return target+(value-target)*exp(-rate*dt)


@dataclass
class Hoof:
    anchor: np.ndarray
    target: np.ndarray
    offset: float
    prior: float
    local: np.ndarray = field(default_factory=lambda: np.zeros(3))


class Mount:
    def __init__(self,x=21.9,y=22.5):
        self.position=np.array((x,y),dtype=float)
        self.heading=-pi/2.3
        self.speed=0.
        self.turn=0.
        self.time=0.
        self.phase=0.
        self.bob=0.
        self.pitch=0.
        self.roll=0.
        self.moving=False
        self.contacts=[]
        self.feet=[]
        self.reset_feet()

    def translate(self,a,b):
        c,s=cos(self.heading),sin(self.heading)
        return self.position+np.array((a*c-b*s,a*s+b*c))

    def reset_feet(self):
        self.feet=[]
        for index,(a,b) in enumerate(FEET):
            offset=(-index*.25)%1
            point=self.translate(a,b)
            self.feet.append(Hoof(point,point.copy(),offset,(self.phase+offset)%1,np.array((a,b,.075))))

    def step(self,dt,drive,steer,bounds=(3,39,3,43)):
        self.time+=dt
        desired=max(0,drive)*1.72
        self.speed=damp(self.speed,desired,3.1 if drive>0 else (7 if drive<0 else 2.8),dt)
        if self.speed<.022:
            self.speed=0.
        self.turn=damp(self.turn,steer*min(self.speed*1.2,1.18),5.0,dt)
        self.heading+=self.turn*dt
        velocity=np.array((cos(self.heading),sin(self.heading)))*self.speed
        future=self.position+velocity*dt
        left,right,top,bottom=bounds
        self.position=np.clip(future,(left,top),(right,bottom))
        if np.any(self.position!=future):
            self.speed*=.87
        cadence=.53+.46*self.speed
        advance=self.speed*cadence/max(.46,self.speed)*dt
        self.phase=(self.phase+advance)%1
        power=min(1,self.speed/.82)
        if self.speed>0 and not self.moving:
            self.reset_feet()
        self.moving=self.speed>0
        contacts=[]
        walking_phase=self.phase
        for (a,b),hoof in zip(FEET,self.feet):
            phase=(walking_phase+hoof.offset)%1
            wrapped=phase<hoof.prior-.5
            if self.moving and hoof.prior<STANCE<=phase:
                hoof.target=self.translate(a,b)+velocity*((1-STANCE+STANCE*.5)/cadence)
            if self.moving and wrapped:
                hoof.anchor=hoof.target.copy()
                contacts.append(tuple(hoof.anchor))
            hoof.prior=phase
            u=smooth((phase-STANCE)/(1-STANCE)) if self.moving else 0.
            foot=hoof.anchor+(hoof.target-hoof.anchor)*u
            delta=foot-self.position
            c,s=cos(self.heading),sin(self.heading)
            height=.075+.20*sin(pi*u)*power
            goal=np.array((delta[0]*c+delta[1]*s,-delta[0]*s+delta[1]*c,height))
            # Finish a suspended foot as the horse comes to rest.
            if not self.moving:
                hoof.local=damp(hoof.local,np.array((a,b,.075)),14,dt)
            else:
                hoof.local=goal
        self.contacts=contacts
        self.bob=damp(self.bob,power*(.033*cos(tau*walking_phase*2)),12,dt)
        self.roll=damp(self.roll,power*.046*sin(tau*walking_phase)-self.turn*.060,9,dt)
        self.pitch=damp(self.pitch,power*.031*sin(tau*walking_phase*2+.7)
                        -max(0,desired-self.speed)*.034,9,dt)


def knee_between(hip,foot,upper,lower,bend):
    """Two-bone IK projected toward the leg's anatomical bend direction."""
    hip,foot=np.asarray(hip),np.asarray(foot)
    delta=foot-hip
    distance=max(.00001,np.linalg.norm(delta))
    axis=delta/distance
    length=min(upper+lower-.001,max(abs(upper-lower)+.001,distance))
    along=(upper*upper-lower*lower+length*length)/(2*length)
    orthogonal=np.array((float(bend),0,0))-axis*axis[0]*bend
    norm=max(1e-6,np.linalg.norm(orthogonal))
    return hip+axis*along+orthogonal/norm*max(0,upper*upper-along*along)**.5
