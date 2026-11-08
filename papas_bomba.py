#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PAPAS BOMBA  -  juego para 2 jugadores en un mismo teclado
Raspberry Pi 3 + GrovePi+ (opcional)

Lanza papas rellenas explosivas y deja frito a tu rival.
Gana el primero que llegue a 3 rondas.

                 moverse    pone papa       tira papa          dispara
  Jugador 1:     W A S D    E               F                  Q
  Jugador 2:     FLECHAS    CTRL derecho    SHIFT derecho      ENTER
                            (o 0 numerico)  (o punto numerico)
  ESC: salir

Tirar papa: sale volando hacia donde miras, pasa por encima de todo y cae
unas 3 casillas adelante. Si estas parado encima de una papa (tuya o del
rival), la recoges y la lanzas.

Canon de papas: cada jugador saca el arma y dispara papitas cuando quiera.
Tiene 3 balas que se recargan solas (1 cada 6 s). Una papita deja frito al
rival y si le pega a una papa bomba la hace explotar.

Muerte subita: a los 90 segundos la cancha se empieza a cerrar desde los
bordes hacia el centro y las balas se vuelven infinitas.

Poderes que salen de las canastas:
  Aji         -> la explosion llega mas lejos
  Papa extra  -> puedes tener mas papas a la vez
  Tinto       -> te mueves mas rapido

GrovePi+ (si no esta conectado, el juego funciona igual):
  Buzzer -> D8   suena con cada explosion
  LED    -> D4   se prende cuando alguien queda frito
  Boton  -> D3   empieza / pasa a la siguiente ronda (igual que ENTER)

Correr:   python3 papas_bomba.py        (pantalla completa: python3 papas_bomba.py -f)
"""
from __future__ import division, print_function, unicode_literals

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
SD_STEP = 0.3          # cada cuanto se cierra una casilla en muerte subita

AMMO_MAX = 3           # balas del canon de papas
AMMO_RECHARGE = 6.0    # segundos para recargar 1 bala
SHOT_COOLDOWN = 0.5    # tiempo minimo entre disparos
SD_SHOT_COOLDOWN = 0.3 # en muerte subita se dispara mas rapido
BULLET_SPEED = 10.0    # casillas por segundo

BUZZER, LED, BOTON = 8, 4, 3   # puertos digitales del GrovePi

EMPTY, WALL, BLOCK = 0, 1, 2
DIRS = [(0, -1), (0, 1), (-1, 0), (1, 0)]      # arriba, abajo, izq, der
POWER_KINDS = ["aji", "papa", "tinto"]

# colores
C_GRASS_A = (104, 168, 88)
C_GRASS_B = (96, 158, 82)
C_WALL = (92, 92, 104)
C_WALL_TOP = (134, 134, 148)
C_WALL_DARK = (60, 60, 70)
C_CRATE = (176, 116, 62)
C_CRATE_DARK = (112, 70, 34)
C_HUD = (36, 30, 42)
C_GOLD = (250, 200, 70)
C_WHITE = (245, 245, 245)
C_SKIN = (240, 205, 165)


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

    def boom(self):
        if self.q.qsize() < 3:
            self._send([(BUZZER, 1, 0.12), (BUZZER, 0, 0.0)])

    def pick(self):
        self._send([(BUZZER, 1, 0.03), (BUZZER, 0, 0.05), (BUZZER, 1, 0.03), (BUZZER, 0, 0.0)])

    def death(self):
        self._send([(LED, 1, 0.0), (BUZZER, 1, 0.5), (BUZZER, 0, 0.0)])

    def win(self):
        self._send([(BUZZER, 1, 0.1), (BUZZER, 0, 0.08)] * 3 + [(BUZZER, 1, 0.4), (BUZZER, 0, 0.0)])

    def throw(self):
        if self.q.qsize() < 3:
            self._send([(BUZZER, 1, 0.02), (BUZZER, 0, 0.0)])

    def shoot(self):
        if self.q.qsize() < 3:
            self._send([(BUZZER, 1, 0.01), (BUZZER, 0, 0.0)])

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
    def __init__(self, num, spawn, color, move_keys, bomb_keys, throw_keys, shoot_keys):
        self.num = num
        self.spawn = spawn
        self.color = color
        self.dark = tuple(int(c * 0.6) for c in color)
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
        self.face = (0, 1)
        self.ammo = AMMO_MAX
        self.ammo_t = 0.0
        self.cool = 0.0
        self.gun_t = 0.0

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


# ------------------------------------------------------------------ juego
class Game(object):
    def __init__(self, screen, hw):
        self.screen = screen
        self.hw = hw
        self.fonts = {}
        self.players = [
            Player(1, (1, 1), (220, 60, 60),
                   [pygame.K_w, pygame.K_s, pygame.K_a, pygame.K_d],
                   [pygame.K_e],                                  # pone
                   [pygame.K_f],                                  # tira
                   [pygame.K_q]),                                 # dispara
            Player(2, (COLS - 2, ROWS - 2), (60, 110, 225),
                   [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT],
                   [pygame.K_RCTRL, pygame.K_KP0],                # pone
                   [pygame.K_RSHIFT, pygame.K_KP_PERIOD],         # tira
                   [pygame.K_RETURN, pygame.K_KP_ENTER]),         # dispara
        ]
        self.state = "menu"
        self.wait = 0.0
        self.round = 0
        self.winner = None
        self.now = 0.0
        self.background = self.make_background()
        self.new_map()

    # ---------------- utilidades
    def font(self, size):
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(None, size)
        return self.fonts[size]

    def text(self, s, size, color, center):
        img = self.font(size).render(s, True, color)
        r = img.get_rect(center=(int(center[0]), int(center[1])))
        self.screen.blit(img, r)
        return r

    def bomb_at(self, x, y):
        """Papa que esta en el piso en (x, y). Las que van volando no cuentan."""
        for b in self.bombs:
            if b.x == x and b.y == y and not b.flying:
                return b
        return None

    def landing_free(self, x, y):
        if not (0 < x < COLS - 1 and 0 < y < ROWS - 1):
            return False
        if self.grid[y][x] != EMPTY:
            return False
        return all(not (b.x == x and b.y == y) for b in self.bombs)

    def walkable(self, x, y):
        return self.grid[y][x] == EMPTY and self.bomb_at(x, y) is None

    # ---------------- mapa
    def new_map(self):
        g = [[EMPTY] * COLS for _ in range(ROWS)]
        for y in range(ROWS):
            for x in range(COLS):
                if x in (0, COLS - 1) or y in (0, ROWS - 1) or (x % 2 == 0 and y % 2 == 0):
                    g[y][x] = WALL
        safe = set([(1, 1), (2, 1), (1, 2)])
        safe |= set((COLS - 1 - x, ROWS - 1 - y) for (x, y) in list(safe))
        hidden = {}
        # mapa simetrico para que sea justo para los dos
        for y in range(ROWS):
            for x in range(COLS):
                mx, my = COLS - 1 - x, ROWS - 1 - y
                if (y, x) > (my, mx):
                    continue
                if g[y][x] != EMPTY or (x, y) in safe:
                    continue
                if random.random() < 0.62:
                    g[y][x] = BLOCK
                    g[my][mx] = BLOCK
                    if random.random() < 0.32:
                        k = random.choice(POWER_KINDS)
                        hidden[(x, y)] = k
                        hidden[(mx, my)] = k
        self.grid = g
        self.hidden = hidden
        self.bombs = []
        self.fire = {}
        self.powerups = {}
        self.bullets = []
        # muerte subita
        self.round_time = ROUND_TIME
        self.sudden = False
        self.sd_timer = 0.0
        self.sd_banner = 0.0
        self.closed = []
        self.sd_cells = self.spiral_cells()

    def spiral_cells(self):
        """Casillas en espiral desde el borde hacia el centro (sin las columnas fijas)."""
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
        # se cierra cada casilla junto con su espejo, para que sea justo
        pairs, seen = [], set()
        for (x, y) in cells:
            if (x % 2 == 0 and y % 2 == 0) or (x, y) in seen:
                continue
            m = (COLS - 1 - x, ROWS - 1 - y)
            seen.add((x, y))
            seen.add(m)
            pairs.append([(x, y)] if m == (x, y) else [(x, y), m])
        return pairs

    def start_round(self):
        self.round += 1
        self.new_map()
        for p in self.players:
            p.reset()
        self.winner = None
        self.state = "playing"
        self.hw.reset()

    def advance(self):
        if self.wait > 0:
            return
        if self.state == "match_over":
            for p in self.players:
                p.wins = 0
            self.round = 0
        if self.state in ("menu", "round_over", "match_over"):
            self.start_round()

    # ---------------- logica
    def place_bomb(self, p):
        if not p.alive or self.state not in ("playing", "ending"):
            return
        mine = sum(1 for b in self.bombs if b.owner is p)
        if mine >= p.max_bombs or self.bomb_at(p.x, p.y):
            return
        self.bombs.append(Bomb(p.x, p.y, p, p.range))

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
        if not p.alive or self.state not in ("playing", "ending"):
            return
        b = self.bomb_at(p.x, p.y)          # si estoy encima de una papa, la recojo
        new = b is None
        if new:
            mine = sum(1 for o in self.bombs if o.owner is p)
            if mine >= p.max_bombs:
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
        self.hw.throw()

    def shoot(self, p):
        if not p.alive or self.state not in ("playing", "ending") or p.cool > 0:
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
        self.hw.shoot()

    def kill(self, p):
        if p.alive:
            p.alive = False
            p.dead_t = 1.2
            self.hw.death()

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
                    hit = True                       # pared o canasta
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
                    self.bullets.remove(bl)
                    break

    def close_next_cell(self):
        if not self.sd_cells:
            return
        for (x, y) in self.sd_cells.pop(0):
            if self.grid[y][x] == WALL:
                continue
            self.grid[y][x] = WALL
            self.closed.append((x, y))
            self.hidden.pop((x, y), None)
            self.powerups.pop((x, y), None)
            self.fire.pop((x, y), None)
            self.bombs = [b for b in self.bombs if b.flying or (b.x, b.y) != (x, y)]
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
                self.hw.sudden()
            return
        self.sd_banner = max(0.0, self.sd_banner - dt)
        self.sd_timer += dt
        while self.sd_timer >= SD_STEP:
            self.sd_timer -= SD_STEP
            self.close_next_cell()

    def add_fire(self, x, y):
        self.fire[(x, y)] = FIRE_TIME

    def explode(self, b):
        self.bombs.remove(b)
        self.hw.boom()
        self.add_fire(b.x, b.y)
        for dx, dy in DIRS:
            for i in range(1, b.range + 1):
                nx, ny = b.x + dx * i, b.y + dy * i
                cell = self.grid[ny][nx]
                if cell == WALL:
                    break
                if cell == BLOCK:
                    self.grid[ny][nx] = EMPTY
                    self.add_fire(nx, ny)
                    k = self.hidden.pop((nx, ny), None)
                    if k:
                        self.powerups[(nx, ny)] = k
                    break
                if (nx, ny) in self.powerups:
                    del self.powerups[(nx, ny)]
                    self.add_fire(nx, ny)
                    break
                other = self.bomb_at(nx, ny)
                self.add_fire(nx, ny)
                if other:
                    other.t = 0      # reaccion en cadena
                    break

    def update_player(self, p, dt, keys):
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
        if p.move_t <= 0:
            p.move_t = 0
            for i, k in enumerate(p.move_keys):
                if keys[k]:
                    dx, dy = DIRS[i]
                    p.face = (dx, dy)
                    if self.walkable(p.x + dx, p.y + dy):
                        p.px, p.py = p.x, p.y
                        p.x += dx
                        p.y += dy
                        p.move_t = p.delay
                    break
        k = self.powerups.pop((p.x, p.y), None)
        if k:
            self.hw.pick()
            if k == "aji":
                p.range = min(p.range + 1, 8)
            elif k == "papa":
                p.max_bombs = min(p.max_bombs + 1, 6)
            elif k == "tinto":
                p.speed_lvl = min(p.speed_lvl + 1, 4)
                p.delay = 0.20 - 0.025 * p.speed_lvl

    def update(self, dt):
        self.now += dt
        if self.wait > 0:
            self.wait -= dt
        if self.state not in ("playing", "ending"):
            return
        keys = pygame.key.get_pressed()
        for p in self.players:
            self.update_player(p, dt, keys)
        self.update_sudden(dt)
        self.update_bullets(dt)

        for b in self.bombs:
            b.t -= dt
            if b.flying:
                b.fly_t += dt
                if b.fly_t >= b.fly_dur:
                    b.flying = False
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
            self.fire[pos] -= dt
            if self.fire[pos] <= 0:
                del self.fire[pos]

        for p in self.players:
            if p.alive and (p.x, p.y) in self.fire:
                self.kill(p)

        alive = [p for p in self.players if p.alive]
        if self.state == "playing" and len(alive) <= 1:
            self.state = "ending"
            self.end_t = 1.5
        elif self.state == "ending":
            self.end_t -= dt
            if self.end_t <= 0:
                if len(alive) == 1:
                    self.winner = alive[0]
                    self.winner.wins += 1
                    self.hw.win()
                else:
                    self.winner = None
                if any(p.wins >= WINS_TO_MATCH for p in self.players):
                    self.state = "match_over"
                else:
                    self.state = "round_over"
                self.wait = 1.0

    # ---------------- dibujo
    def make_background(self):
        bg = pygame.Surface((W, H))
        bg.fill(C_HUD)
        for y in range(ROWS):
            for x in range(COLS):
                r = pygame.Rect(x * TILE, HUD + y * TILE, TILE, TILE)
                pygame.draw.rect(bg, C_GRASS_A if (x + y) % 2 == 0 else C_GRASS_B, r)
                is_wall = x in (0, COLS - 1) or y in (0, ROWS - 1) or (x % 2 == 0 and y % 2 == 0)
                if is_wall:
                    pygame.draw.rect(bg, C_WALL_DARK, r)
                    pygame.draw.rect(bg, C_WALL, r.inflate(-2, -6).move(0, -2))
                    pygame.draw.rect(bg, C_WALL_TOP, pygame.Rect(r.x + 3, r.y + 2, TILE - 6, 6))
        return bg

    def draw_wall(self, x, y):
        r = pygame.Rect(x * TILE, HUD + y * TILE, TILE, TILE)
        pygame.draw.rect(self.screen, C_WALL_DARK, r)
        pygame.draw.rect(self.screen, (120, 70, 70), r.inflate(-2, -6).move(0, -2))
        pygame.draw.rect(self.screen, (160, 100, 100), pygame.Rect(r.x + 3, r.y + 2, TILE - 6, 6))

    def draw_warning(self):
        """Las proximas casillas que se van a cerrar titilan en rojo."""
        if not self.sudden or int(self.now * 8) % 2:
            return
        shade = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        shade.fill((255, 40, 40, 110))
        for pair in self.sd_cells[:3]:
            for (x, y) in pair:
                if self.grid[y][x] != WALL:
                    self.screen.blit(shade, (x * TILE, HUD + y * TILE))

    def draw_bullet(self, bl):
        cx = int(bl.x * TILE + TILE / 2)
        cy = int(HUD + bl.y * TILE + TILE / 2)
        tx, ty = int(cx - bl.dx * 14), int(cy - bl.dy * 14)
        pygame.draw.line(self.screen, (255, 240, 180), (tx, ty), (cx, cy), 3)
        if bl.dx:
            rect = pygame.Rect(cx - 7, cy - 4, 14, 8)
        else:
            rect = pygame.Rect(cx - 4, cy - 7, 8, 14)
        pygame.draw.ellipse(self.screen, (180, 130, 40), rect.inflate(2, 2))
        pygame.draw.ellipse(self.screen, (250, 215, 90), rect)

    def draw_gun(self, p, cx, cy):
        fx, fy = p.face
        sx, sy = cx + fx * 6, cy + 4
        ex, ey = cx + fx * 20, cy + 4 + fy * 14
        pygame.draw.line(self.screen, (45, 45, 52), (sx, sy), (ex, ey), 7)
        pygame.draw.line(self.screen, (90, 90, 100), (sx, sy), (ex, ey), 3)
        pygame.draw.circle(self.screen, (230, 120, 40), (ex, ey), 4)

    def draw_crate(self, x, y):
        r = pygame.Rect(x * TILE + 2, HUD + y * TILE + 2, TILE - 4, TILE - 4)
        pygame.draw.rect(self.screen, C_CRATE_DARK, r)
        inner = r.inflate(-6, -6)
        pygame.draw.rect(self.screen, C_CRATE, inner)
        pygame.draw.line(self.screen, C_CRATE_DARK, inner.topleft, inner.bottomright, 3)
        pygame.draw.line(self.screen, C_CRATE_DARK, inner.topright, inner.bottomleft, 3)
        pygame.draw.rect(self.screen, C_CRATE_DARK, inner, 2)

    def draw_potato(self, cx, cy, r, t_left=None):
        s = self.screen
        color = (214, 170, 90)
        if t_left is not None and t_left < 0.8 and int(self.now * 10) % 2 == 0:
            color = (240, 110, 60)
        rect = pygame.Rect(0, 0, int(r * 2.2), int(r * 1.8))
        rect.center = (int(cx), int(cy))
        pygame.draw.ellipse(s, (120, 80, 35), rect.inflate(4, 4))
        pygame.draw.ellipse(s, color, rect)
        hl = pygame.Rect(0, 0, int(r * 0.9), int(r * 0.5))
        hl.center = (int(cx - r * 0.4), int(cy - r * 0.4))
        pygame.draw.ellipse(s, (240, 212, 145), hl)
        for ox, oy in ((0.4, 0.15), (-0.25, 0.4), (0.1, -0.3)):
            pygame.draw.circle(s, (160, 115, 50), (int(cx + ox * r), int(cy + oy * r)), max(2, int(r * 0.13)))
        if t_left is not None:
            a = (int(cx + r * 0.55), int(cy - r * 0.7))
            b = (int(cx + r * 0.95), int(cy - r * 1.3))
            pygame.draw.line(s, (60, 40, 20), a, b, 3)
            spark = random.choice([(255, 230, 80), (255, 150, 30), (255, 255, 200)])
            pygame.draw.circle(s, spark, b, random.randint(3, 6))

    def draw_bomb(self, b):
        if b.flying:
            p = min(1.0, b.fly_t / b.fly_dur)
            gx = b.fx + (b.x - b.fx) * p
            gy = b.fy + (b.y - b.fy) * p
            cx = gx * TILE + TILE / 2
            cy = HUD + gy * TILE + TILE / 2 + 2
            z = math.sin(math.pi * p) * TILE * 1.1       # altura del arco
            sw = int(22 - z * 0.15)
            pygame.draw.ellipse(self.screen, (64, 112, 58),
                                (int(cx - sw / 2), int(cy + 6), sw, 7))
            self.draw_potato(cx, cy - z, TILE * 0.33, b.t)
            return
        cx = b.x * TILE + TILE / 2
        cy = HUD + b.y * TILE + TILE / 2 + 2
        speed = 6 + (BOMB_TIME - b.t) * 8
        r = TILE * 0.33 * (1 + 0.08 * math.sin(self.now * speed))
        self.draw_potato(cx, cy, r, b.t)

    def draw_fire(self, pos, t):
        x, y = pos
        r = pygame.Rect(x * TILE, HUD + y * TILE, TILE, TILE)
        j = random.randint(0, 3)
        pygame.draw.rect(self.screen, (230, 70, 20), r.inflate(-2 - j, -2 - j))
        pygame.draw.rect(self.screen, (255, 150, 30), r.inflate(-10 - j, -10 - j))
        pygame.draw.rect(self.screen, (255, 235, 120), r.inflate(-20 - j, -20 - j))

    def draw_powerup(self, pos, kind):
        x, y = pos
        cx = x * TILE + TILE // 2
        cy = HUD + y * TILE + TILE // 2 + int(math.sin(self.now * 5 + x) * 2)
        s = self.screen
        pygame.draw.circle(s, (255, 248, 220), (cx, cy), 17)
        pygame.draw.circle(s, C_GOLD, (cx, cy), 17, 2)
        if kind == "aji":
            pygame.draw.ellipse(s, (210, 30, 30), (cx - 6, cy - 9, 12, 22))
            pygame.draw.ellipse(s, (255, 120, 120), (cx - 3, cy - 6, 4, 9))
            pygame.draw.rect(s, (40, 150, 40), (cx - 3, cy - 13, 6, 5))
        elif kind == "papa":
            self.draw_potato(cx - 1, cy + 1, 9)
            self.text("+", 26, (90, 50, 20), (cx + 9, cy - 8))
        elif kind == "tinto":
            pygame.draw.rect(s, C_WHITE, (cx - 8, cy - 4, 15, 13))
            pygame.draw.rect(s, (120, 120, 120), (cx - 8, cy - 4, 15, 13), 1)
            pygame.draw.ellipse(s, (90, 50, 20), (cx - 7, cy - 6, 13, 5))
            pygame.draw.circle(s, (120, 120, 120), (cx + 9, cy + 2), 4, 2)
            for i in (-3, 2):
                pygame.draw.line(s, (170, 170, 170), (cx + i, cy - 9), (cx + i + 2, cy - 15), 2)

    def draw_player(self, p):
        s = self.screen
        cx, cy = p.draw_pos()
        cx, cy = int(cx), int(cy)
        if not p.alive:
            if p.dead_t <= 0:
                return
            gray = (150, 150, 150)
            pygame.draw.ellipse(s, gray, (cx - 12, cy - 2, 24, 20))
            pygame.draw.circle(s, (200, 200, 200), (cx, cy - 9), 10)
            for ex in (-4, 4):
                pygame.draw.line(s, (40, 40, 40), (cx + ex - 2, cy - 11), (cx + ex + 2, cy - 7), 2)
                pygame.draw.line(s, (40, 40, 40), (cx + ex + 2, cy - 11), (cx + ex - 2, cy - 7), 2)
            self.text("FRITO!", 22, C_GOLD, (cx, cy - 28))
            return
        moving = p.move_t > 0
        bob = int(math.sin(self.now * 18) * 2) if moving else 0
        fx, fy = p.face
        pygame.draw.ellipse(s, (64, 112, 58), (cx - 13, cy + 10, 26, 8))
        pygame.draw.ellipse(s, p.dark, (cx - 13, cy - 3 + bob, 26, 22))
        pygame.draw.ellipse(s, p.color, (cx - 11, cy - 2 + bob, 22, 19))
        pygame.draw.circle(s, (150, 110, 80), (cx, cy - 9 + bob), 11)
        pygame.draw.circle(s, C_SKIN, (cx, cy - 9 + bob), 10)
        # gorra
        pygame.draw.polygon(s, p.color, [(cx - 10, cy - 11 + bob), (cx + 10, cy - 11 + bob),
                                         (cx + 7, cy - 19 + bob), (cx - 7, cy - 19 + bob)])
        if fy >= 0:
            pygame.draw.ellipse(s, p.dark, (cx - 6 + fx * 8, cy - 13 + bob, 12, 5))
            for ex in (-4, 4):
                pygame.draw.circle(s, (30, 30, 30), (cx + ex + fx * 3, cy - 7 + fy * 2 + bob), 2)
        if p.gun_t > 0 or self.sudden:          # canon de papas en la mano
            self.draw_gun(p, cx, cy + bob)

    def draw_hud(self):
        s = self.screen
        pygame.draw.rect(s, C_HUD, (0, 0, W, HUD))
        self.text("PAPAS BOMBA", 34, C_GOLD, (W / 2, 18))
        if self.sudden:
            if int(self.now * 4) % 2 == 0:
                self.text("MUERTE SUBITA", 22, (255, 80, 80), (W / 2, 42))
        elif self.round:
            t = int(math.ceil(self.round_time))
            col = (255, 120, 120) if t <= 10 else (200, 200, 210)
            self.text("Ronda {}    {}:{:02d}".format(self.round, t // 60, t % 60), 20, col, (W / 2, 42))
        for p in self.players:
            left = p.num == 1
            x0 = 8 if left else W - 226
            pygame.draw.circle(s, p.color, (x0 + 12, 18), 10)
            self.text("J{}".format(p.num), 22, C_WHITE, (x0 + 12, 18))
            stats = "Papas {}  Fuego {}  Vel {}".format(p.max_bombs, p.range, p.speed_lvl)
            img = self.font(18).render(stats, True, (220, 220, 230))
            s.blit(img, (x0 + 28, 11))
            for i in range(WINS_TO_MATCH):
                c = C_GOLD if i < p.wins else (80, 75, 90)
                pygame.draw.circle(s, c, (x0 + 36 + i * 16, 40), 6)
            # balas del canon
            bx = x0 + 92
            if self.sudden:
                img = self.font(18).render("Balas: sin limite", True, (255, 200, 120))
                s.blit(img, (bx, 34))
            else:
                img = self.font(18).render("Balas", True, (220, 220, 230))
                s.blit(img, (bx, 34))
                for i in range(AMMO_MAX):
                    r = pygame.Rect(bx + 44 + i * 14, 35, 9, 12)
                    if i < p.ammo:
                        pygame.draw.ellipse(s, (250, 215, 90), r)
                    else:
                        pygame.draw.ellipse(s, (80, 75, 90), r, 1)

    def overlay(self, lines):
        shade = pygame.Surface((W, H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 175))
        self.screen.blit(shade, (0, 0))
        total = sum(sz + 8 for _, sz, _ in lines)
        y = H / 2 - total / 2
        for txt, sz, col in lines:
            self.text(txt, sz, col, (W / 2, y + sz / 2))
            y += sz + 8

    def draw(self):
        s = self.screen
        s.blit(self.background, (0, 0))
        for y in range(ROWS):
            for x in range(COLS):
                if self.grid[y][x] == BLOCK:
                    self.draw_crate(x, y)
        for (x, y) in self.closed:
            self.draw_wall(x, y)
        self.draw_warning()
        for pos, kind in self.powerups.items():
            self.draw_powerup(pos, kind)
        for b in self.bombs:
            if not b.flying:
                self.draw_bomb(b)
        for pos, t in self.fire.items():
            self.draw_fire(pos, t)
        for p in self.players:
            self.draw_player(p)
        for bl in self.bullets:
            self.draw_bullet(bl)
        for b in self.bombs:               # las que vuelan van por encima de todo
            if b.flying:
                self.draw_bomb(b)
        self.draw_hud()
        if self.sd_banner > 0 and self.state in ("playing", "ending"):
            band = pygame.Surface((W, 110), pygame.SRCALPHA)
            band.fill((120, 0, 0, 190))
            self.screen.blit(band, (0, H / 2 - 55))
            self.text("MUERTE SUBITA!", 60, C_GOLD, (W / 2, H / 2 - 15))
            self.text("La cancha se cierra  -  balas sin limite", 26, C_WHITE, (W / 2, H / 2 + 30))

        hint = (200, 200, 210)
        go = "ENTER o boton Grove para seguir" if self.wait <= 0 else " "
        if self.state == "menu":
            self.overlay([
                ("PAPAS BOMBA", 72, C_GOLD),
                ("Lanza papas rellenas explosivas y deja frito a tu rival", 24, C_WHITE),
                (" ", 10, C_WHITE),
                ("J1 (rojo):  WASD   E pone   F tira   Q dispara", 26, (255, 140, 140)),
                ("J2 (azul):  FLECHAS   CTRL pone   SHIFT tira   ENTER dispara", 24, (150, 180, 255)),
                ("Parado encima de una papa, la recoges y la lanzas", 22, (200, 200, 210)),
                ("A los {} s: MUERTE SUBITA, la cancha se cierra".format(ROUND_TIME), 22, (255, 150, 150)),
                (" ", 10, C_WHITE),
                ("Aji = mas fuego    Papa = mas papas    Tinto = mas rapido", 22, hint),
                ("Gana el primero en {} rondas".format(WINS_TO_MATCH), 22, hint),
                ("GrovePi: {}".format("conectado" if self.hw.ok else "no encontrado (se juega igual)"), 20, hint),
                (" ", 10, C_WHITE),
                ("ENTER o boton Grove para empezar", 28, C_GOLD),
            ])
        elif self.state == "round_over":
            if self.winner:
                title = "Gana la ronda el Jugador {}!".format(self.winner.num)
                col = self.winner.color
            else:
                title = "Empate! Los dos quedaron fritos"
                col = C_WHITE
            self.overlay([(title, 44, col),
                          ("{}  -  {}".format(self.players[0].wins, self.players[1].wins), 40, C_WHITE),
                          (go, 26, C_GOLD)])
        elif self.state == "match_over":
            w = max(self.players, key=lambda p: p.wins)
            self.overlay([("CAMPEON DE LAS PAPAS", 54, C_GOLD),
                          ("Jugador {}".format(w.num), 48, w.color),
                          ("{}  -  {}".format(self.players[0].wins, self.players[1].wins), 40, C_WHITE),
                          ("ENTER para otra partida  -  ESC para salir" if self.wait <= 0 else " ", 26, hint)])


# ------------------------------------------------------------------ main
def main():
    pygame.init()
    flags = pygame.FULLSCREEN if "-f" in sys.argv else 0
    screen = pygame.display.set_mode((W, H), flags)
    pygame.display.set_caption("Papas Bomba")
    clock = pygame.time.Clock()
    hw = Hardware()
    game = Game(screen, hw)
    start_keys = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
    running = True
    try:
        while running:
            dt = min(clock.tick(FPS) / 1000.0, 0.1)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        running = False
                    elif game.state in ("playing", "ending"):
                        for p in game.players:
                            if ev.key in p.bomb_keys:
                                game.place_bomb(p)
                            elif ev.key in p.throw_keys:
                                game.throw_bomb(p)
                            elif ev.key in p.shoot_keys:
                                game.shoot(p)
                    elif ev.key in start_keys:
                        game.advance()
            if hw.take_button():
                game.advance()
            game.update(dt)
            game.draw()
            pygame.display.flip()
    finally:
        hw.close()
        pygame.quit()


if __name__ == "__main__":
    main()
