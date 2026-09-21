"""Carrega interface/config.yaml (o UNICO lugar com ganhos mundo <-> cerebro)."""

from __future__ import annotations

from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).with_name("config.yaml")


class Config(dict):
    """dict com acesso por atributo em profundidade 1 (cfg.sensory, cfg.motor...)."""

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as e:
            raise AttributeError(k) from e


def load_config(path: Path | str | None = None) -> Config:
    p = Path(path) if path else CONFIG_PATH
    with open(p, encoding="utf-8") as f:
        return Config(yaml.safe_load(f))
