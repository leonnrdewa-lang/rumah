"""Icons for the village-life features (gifts, the newspaper, protests, festivals,
house decor and the Buku Prestasi), drawn with Pillow in the same cel-shaded,
ink-outlined look as tools/make_item_icons.py.

python3 tools/make_social_icons.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_ui_icons import Pad, shade, CREAM_HI  # noqa: E402

INK = (58, 36, 24, 255)
W = 0.035  # ink rim


def orect(p, x0, y0, x1, y1, col, r=0.04):
    p.rect(x0 - W, y0 - W, x1 + W, y1 + W, INK, r=r + W)
    p.rect(x0, y0, x1, y1, col, r=r)


def ocircle(p, cx, cy, r, col):
    p.circle(cx, cy, r + W, INK)
    p.circle(cx, cy, r, col)


def opoly(p, pts, col):
    cx = sum(x for x, _ in pts) / len(pts)
    cy = sum(y for _, y in pts) / len(pts)
    big = []
    for x, y in pts:
        dx, dy = x - cx, y - cy
        d = math.hypot(dx, dy) or 1.0
        big.append((x + dx / d * W * 1.3, y + dy / d * W * 1.3))
    p.poly(big, INK)
    p.poly(pts, col)


def kopi():
    p = Pad(128)
    bag = (150, 92, 52, 255)
    opoly(p, [(0.26, 0.28), (0.74, 0.28), (0.8, 0.88), (0.2, 0.88)], bag)
    p.poly([(0.26, 0.28), (0.36, 0.28), (0.3, 0.88), (0.2, 0.88)], shade(bag, 0.82))
    orect(p, 0.24, 0.16, 0.76, 0.3, shade(bag, 1.15), r=0.03)
    orect(p, 0.32, 0.46, 0.68, 0.72, (246, 226, 176, 255), r=0.04)
    for cx, cy in ((0.44, 0.58), (0.56, 0.6)):
        p.ellipse(cx - 0.06, cy - 0.08, cx + 0.06, cy + 0.08, (96, 56, 30, 255))
        p.line([(cx, cy - 0.06), (cx + 0.01, cy + 0.06)], (60, 32, 18, 255), 0.012)
    p.save("icon_kopi")


def kue():
    p = Pad(128)
    plate = (236, 236, 228, 255)
    p.ellipse(0.12 - W, 0.58 - W, 0.88 + W, 0.88 + W, INK)
    p.ellipse(0.12, 0.58, 0.88, 0.88, plate)
    p.ellipse(0.2, 0.62, 0.8, 0.82, shade(plate, 0.92))
    # klepon: green balls with coconut
    for cx, cy in ((0.36, 0.6), (0.62, 0.6), (0.49, 0.45)):
        ocircle(p, cx, cy, 0.13, (92, 170, 74, 255))
        p.circle(cx - 0.04, cy - 0.04, 0.04, (150, 214, 120, 255))
        for k in range(5):
            a = k * 1.3 + cx * 10
            p.circle(cx + math.cos(a) * 0.08, cy + 0.06 + math.sin(a) * 0.03, 0.014, CREAM_HI)
    p.save("icon_kue")


def hadiah():
    p = Pad(128)
    box = (212, 70, 60, 255)
    orect(p, 0.18, 0.42, 0.82, 0.88, box, r=0.04)
    orect(p, 0.13, 0.32, 0.87, 0.46, shade(box, 1.12), r=0.04)
    p.rect(0.44, 0.32, 0.56, 0.88, (246, 204, 92, 255))
    for s in (-1, 1):
        opoly(p, [(0.5, 0.32), (0.5 + s * 0.25, 0.16), (0.5 + s * 0.3, 0.3)], (246, 204, 92, 255))
    ocircle(p, 0.5, 0.31, 0.05, (230, 170, 60, 255))
    p.save("icon_hadiah")


def koran():
    p = Pad(128)
    paper = (244, 238, 222, 255)
    opoly(p, [(0.16, 0.2), (0.82, 0.14), (0.86, 0.82), (0.2, 0.88)], paper)
    p.poly([(0.22, 0.24), (0.78, 0.2), (0.79, 0.3), (0.23, 0.34)], (60, 44, 36, 255))
    p.poly([(0.24, 0.4), (0.5, 0.38), (0.52, 0.62), (0.26, 0.64)], (190, 180, 160, 255))
    for i in range(5):
        y = 0.4 + i * 0.075
        p.line([(0.56, y - 0.004), (0.78, y - 0.016)], (110, 96, 84, 255), 0.022)
    for i in range(2):
        y = 0.72 + i * 0.07
        p.line([(0.27, y), (0.78, y - 0.035)], (110, 96, 84, 255), 0.022)
    p.circle(0.37, 0.48, 0.05, (130, 116, 100, 255))
    p.save("icon_koran")


def megafon():
    p = Pad(128)
    red = (214, 72, 56, 255)
    opoly(p, [(0.22, 0.42), (0.7, 0.18), (0.7, 0.82), (0.22, 0.6)], red)
    p.poly([(0.22, 0.52), (0.7, 0.52), (0.7, 0.82), (0.22, 0.6)], shade(red, 0.82))
    orect(p, 0.12, 0.4, 0.26, 0.62, (236, 236, 228, 255), r=0.03)
    p.ellipse(0.64 - W, 0.16 - W, 0.82 + W, 0.84 + W, INK)
    p.ellipse(0.64, 0.16, 0.82, 0.84, (240, 228, 210, 255))
    orect(p, 0.32, 0.6, 0.42, 0.86, (90, 90, 96, 255), r=0.02)
    for i in range(3):
        a = -0.5 + i * 0.5
        p.line([(0.88, 0.5 + a * 0.3), (0.95, 0.5 + a * 0.45)], INK, 0.03)
    p.save("icon_megafon")


def bendera():
    p = Pad(128)
    orect(p, 0.2, 0.1, 0.27, 0.92, (150, 110, 70, 255), r=0.02)
    pts = []
    for i in range(9):
        x = 0.27 + i * 0.075
        pts.append((x, 0.16 + math.sin(i * 0.9) * 0.03))
    bot = [(x, y + 0.36) for x, y in reversed(pts)]
    opoly(p, pts + bot, (230, 230, 226, 255))
    mid = [(x, y + 0.18) for x, y in pts]
    p.poly(pts + list(reversed(mid)), (214, 52, 44, 255))
    ocircle(p, 0.235, 0.09, 0.04, (246, 204, 92, 255))
    p.save("icon_bendera")


def sofa():
    p = Pad(128)
    c = (176, 92, 70, 255)
    orect(p, 0.14, 0.3, 0.86, 0.62, c, r=0.08)
    orect(p, 0.1, 0.5, 0.9, 0.78, shade(c, 1.08), r=0.06)
    for x in (0.1, 0.74):
        orect(p, x, 0.44, x + 0.16, 0.78, shade(c, 0.86), r=0.06)
    for x in (0.18, 0.78):
        orect(p, x, 0.78, x + 0.05, 0.88, (90, 60, 40, 255), r=0.01)
    p.rect(0.3, 0.54, 0.7, 0.6, shade(c, 1.2), r=0.02)
    p.save("icon_sofa")


def akuarium():
    p = Pad(128)
    orect(p, 0.12, 0.24, 0.88, 0.8, (150, 206, 226, 255), r=0.03)
    p.rect(0.12, 0.24, 0.88, 0.34, (196, 232, 244, 255))
    p.rect(0.12, 0.7, 0.88, 0.8, (226, 200, 140, 255))
    orect(p, 0.08, 0.8, 0.92, 0.9, (110, 76, 52, 255), r=0.02)
    # a golden arwana
    opoly(p, [(0.3, 0.52), (0.46, 0.42), (0.64, 0.5), (0.46, 0.6)], (236, 180, 60, 255))
    opoly(p, [(0.64, 0.5), (0.76, 0.42), (0.76, 0.58)], (214, 120, 40, 255))
    p.circle(0.38, 0.5, 0.015, INK)
    for x, y, r in ((0.24, 0.4, 0.02), (0.28, 0.32, 0.014)):
        p.circle(x, y, r, CREAM_HI)
    p.line([(0.8, 0.7), (0.78, 0.5), (0.82, 0.38)], (80, 160, 80, 255), 0.03)
    p.save("icon_akuarium")


def medali():
    p = Pad(128)
    for s, col in ((-1, (58, 116, 192, 255)), (1, (214, 72, 56, 255))):
        opoly(p, [(0.5 + s * 0.04, 0.08), (0.5 + s * 0.2, 0.08), (0.5 + s * 0.1, 0.5), (0.5 - s * 0.06, 0.5)], col)
    ocircle(p, 0.5, 0.62, 0.28, (240, 186, 60, 255))
    p.circle(0.5, 0.62, 0.21, (250, 210, 100, 255))
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = 0.15 if i % 2 == 0 else 0.065
        pts.append((0.5 + math.cos(a) * r, 0.63 + math.sin(a) * r))
    p.poly(pts, (214, 140, 30, 255))
    p.save("icon_medali")


def hati():
    p = Pad(128)
    def heart(s, col):
        pts = []
        for i in range(48):
            t = i / 48 * math.tau
            x = 16 * math.sin(t) ** 3
            y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
            pts.append((0.5 + x * s, 0.48 - y * s))
        p.poly(pts, col)
    heart(0.026 + W / 16, INK)
    heart(0.026, (230, 76, 92, 255))
    p.circle(0.36, 0.36, 0.06, (250, 160, 170, 255))
    p.save("icon_hati")


def rumah_up():
    p = Pad(128)
    opoly(p, [(0.1, 0.46), (0.5, 0.12), (0.9, 0.46)], (196, 80, 56, 255))
    orect(p, 0.18, 0.44, 0.82, 0.88, (240, 226, 196, 255), r=0.02)
    orect(p, 0.42, 0.6, 0.58, 0.88, (130, 88, 56, 255), r=0.02)
    for x in (0.24, 0.64):
        orect(p, x, 0.54, x + 0.12, 0.66, (150, 206, 226, 255), r=0.01)
    ocircle(p, 0.78, 0.24, 0.13, (92, 170, 74, 255))
    p.poly([(0.78, 0.14), (0.86, 0.24), (0.81, 0.24), (0.81, 0.33), (0.75, 0.33), (0.75, 0.24), (0.7, 0.24)], CREAM_HI)
    p.save("icon_renovasi")


def panjat():
    p = Pad(128)
    orect(p, 0.46, 0.2, 0.54, 0.94, (170, 120, 80, 255), r=0.02)
    p.ellipse(0.22 - W, 0.12 - W, 0.78 + W, 0.3 + W, INK)
    p.ellipse(0.22, 0.12, 0.78, 0.3, (220, 70, 56, 255))
    p.ellipse(0.3, 0.16, 0.7, 0.26, (240, 228, 210, 255))
    for x, col in ((0.26, (246, 204, 92, 255)), (0.4, (92, 170, 74, 255)), (0.6, (58, 116, 192, 255)), (0.74, (246, 204, 92, 255))):
        orect(p, x - 0.04, 0.3, x + 0.04, 0.42, col, r=0.01)
    for i in range(4):
        y = 0.5 + i * 0.1
        p.line([(0.46, y), (0.54, y + 0.03)], (120, 80, 50, 255), 0.012)
    p.save("icon_panjat")


if __name__ == "__main__":
    for fn in (kopi, kue, hadiah, koran, megafon, bendera, sofa, akuarium, medali, hati, rumah_up, panjat):
        fn()
