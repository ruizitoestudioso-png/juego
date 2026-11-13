#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PAPAS BOMBA  v2  -  encapuchados, papas que explotan, rojo y blanco
Raspberry Pi 3 + GrovePi+ (opcional)

Dos encapuchados (ROJO y BLANCO) se lanzan papas bomba en una cancha.
El que quede frito pierde la ronda. Gana el primero que llegue a 3 rondas.
Se puede jugar de a 2 en el mismo teclado o 1 jugador contra la CPU.

                 moverse    pone papa       tira papa          dispara
  ROJO   (J1):   W A S D    E               F                  Q
  BLANCO (J2):   FLECHAS    CTRL derecho    SHIFT derecho      ENTER
                            (o 0 numerico)  (o punto numerico)

  P o ESC: pausa        F11: pantalla completa        ESC en el menu: salir

Tirar papa: sale volando hacia donde miras, pasa por encima de todo y cae
unas 3 casillas adelante. Parado encima de una papa (tuya o del rival),
la recoges y la lanzas.

Canon de papitas: 3 balas que se recargan solas (1 cada 6 s). Una papita
deja frito al rival y si le pega a una papa bomba la hace explotar.

Muerte subita: a los 90 segundos la cancha se empieza a cerrar desde los
bordes hacia el centro y las balas se vuelven infinitas.

Canchas (rotan por ronda), cada una con su ambiente:
  La Plazoleta  -> ladrillo rojo y cajas de madera
  El Pasillo    -> casilleros azules y cajas de carton
  La Cafeteria  -> barras, mesas en vez de cajas y cocineros sirviendo

Poderes que salen de las cajas:
  Aji         -> la explosion llega mas lejos
  Papa extra  -> puedes tener mas papas a la vez
  Tinto       -> te mueves mas rapido

GrovePi+ (si no esta conectado, el juego funciona igual):
  Buzzer -> D8   suena con cada explosion
  LED    -> D4   se prende cuando alguien queda frito
  Boton  -> D3   acepta en los menus / pasa a la siguiente ronda (como ENTER)

Correr:   python3 papas_bomba.py
Opciones: -f            pantalla completa
          --sin-sonido  no usa el parlante (el buzzer del GrovePi sigue sonando)
"""
from __future__ import division, print_function, unicode_literals

import array
import math
import random
import sys
import threading
import time

try:
    import queue
except ImportError:          # Python 2
    import Queue as queue

import pygame

# ------------------------------------------------------------------ ajustes
COLS, ROWS = 15, 13
TILE = 44
HUD = 56
W, H = COLS * TILE, ROWS * TILE + HUD
FPS = 30

BOMB_TIME = 2.5        # segundos que tarda en explotar una papa
FIRE_TIME = 0.6        # segundos que dura el fuego
WINS_TO_MATCH = 3      # rondas para ganar la partida
THROW_DIST = 3         # casillas que vuela una papa lanzada

ROUND_TIME = 90        # segundos antes de la muerte subita
DEMO_ROUND_TIME = 40   # lo mismo, pero en la demostracion del menu
SD_STEP = 0.3          # cada cuanto se cierra una casilla en muerte subita

AMMO_MAX = 3           # balas del canon de papitas
AMMO_RECHARGE = 6.0    # segundos para recargar 1 bala
SHOT_COOLDOWN = 0.5    # tiempo minimo entre disparos
SD_SHOT_COOLDOWN = 0.3 # en muerte subita se dispara mas rapido
BULLET_SPEED = 10.0    # casillas por segundo

CRATE_CHANCE = 0.62    # que tan llena de cajas sale la cancha
POWER_CHANCE = 0.32    # cuantas cajas esconden un poder

BUZZER, LED, BOTON = 8, 4, 3   # puertos digitales del GrovePi

EMPTY, WALL, BLOCK = 0, 1, 2
DIRS = [(0, -1), (0, 1), (-1, 0), (1, 0)]      # arriba, abajo, izq, der
POWER_KINDS = ["aji", "papa", "tinto"]
POWER_TEXT = {"aji": "+FUEGO", "papa": "+PAPA", "tinto": "+VELOCIDAD"}

# Canchas. '#' es muro fijo. Todas son simetricas (girando 180 grados) para
# que sea justo: ROJO sale arriba a la izquierda y BLANCO abajo a la derecha.
LAYOUTS = [
    ("LA PLAZOLETA", [
        "###############",
        "#.............#",
        "#.##.#...#.##.#",
        "#.#.........#.#",
        "#....##.##....#",
        "#.#.#.....#.#.#",
        "#......#......#",
        "#.#.#.....#.#.#",
        "#....##.##....#",
        "#.#.........#.#",
        "#.##.#...#.##.#",
        "#.............#",
        "###############"]),
    ("EL PASILLO", [
        "###############",
        "#.............#",
        "#.###.#.#.###.#",
        "#.....#.#.....#",
        "#.#.#.....#.#.#",
        "#.#.#.###.#.#.#",
        "#.............#",
        "#.#.#.###.#.#.#",
        "#.#.#.....#.#.#",
        "#.....#.#.....#",
        "#.###.#.#.###.#",
        "#.............#",
        "###############"]),
    ("LA CAFETERIA", [
        "###############",
        "#.............#",
        "#.##..#.#..##.#",
        "#.....#.#.....#",
        "#..#.......#..#",
        "#.##.##.##.##.#",
        "#.............#",
        "#.##.##.##.##.#",
        "#..#.......#..#",
        "#.....#.#.....#",
        "#.##..#.#..##.#",
        "#.............#",
        "###############"]),
]

# ------------------------------------------------------------------ colores
# Paleta base roja y blanca (personajes, barra, menus). Cada cancha le suma
# sus propios colores en THEMES.
C_INK = (42, 14, 18)            # contornos
C_BLACK = (12, 4, 6)
C_RED = (214, 40, 48)
C_RED_L = (240, 86, 86)
C_RED_D = (160, 24, 34)
C_RED_DD = (100, 14, 22)
C_WHITE = (250, 247, 242)
C_CREAM = (236, 229, 220)
C_PINK = (255, 214, 214)
C_FLOOR_A = (233, 226, 217)
C_FLOOR_B = (223, 215, 205)
C_GROUT = (206, 197, 187)
C_SHADOW = (190, 180, 170)      # sombra sobre el piso (opaca: mas rapida en la Pi)
C_HUD = (112, 14, 24)
C_HUD_D = (72, 8, 16)
C_GRAY = (150, 140, 136)
C_SPARK = (255, 214, 120)
C_FIRE_MID = (255, 122, 72)
C_POTATO = (214, 170, 90)
C_POTATO_D = (120, 80, 35)
C_POTATO_L = (240, 212, 145)

# cada encapuchado: color del saco, su sombra, cordones y ojos
SCH_ROJO = {"main": C_RED, "dark": C_RED_D, "string": C_WHITE, "eye": C_WHITE}
SCH_BLANCO = {"main": C_WHITE, "dark": (204, 196, 188), "string": C_RED, "eye": C_WHITE}
SCH_FRITO = {"main": (62, 44, 40), "dark": (44, 30, 28), "string": (96, 76, 66), "eye": (200, 190, 180)}

# Cada cancha tiene su propio ambiente (mismo orden que LAYOUTS).
#   walls: como se ven los muros      crate: como se ven las "cajas" que se rompen
#   cooks: si hay cocineros sirviendo en la linea de comida de arriba
THEMES = [
    # La Plazoleta: ladrillo rojo, baldosa blanca y cajas de madera
    {"floor_a": C_FLOOR_A, "floor_b": C_FLOOR_B, "grout": C_GROUT, "hi": C_WHITE,
     "shadow": C_SHADOW, "walls": "brick", "crate": "crate", "cooks": False,
     "debris": [C_WHITE, C_RED, C_CREAM, C_RED_D]},
    # El Pasillo: piso azul claro, casilleros y cajas de carton
    {"floor_a": (214, 223, 234), "floor_b": (198, 209, 224), "grout": (176, 189, 206), "hi": (234, 240, 248),
     "shadow": (160, 173, 192), "walls": "locker", "crate": "box", "cooks": False,
     "debris": [(206, 164, 112), (224, 188, 140), (150, 112, 70), (236, 214, 170)]},
    # La Cafeteria: piso amarillo, barras de madera, mesas con mantel y cocineros
    {"floor_a": (250, 233, 192), "floor_b": (241, 216, 164), "grout": (222, 197, 142), "hi": (255, 245, 218),
     "shadow": (208, 182, 130), "walls": "counter", "crate": "table", "cooks": True,
     "debris": [C_WHITE, (240, 150, 150), (150, 96, 46), (204, 146, 80)]},
]


def irect(x, y, w, h):
    return pygame.Rect(int(x), int(y), max(1, int(w)), max(1, int(h)))


def circ(s, color, x, y, r, width=0):
    r = max(1, int(r))
    pygame.draw.circle(s, color, (int(x), int(y)), r, min(int(width), r))


def line(s, color, a, b, width=1):
    pygame.draw.line(s, color, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), max(1, int(width)))


def rrect(s, color, rect, r):
    """Rectangulo con esquinas redondas (sirve en pygame 1.9 y 2)."""
    rect = pygame.Rect(rect)
    r = int(min(r, rect.w // 2, rect.h // 2))
    if r <= 0:
        pygame.draw.rect(s, color, rect)
        return
    pygame.draw.rect(s, color, (rect.x + r, rect.y, rect.w - 2 * r, rect.h))
    pygame.draw.rect(s, color, (rect.x, rect.y + r, rect.w, rect.h - 2 * r))
    for cx, cy in ((rect.x + r, rect.y + r), (rect.right - r - 1, rect.y + r),
                   (rect.x + r, rect.bottom - r - 1), (rect.right - r - 1, rect.bottom - r - 1)):
        pygame.draw.circle(s, color, (cx, cy), r)


def draw_hooded(s, cx, cy, sch, face, k=1.0, step=0.0, moving=False,
                gun=False, blink=False, shadow=True, fried=False):
    """Dibuja un encapuchado centrado en (cx, cy). k es la escala."""
    fx, fy = face
    bob = math.sin(step) * 1.5 if moving else 0.0
    swing = math.sin(step) if moving else 0.0
    main, dark = sch["main"], sch["dark"]

    def P(dx, dy):
        return (int(cx + dx * k), int(cy + dy * k))

    def R(dx, dy, w, h):
        return irect(cx + dx * k, cy + dy * k, w * k, h * k)

    lw = max(1, int(round(k)))
    if shadow:           # shadow puede ser True o el color de sombra del piso
        pygame.draw.ellipse(s, shadow if isinstance(shadow, tuple) else C_SHADOW, R(-13, 11, 26, 9))
    # piernas
    pygame.draw.rect(s, C_INK, R(-7, 9, 6, 8 - max(0.0, swing) * 3))
    pygame.draw.rect(s, C_INK, R(1, 9, 6, 8 - max(0.0, -swing) * 3))
    # canon detras del cuerpo si mira hacia arriba
    if gun and fy < 0:
        _draw_gun(s, P, fx, fy, k)
    # brazos y cuerpo
    for side in (-1, 1):
        ax, ay = side * 12, 4 + bob + side * swing * 1.5
        circ(s, C_INK, cx + ax * k, cy + ay * k, 5.2 * k)
        circ(s, main, cx + ax * k, cy + ay * k, 3.8 * k)
    pygame.draw.ellipse(s, C_INK, R(-13, -6 + bob, 26, 24))
    pygame.draw.ellipse(s, dark, R(-11, -4 + bob, 22, 20))
    pygame.draw.ellipse(s, main, R(-11, -5 + bob, 22, 18))
    if fy >= 0:      # bolsillo canguro
        line(s, dark, P(-5, 9 + bob), P(5, 9 + bob), lw)
    # capucha con punta
    tip = -fx * 4
    pygame.draw.polygon(s, C_INK, [P(-12, -13 + bob), P(tip - 1, -27 + bob), P(12, -13 + bob)])
    circ(s, C_INK, cx, cy + (-10 + bob) * k, 13 * k)
    pygame.draw.polygon(s, main, [P(-9, -14 + bob), P(tip - 1, -24 + bob), P(9, -14 + bob)])
    circ(s, main, cx, cy + (-10 + bob) * k, 11.4 * k)
    if fy < 0:
        # de espaldas: solo la costura de la capucha
        line(s, dark, P(0, -21 + bob), P(0, -1 + bob), lw)
    else:
        ox = fx * 4.5
        if fx == 0:
            pygame.draw.ellipse(s, C_BLACK, R(-7.5, -16 + bob, 15, 13))
            eyes = (-3.4, 3.4)
        else:
            pygame.draw.ellipse(s, C_BLACK, R(ox - 5.5, -16 + bob, 11, 13))
            eyes = (ox - 2.2 + fx, ox + 2.2 + fx)
        ey = -9.5 + bob
        for e in eyes:
            if fried:
                line(s, sch["eye"], P(e - 1.5, ey - 1.5), P(e + 1.5, ey + 1.5), lw)
                line(s, sch["eye"], P(e + 1.5, ey - 1.5), P(e - 1.5, ey + 1.5), lw)
            elif blink:
                line(s, sch["eye"], P(e - 1.6, ey), P(e + 1.6, ey), lw)
            else:
                pygame.draw.ellipse(s, sch["eye"], R(e - 1.6, ey - 2.2, 3.2, 4.4))
        # cordones
        for sx in (-3, 3):
            line(s, sch["string"], P(sx + ox * 0.6, -1 + bob), P(sx + ox * 0.6, 5 + bob), lw)
            circ(s, sch["string"], cx + (sx + ox * 0.6) * k, cy + (6 + bob) * k, 1.3 * k)
    if gun and fy >= 0:
        _draw_gun(s, P, fx, fy, k)


def _draw_gun(s, P, fx, fy, k):
    a = P(fx * 6, 5)
    b = P(fx * 20, 5 + fy * 14)
    line(s, C_INK, a, b, 7 * k)
    line(s, C_GRAY, a, b, 3 * k)
    circ(s, C_RED, b[0], b[1], 3.5 * k)
    circ(s, C_WHITE, b[0], b[1], 1.5 * k)


# ------------------------------------------------------------------ GrovePi
class Hardware(object):
    """Maneja el GrovePi en un hilo aparte para no trabar el juego.
    Si no hay GrovePi, todas las funciones simplemente no hacen nada."""

    def __init__(self):
        self.ok = False
        self.q = queue.Queue()
        self.button_flag = False
        self.running = True
        try:
            import grovepi
            self.g = grovepi
            grovepi.pinMode(BUZZER, "OUTPUT")
            grovepi.pinMode(LED, "OUTPUT")
            grovepi.pinMode(BOTON, "INPUT")
            grovepi.digitalWrite(BUZZER, 0)
            grovepi.digitalWrite(LED, 0)
            self.ok = True
        except Exception as e:
            print("GrovePi no disponible ({}). Se juega sin buzzer ni LED.".format(e))
        if self.ok:
            t = threading.Thread(target=self._loop)
            t.daemon = True
            t.start()

    # pasos: lista de (pin, valor, espera_despues)
    def _send(self, steps):
        if self.ok:
            self.q.put(steps)

    def _short(self, dur):
        if self.q.qsize() < 3:
            self._send([(BUZZER, 1, dur), (BUZZER, 0, 0.0)])

    def boom(self):
        self._short(0.12)

    def throw(self):
        self._short(0.02)

    def shoot(self):
        self._short(0.01)

    def tick(self):
        self._short(0.04)

    def go(self):
        self._short(0.25)

    def pick(self):
        self._send([(BUZZER, 1, 0.03), (BUZZER, 0, 0.05), (BUZZER, 1, 0.03), (BUZZER, 0, 0.0)])

    def death(self):
        self._send([(LED, 1, 0.0), (BUZZER, 1, 0.5), (BUZZER, 0, 0.0)])

    def win(self):
        self._send([(BUZZER, 1, 0.1), (BUZZER, 0, 0.08)] * 3 + [(BUZZER, 1, 0.4), (BUZZER, 0, 0.0)])

    def sudden(self):
        self._send([(BUZZER, 1, 0.15), (BUZZER, 0, 0.1)] * 4)

    def reset(self):
        self._send([(LED, 0, 0.0), (BUZZER, 0, 0.0)])

    def take_button(self):
        f = self.button_flag
        self.button_flag = False
        return f

    def _loop(self):
        pending = []          # (momento, pin, valor) en orden
        last_btn = 0
        next_poll = 0.0
        while self.running:
            now = time.time()
            try:
                while True:
                    steps = self.q.get_nowait()
                    t = max(now, pending[-1][0]) if pending else now
                    for pin, val, wait in steps:
                        pending.append((t, pin, val))
                        t += wait
            except queue.Empty:
                pass
            while pending and pending[0][0] <= now:
                _, pin, val = pending.pop(0)
                try:
                    self.g.digitalWrite(pin, val)
                except (IOError, OSError):
                    pass
            if now >= next_poll:
                next_poll = now + 0.05
                try:
                    v = self.g.digitalRead(BOTON)
                except (IOError, OSError, TypeError):
                    v = 0
                if v == 1 and last_btn != 1:
                    self.button_flag = True
                last_btn = v
            time.sleep(0.01)

    def close(self):
        self.running = False
        if self.ok:
            time.sleep(0.05)
            try:
                self.g.digitalWrite(BUZZER, 0)
                self.g.digitalWrite(LED, 0)
            except (IOError, OSError):
                pass


# ------------------------------------------------------------------ sonido
class Sfx(object):
    """Efectos de sonido hechos con matematicas (no hay archivos de audio).
    Salen por el HDMI o el plug de audio. Si no hay parlante, no pasa nada."""

    def __init__(self, enabled=True):
        self.ok = False
        self.snd = {}
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
            self.rate, fmt, self.ch = pygame.mixer.get_init()[:3]
            if fmt != -16:
                raise ValueError("formato de audio no soportado")
            self.build()
            self.ok = True
        except Exception as e:
            print("Sin sonido ({}).".format(e))

    def synth(self, parts, vol=0.5):
        """parts: lista de (onda, frec_inicial, frec_final, duracion).
        onda: 'sq' cuadrada, 'sin' seno, 'noise' ruido, 'rest' silencio."""
        rate = self.rate
        out = []
        rnd = random.Random(7)
        for wave, f0, f1, dur in parts:
            n = max(1, int(rate * dur))
            phase, lp = 0.0, 0.0
            for i in range(n):
                u = i / n
                f = f0 + (f1 - f0) * u
                phase += f / rate
                if wave == "sq":
                    v = 0.7 if (phase % 1.0) < 0.5 else -0.7
                elif wave == "sin":
                    v = math.sin(2 * math.pi * phase)
                elif wave == "noise":
                    lp += (rnd.uniform(-1, 1) - lp) * min(1.0, f / 3000.0)
                    v = lp * 1.6
                else:
                    v = 0.0
                env = min(1.0, i / 40.0) * (1.0 - u) ** 1.4
                out.append(v * env * vol)
        return out

    def mix(self, a, b):
        if len(a) < len(b):
            a, b = b, a
        return [a[i] + (b[i] if i < len(b) else 0.0) for i in range(len(a))]

    def make(self, samples):
        buf = array.array("h")
        for v in samples:
            iv = int(max(-1.0, min(1.0, v)) * 32000)
            for _ in range(self.ch):
                buf.append(iv)
        raw = buf.tobytes() if hasattr(buf, "tobytes") else buf.tostring()
        return pygame.mixer.Sound(buffer=raw)

    def build(self):
        S, M = self.synth, self.make
        self.snd = {
            "boom": M(self.mix(S([("noise", 2600, 120, 0.6)], 0.9), S([("sin", 110, 38, 0.5)], 0.8))),
            "place": M(S([("sq", 240, 150, 0.07)], 0.35)),
            "throw": M(S([("noise", 500, 2600, 0.17)], 0.45)),
            "shoot": M(self.mix(S([("sq", 900, 180, 0.1)], 0.35), S([("noise", 3000, 800, 0.08)], 0.4))),
            "pick": M(S([("sq", 660, 660, 0.06), ("sq", 880, 880, 0.06), ("sq", 1320, 1320, 0.12)], 0.35)),
            "death": M(S([("sq", 520, 70, 0.55)], 0.45)),
            "win": M(S([("sq", 523, 523, 0.1), ("sq", 659, 659, 0.1), ("sq", 784, 784, 0.1),
                        ("sq", 1047, 1047, 0.35)], 0.4)),
            "tick": M(S([("sin", 660, 660, 0.09)], 0.5)),
            "go": M(S([("sin", 990, 990, 0.3)], 0.5)),
            "sudden": M(S([("sq", 440, 880, 0.22), ("sq", 440, 880, 0.22), ("sq", 440, 880, 0.3)], 0.4)),
            "menu": M(S([("sin", 520, 520, 0.05)], 0.4)),
            "select": M(S([("sq", 700, 1050, 0.1)], 0.35)),
        }

    def play(self, name):
        if self.ok and name in self.snd:
            self.snd[name].play()


# ------------------------------------------------------------------ objetos
class Bomb(object):
    def __init__(self, x, y, owner, rng):
        self.x, self.y = x, y
        self.owner = owner
        self.range = rng
        self.t = BOMB_TIME
        self.flying = False
        self.fx, self.fy = x, y      # casilla de donde salio volando
        self.fly_t = 0.0
        self.fly_dur = 0.0


class Bullet(object):
    """Papita disparada por el canon. x, y en casillas (con decimales)."""
    def __init__(self, owner, x, y, dx, dy):
        self.owner = owner
        self.x, self.y = x, y
        self.dx, self.dy = dx, dy


class Player(object):
    def __init__(self, num, name, spawn, sch, move_keys, bomb_keys, throw_keys, shoot_keys):
        self.num = num
        self.base_name = name
        self.name = name
        self.spawn = spawn
        self.sch = sch
        self.move_keys = move_keys      # arriba, abajo, izq, der
        self.bomb_keys = bomb_keys
        self.throw_keys = throw_keys
        self.shoot_keys = shoot_keys
        self.wins = 0
        self.reset()

    def reset(self):
        self.x, self.y = self.spawn
        self.px, self.py = self.x, self.y
        self.alive = True
        self.dead_t = 0.0
        self.max_bombs = 1
        self.range = 2
        self.speed_lvl = 0
        self.delay = 0.20
        self.move_t = 0.0
        self.face = (0, 1) if self.num == 1 else (0, -1)
        self.ammo = AMMO_MAX
        self.ammo_t = 0.0
        self.cool = 0.0
        self.gun_t = 0.0
        self.held = []                  # direcciones apretadas, la ultima manda

    def progress(self):
        if self.move_t <= 0:
            return 1.0
        return max(0.0, min(1.0, 1.0 - self.move_t / self.delay))

    def tile_pos(self):
        """Posicion en casillas con decimales (mientras camina entre dos casillas)."""
        p = self.progress()
        return self.px + (self.x - self.px) * p, self.py + (self.y - self.py) * p

    def draw_pos(self):
        fx, fy = self.tile_pos()
        return fx * TILE + TILE / 2, HUD + fy * TILE + TILE / 2


# ------------------------------------------------------------------ CPU
class Bot(object):
    """Cerebro de la CPU. Decide en cada casilla: huir del peligro, poner o
    tirar papas, disparar si tiene al rival en la mira, o ir por poderes."""

    def __init__(self, game, me, rival):
        self.g, self.p, self.r = game, me, rival
        self.reset()

    def reset(self):
        self.react = 0.6
        self.act_cool = 1.0          # no hace nada el primer segundo
        self.bad = set()             # casillas donde poner papa era un suicidio
        self.bad_t = 4.0
        self.wander = None
        self.hunt = 7                # a cuantos pasos empieza a perseguir

    def danger_map(self, extra=None):
        """Casilla -> segundos que faltan para que le llegue el fuego."""
        g = self.g
        d = {}
        for pos in g.fire:
            d[pos] = 0.0
        bombs = []
        for b in g.bombs:
            t = b.t
            if b.flying:
                t = max(t, b.fly_dur - b.fly_t)
            bombs.append([b.x, b.y, b.range, t])
        if extra:
            bombs.append(list(extra))
        blasts = [g.blast_cells(b[0], b[1], b[2]) for b in bombs]
        for _ in range(2):           # reaccion en cadena: explota con la mas rapida
            for i, b in enumerate(bombs):
                for j, cells in enumerate(blasts):
                    if i != j and (b[0], b[1]) in cells and bombs[j][3] < b[3]:
                        b[3] = bombs[j][3]
        for b, cells in zip(bombs, blasts):
            for c in cells:
                if b[3] < d.get(c, 99.0):
                    d[c] = b[3]
        if g.sudden:
            for i, pair in enumerate(g.sd_cells[:10]):
                t = (i + 1) * SD_STEP - g.sd_timer
                for c in pair:
                    if t < d.get(c, 99.0):
                        d[c] = t
        return d

    def bfs(self, danger, flee):
        """Casillas alcanzables -> (distancia, primera direccion).
        flee=True deja cruzar casillas peligrosas si alcanza a salir a tiempo."""
        g, p = self.g, self.p
        start = (p.x, p.y)
        seen = {start: (0, None)}
        order = [start]
        i = 0
        while i < len(order):
            c = order[i]
            i += 1
            dist, first = seen[c]
            for di, (dx, dy) in enumerate(DIRS):
                n = (c[0] + dx, c[1] + dy)
                if n in seen or not g.walkable(n[0], n[1]):
                    continue
                if n in danger:
                    if not flee or danger[n] < (dist + 2) * p.delay + 0.2:
                        continue
                seen[n] = (dist + 1, di if first is None else first)
                order.append(n)
        return seen, order

    def can_escape(self, extra):
        d2 = self.danger_map(extra)
        seen, _ = self.bfs(d2, True)
        return any(c not in d2 for c in seen)

    def try_shoot(self, dt):
        g, p, r = self.g, self.p, self.r
        lined = None
        if r.alive and (p.x == r.x) != (p.y == r.y):
            dx = (r.x > p.x) - (r.x < p.x)
            dy = (r.y > p.y) - (r.y < p.y)
            dist = abs(r.x - p.x) + abs(r.y - p.y)
            if dist <= 7:
                lined = (dx, dy)
                for i in range(1, dist):
                    cx, cy = p.x + dx * i, p.y + dy * i
                    if g.grid[cy][cx] != EMPTY or g.bomb_at(cx, cy):
                        lined = None
                        break
        if lined and p.cool <= 0 and (p.ammo > 0 or g.sudden):
            self.react -= dt
            if self.react <= 0:
                p.face = lined
                g.shoot(p)
                self.react = random.uniform(0.5, 1.0)
        elif not lined:
            self.react = max(self.react, 0.45)

    def think(self, dt):
        """Devuelve la direccion (0-3) a la que quiere caminar, o None."""
        g, p, r = self.g, self.p, self.r
        self.act_cool = max(0.0, self.act_cool - dt)
        self.bad_t -= dt
        if self.bad_t <= 0:
            self.bad.clear()
            self.bad_t = 4.0
        if not p.alive:
            return None
        self.try_shoot(dt)
        if p.move_t > 0:
            return None
        here = (p.x, p.y)
        danger = self.danger_map()

        # 1. si me va a llegar el fuego, corro a la casilla segura mas cercana
        if here in danger:
            seen, order = self.bfs(danger, True)
            for c in order:
                if c not in danger:
                    return seen[c][1]
            return None

        seen, order = self.bfs(danger, False)

        # 2. poner o tirar una papa
        if self.act_cool <= 0 and g.count_bombs(p) < p.max_bombs:
            rp = (r.x, r.y) if r.alive else None
            if g.bomb_at(p.x, p.y) is None:
                cells = g.blast_cells(p.x, p.y, p.range)
                hits_rival = rp in cells
                hits_crate = any(g.grid[cy][cx] == BLOCK for (cx, cy) in cells)
                if hits_rival or (hits_crate and here not in self.bad):
                    if self.can_escape((p.x, p.y, p.range, BOMB_TIME)):
                        g.place_bomb(p)
                        self.act_cool = 0.4
                        return None
                    self.bad.add(here)
            if rp and random.random() < 0.5:
                for d in DIRS:
                    dest = g.throw_target(p.x, p.y, d)
                    if not dest:
                        continue
                    cells = g.blast_cells(dest[0], dest[1], p.range)
                    if rp in cells and here not in cells:
                        p.face = d
                        g.throw_bomb(p)
                        self.act_cool = 0.8
                        return None

        # 3. a donde camino
        target, best = None, 99
        for c in g.powerups:
            if c in seen and seen[c][0] < best:
                target, best = c, seen[c][0]
        if target is None or best > 8:
            if g.sudden:              # al centro, que es lo ultimo que se cierra
                target = min(order, key=lambda c: (abs(c[0] - COLS // 2) + abs(c[1] - ROWS // 2), seen[c][0]))
            else:
                target = None
                rp = (r.x, r.y)
                if r.alive and rp in seen and seen[rp][0] <= self.hunt:
                    target = rp               # el rival esta cerca: a cazarlo
                else:
                    for c in order:
                        if c not in self.bad and g.near_crate(c[0], c[1]):
                            target = c
                            break
                if target is None and r.alive and rp in seen:
                    target = rp
                if target is None:
                    if self.wander not in seen or self.wander == here:
                        self.wander = random.choice(order)
                    target = self.wander
        if target is None or target == here:
            return None
        return seen[target][1]


# ------------------------------------------------------------------ juego
class Game(object):
    MENU = ["2 JUGADORES", "1 JUGADOR VS CPU", "CÓMO JUGAR", "SALIR"]

    def __init__(self, canvas, hw, sfx):
        self.s = canvas
        self.hw = hw
        self.sfx = sfx
        self.fonts = {}
        self.text_cache = {}
        self.shades = {}
        self.players = [
            Player(1, "ROJO", (1, 1), SCH_ROJO,
                   [pygame.K_w, pygame.K_s, pygame.K_a, pygame.K_d],
                   [pygame.K_e],                                  # pone
                   [pygame.K_f],                                  # tira
                   [pygame.K_q]),                                 # dispara
            Player(2, "BLANCO", (COLS - 2, ROWS - 2), SCH_BLANCO,
                   [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT],
                   [pygame.K_RCTRL, pygame.K_KP0],                # pone
                   [pygame.K_RSHIFT, pygame.K_KP_PERIOD],         # tira
                   [pygame.K_RETURN, pygame.K_KP_ENTER]),         # dispara
        ]
        self.bots = [None, None]
        self.vs_cpu = False
        self.demo = True
        self.quit = False
        self.paused = False
        self.state = "menu"
        self.menu_i = 0
        self.wait = 0.0
        self.round = 0
        self.winner = None
        self.now = 0.0
        self.shake = 0.0
        self.count_t = 0.0
        self.go_t = 0.0
        self.end_t = 0.0
        self.confetti_t = 0.0
        self.npc_duck = 0.0
        self.layout_order = [0, 1, 2]
        self.layout_name = ""
        self.layer = pygame.Surface((W, H))
        self.make_tiles()
        self.goto_menu()

    # ---------------- utilidades
    def font(self, size):
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(None, size)
        return self.fonts[size]

    def render(self, s, size, color):
        key = (s, size, color)
        img = self.text_cache.get(key)
        if img is None:
            if len(self.text_cache) > 400:
                self.text_cache.clear()
            img = self.font(size).render(s, True, color)
            self.text_cache[key] = img
        return img

    def text(self, s, size, color, pos, shadow=None, anchor="center", off=2):
        img = self.render(s, size, color)
        r = img.get_rect()
        setattr(r, anchor, (int(pos[0]), int(pos[1])))
        if shadow:
            self.s.blit(self.render(s, size, shadow), r.move(off, off))
        self.s.blit(img, r)
        return r

    def shade(self, color, alpha, size=None):
        """Capa semitransparente (se guarda para no crearla en cada cuadro)."""
        size = size or (W, H)
        key = (color, alpha, size)
        if key not in self.shades:
            sh = pygame.Surface(size, pygame.SRCALPHA)
            sh.fill(color + (alpha,))
            self.shades[key] = sh
        return self.shades[key]

    def emit(self, name):
        """Un evento del juego: suena en el parlante y en el buzzer del GrovePi."""
        if name == "boom":
            self.shake = max(self.shake, 7.0)
        if self.demo:
            return
        self.sfx.play(name)
        fn = getattr(self.hw, name, None)
        if fn:
            fn()

    def world_active(self):
        return self.state in ("playing", "ending", "menu", "howto")

    def bomb_at(self, x, y):
        """Papa que esta en el piso en (x, y). Las que van volando no cuentan."""
        for b in self.bombs:
            if b.x == x and b.y == y and not b.flying:
                return b
        return None

    def count_bombs(self, p):
        return sum(1 for b in self.bombs if b.owner is p)

    def landing_free(self, x, y):
        if not (0 < x < COLS - 1 and 0 < y < ROWS - 1):
            return False
        if self.grid[y][x] != EMPTY:
            return False
        return all(not (b.x == x and b.y == y) for b in self.bombs)

    def walkable(self, x, y):
        return self.grid[y][x] == EMPTY and self.bomb_at(x, y) is None

    def near_crate(self, x, y):
        return any(self.grid[y + dy][x + dx] == BLOCK for dx, dy in DIRS)

    # ---------------- particulas y efectos
    def spark(self, x, y, vx, vy, life, size, color, grav=0.0, square=False):
        if len(self.parts) < 240:
            self.parts.append([x, y, vx, vy, life, life, size, color, grav, square])

    def burst(self, x, y, n, colors, speed=120.0, life=0.5, size=4.0, grav=0.0, square=False):
        for _ in range(n):
            a = random.uniform(0, 2 * math.pi)
            v = random.uniform(0.3, 1.0) * speed
            self.spark(x, y, math.cos(a) * v, math.sin(a) * v, random.uniform(0.5, 1.0) * life,
                       random.uniform(0.6, 1.0) * size, random.choice(colors), grav, square)

    def floater(self, x, y, txt, color):
        self.floaters.append([x, y, txt, color, 1.0])

    def update_fx(self, dt):
        self.shake = max(0.0, self.shake - dt * 22.0)
        duck = 12.0 if self.fire else 0.0       # los cocineros se agachan con el fuego
        self.npc_duck += (duck - self.npc_duck) * min(1.0, dt * 12.0)
        for p in self.parts:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += p[8] * dt
            p[4] -= dt
        self.parts = [p for p in self.parts if p[4] > 0 and p[1] < H + 10]
        for f in self.floaters:
            f[1] -= 28 * dt
            f[4] -= dt
        self.floaters = [f for f in self.floaters if f[4] > 0]
        for r in self.rings:
            r[2] += dt
        self.rings = [r for r in self.rings if r[2] < 0.3]

    # ---------------- mapa
    def floor_tiles(self, th, rnd):
        out = []
        for col in (th["floor_a"], th["floor_b"]):
            t = pygame.Surface((TILE, TILE))
            t.fill(col)
            pygame.draw.line(t, th["grout"], (0, TILE - 1), (TILE - 1, TILE - 1))
            pygame.draw.line(t, th["grout"], (TILE - 1, 0), (TILE - 1, TILE - 1))
            pygame.draw.line(t, th["hi"], (0, 0), (TILE - 2, 0))
            for _ in range(5):
                t.set_at((rnd.randint(3, TILE - 4), rnd.randint(3, TILE - 4)), th["grout"])
            out.append(t)
        return out

    def block_tile(self, top, front, hi, edge):
        """Bloque basico: cara de arriba (34 px) y cara del frente (10 px)."""
        t = pygame.Surface((TILE, TILE))
        t.fill(front)
        pygame.draw.rect(t, top, (0, 0, TILE, TILE - 10))
        pygame.draw.line(t, hi, (0, 0), (TILE, 0))
        pygame.draw.line(t, edge, (0, TILE - 11), (TILE, TILE - 11))
        pygame.draw.line(t, C_BLACK, (0, TILE - 1), (TILE, TILE - 1))
        return t

    def walls_brick(self):
        """Muro de ladrillo rojo."""
        top_h = TILE - 10
        t = self.block_tile(C_RED_D, C_RED_DD, C_RED_L, C_RED)
        mortar = (128, 18, 28)
        for i, y in enumerate(range(0, top_h, 11)):
            if y:
                pygame.draw.line(t, mortar, (0, y), (TILE, y))
            for x in range(11 if i % 2 else 0, TILE, 22):
                pygame.draw.line(t, mortar, (x, y + 1), (x, min(top_h - 2, y + 11)))
        for x in (0, 22):
            pygame.draw.line(t, C_HUD_D, (x, top_h), (x, TILE))
        pygame.draw.line(t, C_HUD_D, (11, top_h + 5), (11, TILE))
        pygame.draw.line(t, C_HUD_D, (33, top_h + 5), (33, TILE))
        pygame.draw.line(t, C_HUD_D, (0, top_h + 5), (TILE, top_h + 5))
        return {"inner": [t, t], "border": [t, t], "top": [t, t]}

    def walls_locker(self):
        """Casilleros azules, de a dos puertas por casilla."""
        dark, mid = (46, 62, 88), (60, 82, 112)
        t = self.block_tile((84, 112, 150), dark, (134, 162, 200), mid)
        for x0 in (0, 22):
            pygame.draw.line(t, dark, (x0, 1), (x0, TILE - 11))
            pygame.draw.line(t, (104, 132, 170), (x0 + 1, 1), (x0 + 1, TILE - 12))
            for y in (6, 9, 12):
                pygame.draw.line(t, mid, (x0 + 6, y), (x0 + 16, y))
            pygame.draw.rect(t, (214, 224, 236), (x0 + 16, 19, 3, 6))
            pygame.draw.rect(t, C_WHITE, (x0 + 6, 18, 6, 4))        # etiqueta
        pygame.draw.line(t, dark, (TILE - 1, 1), (TILE - 1, TILE - 11))
        return {"inner": [t, t], "border": [t, t], "top": [t, t]}

    def walls_counter(self):
        """Cafeteria: barras de madera con comida, muro de baldosin y la
        linea de servicio de arriba (donde atienden los cocineros)."""
        wood, wood_d, wood_l = (204, 146, 80), (120, 76, 38), (234, 184, 120)
        inner = []
        for variant in (0, 1):
            t = self.block_tile(wood, wood_d, wood_l, (150, 100, 50))
            for y in (11, 22):
                pygame.draw.line(t, (184, 128, 66), (0, y), (TILE, y))
            for x in (0, 22):
                pygame.draw.line(t, (92, 56, 26), (x, TILE - 10), (x, TILE))
            if variant == 0:              # plato servido
                pygame.draw.circle(t, (168, 150, 130), (22, 17), 10)
                pygame.draw.circle(t, C_WHITE, (22, 16), 9)
                pygame.draw.circle(t, (222, 214, 204), (22, 16), 6, 1)
                pygame.draw.circle(t, (226, 150, 60), (20, 15), 3)
                pygame.draw.circle(t, C_RED, (25, 18), 2)
            else:                         # bandeja con pan y tinto
                pygame.draw.rect(t, (120, 126, 134), (7, 7, 30, 20))
                pygame.draw.rect(t, (192, 198, 206), (8, 8, 28, 18))
                pygame.draw.ellipse(t, (150, 104, 50), (11, 11, 12, 9))
                pygame.draw.ellipse(t, (226, 174, 96), (12, 12, 10, 7))
                pygame.draw.circle(t, C_WHITE, (29, 18), 5)
                pygame.draw.circle(t, (96, 52, 26), (29, 18), 3)
            inner.append(t)
        b = self.block_tile((208, 106, 60), (132, 60, 32), (236, 146, 98), (170, 80, 42))
        for i in range(11, TILE, 11):     # baldosin terracota
            pygame.draw.line(b, (184, 88, 46), (i, 1), (i, TILE - 12))
            if i < TILE - 11:
                pygame.draw.line(b, (184, 88, 46), (0, i), (TILE, i))
        top = []
        for food in ((232, 190, 96), (206, 72, 56)):
            t = pygame.Surface((TILE, TILE))
            t.fill((238, 232, 222))       # pared de la cocina
            for i in range(0, TILE, 11):
                pygame.draw.line(t, (216, 208, 196), (i, 0), (i, 30))
            for y in (9, 19):
                pygame.draw.line(t, (216, 208, 196), (0, y), (TILE, y))
            pygame.draw.rect(t, (176, 184, 194), (0, 30, TILE, 14))      # meson de acero
            pygame.draw.line(t, (228, 234, 240), (0, 30), (TILE, 30))
            pygame.draw.line(t, (88, 94, 104), (0, TILE - 1), (TILE, TILE - 1))
            pygame.draw.rect(t, (70, 76, 86), (7, 33, 30, 8))            # olla con comida
            pygame.draw.rect(t, food, (9, 34, 26, 5))
            top.append(t)
        return {"inner": inner, "border": [b, b], "top": top}

    def make_tiles(self):
        rnd = random.Random(3)
        self.tiles = []
        for th in THEMES:
            d = getattr(self, "walls_" + th["walls"])()
            d["floor"] = self.floor_tiles(th, rnd)
            self.tiles.append(d)
        # muro de la muerte subita: oscuro, con cinta de peligro (igual en todas)
        top_h = TILE - 10
        t = pygame.Surface((TILE, TILE))
        t.fill(C_BLACK)
        pygame.draw.rect(t, C_INK, (0, 0, TILE, top_h))
        for x in range(-TILE, TILE, 14):
            pygame.draw.polygon(t, C_RED, [(x, top_h), (x + 7, top_h), (x + 7 + 10, top_h + 10), (x + 10, top_h + 10)])
        pygame.draw.line(t, C_RED_D, (0, 0), (TILE, 0))
        pygame.draw.line(t, C_RED_DD, (6, 8), (TILE - 7, top_h - 8), 3)
        pygame.draw.line(t, C_RED_DD, (TILE - 7, 8), (6, top_h - 8), 3)
        self.t_closed = t

    def draw_crate(self, s, x0, y0):
        """Lo que se rompe con las papas: caja, caja de carton o mesa, segun la cancha."""
        kind = self.th["crate"]
        sh = self.th["shadow"]
        if kind == "table":
            pygame.draw.rect(s, sh, (x0 + 7, y0 + 12, TILE - 9, TILE - 13))
            for lx in (x0 + 6, x0 + TILE - 10):                      # patas
                pygame.draw.rect(s, (92, 56, 26), (lx, y0 + TILE - 10, 4, 7))
            top = pygame.Rect(x0 + 3, y0 + 3, TILE - 6, TILE - 11)
            rrect(s, C_INK, top, 6)
            rrect(s, C_WHITE, top.inflate(-4, -4), 4)
            cloth = top.inflate(-10, -10)                            # mantel de cuadros
            for j in range(0, cloth.h, 6):
                for i in range(0, cloth.w, 6):
                    if (i // 6 + j // 6) % 2 == 0:
                        pygame.draw.rect(s, (240, 150, 150), (cloth.x + i, cloth.y + j,
                                                              min(6, cloth.w - i), min(6, cloth.h - j)))
            cx, cy = top.center
            pygame.draw.circle(s, (176, 164, 152), (cx, cy + 1), 8)  # plato
            pygame.draw.circle(s, C_WHITE, (cx, cy), 7)
            pygame.draw.circle(s, (226, 150, 60), (cx, cy), 3)
        elif kind == "box":
            pygame.draw.rect(s, sh, (x0 + 5, y0 + 8, TILE - 7, TILE - 9))
            pygame.draw.rect(s, C_INK, (x0 + 3, y0 + 4, TILE - 6, TILE - 7))
            pygame.draw.rect(s, (206, 164, 112), (x0 + 5, y0 + 6, TILE - 10, TILE - 11))
            pygame.draw.rect(s, (224, 188, 140), (x0 + 5, y0 + 6, TILE - 10, 9))      # tapa
            pygame.draw.line(s, (150, 112, 70), (x0 + 5, y0 + 15), (x0 + TILE - 6, y0 + 15))
            pygame.draw.rect(s, (236, 214, 170), (x0 + 19, y0 + 6, 6, TILE - 11))     # cinta
            pygame.draw.rect(s, C_WHITE, (x0 + 8, y0 + 22, 8, 7))                     # etiqueta
            pygame.draw.line(s, (150, 112, 70), (x0 + 9, y0 + 25), (x0 + 14, y0 + 25))
        else:
            pygame.draw.rect(s, sh, (x0 + 5, y0 + 8, TILE - 7, TILE - 9))
            pygame.draw.rect(s, C_INK, (x0 + 3, y0 + 3, TILE - 6, TILE - 6))
            inner = pygame.Rect(x0 + 5, y0 + 5, TILE - 10, TILE - 10)
            pygame.draw.rect(s, C_WHITE, inner)
            pygame.draw.line(s, C_RED, inner.topleft, (inner.right - 1, inner.bottom - 1), 4)
            pygame.draw.line(s, C_RED, (inner.right - 1, inner.top), (inner.left, inner.bottom - 1), 4)
            pygame.draw.rect(s, C_RED, inner, 4)
            pygame.draw.rect(s, C_CREAM, (inner.x, inner.bottom - 6, inner.w, 2))
            pygame.draw.rect(s, C_INK, inner, 1)

    def redraw_cell(self, x, y):
        """Repinta una casilla en la capa fija (piso, muros y cajas)."""
        s = self.layer
        x0, y0 = x * TILE, HUD + y * TILE
        cell = self.grid[y][x]
        ts = self.tiles[self.theme_i]
        if cell == WALL:
            if (x, y) in self.closed_set:
                s.blit(self.t_closed, (x0, y0))
                return
            if y == 0:
                kind = "top"
            elif x in (0, COLS - 1) or y == ROWS - 1:
                kind = "border"
            else:
                kind = "inner"
            s.blit(ts[kind][(x + y) % 2], (x0, y0))
            return
        s.blit(ts["floor"][(x + y) % 2], (x0, y0))
        if self.grid[y - 1][x] == WALL:       # sombra del muro de arriba
            pygame.draw.rect(s, self.th["shadow"], (x0, y0, TILE, 5))
        if cell == BLOCK:
            self.draw_crate(s, x0, y0)

    def draw_cooks(self):
        """Cocineros de la cafeteria, detras de la linea de servicio. Sirven
        con el cucharon y se agachan cuando explota una papa."""
        s = self.s
        s.set_clip(pygame.Rect(0, HUD, W, 30))
        skins = [(236, 190, 150), (176, 120, 84), (214, 160, 118), (150, 100, 70)]
        for i, tx in enumerate((2, 5, 9, 12)):
            cx = tx * TILE + TILE // 2
            side = 1 if i % 2 == 0 else -1
            y = HUD + self.npc_duck + math.sin(self.now * 3 + i * 1.7) * 1.2
            skin = skins[i]
            # brazo con cucharon
            hx = cx + side * 13
            hy = y + 24 + math.sin(self.now * 4 + i * 2.1) * 3
            line(s, C_GRAY, (hx, hy), (hx + side * 2, HUD + 34), 2)
            line(s, skin, (cx + side * 8, y + 21), (hx, hy), 4)
            # cuerpo: camisa roja y delantal blanco
            pygame.draw.rect(s, C_INK, irect(cx - 10, y + 18, 20, 16))
            pygame.draw.rect(s, C_RED, irect(cx - 9, y + 19, 18, 15))
            pygame.draw.rect(s, C_WHITE, irect(cx - 5, y + 21, 10, 13))
            # cabeza
            circ(s, C_INK, cx, y + 13, 8)
            circ(s, skin, cx, y + 13, 7)
            if self.npc_duck > 3:          # susto
                for e in (-3, 3):
                    circ(s, C_WHITE, cx + e, y + 12, 2.4)
                    circ(s, C_INK, cx + e, y + 12, 1)
                circ(s, C_INK, cx, y + 17, 1.6)
            else:
                for e in (-3, 3):
                    circ(s, C_INK, cx + e, y + 13, 1.3)
                line(s, C_INK, (cx - 2, y + 17), (cx + 2, y + 17), 1)
            # gorro de cocinero
            pygame.draw.rect(s, C_INK, irect(cx - 7, y + 2, 14, 7))
            for ox, oy in ((-4, 3), (4, 3), (0, 1)):
                circ(s, C_INK, cx + ox, y + oy, 5)
            pygame.draw.rect(s, C_WHITE, irect(cx - 6, y + 3, 12, 5))
            for ox, oy in ((-4, 3), (4, 3), (0, 1)):
                circ(s, C_WHITE, cx + ox, y + oy, 4)
            line(s, C_GRAY, (cx - 6, y + 8), (cx + 5, y + 8), 1)
        s.set_clip(None)

    def new_map(self, layout):
        self.layout_name, rows = LAYOUTS[layout]
        self.theme_i = layout
        self.th = THEMES[layout]
        g = [[WALL if rows[y][x] == "#" else EMPTY for x in range(COLS)] for y in range(ROWS)]
        safe = set([(1, 1), (2, 1), (1, 2)])
        safe |= set((COLS - 1 - x, ROWS - 1 - y) for (x, y) in list(safe))
        hidden = {}
        # cajas y poderes simetricos, para que sea justo para los dos
        for y in range(ROWS):
            for x in range(COLS):
                mx, my = COLS - 1 - x, ROWS - 1 - y
                if (y, x) > (my, mx):
                    continue
                if g[y][x] != EMPTY or (x, y) in safe:
                    continue
                if random.random() < CRATE_CHANCE:
                    g[y][x] = BLOCK
                    g[my][mx] = BLOCK
                    if random.random() < POWER_CHANCE:
                        k = random.choice(POWER_KINDS)
                        hidden[(x, y)] = k
                        hidden[(mx, my)] = k
        self.grid = g
        self.hidden = hidden
        self.bombs = []
        self.fire = {}                 # casilla -> [tiempo, forma]
        self.powerups = {}
        self.bullets = []
        self.parts = []
        self.floaters = []
        self.rings = []
        # muerte subita
        self.round_time = DEMO_ROUND_TIME if self.demo else ROUND_TIME
        self.sudden = False
        self.sd_timer = 0.0
        self.sd_banner = 0.0
        self.closed_set = set()
        self.sd_cells = self.spiral_cells()
        self.layer.fill(C_HUD)
        for y in range(ROWS):
            for x in range(COLS):
                self.redraw_cell(x, y)

    def spiral_cells(self):
        """Casillas en espiral desde el borde hacia el centro, de a pares espejo."""
        cells = []
        k = 0
        while True:
            x0, y0, x1, y1 = 1 + k, 1 + k, COLS - 2 - k, ROWS - 2 - k
            if x0 > x1 or y0 > y1:
                break
            for x in range(x0, x1 + 1):
                cells.append((x, y0))
            for y in range(y0 + 1, y1 + 1):
                cells.append((x1, y))
            if y1 > y0:
                for x in range(x1 - 1, x0 - 1, -1):
                    cells.append((x, y1))
            if x1 > x0:
                for y in range(y1 - 1, y0, -1):
                    cells.append((x0, y))
            k += 1
        pairs, seen = [], set()
        for (x, y) in cells:
            if self.grid[y][x] == WALL or (x, y) in seen:
                continue
            m = (COLS - 1 - x, ROWS - 1 - y)
            seen.add((x, y))
            seen.add(m)
            pairs.append([(x, y)] if m == (x, y) else [(x, y), m])
        return pairs

    # ---------------- flujo de la partida
    def setup_round(self):
        if self.demo:
            layout = random.randrange(len(LAYOUTS))
        else:
            layout = self.layout_order[(self.round - 1) % len(LAYOUTS)]
        self.new_map(layout)
        for p in self.players:
            p.reset()
        for b in self.bots:
            if b:
                b.reset()
        self.winner = None
        self.demo_end = 0.0

    def goto_menu(self):
        self.state = "menu"
        self.paused = False
        self.demo = True
        p1, p2 = self.players
        self.bots = [Bot(self, p1, p2), Bot(self, p2, p1)]
        self.setup_round()
        self.hw.reset()

    def start_match(self, cpu):
        self.demo = False
        self.vs_cpu = cpu
        p1, p2 = self.players
        p1.name, p2.name = p1.base_name, ("CPU" if cpu else p2.base_name)
        self.bots = [None, Bot(self, p2, p1) if cpu else None]
        for p in self.players:
            p.wins = 0
        self.round = 0
        random.shuffle(self.layout_order)
        self.start_round()

    def start_round(self):
        self.round += 1
        self.setup_round()
        self.state = "countdown"
        self.count_t = 2.1
        self.go_t = 0.0
        self.hw.reset()
        self.emit("tick")

    def advance(self):
        if self.wait > 0:
            return
        if self.state == "match_over":
            self.start_match(self.vs_cpu)
        elif self.state == "round_over":
            self.start_round()

    def menu_select(self):
        self.sfx.play("select")
        if self.menu_i == 0:
            self.start_match(False)
        elif self.menu_i == 1:
            self.start_match(True)
        elif self.menu_i == 2:
            self.state = "howto"
        else:
            self.quit = True

    def button(self):
        """Boton del GrovePi: acepta en menus y pantallas, pero no hace nada
        en plena ronda (ENTER tambien es el disparo de BLANCO)."""
        if self.paused or self.state in ("menu", "howto", "round_over", "match_over"):
            self.handle_key(pygame.K_RETURN)

    def handle_key(self, key):
        start = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
        st = self.state
        if self.paused:
            if key in start or key == pygame.K_p:
                self.paused = False
            elif key == pygame.K_ESCAPE:
                self.goto_menu()
            return
        if st == "menu":
            if key in (pygame.K_UP, pygame.K_w):
                self.menu_i = (self.menu_i - 1) % len(self.MENU)
                self.sfx.play("menu")
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.menu_i = (self.menu_i + 1) % len(self.MENU)
                self.sfx.play("menu")
            elif key in start:
                self.menu_select()
            elif key == pygame.K_ESCAPE:
                self.quit = True
        elif st == "howto":
            if key in start or key == pygame.K_ESCAPE:
                self.sfx.play("menu")
                self.state = "menu"
        elif st in ("countdown", "playing", "ending"):
            if key in (pygame.K_ESCAPE, pygame.K_p):
                self.paused = True
            elif st != "countdown":
                for i, p in enumerate(self.players):
                    if self.bots[i]:
                        continue
                    if key in p.bomb_keys:
                        self.place_bomb(p)
                    elif key in p.throw_keys:
                        self.throw_bomb(p)
                    elif key in p.shoot_keys:
                        self.shoot(p)
        elif st in ("round_over", "match_over"):
            if key in start:
                self.advance()
            elif key == pygame.K_ESCAPE:
                self.goto_menu()

    # ---------------- logica
    def place_bomb(self, p):
        if not p.alive or not self.world_active():
            return
        if self.count_bombs(p) >= p.max_bombs or self.bomb_at(p.x, p.y):
            return
        self.bombs.append(Bomb(p.x, p.y, p, p.range))
        self.emit("place")

    def throw_target(self, x, y, face):
        """Primera casilla libre a THROW_DIST o mas; si no hay, la mas cercana antes."""
        dx, dy = face
        d = THROW_DIST
        while True:
            nx, ny = x + dx * d, y + dy * d
            if not (0 < nx < COLS - 1 and 0 < ny < ROWS - 1):
                break
            if self.landing_free(nx, ny):
                return nx, ny
            d += 1
        for d in range(THROW_DIST - 1, 0, -1):
            nx, ny = x + dx * d, y + dy * d
            if self.landing_free(nx, ny):
                return nx, ny
        return None

    def throw_bomb(self, p):
        if not p.alive or not self.world_active():
            return
        b = self.bomb_at(p.x, p.y)          # si estoy encima de una papa, la recojo
        new = b is None
        if new:
            if self.count_bombs(p) >= p.max_bombs:
                return
            b = Bomb(p.x, p.y, p, p.range)
        dest = self.throw_target(p.x, p.y, p.face)
        if dest is None:
            return
        if new:
            self.bombs.append(b)
        dist = abs(dest[0] - b.x) + abs(dest[1] - b.y)
        b.fx, b.fy = b.x, b.y
        b.x, b.y = dest
        b.flying = True
        b.fly_t = 0.0
        b.fly_dur = 0.15 + 0.07 * dist
        self.emit("throw")

    def shoot(self, p):
        if not p.alive or not self.world_active() or p.cool > 0:
            return
        if not self.sudden:
            if p.ammo <= 0:
                return
            p.ammo -= 1
        p.cool = SD_SHOT_COOLDOWN if self.sudden else SHOT_COOLDOWN
        p.gun_t = 0.6
        dx, dy = p.face
        tx, ty = p.tile_pos()
        self.bullets.append(Bullet(p, tx + dx * 0.4, ty + dy * 0.4, dx, dy))
        cx, cy = p.draw_pos()
        self.burst(cx + dx * 20, cy + 5 + dy * 14, 4, [C_WHITE, C_SPARK], 70, 0.2, 3)
        self.emit("shoot")

    def kill(self, p):
        if not p.alive:
            return
        p.alive = False
        p.dead_t = 1.4
        cx, cy = p.draw_pos()
        self.burst(cx, cy - 4, 16, [p.sch["main"], p.sch["dark"], C_INK], 150, 0.7, 5, 260, True)
        self.burst(cx, cy - 8, 8, [C_GRAY, (90, 80, 78)], 40, 1.0, 7, -60)
        self.floater(cx, cy - 30, "¡FRITO!", C_WHITE)
        self.shake = max(self.shake, 9.0)
        self.emit("death")

    def update_bullets(self, dt):
        dist = BULLET_SPEED * dt
        steps = int(dist / 0.25) + 1
        step = dist / steps
        for bl in list(self.bullets):
            for _ in range(steps):
                bl.x += bl.dx * step
                bl.y += bl.dy * step
                tx, ty = int(round(bl.x)), int(round(bl.y))
                hit = False
                if not (0 <= tx < COLS and 0 <= ty < ROWS) or self.grid[ty][tx] != EMPTY:
                    hit = True                       # pared o caja
                else:
                    b = self.bomb_at(tx, ty)
                    if b:
                        b.t = 0                      # le pego a una papa: explota
                        hit = True
                    for p in self.players:
                        if p.alive and p is not bl.owner:
                            px, py = p.tile_pos()
                            if abs(px - bl.x) < 0.45 and abs(py - bl.y) < 0.45:
                                self.kill(p)
                                hit = True
                if hit:
                    self.burst(bl.x * TILE + TILE / 2, HUD + bl.y * TILE + TILE / 2, 5,
                               [C_POTATO, C_POTATO_L, C_WHITE], 80, 0.25, 3)
                    self.bullets.remove(bl)
                    break

    def close_next_cell(self):
        if not self.sd_cells:
            return
        for (x, y) in self.sd_cells.pop(0):
            if self.grid[y][x] == WALL:
                continue
            self.grid[y][x] = WALL
            self.closed_set.add((x, y))
            self.hidden.pop((x, y), None)
            self.powerups.pop((x, y), None)
            self.fire.pop((x, y), None)
            self.bombs = [b for b in self.bombs if b.flying or (b.x, b.y) != (x, y)]
            self.redraw_cell(x, y)
            if y + 1 < ROWS:
                self.redraw_cell(x, y + 1)
            self.burst(x * TILE + TILE / 2, HUD + y * TILE + TILE / 2, 4, [C_GRAY, C_CREAM], 60, 0.35, 5)
            self.shake = max(self.shake, 2.0)
            for p in self.players:
                if p.alive and (p.x, p.y) == (x, y):
                    self.kill(p)

    def update_sudden(self, dt):
        if not self.sudden:
            self.round_time -= dt
            if self.round_time <= 0:
                self.round_time = 0
                self.sudden = True
                self.sd_banner = 2.5
                self.emit("sudden")
            return
        self.sd_banner = max(0.0, self.sd_banner - dt)
        self.sd_timer += dt
        while self.sd_timer >= SD_STEP:
            self.sd_timer -= SD_STEP
            self.close_next_cell()

    def blast_cells(self, x, y, rng):
        """Casillas que alcanza la explosion de una papa puesta en (x, y)."""
        cells = [(x, y)]
        for dx, dy in DIRS:
            for i in range(1, rng + 1):
                nx, ny = x + dx * i, y + dy * i
                cell = self.grid[ny][nx]
                if cell == WALL:
                    break
                cells.append((nx, ny))
                if cell == BLOCK or (nx, ny) in self.powerups or self.bomb_at(nx, ny):
                    break
        return cells

    def add_fire(self, x, y, kind):
        old = self.fire.get((x, y))
        if old and old[1] != kind:
            kind = "c"
        self.fire[(x, y)] = [FIRE_TIME, kind]

    def explode(self, b):
        self.bombs.remove(b)
        cells = self.blast_cells(b.x, b.y, b.range)
        for (nx, ny) in cells:
            px, py = nx * TILE + TILE / 2, HUD + ny * TILE + TILE / 2
            if self.grid[ny][nx] == BLOCK:
                self.grid[ny][nx] = EMPTY
                self.redraw_cell(nx, ny)
                self.burst(px, py, 9, self.th["debris"], 140, 0.6, 6, 300, True)
                k = self.hidden.pop((nx, ny), None)
                if k:
                    self.powerups[(nx, ny)] = k
            elif (nx, ny) in self.powerups and (nx, ny) != (b.x, b.y):
                del self.powerups[(nx, ny)]
                self.burst(px, py, 6, [C_WHITE, C_RED], 90, 0.4, 4)
            else:
                other = self.bomb_at(nx, ny)
                if other:
                    other.t = 0      # reaccion en cadena
            kind = "c" if (nx, ny) == (b.x, b.y) else ("h" if ny == b.y else "v")
            self.add_fire(nx, ny, kind)
            if random.random() < 0.6:
                self.spark(px + random.uniform(-10, 10), py + random.uniform(-10, 10),
                           random.uniform(-30, 30), random.uniform(-90, -30),
                           random.uniform(0.4, 0.8), random.uniform(3, 5),
                           random.choice([C_SPARK, C_WHITE, C_RED_L]))
        cx, cy = b.x * TILE + TILE / 2, HUD + b.y * TILE + TILE / 2
        self.burst(cx, cy, 14, [C_WHITE, C_SPARK, C_RED_L, C_RED], 230, 0.5, 5)
        self.burst(cx, cy, 5, [C_GRAY, (110, 100, 98)], 50, 0.9, 8, -50)
        self.rings.append([cx, cy, 0.0])
        self.emit("boom")

    def update_player(self, i, p, dt, keys):
        if not p.alive:
            p.dead_t = max(0.0, p.dead_t - dt)
            return
        p.cool = max(0.0, p.cool - dt)
        p.gun_t = max(0.0, p.gun_t - dt)
        if p.ammo < AMMO_MAX:
            p.ammo_t += dt
            if p.ammo_t >= AMMO_RECHARGE:
                p.ammo += 1
                p.ammo_t = 0.0
        else:
            p.ammo_t = 0.0
        if p.move_t > 0:
            p.move_t -= dt
        bot = self.bots[i]
        if bot:
            d = bot.think(dt)
            wanted = [] if d is None else [d]
        else:
            # la ultima direccion apretada manda; las otras quedan de respaldo
            for d, k in enumerate(p.move_keys):
                if keys[k]:
                    if d not in p.held:
                        p.held.append(d)
                elif d in p.held:
                    p.held.remove(d)
            wanted = p.held[::-1]
        if p.move_t <= 0:
            p.move_t = 0
            if wanted:
                p.face = DIRS[wanted[0]]
            for d in wanted:
                dx, dy = DIRS[d]
                if self.walkable(p.x + dx, p.y + dy):
                    p.face = (dx, dy)
                    p.px, p.py = p.x, p.y
                    p.x += dx
                    p.y += dy
                    p.move_t = p.delay
                    break
        k = self.powerups.pop((p.x, p.y), None)
        if k:
            if k == "aji":
                p.range = min(p.range + 1, 8)
            elif k == "papa":
                p.max_bombs = min(p.max_bombs + 1, 6)
            elif k == "tinto":
                p.speed_lvl = min(p.speed_lvl + 1, 4)
                p.delay = 0.20 - 0.025 * p.speed_lvl
            cx, cy = p.x * TILE + TILE / 2, HUD + p.y * TILE + TILE / 2
            self.floater(cx, cy - 26, POWER_TEXT[k], C_WHITE)
            self.burst(cx, cy, 10, [C_WHITE, C_RED, C_SPARK], 110, 0.45, 4)
            self.emit("pick")

    def update_world(self, dt):
        keys = pygame.key.get_pressed()
        for i, p in enumerate(self.players):
            self.update_player(i, p, dt, keys)
        self.update_sudden(dt)
        self.update_bullets(dt)

        for b in self.bombs:
            b.t -= dt
            if b.flying:
                b.fly_t += dt
                if b.fly_t >= b.fly_dur:
                    b.flying = False
                    self.burst(b.x * TILE + TILE / 2, HUD + b.y * TILE + TILE / 2 + 10, 4,
                               [C_GROUT, C_CREAM], 50, 0.3, 4)
                    # cayo en el fuego o en una casilla que se cerro: explota ya
                    if (b.x, b.y) in self.fire or self.grid[b.y][b.x] != EMPTY:
                        b.t = 0
        while True:
            # una papa que va volando explota apenas caiga
            due = [b for b in self.bombs if b.t <= 0 and not b.flying]
            if not due:
                break
            for b in due:
                if b in self.bombs:
                    self.explode(b)

        for pos in list(self.fire):
            self.fire[pos][0] -= dt
            if self.fire[pos][0] <= 0:
                del self.fire[pos]

        for p in self.players:
            if p.alive and (p.x, p.y) in self.fire:
                self.kill(p)

    def update(self, dt):
        if self.paused:
            return
        self.now += dt
        self.wait = max(0.0, self.wait - dt)
        self.go_t = max(0.0, self.go_t - dt)
        self.update_fx(dt)
        st = self.state
        alive = [p for p in self.players if p.alive]
        if st in ("menu", "howto"):
            self.update_world(dt)
            if len(alive) <= 1:
                self.demo_end += dt
                if self.demo_end > 2.5:
                    self.setup_round()
        elif st == "countdown":
            before = math.ceil(self.count_t / 0.7)
            self.count_t -= dt
            if self.count_t <= 0:
                self.state = "playing"
                self.go_t = 0.7
                self.emit("go")
            elif math.ceil(self.count_t / 0.7) != before:
                self.emit("tick")
        elif st in ("playing", "ending"):
            self.update_world(dt)
            alive = [p for p in self.players if p.alive]
            if st == "playing" and len(alive) <= 1:
                self.state = "ending"
                self.end_t = 1.5
            elif st == "ending":
                self.end_t -= dt
                if self.end_t <= 0:
                    if len(alive) == 1:
                        self.winner = alive[0]
                        self.winner.wins += 1
                        self.emit("win")
                    else:
                        self.winner = None
                    if any(p.wins >= WINS_TO_MATCH for p in self.players):
                        self.state = "match_over"
                    else:
                        self.state = "round_over"
                    self.wait = 1.0
        elif st == "match_over":
            self.confetti_t -= dt
            if self.confetti_t <= 0:
                self.confetti_t = 0.06
                self.spark(random.uniform(0, W), -6, random.uniform(-30, 30), random.uniform(60, 140),
                           4.0, random.uniform(5, 8), random.choice([C_RED, C_WHITE, C_RED_L]), 60, True)

    # ---------------- dibujo
    def draw_warning(self):
        """Las proximas casillas que se van a cerrar titilan en rojo."""
        if not self.sudden or int(self.now * 8) % 2:
            return
        sh = self.shade(C_RED, 120, (TILE, TILE))
        for pair in self.sd_cells[:3]:
            for (x, y) in pair:
                if self.grid[y][x] != WALL:
                    self.s.blit(sh, (x * TILE, HUD + y * TILE))

    def draw_bullet(self, bl):
        s = self.s
        cx = int(bl.x * TILE + TILE / 2)
        cy = int(HUD + bl.y * TILE + TILE / 2)
        line(s, C_WHITE, (cx - bl.dx * 16, cy - bl.dy * 16), (cx, cy), 3)
        if bl.dx:
            rect = pygame.Rect(cx - 7, cy - 4, 14, 8)
        else:
            rect = pygame.Rect(cx - 4, cy - 7, 8, 14)
        pygame.draw.ellipse(s, C_INK, rect.inflate(4, 4))
        pygame.draw.ellipse(s, C_POTATO, rect)

    def draw_potato(self, cx, cy, r, t_left=None, fuse=False, face=True):
        s = self.s
        color = C_POTATO
        if t_left is not None and t_left < 0.8 and int(self.now * 12) % 2 == 0:
            color = C_RED_L                      # a punto de explotar
        rect = irect(0, 0, r * 2.2, r * 1.8)
        rect.center = (int(cx), int(cy))
        pygame.draw.ellipse(s, C_INK, rect.inflate(4, 4))
        pygame.draw.ellipse(s, color, rect)
        hl = irect(0, 0, r * 0.9, r * 0.45)
        hl.center = (int(cx - r * 0.4), int(cy - r * 0.45))
        pygame.draw.ellipse(s, C_POTATO_L, hl)
        for ox, oy in ((0.62, 0.3), (-0.6, 0.35), (0.25, -0.5)):
            circ(s, C_POTATO_D, cx + ox * r, cy + oy * r, max(1.5, r * 0.1))
        if face and r >= 9:                      # carita brava
            for e in (-1, 1):
                circ(s, C_INK, cx + e * r * 0.3, cy + r * 0.05, max(1.5, r * 0.13))
                line(s, C_INK, (cx + e * r * 0.5, cy - r * 0.32), (cx + e * r * 0.12, cy - r * 0.12),
                     max(1, r * 0.1))
        if t_left is not None or fuse:
            a = (cx + r * 0.55, cy - r * 0.7)
            b = (cx + r * 0.95, cy - r * 1.3)
            line(s, C_INK, a, b, max(2, r * 0.2))
            circ(s, random.choice([C_RED, C_RED_L]), b[0], b[1], random.uniform(0.3, 0.5) * r)
            circ(s, random.choice([C_WHITE, C_SPARK]), b[0], b[1], random.uniform(0.12, 0.25) * r)

    def draw_bomb(self, b):
        if b.flying:
            p = min(1.0, b.fly_t / b.fly_dur)
            gx = b.fx + (b.x - b.fx) * p
            gy = b.fy + (b.y - b.fy) * p
            cx = gx * TILE + TILE / 2
            cy = HUD + gy * TILE + TILE / 2 + 2
            z = math.sin(math.pi * p) * TILE * 1.1       # altura del arco
            sw = 22 - z * 0.15
            pygame.draw.ellipse(self.s, self.th["shadow"], irect(cx - sw / 2, cy + 6, sw, 7))
            self.draw_potato(cx, cy - z, TILE * 0.33, b.t)
            return
        cx = b.x * TILE + TILE / 2
        cy = HUD + b.y * TILE + TILE / 2 + 2
        pygame.draw.ellipse(self.s, self.th["shadow"], irect(cx - 13, cy + 7, 26, 8))
        speed = 6 + (BOMB_TIME - b.t) * 8
        r = TILE * 0.33 * (1 + 0.08 * math.sin(self.now * speed))
        self.draw_potato(cx, cy, r, b.t)

    def draw_fire(self):
        """Fuego en tres pasadas (rojo, naranja, blanco) para que se una bien."""
        s = self.s
        for color, scale in ((C_RED, 1.0), (C_FIRE_MID, 0.66), (C_WHITE, 0.34)):
            for (x, y), (t, kind) in self.fire.items():
                frac = min(1.0, t / FIRE_TIME * 1.7)
                wdt = (TILE * (0.3 + 0.62 * frac) + random.uniform(-3, 3)) * scale
                x0, y0 = x * TILE, HUD + y * TILE
                cx, cy = x0 + TILE / 2, y0 + TILE / 2
                if kind in ("h", "c"):
                    pygame.draw.rect(s, color, irect(x0, cy - wdt / 2, TILE, wdt))
                if kind in ("v", "c"):
                    pygame.draw.rect(s, color, irect(cx - wdt / 2, y0, wdt, TILE))
                if kind == "c":
                    circ(s, color, cx, cy, wdt * 0.66)

    def draw_powerup(self, pos, kind):
        x, y = pos
        cx = x * TILE + TILE // 2
        cy = HUD + y * TILE + TILE // 2 + int(math.sin(self.now * 5 + x) * 2)
        s = self.s
        pygame.draw.ellipse(s, self.th["shadow"], (cx - 14, HUD + y * TILE + TILE - 10, 28, 8))
        circ(s, C_INK, cx, cy, 18)
        circ(s, C_WHITE, cx, cy, 16)
        circ(s, C_RED, cx, cy, 16, 2)
        self.draw_power_icon(kind, cx, cy)

    def draw_power_icon(self, kind, cx, cy):
        s = self.s
        if kind == "aji":
            pygame.draw.ellipse(s, C_RED_D, (cx - 6, cy - 9, 12, 22))
            pygame.draw.ellipse(s, C_RED, (cx - 5, cy - 8, 10, 20))
            pygame.draw.ellipse(s, C_PINK, (cx - 3, cy - 5, 3, 8))
            pygame.draw.rect(s, C_INK, (cx - 2, cy - 13, 5, 5))
        elif kind == "papa":
            self.draw_potato(cx - 2, cy + 2, 8, face=False)
            self.text("+", 26, C_RED, (cx + 9, cy - 8))
        elif kind == "tinto":
            pygame.draw.rect(s, C_RED, (cx - 8, cy - 4, 15, 13))
            pygame.draw.rect(s, C_INK, (cx - 8, cy - 4, 15, 13), 1)
            pygame.draw.ellipse(s, C_INK, (cx - 7, cy - 6, 13, 5))
            pygame.draw.circle(s, C_INK, (cx + 9, cy + 2), 4, 2)
            for i in (-3, 2):
                pygame.draw.line(s, C_GRAY, (cx + i, cy - 9), (cx + i + 2, cy - 14), 2)

    def draw_player(self, p):
        s = self.s
        cx, cy = p.draw_pos()
        if not p.alive:
            if p.dead_t <= 0:             # quedan las cenizas
                pygame.draw.ellipse(s, C_INK, irect(cx - 12, cy + 4, 24, 11))
                pygame.draw.ellipse(s, SCH_FRITO["main"], irect(cx - 10, cy + 5, 20, 8))
                return
            wob = math.sin(self.now * 40) * 2 * (p.dead_t / 1.4)
            draw_hooded(s, cx + wob, cy, SCH_FRITO, (0, 1), fried=True, shadow=self.th["shadow"])
            return
        blink = (self.now * 0.9 + p.num * 1.37) % 3.0 < 0.12
        draw_hooded(s, cx, cy, p.sch, p.face, step=self.now * 18 + p.num, moving=p.move_t > 0,
                    gun=p.gun_t > 0 or self.sudden, blink=blink, shadow=self.th["shadow"])

    def draw_fx(self):
        s = self.s
        for (x, y, t) in self.rings:
            u = t / 0.3
            circ(s, C_WHITE, x, y, 10 + u * TILE * 1.3, max(1, 5 * (1 - u)))
        for p in self.parts:
            r = p[6] * (p[4] / p[5])
            if r < 0.6:
                continue
            if p[9]:
                pygame.draw.rect(s, p[7], irect(p[0] - r, p[1] - r, r * 2, r * 2))
            else:
                circ(s, p[7], p[0], p[1], r)
        for (x, y, txt, color, t) in self.floaters:
            self.text(txt, 24, color, (x, y), shadow=C_INK, off=2)

    def draw_world(self):
        s = self.s
        s.blit(self.layer, (0, 0))
        if self.th["cooks"]:
            self.draw_cooks()
        self.draw_warning()
        for pos, kind in self.powerups.items():
            self.draw_powerup(pos, kind)
        for b in self.bombs:
            if not b.flying:
                self.draw_bomb(b)
        self.draw_fire()
        for p in sorted(self.players, key=lambda q: (q.alive, q.tile_pos()[1])):
            self.draw_player(p)
        for bl in self.bullets:
            self.draw_bullet(bl)
        for b in self.bombs:               # las que vuelan van por encima de todo
            if b.flying:
                self.draw_bomb(b)
        self.draw_fx()

    def draw_hud(self):
        s = self.s
        pygame.draw.rect(s, C_HUD, (0, 0, W, HUD))
        pygame.draw.rect(s, C_HUD_D, (0, HUD - 4, W, 4))
        pygame.draw.line(s, C_RED, (0, HUD - 5), (W, HUD - 5))
        self.text("PAPAS BOMBA", 32, C_WHITE, (W / 2, 19), shadow=C_HUD_D)
        if self.sudden:
            if int(self.now * 4) % 2 == 0:
                self.text("¡MUERTE SÚBITA!", 21, C_WHITE, (W / 2, 42))
        else:
            t = int(math.ceil(self.round_time))
            col = C_WHITE if (t > 10 or int(self.now * 4) % 2) else C_RED_L
            self.text("Ronda {}  ·  {}:{:02d}".format(self.round, t // 60, t % 60), 20, col, (W / 2, 42))
        for p in self.players:
            x0 = 4 if p.num == 1 else W - 226
            rrect(s, C_HUD_D, (x0, 4, 222, HUD - 12), 8)
            draw_hooded(s, x0 + 22, 30, p.sch if p.alive else SCH_FRITO, (0, 1), k=0.8,
                        shadow=False, fried=not p.alive)
            r = self.text(p.name, 21, C_WHITE, (x0 + 44, 7), anchor="topleft")
            for i in range(WINS_TO_MATCH):          # rondas ganadas: papitas
                px, py = r.right + 14 + i * 19, 14
                if i < p.wins:
                    pygame.draw.ellipse(s, C_INK, (px - 8, py - 6, 16, 12))
                    pygame.draw.ellipse(s, C_POTATO, (px - 6, py - 4, 12, 8))
                else:
                    pygame.draw.ellipse(s, C_HUD, (px - 7, py - 5, 14, 10))
            stats = "Papas {}   Fuego {}   Vel {}".format(p.max_bombs, p.range, p.speed_lvl)
            self.text(stats, 17, C_PINK, (x0 + 44, 23), anchor="topleft")
            if self.sudden:
                self.text("Balas sin límite", 16, C_WHITE, (x0 + 44, 36), anchor="topleft")
            else:
                self.text("Balas", 16, C_PINK, (x0 + 44, 36), anchor="topleft")
                for i in range(AMMO_MAX):
                    rc = pygame.Rect(x0 + 84 + i * 15, 37, 11, 8)
                    if i < p.ammo:
                        pygame.draw.ellipse(s, C_POTATO, rc)
                    else:
                        pygame.draw.ellipse(s, C_HUD, rc)
                if p.ammo < AMMO_MAX and p.alive:   # barrita de recarga
                    bw = int(36 * p.ammo_t / AMMO_RECHARGE)
                    pygame.draw.rect(s, C_HUD, (x0 + 134, 39, 36, 4))
                    pygame.draw.rect(s, C_WHITE, (x0 + 134, 39, bw, 4))

    def band(self, y, h, color=C_HUD_D, alpha=225):
        self.s.blit(self.shade(color, alpha, (W, h)), (0, int(y)))
        pygame.draw.rect(self.s, C_WHITE, (0, int(y), W, 3))
        pygame.draw.rect(self.s, C_WHITE, (0, int(y) + h - 3, W, 3))

    def draw_menu(self):
        s = self.s
        s.blit(self.shade(C_HUD_D, 205), (0, 0))
        bob = math.sin(self.now * 2.2) * 5
        self.text("PAPAS BOMBA", 104, C_WHITE, (W / 2, 104 + bob), shadow=C_RED, off=5)
        self.text("Deja frito a tu rival", 28, C_PINK, (W / 2, 164 + bob * 0.5))
        step = self.now * 5
        draw_hooded(s, 118, 300, SCH_ROJO, (1, 0), k=3.4, step=step, moving=True, shadow=False,
                    blink=self.now % 3.1 < 0.12)
        draw_hooded(s, W - 118, 300, SCH_BLANCO, (-1, 0), k=3.4, step=step + 2, moving=True, shadow=False,
                    blink=(self.now + 1.3) % 3.4 < 0.12)
        self.draw_potato(W / 2, 268 + math.sin(self.now * 3) * 8, 44, fuse=True)
        for i, item in enumerate(self.MENU):
            y = 394 + i * 44
            if i == self.menu_i:
                rrect(s, C_WHITE, (W // 2 - 170, y - 19, 340, 38), 19)
                self.text(item, 34, C_RED_D, (W / 2, y + 1))
                self.draw_potato(W / 2 - 145, y, 9, fuse=True, face=False)
            else:
                self.text(item, 30, C_PINK, (W / 2, y + 1))
        self.text("W / S o flechas: elegir     ENTER o botón Grove: aceptar     ESC: salir",
                  18, C_PINK, (W / 2, 584))
        grove = "GrovePi conectado" if self.hw.ok else "GrovePi no encontrado (se juega igual)"
        self.text(grove, 16, C_GRAY, (W / 2, 606))

    def draw_howto(self):
        s = self.s
        s.blit(self.shade(C_HUD_D, 235), (0, 0))
        self.text("CÓMO JUGAR", 60, C_WHITE, (W / 2, 46), shadow=C_RED, off=3)
        rows = [("Moverse", "W  A  S  D", "FLECHAS"),
                ("Poner papa", "E", "CTRL derecho  (o 0 num.)"),
                ("Tirar papa", "F", "SHIFT derecho  (o . num.)"),
                ("Disparar", "Q", "ENTER")]
        for cx, sch, name in ((255, SCH_ROJO, "ROJO"), (490, SCH_BLANCO, "BLANCO")):
            draw_hooded(s, cx - 62, 112, sch, (0, 1), k=1.0, shadow=False)
            self.text(name, 30, C_WHITE, (cx, 112))
        for i, (what, k1, k2) in enumerate(rows):
            y = 152 + i * 30
            if i % 2 == 0:
                rrect(s, C_HUD, (24, y - 14, W - 48, 28), 6)
            self.text(what, 24, C_PINK, (40, y), anchor="midleft")
            self.text(k1, 24, C_WHITE, (255, y))
            self.text(k2, 22, C_WHITE, (490, y))
        tips = ["Las papas explotan en cruz a los 2,5 segundos y rompen las cajas.",
                "Tirar: la papa vuela 3 casillas por encima de todo.",
                "Parado sobre una papa (tuya o del rival), la recoges y la lanzas.",
                "Cañón de papitas: 3 balas que se recargan solas. Una papita deja frito al rival.",
                "A los {} s, MUERTE SÚBITA: la cancha se cierra y las balas no se acaban.".format(ROUND_TIME)]
        for i, tip in enumerate(tips):
            y = 296 + i * 28
            circ(s, C_RED, 36, y, 4)
            self.text(tip, 20, C_WHITE, (50, y), anchor="midleft")
        self.text("Poderes que salen de las cajas", 24, C_PINK, (W / 2, 452))
        for i, (kind, label) in enumerate((("aji", "Ají: más fuego"), ("papa", "Papa: más papas"),
                                           ("tinto", "Tinto: más rápido"))):
            cx = 58 + i * 205
            circ(s, C_WHITE, cx, 494, 18)
            circ(s, C_RED, cx, 494, 18, 2)
            self.draw_power_icon(kind, cx, 494)
            self.text(label, 20, C_WHITE, (cx + 26, 494), anchor="midleft")
        self.text("Gana el primero que llegue a {} rondas.   P o ESC: pausa.".format(WINS_TO_MATCH),
                  21, C_PINK, (W / 2, 544))
        if int(self.now * 2) % 2 == 0:
            self.text("ENTER para volver", 26, C_WHITE, (W / 2, 590))

    def draw_score(self, y):
        p1, p2 = self.players
        self.text("{}  -  {}".format(p1.wins, p2.wins), 54, C_WHITE, (W / 2, y), shadow=C_RED_DD, off=3)

    def draw(self):
        s = self.s
        self.draw_world()
        st = self.state
        if st == "menu":
            self.draw_menu()
            return
        if st == "howto":
            self.draw_howto()
            return
        self.draw_hud()
        mid = HUD + (H - HUD) / 2
        if st == "countdown":
            n = int(math.ceil(self.count_t / 0.7))
            u = (self.count_t / 0.7) % 1.0
            self.band(mid - 70, 140, alpha=180)
            self.text("Ronda {}  ·  {}".format(self.round, self.layout_name), 26, C_PINK, (W / 2, mid - 46))
            self.text(str(max(1, n)), int(70 + 50 * u) // 4 * 4, C_WHITE, (W / 2, mid + 12), shadow=C_RED, off=4)
        elif self.go_t > 0:
            self.text("¡YA!", 120, C_WHITE, (W / 2, mid), shadow=C_RED, off=5)
        if self.sd_banner > 0 and st in ("playing", "ending"):
            self.band(mid - 55, 110, C_RED_D, 215)
            self.text("¡MUERTE SÚBITA!", 62, C_WHITE, (W / 2, mid - 14), shadow=C_HUD_D, off=3)
            self.text("La cancha se cierra  ·  balas sin límite", 26, C_PINK, (W / 2, mid + 30))

        go = "ENTER o botón Grove para seguir" if self.wait <= 0 and int(self.now * 2) % 2 == 0 else " "
        if st == "round_over":
            self.band(mid - 105, 210)
            if self.winner:
                draw_hooded(s, 96, mid + 12, self.winner.sch, (0, 1), k=3.0, shadow=False,
                            step=self.now * 10, moving=True)
                self.text("¡Ronda para {}!".format(self.winner.name), 46, C_WHITE, (W / 2 + 50, mid - 62),
                          shadow=C_RED, off=3)
            else:
                self.text("¡Empate! Los dos quedaron fritos", 40, C_WHITE, (W / 2, mid - 62), shadow=C_RED, off=3)
            self.draw_score(mid)
            self.text(go, 24, C_PINK, (W / 2, mid + 66))
        elif st == "match_over":
            w = max(self.players, key=lambda p: p.wins)
            self.band(mid - 150, 300)
            self.text("¡CAMPEÓN DE LAS PAPAS!", 54, C_WHITE, (W / 2, mid - 112), shadow=C_RED, off=4)
            draw_hooded(s, W / 2, mid - 8, w.sch, (0, 1), k=3.2, shadow=False,
                        step=self.now * 12, moving=True)
            self.draw_potato(W / 2 - 110, mid - 10 + math.sin(self.now * 5) * 6, 22)
            self.draw_potato(W / 2 + 110, mid - 10 + math.cos(self.now * 5) * 6, 22)
            self.text(w.name, 44, C_WHITE, (W / 2, mid + 70), shadow=C_RED_DD, off=3)
            self.text("{}  -  {}".format(self.players[0].wins, self.players[1].wins), 30, C_PINK, (W / 2, mid + 102))
            if self.wait <= 0:
                self.text("ENTER: revancha     ESC: menú", 24, C_PINK, (W / 2, mid + 130))
            self.draw_fx()                 # el confeti va por encima
        if self.paused:
            s.blit(self.shade(C_HUD_D, 200), (0, 0))
            self.text("PAUSA", 96, C_WHITE, (W / 2, H / 2 - 40), shadow=C_RED, off=5)
            self.text("ENTER o P: seguir          ESC: volver al menú", 26, C_PINK, (W / 2, H / 2 + 40))


# ------------------------------------------------------------------ pantalla
def make_screen(full, desktop):
    if full:
        pygame.mouse.set_visible(False)
        if hasattr(pygame, "SCALED"):                 # pygame 2: escala con la GPU
            try:
                return pygame.display.set_mode((W, H), pygame.FULLSCREEN | pygame.SCALED)
            except pygame.error:
                pass
        return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.mouse.set_visible(True)
    dw, dh = desktop
    size = (W, H)
    if dw > 0 and dh > 0 and (dw < W or dh - 70 < H):  # pantalla pequena: ventana reducida
        k = min(dw / W, (dh - 70) / H)
        size = (int(W * k), int(H * k))
    return pygame.display.set_mode(size)


def present(screen, canvas, off):
    sw, sh = screen.get_size()
    if (sw, sh) == (W, H):
        if off != (0, 0):
            screen.fill(C_BLACK)
        screen.blit(canvas, off)
    else:
        k = min(sw / W, sh / H)
        nw, nh = int(W * k), int(H * k)
        screen.fill(C_BLACK)
        screen.blit(pygame.transform.scale(canvas, (nw, nh)),
                    ((sw - nw) // 2 + int(off[0] * k), (sh - nh) // 2 + int(off[1] * k)))
    pygame.display.flip()


def make_icon():
    icon = pygame.Surface((32, 32), pygame.SRCALPHA)
    pygame.draw.ellipse(icon, C_INK, (2, 8, 28, 22))
    pygame.draw.ellipse(icon, C_POTATO, (4, 10, 24, 18))
    pygame.draw.line(icon, C_INK, (22, 11), (27, 4), 3)
    pygame.draw.circle(icon, C_RED, (27, 4), 4)
    pygame.draw.circle(icon, C_WHITE, (27, 4), 2)
    return icon


def main():
    args = sys.argv[1:]
    full = "-f" in args or "--fullscreen" in args
    try:
        pygame.mixer.pre_init(22050, -16, 1, 512)
    except Exception:
        pass
    pygame.init()
    info = pygame.display.Info()
    desktop = (info.current_w, info.current_h)
    pygame.display.set_caption("Papas Bomba")
    try:
        pygame.display.set_icon(make_icon())
    except pygame.error:
        pass
    screen = make_screen(full, desktop)
    canvas = pygame.Surface((W, H)).convert()
    clock = pygame.time.Clock()
    hw = Hardware()
    sfx = Sfx("--sin-sonido" not in args)
    game = Game(canvas, hw, sfx)
    try:
        while not game.quit:
            dt = min(clock.tick(FPS) / 1000.0, 0.1)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    game.quit = True
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_F11:
                        full = not full
                        screen = make_screen(full, desktop)
                    else:
                        game.handle_key(ev.key)
            if hw.take_button():
                game.button()
            game.update(dt)
            game.draw()
            off = (0, 0)
            if game.shake > 0.5 and not game.paused:
                off = (int(random.uniform(-1, 1) * game.shake), int(random.uniform(-1, 1) * game.shake))
            present(screen, canvas, off)
    finally:
        hw.close()
        pygame.quit()


if __name__ == "__main__":
    main()
