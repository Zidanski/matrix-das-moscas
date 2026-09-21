"""Populacoes por rotulo de tipo celular, por conectoma e lado.

Todo indice vem das tabelas de anotacao guardadas no pacote (neurons.parquet).
Se um rotulo nao existir no conectoma, a populacao fica vazia e isso e
reportado, nunca inventado. Lados: 'L' e 'R' na convencao de cada conectoma.
"""

from __future__ import annotations

import numpy as np

from .pack import ConnectomePack

# Rotulos por conectoma. Chave = nome funcional; valor = (coluna, rotulos, prefixo?)
FLYWIRE_LABELS = {
    "sugar": ("type", ["LB3", "LB2d"], False),          # cell_sub_class sugar/water (agua indistinguivel)
    "water": ("type", ["LB3"], False),                  # lacuna: FlyWire nao separa agua de acucar
    "bitter": ("cell_sub_class", ["bitter"], False),
    "leg_grn": ("type", ["SA_VTV_"], True),
    "orn_dm1": ("type", ["ORN_DM1"], False),
    "orn_v": ("type", ["ORN_V"], False),
    "orn_da2": ("type", ["ORN_DA2"], False),
    "orn_da1": ("type", ["ORN_DA1"], False),
    "orn_dl3": ("type", ["ORN_DL3"], False),
    "jo_a": ("type", ["JO-A"], True),
    "jo_b": ("type", ["JO-B"], True),
    "lc4": ("type", ["LC4"], False),
    "lplc2": ("type", ["LPLC2"], False),
    "lc11": ("type", ["LC11"], False),
    "MN9": ("type", ["CB0701"], False),
    "gf": ("type", ["DNp01"], False),
    "dnp09": ("type", ["DNp09"], False),
    "odn1": ("type", ["DNg97"], False),                 # rotulo comunitario "P9-oDN1" (candidato)
    "dna01": ("type", ["DNa01"], False),
    "dna02": ("type", ["DNa02"], False),
    "mdn": ("type", ["MDN"], False),
    "adn": ("type", ["DNge078"], False),                # "putative aDN 2" (candidato)
    "pc1": ("type", ["pC1a", "pC1b", "pC1c", "pC1d", "pC1e"], False),
    "aipg": ("hemibrain_type", ["aIPg1", "aIPg2", "aIPg3", "aIPg4"], False),
    "vpodn": ("hemibrain_type", ["vpoDN"], False),
    "dnp13": ("type", ["DNp13"], False),
    "asp22": ("type", ["aSP22"], False),
    "da1_lpn": ("type", ["DA1_lPN"], False),
}

MALECNS_LABELS = {
    "sugar": ("type", ["LB3b", "LB3c", "LB3"], False),   # Gr64f (Tastekin 2025 via Kisame76); LB3 sem sufixo (n=1) incluido; LB3d nao resolvido
    "water": ("type", ["LB3a"], False),
    "bitter": ("flywire_type", ["LB1a,LB1d", "LB1b", "LB1c", "LB1e"], False),
    "leg_grn": ("type", ["LgLG"], True),
    "ppk23": ("type", ["LgLG5", "LgLG6", "LgLG7", "LgLG8"], False),
    "orn_dm1": ("type", ["ORN_DM1"], False),
    "orn_v": ("type", ["ORN_V"], False),
    "orn_da2": ("type", ["ORN_DA2"], False),
    "orn_da1": ("type", ["ORN_DA1"], False),
    "orn_dl3": ("type", ["ORN_DL3"], False),
    "jo_a": ("type", ["JO-A"], True),
    "jo_b": ("type", ["JO-B"], True),
    "lc4": ("type", ["LC4"], False),
    "lplc2": ("type", ["LPLC2"], False),
    "lc11": ("type", ["LC11"], False),
    "MN9": ("type", ["MN9"], False),
    "gf": ("type", ["DNp01"], False),
    "dnp09": ("type", ["DNp09"], False),
    "odn1": ("type", ["DNg97"], False),
    "dna01": ("type", ["DNa01"], False),
    "dna02": ("type", ["DNa02"], False),
    "mdn": ("type", ["MDN"], False),
    "adn": ("type", ["DNge078"], False),
    "p1": ("type", ["pC1_"], True),
    "pc1": ("type", ["pC1x_b", "pC1x_c"], False),
    "aipg": ("type", ["aIPg"], True),
    "tk": ("type", ["AVLP727m"], False),
    "pip10": ("type", ["pIP10"], False),
    "vpr6": ("type", ["vPR6"], False),
    "dnp13": ("type", ["DNp13"], False),
    "asp22": ("type", ["aSP22"], False),
    "da1_lpn": ("type", ["DA1_lPN"], False),
}


# Quais populacoes sao entradas sensoriais e quais sao leituras motoras/sociais
INPUTS = ["sugar", "water", "bitter", "leg_grn", "ppk23", "orn_dm1", "orn_v", "orn_da2", "orn_da1", "orn_dl3",
          "jo_a", "jo_b", "lc4", "lplc2", "lc11"]
OUTPUTS = ["MN9", "gf", "dnp09", "odn1", "dna01", "dna02", "mdn", "adn", "pc1", "p1", "aipg", "tk", "pip10",
           "vpr6", "vpodn", "dnp13", "asp22", "da1_lpn"]


def label_table(pack: ConnectomePack) -> dict:
    return FLYWIRE_LABELS if pack.meta.get("sex") == "female" else MALECNS_LABELS


def populations(pack: ConnectomePack) -> dict[str, np.ndarray]:
    """Dicionario nome -> indices; para cada nome, tambem nome_L e nome_R."""
    out = {}
    for name, (col, labels, prefix) in label_table(pack).items():
        out[name] = pack.select(labels, None, column=col, startswith=prefix)
        for side in ("L", "R"):
            out[f"{name}_{side}"] = pack.select(labels, side, column=col, startswith=prefix)
    return out


def population_report(pack: ConnectomePack) -> "pd.DataFrame":  # noqa: F821
    import pandas as pd
    pops = populations(pack)
    rows = []
    for name in label_table(pack):
        rows.append({"population": name, "n": len(pops[name]), "n_L": len(pops[name + "_L"]),
                     "n_R": len(pops[name + "_R"]),
                     "n_unsided": len(pops[name]) - len(pops[name + "_L"]) - len(pops[name + "_R"])})
    return pd.DataFrame(rows)
