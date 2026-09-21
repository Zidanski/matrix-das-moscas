"""Testes do formato de pacote, do CSR em fluxo e do subcircuito reduzido."""

import numpy as np
import pandas as pd
import pytest

from brain.pack import ConnectomePack, csr_from_stream, nt_sign
from brain.reduce import reduce_pack, transpose_csr


def test_nt_sign_rule():
    assert nt_sign("acetylcholine") == 1 and nt_sign("dopamine") == 1
    assert nt_sign("gaba") == -1 and nt_sign("glutamate") == -1 and nt_sign("histamine") == -1
    assert nt_sign("unclear") == 0 and nt_sign(None) == 0 and nt_sign(float("nan")) == 0


def test_csr_from_stream_matches_from_edges():
    rng = np.random.default_rng(0)
    n = 50
    pre = rng.integers(0, n, 400); post = rng.integers(0, n, 400); w = rng.integers(-20, 30, 400)
    w[w == 0] = 1
    ref = ConnectomePack.from_edges("ref", n, pre, post, w)
    cuts = [0, 120, 250, 400]
    batches = lambda: ((pre[a:b], post[a:b], w[a:b]) for a, b in zip(cuts[:-1], cuts[1:]))  # noqa: E731
    indptr, indices, weights = csr_from_stream(n, batches(), batches())
    assert np.array_equal(indptr, ref.indptr)
    # mesma multiconjunto de (post, w) por linha
    for i in range(n):
        a = sorted(zip(indices[indptr[i]:indptr[i+1]].tolist(), weights[indptr[i]:indptr[i+1]].tolist()))
        b = sorted(zip(ref.indices[ref.indptr[i]:ref.indptr[i+1]].tolist(), ref.weights[ref.indptr[i]:ref.indptr[i+1]].tolist()))
        assert a == b


def test_save_load_roundtrip(tmp_path):
    p = ConnectomePack.from_edges("rt", 4, [0, 1, 2], [1, 2, 3], [5, -3, 7], meta={"sex": "female"})
    p.neurons["type"] = ["A", "B", "B", "C"]; p.neurons["side"] = ["L", "R", "L", "R"]
    p.save(tmp_path)
    q = ConnectomePack.load("rt", tmp_path)
    assert q.n == 4 and q.n_edges == 3 and q.meta["sex"] == "female"
    assert np.array_equal(q.indices, p.indices) and np.array_equal(q.weights, p.weights)
    assert q.select("B").tolist() == [1, 2] and q.select("B", side="R").tolist() == [1]
    assert q.select(["A", "C"]).tolist() == [0, 3]


def test_transpose_and_reduce():
    # cadeia 0->1->2->3->4 mais um ramo isolado 5->6
    p = ConnectomePack.from_edges("chain", 7, [0, 1, 2, 3, 5], [1, 2, 3, 4, 6], [10, 10, 10, 10, 10])
    t_indptr, t_indices = transpose_csr(np.asarray(p.indptr), np.asarray(p.indices), 7)
    assert t_indices[t_indptr[2]:t_indptr[3]].tolist() == [1]
    sub = reduce_pack(p, inputs=np.array([0]), outputs=np.array([4]), k=4)
    assert sub.neurons["idx_full"].tolist() == [0, 1, 2, 3, 4]
    assert sub.n_edges == 4
    sub2 = reduce_pack(p, inputs=np.array([0]), outputs=np.array([4]), k=3)
    # com k=3 o caminho de 4 saltos nao cabe: so entradas e saidas sobrevivem
    assert sub2.neurons["idx_full"].tolist() == [0, 4] and sub2.n_edges == 0


@pytest.mark.data
@pytest.mark.parametrize("name,sex,n_expected", [("flywire783", "female", 138639), ("malecns10", "male", 165122)])
def test_real_packs(name, sex, n_expected):
    from pathlib import Path
    from brain.types import populations
    if not (Path("data/packs") / name / "meta.json").exists():
        pytest.skip("pacote nao construido")
    p = ConnectomePack.load(name)
    assert p.n == n_expected and p.meta["sex"] == sex
    assert p.indptr[0] == 0 and p.indptr[-1] == len(p.indices) == len(p.weights)
    assert p.indices.max() < p.n
    pops = populations(p)
    for key in ["sugar_R", "bitter_R", "MN9_L", "MN9_R", "gf_L", "gf_R", "dna01_L", "dna02_R", "orn_da1", "lc4_L"]:
        assert len(pops[key]) > 0, key
    assert len(pops["MN9_L"]) == 1 and len(pops["MN9_R"]) == 1
    if sex == "male":
        assert len(pops["p1"]) > 50 and len(pops["ppk23"]) > 0 and len(pops["vpr6"]) > 0
    else:
        assert len(pops["pc1"]) == 10 and len(pops["vpodn"]) == 2


def test_shuffle_preserves_degrees_and_row_weights():
    from brain.shuffle import shuffled_pack
    rng = np.random.default_rng(5)
    n = 200
    pre = rng.integers(0, n, 5000); post = rng.integers(0, n, 5000); w = rng.integers(-30, 40, 5000); w[w == 0] = 1
    p = ConnectomePack.from_edges("base", n, pre, post, w, meta={"sex": "female"})
    q = shuffled_pack(p, seed=1)
    assert np.array_equal(q.indptr, p.indptr)                       # grau de saida
    assert np.array_equal(np.bincount(q.indices, minlength=n), np.bincount(p.indices, minlength=n))  # grau de entrada
    assert np.array_equal(q.weights, p.weights)                     # pesos ficam na linha
    assert not np.array_equal(q.indices, p.indices)                 # mas os alvos mudaram
    assert q.meta["control_shuffled"] is True
