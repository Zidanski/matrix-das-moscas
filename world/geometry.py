"""Terreno, objetos e utilidades geometricas do mundo (cm)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

WORLD_PATH = Path(__file__).with_name("world.yaml")


def load_world(path: Path | str | None = None) -> dict:
    with open(Path(path) if path else WORLD_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


class Terrain:
    """Altura = soma de gaussianas (colinas de cor chapada)."""

    def __init__(self, hills: list, radius: float):
        self.hills = [tuple(map(float, h)) for h in hills]
        self.radius = float(radius)

    def height(self, x: float, y: float) -> float:
        z = 0.0
        for hx, hy, s, a in self.hills:
            z += a * math.exp(-((x - hx) ** 2 + (y - hy) ** 2) / (2 * s * s))
        return z

    def heights(self, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        z = np.zeros_like(xs, dtype=float)
        for hx, hy, s, a in self.hills:
            z += a * np.exp(-((xs - hx) ** 2 + (ys - hy) ** 2) / (2 * s * s))
        return z


@dataclass
class Sphere:
    name: str
    x: float
    y: float
    r: float
    surface: str        # sugar | bitter | none
    mass: float
    vx: float = 0.0
    vy: float = 0.0
    pushes: int = 0


@dataclass
class Cube:
    name: str
    x: float
    y: float
    size: float
    hollow: bool = False

    @property
    def half(self) -> float:
        return self.size / 2


@dataclass
class Prism:
    name: str
    x: float
    y: float
    size: float
    odor: str           # co2 | food | geosmin | none
    strength: float = 1.0
    sigma_cm: float = 8.0


@dataclass
class Patch:
    name: str
    x: float
    y: float
    r: float
    kind: str           # sugar | bitter | water | geosmin | food
    odor_sigma_cm: float = 6.0


@dataclass
class Playground:
    name: str
    x: float
    y: float
    r: float
    kind: str           # cards | roulette


@dataclass
class Water:
    name: str
    x: float
    y: float
    r: float


@dataclass
class Objects:
    spheres: list = field(default_factory=list)
    cubes: list = field(default_factory=list)
    prisms: list = field(default_factory=list)
    patches: list = field(default_factory=list)
    water: list = field(default_factory=list)
    playgrounds: list = field(default_factory=list)

    @classmethod
    def from_config(cls, cfg: dict) -> "Objects":
        o = cfg["objects"]
        return cls(
            spheres=[Sphere(**s) for s in o.get("spheres", [])],
            cubes=[Cube(**c) for c in o.get("cubes", [])],
            prisms=[Prism(**p) for p in o.get("prisms", [])],
            patches=[Patch(**p) for p in o.get("patches", [])],
            water=[Water(**w) for w in o.get("water", [])],
            playgrounds=[Playground(**p) for p in o.get("playgrounds", [])],
        )

    def odor_sources(self) -> list[tuple[str, float, float, float, float]]:
        """(tipo, x, y, forca, sigma) de tudo que cheira."""
        out = []
        for p in self.prisms:
            if p.odor and p.odor != "none":
                out.append((p.odor, p.x, p.y, p.strength, p.sigma_cm))
        for p in self.patches:
            if p.kind in ("sugar", "food"):
                out.append(("food", p.x, p.y, 1.0, p.odor_sigma_cm))
            elif p.kind == "geosmin":
                out.append(("geosmin", p.x, p.y, 1.0, p.odor_sigma_cm))
        return out


def wrap_angle(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


def bearing(from_x: float, from_y: float, heading: float, to_x: float, to_y: float) -> float:
    """Angulo do alvo relativo a direcao da mosca; positivo = a esquerda."""
    return wrap_angle(math.atan2(to_y - from_y, to_x - from_x) - heading)


def sides_from_bearing(b: float, sharpness: float = 1.0) -> tuple[float, float]:
    s = max(-1.0, min(1.0, math.sin(b) * sharpness))
    return 0.5 + 0.5 * s, 0.5 - 0.5 * s
