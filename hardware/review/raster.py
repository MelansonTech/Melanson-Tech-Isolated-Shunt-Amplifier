# -*- coding: utf-8 -*-
"""Rasters of the board, shared by the geometry solvers.

Everything is drawn on one grid at PITCH mm per pixel, in absolute board
coordinates (the Gerbers of this project are written in absolute coordinates,
checked against the outline: X 18.25..68.25 mm in both).

    from raster import Grid, copper_of
    g = Grid(board)                       # g.inb = inside the outline and not in the slot
    im = copper_of(board, g, layer_byte, nets=None)

Pours are drawn as their first contour filled minus every later contour (the
holes CircuitStudio leaves around pads and vias). Pads on the multi-layer
(byte 74) and vias are drawn on every copper layer.
"""
import math

import numpy as np
from skimage.draw import polygon as _poly, disk as _disk

PITCH = 0.05                     # mm per pixel
MULTI = 74
COPPER = (1, 2, 3, 32)


class Grid(object):
    def __init__(self, board, margin=1.5, pitch=PITCH, cutouts=None):
        xs = [p[0] for p in board.outline]
        ys = [p[1] for p in board.outline]
        self.pitch = pitch
        self.ox = min(xs) - margin
        self.oy = min(ys) - margin
        self.W = int(math.ceil((max(xs) - min(xs) + 2 * margin) / pitch))
        self.H = int(math.ceil((max(ys) - min(ys) + 2 * margin) / pitch))
        self.outline = np.zeros((self.H, self.W), bool)
        fill(self.outline, [board.outline], self)
        self.cut = np.zeros((self.H, self.W), bool)
        for c in (cutouts or []):
            fill(self.cut, [c], self)
        self.inb = self.outline & ~self.cut

    def px(self, x, y):
        """mm -> (row, col) floats."""
        return (y - self.oy) / self.pitch, (x - self.ox) / self.pitch

    def mm(self, r, c):
        return self.ox + c * self.pitch, self.oy + r * self.pitch

    def extent(self):
        """matplotlib imshow extent, origin lower."""
        return [self.ox, self.ox + self.W * self.pitch, self.oy, self.oy + self.H * self.pitch]


def fill(im, contours, g):
    """First contour filled, later contours cleared (holes)."""
    for k, c in enumerate(contours):
        if len(c) < 3:
            continue
        rr, cc = zip(*[g.px(x, y) for x, y in c])
        r, cidx = _poly(np.array(rr), np.array(cc), im.shape)
        if k == 0:
            im[r, cidx] = True
        else:
            im[r, cidx] = False


def disc(im, x, y, d, g):
    r0, c0 = g.px(x, y)
    rr, cc = _disk((r0, c0), max(d / 2 / g.pitch, 0.5), shape=im.shape)
    im[rr, cc] = True


def rect(im, x, y, w, h, g, rot=0.0):
    a = math.radians(rot or 0.0)
    ca, sa = math.cos(a), math.sin(a)
    pts = []
    for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        pts.append((x + dx * ca - dy * sa, y + dx * sa + dy * ca))
    fill(im, [pts], g)


def stroke(im, x1, y1, x2, y2, w, g):
    if w <= 0:
        w = g.pitch
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    if L < 1e-9:
        disc(im, x1, y1, w, g)
        return
    nx, ny = -dy / L * w / 2, dx / L * w / 2
    fill(im, [[(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]], g)
    disc(im, x1, y1, w, g)
    disc(im, x2, y2, w, g)


def pad_shape(im, p, g):
    """A pad: round if shape 1 and square aspect, else a rotated rectangle.
    Rounded-rectangle and octagonal pads are drawn as rectangles (the error
    is the corner, below the pitch for 0805 pads)."""
    if p["shape"] == 1 and abs(p["w"] - p["h"]) < 1e-6:
        disc(im, p["x"], p["y"], p["w"], g)
    elif p["shape"] == 1:
        # oblong: a stroke along the long axis
        w, h = p["w"], p["h"]
        a = math.radians(p.get("rot") or 0.0)
        if w >= h:
            L, d = w - h, h
            dx, dy = math.cos(a) * L / 2, math.sin(a) * L / 2
        else:
            L, d = h - w, w
            dx, dy = -math.sin(a) * L / 2, math.cos(a) * L / 2
        stroke(im, p["x"] - dx, p["y"] - dy, p["x"] + dx, p["y"] + dy, d, g)
    else:
        rect(im, p["x"], p["y"], p["w"], p["h"], g, p.get("rot") or 0.0)


def copper_of(board, g, layer, nets=None, include_netless=True, pours=True, pads=True,
              tracks=True, vias=True):
    """Boolean raster of the copper on one layer byte, optionally only for a
    set of net names (None = every net). Netless pads are included when
    include_netless is True and nets is None."""
    im = np.zeros((g.H, g.W), bool)

    def want(net):
        if nets is None:
            return include_netless or net is not None
        return net in nets

    # Pours FIRST: a pour is drawn as its outer contour minus its clearance
    # holes, and the holes are cleared by overwriting. Drawn after the tracks
    # and pads, those holes erased every track and pad that sits inside a
    # pour clearance - 185 mm2 of copper on the outer layers of this board,
    # which then read as "Gerber only".
    if pours:
        for pr in board.pours:
            if pr["layer"] == layer and want(pr["net"]):
                fill(im, pr["contours"], g)
    if tracks:
        for t in board.tracks:
            if t["layer"] == layer and want(t["net"]):
                stroke(im, t["x1"], t["y1"], t["x2"], t["y2"], t["width"], g)
    if pads:
        for p in board.pads:
            if (p["layer"] == layer or p["layer"] == MULTI) and want(p["net"]):
                pad_shape(im, p, g)
    if vias:
        for v in board.vias:
            if want(v["net"]):
                disc(im, v["x"], v["y"], v["pad_d"], g)
    return im


def label_blobs(mask, g, n=8):
    """The n largest connected blobs of a mask, as (area mm2, bbox mm)."""
    from scipy import ndimage
    lab, k = ndimage.label(mask)
    if k == 0:
        return []
    sizes = ndimage.sum(mask, lab, range(1, k + 1))
    order = np.argsort(sizes)[::-1][:n]
    out = []
    objs = ndimage.find_objects(lab)
    for i in order:
        sl = objs[i]
        y0, x0 = g.mm(sl[0].start, sl[1].start)
        y1, x1 = g.mm(sl[0].stop, sl[1].stop)
        out.append(dict(area_mm2=float(sizes[i] * g.pitch ** 2),
                        bbox=[round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)]))
    return out
