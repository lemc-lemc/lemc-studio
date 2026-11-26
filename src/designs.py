from dataclasses import dataclass
from functools import lru_cache
import math

from PIL import Image, ImageDraw


PALETTES = {
    'Carbón': ('#080809', '#b2b2b2', '#e6e6e6', '#c9c9c9'),
    'Rojiblanco': ('#0d090e', '#ff524f', '#ffede3', '#ffd2c5'),
    'Invierno': ('#071526', '#54e2ac', '#ffe1a0', '#9bcaff'),
    'Aurora': ('#0d1029', '#b698ff', '#fff1ad', '#70dfdf'),
    'Cobre': ('#1b111f', '#ff8f75', '#fff2cf', '#a3b9ff'),
    'Pétalo': ('#22101d', '#ff9eb7', '#ffe2c5', '#ebbfeb'),
    'Noche azul': ('#0b1430', '#98b9ff', '#ffe4aa', '#b7e5ff'),
    'Esmeralda': ('#0d2220', '#7ceac4', '#f9e7a0', '#a8d9f5'),
    'Amanecer': ('#291827', '#ffb180', '#fff0b2', '#ebcbff'),
    'Lavanda': ('#1b1432', '#d0b4ff', '#ffe0f1', '#a8c9ff'),
    'Coral': ('#281520', '#ff8179', '#ffd1a1', '#ffc8df'),
    'Lluvia': ('#141d2a', '#a1bedc', '#e3e8ff', '#89bbdc'),
    'Mar profundo': ('#071e2b', '#67dce8', '#f4e2a7', '#a8bcff'),
    'Oro antiguo': ('#201812', '#ffc575', '#fff3ce', '#c7d0c4'),
}


@dataclass(frozen=True)
class CodeTheme:
    panel: str
    border: str
    text: str
    keyword: str
    literal: str
    muted: str
    active: str


CODE_THEMES = {
    'Rojiblanco': CodeTheme('#1b1015', '#74333d', '#fbebe5', '#ff817e', '#ffd4ae', '#c7a6a8', '#41212a'),
    'Terminal': CodeTheme('#101822', '#334760', '#d6e8f5', '#96bbff', '#f6ca90', '#879cb9', '#1c2e42'),
    'Ciruela': CodeTheme('#1e1426', '#594162', '#f4e5fb', '#f6a7eb', '#ffca9f', '#b6a0be', '#372445'),
    'Bosque': CodeTheme('#102621', '#355749', '#dcf3e5', '#7ee7b5', '#f4d38b', '#a0b9ae', '#1e4739'),
    'Glaciar': CodeTheme('#101c38', '#3c5a83', '#e5f0ff', '#80d3ff', '#ffd6ae', '#9eb3d7', '#1c3359'),
    'Grafito': CodeTheme('#1c1c1e', '#4b4b52', '#f1f0f4', '#ece0b7', '#ffb5ae', '#aaaab5', '#34343b'),
    'Papel': CodeTheme('#f2ece0', '#b8a691', '#251d24', '#723575', '#8a3b20', '#5f505b', '#e0d5c9'),
    'Océano': CodeTheme('#0b2430', '#31576a', '#dcf3fa', '#74e0e3', '#ffcf95', '#93b8c4', '#143e51'),
}


@dataclass(frozen=True)
class Design:
    palette: str
    code: str
    phrases: dict


DESIGNS = {
    'Árbol': Design('Invierno', 'Bosque', {
        'Esperanza': ('Todavía me quedan ganas de crecer.', 'La raíz también crece en la oscuridad.'),
        'Constancia': ('Lo que cuidas un poco cada día acaba dando sombra.', 'Crecer despacio sigue siendo crecer.'),
    }),
    'Estrella': Design('Noche azul', 'Glaciar', {
        'Esperanza': ('A veces basta una luz pequeña para encontrar el camino.', 'Todavía hay luz, aunque hoy parezca lejos.'),
        'Amor': ('De todas las luces, aprendí a reconocer la tuya.', 'Me gusta el cielo desde que lo miro contigo.'),
    }),
    'Corazón': Design('Pétalo', 'Ciruela', {
        'Amor': ('Contigo, hasta el silencio tiene compañía.', 'Te elijo en las cosas pequeñas de todos los días.'),
        'Gratitud': ('Gracias por escuchar lo que no sabía decir.', 'Qué bueno haber coincidido contigo.'),
    }),
    'Luna': Design('Lavanda', 'Glaciar', {
        'Calma': ('No tienes que resolverlo todo esta noche.', 'Baja el ritmo. Todavía hay tiempo.'),
        'Tristeza': ('Hoy me pesa un poco más. Mañana lo hablaré.', 'Aunque hoy me falte luz, sigo aquí.'),
    }),
    'Sol': Design('Amanecer', 'Papel', {
        'Esperanza': ('Mañana también es un buen lugar para empezar.', 'Hoy vuelve a entrar la luz por la ventana.'),
        'Inspiración': ('Abre la ventana y elige una cosa para empezar.', 'Hazle sitio a lo que te devuelve las ganas.'),
    }),
    'Montaña': Design('Noche azul', 'Glaciar', {
        'Constancia': ('Si hoy llegas hasta aquí, mañana puedes partir desde aquí.', 'Descansar también cuenta en una subida larga.'),
        'Fortaleza': ('La cima espera. Ahora importa el paso que sí puedes dar.', 'El terreno difícil también se cruza por tramos.'),
    }),
    'Ola': Design('Mar profundo', 'Océano', {
        'Calma': ('Lo que sientes puede moverse sin arrastrarte.', 'Respira antes de decidir qué hacer con este día.'),
        'Tristeza': ('Este oleaje también bajará.', 'Hoy dejo que la pena pase a su ritmo.'),
    }),
    'Flor': Design('Pétalo', 'Ciruela', {
        'Gratitud': ('Gracias por quedarte cuando apenas empezaba a crecer.', 'Me acuerdo de quien me cuidó en los días difíciles.'),
        'Esperanza': ('Puedo volver a abrirme, a mi ritmo.', 'No todas las flores despiertan el mismo día.'),
    }),
    'Mariposa': Design('Aurora', 'Ciruela', {
        'Inspiración': ('Tal vez cambiar también sea volver a conocerte.', 'Puedes probar otra forma de vivir este día.'),
        'Fortaleza': ('Aprendí a salir de lo que ya no me dejaba crecer.', 'Cambiar me dio miedo y aun así di el paso.'),
    }),
    'Infinito': Design('Aurora', 'Terminal', {
        'Amor': ('Quiero seguir encontrándote en las pequeñas cosas.', 'Contigo, siempre me quedo un ratito más.'),
        'Constancia': ('Si tropiezas, puedes retomar desde donde estás.', 'Volver a intentarlo también es una forma de aprender.'),
    }),
    'Brújula': Design('Oro antiguo', 'Papel', {
        'Inspiración': ('Cuando tengas dudas, vuelve a lo que te importa.', 'Puedes cambiar de rumbo sin perder todo lo aprendido.'),
        'Esperanza': ('Aunque no veas el mapa entero, puedes elegir un paso.', 'Hoy solo necesito saber en qué dirección quiero ir.'),
    }),
    'Rayo': Design('Oro antiguo', 'Grafito', {
        'Fortaleza': ('Defiende lo que te importa sin dejar de cuidarte.', 'Hoy me atrevo a dar el paso que llevaba posponiendo.'),
        'Constancia': ('Haz una parte pequeña, incluso si las ganas tardan.', 'Empieza con lo que tienes a mano.'),
    }),
    'Lágrima': Design('Lluvia', 'Glaciar', {
        'Tristeza': ('Si hoy necesitas llorar, puedes darte ese tiempo.', 'Esta tristeza merece un lugar y alguien que escuche.'),
        'Calma': ('Puedo sentirlo sin tener que explicarlo ahora.', 'Hoy me basta con tratarme con un poco de paciencia.'),
    }),
    'Ancla': Design('Mar profundo', 'Océano', {
        'Fortaleza': ('Vuelve a lo que te sostiene cuando todo se mueve.', 'Pedir apoyo también requiere valor.'),
        'Gratitud': ('Gracias por ser un lugar seguro para volver.', 'Me sostuvo saber que podía contar contigo.'),
    }),
    'Diamante': Design('Lavanda', 'Grafito', {
        'Fortaleza': ('Lo difícil que viví no decide lo que valgo.', 'Puedo protegerme y seguir siendo sensible.'),
        'Inspiración': ('Haz algo que te recuerde de qué eres capaz.', 'Mira con cuidado lo que haces bien a diario.'),
    }),
    'Puente': Design('Cobre', 'Papel', {
        'Constancia': ('Hoy solo necesito avanzar hasta el siguiente paso.', 'Lo atravesaré por partes, con las pausas que necesite.'),
        'Amor': ('Puedo acercarme a ti y seguir siendo yo.', 'Hablemos hasta encontrar por dónde acercarnos.'),
    }),
    'Planeta': Design('Aurora', 'Glaciar', {
        'Inspiración': ('Sal de tu órbita un momento y mira qué encuentras.', 'Sigue la pregunta que te da curiosidad.'),
        'Calma': ('Haz espacio. Todo puede esperar unos minutos.', 'Mi vida tiene un ritmo que puedo cuidar.'),
    }),
    'Llama': Design('Coral', 'Ciruela', {
        'Fortaleza': ('Cuida esa parte de ti que aún quiere intentarlo.', 'Lo valiente hoy puede ser dar un paso pequeño.'),
        'Amor': ('Hay afectos que abrigan sin quemar.', 'Me gusta lo fácil que es estar cerca de ti.'),
    }),
}
MOODS = ('Amor', 'Esperanza', 'Constancia', 'Fortaleza', 'Tristeza', 'Calma', 'Gratitud', 'Inspiración')


@lru_cache(maxsize=42)
def silhouette(name, size=256):
    mask = Image.new('L', (size, size))
    draw = ImageDraw.Draw(mask)
    def polygon(coords, fill=255):
        draw.polygon([(round(x * size), round(y * size)) for x, y in coords], fill=fill)
    def oval(bounds, fill=255):
        draw.ellipse(tuple(round(n * size) for n in bounds), fill=fill)
    def line(coords, width, fill=255):
        draw.line([(round(x * size), round(y * size)) for x, y in coords], fill=fill,
                  width=max(1, round(width * size)), joint='curve')
    if name == 'Estrella':
        a = [i * math.pi / 5 - math.pi / 2 for i in range(10)]
        polygon([(0.5 + math.cos(t) * (0.45 if i % 2 == 0 else 0.2),
                  0.52 + math.sin(t) * (0.45 if i % 2 == 0 else 0.2)) for i, t in enumerate(a)])
    elif name == 'Corazón':
        angles = (i * math.tau / 150 for i in range(150))
        polygon([(0.5 + 0.40 * math.sin(a) ** 3, 0.46 - .026 * (13*math.cos(a) - 5*math.cos(2*a)
                  - 2*math.cos(3*a) - math.cos(4*a))) for a in angles])
    elif name == 'Árbol':
        polygon(((.5,.06),(.23,.40),(.31,.40),(.13,.62),(.22,.62),(.07,.82),(.44,.82),(.44,.94),(.56,.94),(.56,.82),(.93,.82),(.77,.62),(.87,.62),(.69,.40),(.77,.40)))
    elif name == 'Luna':
        oval((.10,.09,.91,.91)); oval((.36,.025,.96,.73), 0)
    elif name == 'Sol':
        oval((.23,.23,.77,.77))
        for i in range(12):
            a = i * math.tau / 12
            line(((.5 + .32*math.cos(a), .5 + .32*math.sin(a)), (.5 + .44*math.cos(a), .5 + .44*math.sin(a))), .048)
    elif name == 'Montaña':
        polygon(((.04,.79),(.382,.19),(.54,.47),(.67,.28),(.96,.79)))
        polygon(((.30,.34),(.382,.22),(.46,.36),(.419,.34),(.385,.39),(.353,.325)), 0)
    elif name == 'Ola':
        polygon(((.04,.73),(.10,.62),(.21,.59),(.30,.40),(.39,.29),(.48,.24),(.62,.23),(.76,.30),(.86,.38),(.94,.52),(.81,.48),(.70,.47),(.61,.52),(.575,.61),(.67,.69),(.79,.73),(.95,.68),(.94,.82),(.70,.88),(.46,.81),(.26,.87),(.07,.82)))
    elif name == 'Flor':
        for i in range(5):
            a = i * math.tau / 5 - math.pi/2
            x, y = .5 + .23*math.cos(a), .46 + .23*math.sin(a)
            oval((x-.18,y-.18,x+.18,y+.18))
        oval((.385,.35,.615,.58), 0); oval((.417,.382,.583,.55)); line(((.5,.68),(.5,.94)), .068)
    elif name == 'Mariposa':
        for flip in (-1, 1):
            for wing in (((.01,.39),(.16,.13),(.31,.11),(.42,.25),(.42,.41),(.32,.49),(.20,.52),(.035,.51)),
                         ((.01,.51),(.22,.48),(.34,.55),(.31,.75),(.19,.88),(.08,.78))):
                polygon(tuple((.5 + flip*x, y) for x, y in wing))
            line(((.5,.40),(.5 + flip*.10,.20)), .022)
        oval((.465,.36,.535,.77))
    elif name == 'Infinito':
        curve = [(0.5 + .37*math.cos(i*math.tau/170), 0.5 + .22*math.sin(i*2*math.tau/170)) for i in range(171)]
        line(curve, .10)
    elif name == 'Brújula':
        oval((.07,.07,.93,.93)); oval((.13,.13,.87,.87),0)
        polygon(((.70,.23),(.62,.60),(.29,.78),(.42,.39))); polygon(((.64,.32),(.49,.44),(.57,.51)),0)
    elif name == 'Rayo':
        polygon(((.56,.06),(.18,.57),(.47,.57),(.38,.95),(.83,.36),(.54,.38),(.68,.06)))
    elif name == 'Lágrima':
        polygon(((.5,.055),(.39,.24),(.30,.39),(.22,.55),(.19,.68),(.24,.82),(.37,.92),(.50,.95),(.63,.92),(.76,.82),(.81,.68),(.78,.55),(.70,.39),(.61,.24)))
        oval((.287,.58,.35,.78), 0)
    elif name == 'Ancla':
        oval((.39,.06,.61,.28)); oval((.455,.12,.545,.21),0)
        line(((.5,.25),(.5,.87)),.08); line(((.31,.35),(.69,.35)),.07)
        line(((.15,.64),(.19,.76),(.30,.86),(.50,.92),(.70,.86),(.81,.76),(.85,.64)),.088)
        polygon(((.09,.70),(.14,.56),(.25,.65))); polygon(((.91,.70),(.86,.56),(.75,.65)))
    elif name == 'Diamante':
        polygon(((.20,.20),(.80,.20),(.95,.41),(.50,.90),(.05,.41)))
        line(((.08,.42),(.92,.42)),.025,0); line(((.40,.23),(.32,.42),(.50,.86),(.68,.42),(.60,.23)),.025,0)
    elif name == 'Puente':
        polygon(((.08,.45),(.92,.45),(.92,.78),(.76,.78),(.70,.66),(.58,.59),(.42,.59),(.30,.66),(.24,.78),(.08,.78)))
        line(((.10,.40),(.90,.40)),.045)
        for x in (.17,.33,.5,.67,.83):
            line(((x,.32),(x,.45)),.033)
    elif name == 'Planeta':
        oval((.22,.21,.78,.77))
        curve = [(0.5 + .41 * math.cos(t) * .94 - .13*math.sin(t)*.34,
                  0.5 + .41*math.cos(t)*.34 + .13*math.sin(t)*.94) for t in (i*math.tau/150 for i in range(151))]
        line(curve,.048)
    elif name == 'Llama':
        polygon(((.46,.06),(.70,.27),(.78,.42),(.80,.57),(.81,.68),(.75,.82),(.65,.91),(.50,.95),(.35,.91),(.23,.82),(.19,.67),(.22,.53),(.33,.39),(.38,.50),(.48,.40),(.51,.31)))
        polygon(((.53,.45),(.63,.58),(.66,.72),(.59,.83),(.50,.87),(.41,.81),(.37,.72),(.42,.64),(.46,.70)),0)
    else:
        oval((.12,.12,.88,.88))
    return mask
