"""Hand-drawn, articulated mount and rider in the storm scene."""
from math import cos, pi, sin, tau

from PIL import Image, ImageDraw

from caballero_del_faro import ease

WIDTH, HEIGHT = 160, 144
OUTLINE = '#140f16'
HORSE = '#c08257'
FAR = '#83574f'
LIGHT = '#edb78a'
MANE = '#432b38'
STEEL = '#b8d8e9'
ARMOR = '#7793ac'
CAPE = '#bd3f5d'
TRIM = '#ecc57f'


def frame(time, wind):
    """Draw a full side silhouette with four independently timed hooves."""
    image = Image.new('RGBA', (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    moving = ease(time/.6)*(1-ease((time-18.95)/1.02))
    stride = time*1.27
    bob = 2.1*cos(tau*stride*2)*moving + .45*sin(time*2.7)
    reach = ease((time-18.64)/1.16)*(1-ease((time-20.1)/1.7))

    def poly(points, fill, edge=OUTLINE, line=2):
        draw.polygon(points, fill=fill, outline=edge, width=line)

    def ellipse(box, fill, edge=OUTLINE):
        draw.ellipse(box, fill=fill, outline=edge, width=2)

    def path(points, color, width):
        draw.line(points, fill=color, width=width, joint='curve')

    def leg(x, back, far, offset):
        phase = (stride+offset)%1
        swing = ease((phase-.56)/.44)
        hoof_x = x+(-11+22*(1-phase/.56) if phase<.56 else -11+22*swing)*moving
        lift = 13*sin(pi*swing)*moving
        hoof_y = 136-lift-(4 if far else 0)
        hip = (x, 92+bob)
        knee = (x+(hoof_x-x)*.56+(8 if back else -4), 113-lift*.28+bob)
        ankle = (hoof_x, hoof_y-3)
        color = FAR if far else HORSE
        path((hip,knee,ankle), OUTLINE, 10 if far else 12)
        path((hip,knee,ankle), color, 6 if far else 8)
        if not far:
            path((knee,(ankle[0]-1,ankle[1]-1)), LIGHT, 2)
        poly(((hoof_x-4,hoof_y-4),(hoof_x+3,hoof_y-4),
              (hoof_x+6,hoof_y+1),(hoof_x-4,hoof_y+1)), MANE)

    for x,back,offset in ((50,True,.52),(112,False,.12)):
        leg(x,back,True,offset)
    tail = wind*7 + 2*sin(time*4.3)
    poly(((48,79+bob),(36,78+bob),(25,89+bob),
          (15+tail,106),(4+tail,109),(14+tail,115),(26+tail,111),
          (33,98),(47,89+bob)),MANE)
    path(((45,83+bob),(33,84),(24+tail*.4,101),(12+tail,112)),FAR,2)

    poly(((41,78+bob),(54,72+bob),(75,75+bob),(97,73+bob),
          (112,69+bob),(123,79+bob),(119,100+bob),(107,107+bob),
          (78,109+bob),(56,104+bob),(43,99+bob)),HORSE)
    poly(((46,80+bob),(65,76+bob),(101,77+bob),(111,84+bob),
          (99,89+bob),(63,91+bob),(49,89+bob)),LIGHT,None)
    poly(((52,98+bob),(75,101+bob),(110,97+bob),(113,102+bob),
          (106,107+bob),(77,109+bob),(60,105+bob)),FAR,None)

    head = 2.4*sin(tau*stride-.48)*moving + 1.25*sin(time*1.58)
    hy = bob+head
    poly(((100,78+bob),(110,61+hy),(118,49+hy),(126,53+hy),
          (131,71+hy),(125,94+bob),(112,103+bob),(103,94+bob)),HORSE)
    poly(((104,80+bob),(109,61+hy),(118,48+hy),(125,54+hy),
          (115,64+hy),(112,77+bob),(108,92+bob),(102,95+bob)),MANE)
    poly(((117,58+hy),(118,49+hy),(123,45+hy),(130,48+hy),
          (135,56+hy),(146,61+hy),(149,69+hy),(145,76+hy),
          (135,77+hy),(126,69+hy),(122,72+hy)),HORSE)
    poly(((120,51+hy),(118,38+hy),(123,39+hy),(126,49+hy)),HORSE)
    poly(((126,48+hy),(129,36+hy),(133,40+hy),(131,53+hy)),LIGHT)
    poly(((126,52+hy),(131,51+hy),(137,61+hy),(145,63+hy),
          (147,69+hy),(142,72+hy),(135,68+hy)),LIGHT,None)
    path(((130,58+hy),(125,65+hy),(134,72+hy),(145,70+hy)),MANE,2)
    draw.ellipse((130,55+hy,133,58+hy),fill=OUTLINE)
    draw.point((132,55+hy),fill='#fff0cb')
    draw.line((143,67+hy,145,68+hy),fill=OUTLINE,width=2)
    for x,back,offset in ((48,True,.03),(113,False,.62)):
        leg(x,back,False,offset)

    poly(((64,77+bob),(96,75+bob),(102,82+bob),(95,97+bob),(73,99+bob),(66,91+bob)),CAPE)
    path(((68,81+bob),(74,94+bob),(93,93+bob),(98,81+bob)),TRIM,2)
    poly(((66,77+bob),(80,73+bob),(99,75+bob),(96,82+bob),(72,84+bob)),MANE)

    hem = wind*11 + 3*sin(time*5.1)
    poly(((81,45+bob),(71,46+bob),(65,58+bob),(50,66+bob),
          (33+hem,70+bob),(42+hem*.6,80+bob),(57,82+bob),
          (72,72+bob),(86,57+bob)),CAPE)
    path(((76,50+bob),(63,65+bob),(50+hem*.35,73+bob),(38+hem,72+bob)), '#f67485',2)
    path(((75,56+bob),(58,75+bob),(46+hem*.6,77+bob)), '#762b51',3)

    poly(((73,44+bob),(79,39+bob),(93,41+bob),(99,52+bob),
          (95,65+bob),(91,75+bob),(75,74+bob),(71,60+bob)),STEEL)
    poly(((75,50+bob),(88,48+bob),(94,52+bob),(85,61+bob),(74,62+bob)),ARMOR,None)
    path(((75,66+bob),(84,65+bob),(91,66+bob)),TRIM,2)
    poly(((78,72+bob),(88,72+bob),(98,84+bob),(92,92+bob),
          (86,100+bob),(80,98+bob),(84,87+bob),(77,82+bob)),ARMOR)
    path(((81,74+bob),(93,84+bob),(87,93+bob)),STEEL,3)
    poly(((81,95+bob),(88,96+bob),(89,101+bob),(96,103+bob),
          (96,107+bob),(79,106+bob)),MANE)
    path(((79,101+bob),(88,103+bob),(94,104+bob)),TRIM,2)

    ellipse((77,20+bob,101,45+bob), STEEL)
    poly(((79,29+bob),(94,27+bob),(101,32+bob),(101,39+bob),
          (95,44+bob),(82,42+bob)),ARMOR)
    path(((84,33+bob),(92,32+bob),(101,33+bob)),OUTLINE,3)
    path(((83,24+bob),(91,22+bob),(97,25+bob)), '#e8f7ff',2)
    path(((96,35+bob),(98,38+bob)),TRIM,2)
    poly(((82,21+bob),(79,15+bob),(68+wind*4,12+bob),
          (76+wind*3,9+bob),(87,14+bob),(91,20+bob)),CAPE)

    hand = (111+reach*8,60+bob-reach*24)
    path(((95,49+bob),(102,59+bob),hand),OUTLINE,10)
    path(((95,49+bob),(102,59+bob),hand),STEEL,6)
    ellipse((hand[0]-3,hand[1]-3,hand[0]+3,hand[1]+3),TRIM)
    path((hand,(130,67+hy)),MANE,2)
    if time>17.7:
        tip=(hand[0]+3,hand[1]-12)
        path(((hand[0]-1,hand[1]+4),tip),TRIM,3)
        poly(((tip[0]-3,tip[1]),(tip[0]+wind*3,tip[1]-8-2*sin(time*11)),
              (tip[0]+4,tip[1]-4),(tip[0]+4,tip[1]+1)), '#ff9f51')
    return image, hand
