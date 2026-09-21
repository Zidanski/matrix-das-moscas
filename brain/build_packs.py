"""Converte os arquivos brutos dos dois conectomas em pacotes CSR.

FlyWire v783 (femeas): Connectivity_783.parquet de Shiu et al. (ja assinado;
coluna 'Excitatory x Connectivity') + Completeness_783.csv (indice -> root_id)
+ anotacoes flyconnectome v3.1.0 (tipos, lado, NT, soma).

MaleCNS v1.0 (machos): body-annotations + body-neurotransmitters +
connectome-weights (traced-only). Mantem cerebro E cordao nervoso ventral
(decisao F0: feromonio de contato e cancao vivem no VNC). Sinal pela regra de
Shiu aplicada ao consensus_nt do pre-sinaptico.

Pico de memoria < 2 GB (lotes do pyarrow, duas passadas).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.feather as pf
import pyarrow.parquet as pq

from .pack import ConnectomePack, csr_from_stream, nt_sign, SIDE_MAP

RAW = Path("data/raw")

FLYWIRE_FILES = {
    "connectivity": RAW / "flywire/Connectivity_783.parquet",
    "completeness": RAW / "flywire/Completeness_783.csv",
    "annotations": RAW / "flywire/neuron_annotations_v3.1.0.tsv",
}
# v630 = materializacao usada no artigo de Shiu (so para conferencia; root_ids
# diferem de v783, entao as anotacoes v783 cobrem apenas os neuronios estaveis)
FLYWIRE630_FILES = {
    "connectivity": RAW / "flywire/2023_03_23_connectivity_630_final.parquet",
    "completeness": RAW / "flywire/2023_03_23_completeness_630_final.csv",
    "annotations": RAW / "flywire/neuron_annotations_v3.1.0.tsv",
}
MALECNS_FILES = {
    "annotations": RAW / "malecns/body-annotations-male-cns-v1.0-minconf-0.5.feather",
    "nt": RAW / "malecns/body-neurotransmitters-male-cns-v1.0.feather",
    "weights": RAW / "malecns/connectome-weights-male-cns-v1.0-minconf-0.5-traced-only.feather",
}


def raw_available(which: str) -> bool:
    files = FLYWIRE_FILES if which == "flywire" else MALECNS_FILES
    return all(p.exists() for p in files.values())


# ----------------------------------------------------------------------------
# FlyWire
# ----------------------------------------------------------------------------
def _flywire_batches(path: Path, min_syn: int):
    p = pq.ParquetFile(path)
    for rg in range(p.metadata.num_row_groups):
        t = p.read_row_group(rg, columns=["Presynaptic_Index", "Postsynaptic_Index", "Excitatory x Connectivity"])
        pre = t.column(0).to_numpy().astype(np.int64)
        post = t.column(1).to_numpy().astype(np.int64)
        w = t.column(2).to_numpy().astype(np.int64)
        keep = (np.abs(w) >= min_syn) & (w != 0)
        yield pre[keep], post[keep], w[keep]


def build_flywire(name: str = "flywire783", min_syn: int = 1, version: int = 783) -> ConnectomePack:
    files = FLYWIRE_FILES if version == 783 else FLYWIRE630_FILES
    comp = pd.read_csv(files["completeness"])
    comp.columns = ["root_id", "completed"]
    n = len(comp)
    ann = pd.read_csv(FLYWIRE_FILES["annotations"], sep="\t", low_memory=False,
                      usecols=["root_id", "super_class", "cell_class", "cell_sub_class", "cell_type",
                               "hemibrain_type", "supertype", "top_nt", "top_nt_conf", "side", "nerve",
                               "soma_x", "soma_y", "soma_z", "dimorphism", "fru_dsx"])
    ann = ann.drop_duplicates("root_id").set_index("root_id")
    a = ann.reindex(comp["root_id"].to_numpy())
    neurons = pd.DataFrame({
        "idx": np.arange(n, dtype=np.int32),
        "id": comp["root_id"].to_numpy().astype(np.int64),
        "type": a["cell_type"].to_numpy(),
        "hemibrain_type": a["hemibrain_type"].to_numpy(),
        "supertype": a["supertype"].to_numpy(),
        "flywire_type": a["cell_type"].to_numpy(),
        "super_class": a["super_class"].to_numpy(),
        "cell_class": a["cell_class"].to_numpy(),
        "cell_sub_class": a["cell_sub_class"].to_numpy(),
        "side": a["side"].map(SIDE_MAP).fillna("?").to_numpy(),
        "nerve": a["nerve"].to_numpy(),
        "nt": a["top_nt"].to_numpy(),
        "nt_conf": a["top_nt_conf"].to_numpy(),
        "sign": a["top_nt"].map(nt_sign).fillna(0).astype(np.int8).to_numpy(),
        # soma em nm: anotacoes vem em voxels de 4x4x40 nm
        "soma_x": (a["soma_x"] * 4.0).to_numpy(),
        "soma_y": (a["soma_y"] * 4.0).to_numpy(),
        "soma_z": (a["soma_z"] * 40.0).to_numpy(),
        "dimorphism": a["dimorphism"].to_numpy(),
        "fru_dsx": a["fru_dsx"].to_numpy(),
    })
    indptr, indices, weights = csr_from_stream(
        n, _flywire_batches(files["connectivity"], min_syn),
        _flywire_batches(files["connectivity"], min_syn))
    meta = {
        "source": f"FlyWire v{version} (Dorkenwald 2024; Schlegel 2024); arestas assinadas de Shiu et al. 2024 ({files['connectivity'].name})",
        "version": version,
        "sex": "female", "n_neurons": int(n), "n_edges": int(indptr[-1]), "min_syn": min_syn,
        "sign_rule": "sinal pre-computado por Shiu: GABA/Glu -1; ACh/DA/OA/5-HT +1 (voto majoritario por neuronio)",
        "annotations": "flyconnectome/flywire_annotations v3.1.0", "soma_units": "nm",
        "annotated": int(a["cell_type"].notna().sum()),
    }
    return ConnectomePack(name, indptr, indices, weights, neurons, meta)


# ----------------------------------------------------------------------------
# MaleCNS
# ----------------------------------------------------------------------------
def _malecns_batches(path: Path, body_to_idx_sorted: np.ndarray, idx_of_sorted: np.ndarray,
                     sign: np.ndarray, min_syn: int):
    r = pa.ipc.open_file(pa.memory_map(str(path)))
    for b in range(r.num_record_batches):
        t = r.get_batch(b)
        pre_b = t.column("body_pre").to_numpy()
        post_b = t.column("body_post").to_numpy()
        w = t.column("weight").to_numpy().astype(np.int64)
        pi = np.searchsorted(body_to_idx_sorted, pre_b)
        qi = np.searchsorted(body_to_idx_sorted, post_b)
        pi = np.minimum(pi, len(body_to_idx_sorted) - 1)
        qi = np.minimum(qi, len(body_to_idx_sorted) - 1)
        ok = (body_to_idx_sorted[pi] == pre_b) & (body_to_idx_sorted[qi] == post_b)
        pre = idx_of_sorted[pi]
        post = idx_of_sorted[qi]
        s = sign[np.where(ok, pre, 0)]
        keep = ok & (s != 0) & (w >= min_syn)
        yield pre[keep].astype(np.int64), post[keep].astype(np.int64), (w[keep] * s[keep]).astype(np.int64)


def build_malecns(name: str = "malecns10", min_syn: int = 1, brain_only: bool = False) -> ConnectomePack:
    cols = ["bodyId", "status", "superclass", "class", "subclass", "type", "instance", "flywireType",
            "hemibrainType", "supertype", "somaSide", "rootSide", "somaLocation", "dimorphism", "fruDsx",
            "entryNerve"]
    ann = pf.read_table(MALECNS_FILES["annotations"], columns=cols).to_pandas()
    ann = ann[ann["status"] == "Traced"].copy()
    if brain_only:
        keep = ann["superclass"].fillna("").str.match(r"^(cb_|ol_|visual_|descending_neuron)")
        ann = ann[keep].copy()
    ann = ann.sort_values("bodyId").reset_index(drop=True)
    n = len(ann)
    nt = pf.read_table(MALECNS_FILES["nt"], columns=["body", "consensus_nt", "predicted_nt_confidence"]).to_pandas()
    nt = nt.drop_duplicates("body").set_index("body").reindex(ann["bodyId"].to_numpy())
    # lado: somaSide, senao rootSide, senao sufixo _L/_R da instancia
    side = ann["somaSide"].copy()
    side = side.where(side.notna(), ann["rootSide"])
    inst_side = ann["instance"].astype("string").str.extract(r"_([LRM])$")[0]
    side = side.where(side.notna(), inst_side)
    side = side.map(SIDE_MAP).fillna("?")
    soma = ann["somaLocation"]
    soma_xyz = np.full((n, 3), np.nan)
    has = soma.notna().to_numpy()
    if has.any():
        soma_xyz[has] = np.stack(soma[has].to_numpy()).astype(float)
    neurons = pd.DataFrame({
        "idx": np.arange(n, dtype=np.int32),
        "id": ann["bodyId"].to_numpy().astype(np.int64),
        "type": ann["type"].to_numpy(),
        "hemibrain_type": ann["hemibrainType"].to_numpy(),
        "supertype": ann["supertype"].to_numpy(),
        "flywire_type": ann["flywireType"].to_numpy(),
        "super_class": ann["superclass"].to_numpy(),
        "cell_class": ann["class"].to_numpy(),
        "cell_sub_class": ann["subclass"].to_numpy(),
        "side": side.to_numpy(),
        "nerve": ann["entryNerve"].to_numpy(),
        "nt": nt["consensus_nt"].to_numpy(),
        "nt_conf": nt["predicted_nt_confidence"].to_numpy(),
        "sign": nt["consensus_nt"].map(nt_sign).fillna(0).astype(np.int8).to_numpy(),
        # somaLocation em voxels de 8 nm (resolucao do volume MaleCNS) -> nm
        "soma_x": soma_xyz[:, 0] * 8.0, "soma_y": soma_xyz[:, 1] * 8.0, "soma_z": soma_xyz[:, 2] * 8.0,
        "dimorphism": ann["dimorphism"].to_numpy(),
        "fru_dsx": ann["fruDsx"].to_numpy(),
    })
    bodies = ann["bodyId"].to_numpy().astype(np.int64)  # ja ordenado
    idx_of_sorted = np.arange(n, dtype=np.int64)
    sign = neurons["sign"].to_numpy().astype(np.int64)
    mk = lambda: _malecns_batches(MALECNS_FILES["weights"], bodies, idx_of_sorted, sign, min_syn)  # noqa: E731
    indptr, indices, weights = csr_from_stream(n, mk(), mk())
    meta = {
        "source": "MaleCNS v1.0 (Berg et al. 2026, Cell; CC-BY 4.0), connectome-weights traced-only, minconf 0.5",
        "sex": "male", "n_neurons": int(n), "n_edges": int(indptr[-1]), "min_syn": min_syn,
        "vnc_included": not brain_only,
        "sign_rule": "regra de Shiu aplicada ao consensus_nt: ACh/DA/OA/5-HT +1; GABA/Glu/histamina -1; unclear 0 (sem saidas)",
        "constants_caveat": "constantes LIF de Shiu foram ajustadas ao FlyWire e sao reutilizadas aqui sem reajuste (premissa)",
        "soma_units": "nm (somaLocation x 8 nm/voxel; resolucao nao verificada na documentacao oficial)",
        "annotated": int(ann["type"].notna().sum()),
        "n_sign0": int((sign == 0).sum()),
    }
    return ConnectomePack(name, indptr, indices, weights, neurons, meta)
