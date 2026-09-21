"""Testes do motor event-driven: analiticos e equivalencia com Brian2."""

import numpy as np
import pytest

from brain.engine import LIFEngine
from brain.pack import ConnectomePack
from brain.params import SHIU, LIFParams

KICK = SHIU.poisson_weight_mv  # 68.75 mV: um evento Poisson dispara o neuronio


def tiny(n=3, edges=()):
    pre = np.array([e[0] for e in edges], dtype=np.int64)
    post = np.array([e[1] for e in edges], dtype=np.int64)
    w = np.array([e[2] for e in edges], dtype=np.int64)
    return ConnectomePack.from_edges("tiny", n, pre, post, w)


def test_params_match_shiu():
    p = SHIU
    assert (p.v_rest_mv, p.v_reset_mv, p.v_th_mv) == (-52.0, -52.0, -45.0)
    assert (p.tau_m_ms, p.tau_syn_ms, p.t_refrac_ms, p.t_delay_ms) == (20.0, 5.0, 2.2, 1.8)
    assert p.w_syn_mv == 0.275 and p.dt_ms == 0.1
    assert p.refrac_steps == 22 and p.delay_steps == 18
    assert p.poisson_weight_mv == pytest.approx(68.75)


def test_silent_without_input():
    eng = LIFEngine(tiny(), eps_mv=0.0)
    rec = eng.run(100.0)
    assert len(rec.idx) == 0 and eng.n_active == 0


def test_kick_spikes_next_step_and_refractory_spacing():
    eng = LIFEngine(tiny(), eps_mv=0.0)
    steps = np.arange(0, 100)  # kick a cada passo no neuronio 0
    eng.set_external(steps, np.zeros_like(steps), np.full(len(steps), KICK))
    rec = eng.run(20.0)
    s = rec.of(0)
    assert s[0] == 1                       # kick no passo 0 -> disparo no passo 1
    # kicks durante o refratario sao descartados (semantica do Brian2); o primeiro
    # kick aceito e no passo n+22 e o disparo vem no passo seguinte: intervalo 23
    assert np.all(np.diff(s) == SHIU.refrac_steps + 1)


def test_input_during_refractory_is_discarded():
    eng = LIFEngine(tiny(2, [(0, 1, 200)]), eps_mv=0.0)
    # neuronio 1 dispara no passo 1 (kick em 0); neuronio 0 dispara no passo 1 tambem e
    # sua entrega chega em 19, dentro do refratario de 1 (ate 22): deve ser descartada
    eng.set_external([0, 0], [0, 1], [KICK, KICK])
    eng.run(3.0)  # passos 0..29
    assert eng.g[1] == 0.0 and eng.v[1] == SHIU.v_rest_mv
    # controle: com a entrega apos o refratario, g muda
    eng2 = LIFEngine(tiny(2, [(0, 1, 200)]), eps_mv=0.0)
    eng2.set_external([0, 5], [1, 0], [KICK, KICK])  # 0 dispara em 6, entrega em 24 > 22
    eng2.run(3.0)
    assert eng2.g[1] > 0.0


def test_exact_integration_matches_closed_form():
    # um EPSP de g0 sem disparo: v(t) segue a solucao fechada
    p = SHIU
    eng = LIFEngine(tiny(2, [(0, 1, 30)]), eps_mv=0.0)
    eng.set_external([0], [0], [KICK])
    eng.run(0.2)  # neuronio 0 dispara no passo 1
    # entrega em passo 1 + 18 = 19; v de 1 e atualizado a partir do passo 20
    eng.run(1.9)  # passos 2..20: entrega no 19, primeira integracao de g no 20
    g0 = 30 * p.w_syn_mv
    assert eng.g[1] == pytest.approx(g0 * np.exp(-p.dt_ms / p.tau_syn_ms))
    k = 50
    eng.run(k * p.dt_ms)
    t = (k + 1) * p.dt_ms
    ts, tm = p.tau_syn_ms, p.tau_m_ms
    v_expected = p.v_rest_mv + g0 * ts / (tm - ts) * (np.exp(-t / tm) - np.exp(-t / ts))
    assert eng.v[1] == pytest.approx(v_expected, abs=1e-9)


def test_inhibition_is_negative():
    eng = LIFEngine(tiny(2, [(0, 1, -40)]), eps_mv=0.0)
    eng.set_external([0], [0], [KICK])
    eng.run(5.0)
    assert eng.g[1] < 0 and eng.v[1] < SHIU.v_rest_mv


def test_gain_scales_epsp():
    gain = np.array([1.0, 2.0])
    e1 = LIFEngine(tiny(2, [(0, 1, 10)]), eps_mv=0.0)
    e2 = LIFEngine(tiny(2, [(0, 1, 10)]), eps_mv=0.0, gain=gain)
    for e in (e1, e2):
        e.set_external([0], [0], [KICK])
        e.run(2.0)
    assert e2.g[1] == pytest.approx(2 * e1.g[1])


def test_state_persists_across_chunks():
    eng = LIFEngine(tiny(2, [(0, 1, 200)]), eps_mv=0.0, chunk_steps=7)
    eng.set_external([0], [0], [KICK])
    a = eng.run(30.0)
    eng2 = LIFEngine(tiny(2, [(0, 1, 200)]), eps_mv=0.0, chunk_steps=1000)
    eng2.set_external([0], [0], [KICK])
    b = eng2.run(30.0)
    assert np.array_equal(a.idx, b.idx) and np.array_equal(a.step, b.step)
    assert 1 in a.idx  # 200 sinapses bastam para o pos-sinaptico disparar


def test_deactivation_with_eps_keeps_spikes():
    eng_a = LIFEngine(tiny(2, [(0, 1, 200)]), eps_mv=0.0)
    eng_b = LIFEngine(tiny(2, [(0, 1, 200)]), eps_mv=1e-4)
    for e in (eng_a, eng_b):
        e.set_external([0, 300, 600], [0, 0, 0], [KICK] * 3)
    ra, rb = eng_a.run(100.0), eng_b.run(100.0)
    assert np.array_equal(ra.step, rb.step)
    assert eng_b.n_active == 0  # tudo decaiu e foi desativado


@pytest.mark.slow
def test_matches_brian2_spike_for_spike():
    """Rede pequena com pesos mistos, kicks deterministicos: trens de disparo identicos."""
    from brain.brian2_ref import run_brian2
    rng = np.random.default_rng(1)
    n = 12
    pre = rng.integers(0, n, 60)
    post = rng.integers(0, n, 60)
    keep = pre != post
    pre, post = pre[keep], post[keep]
    w = rng.integers(-150, 260, len(pre))
    edges = list(zip(pre, post, w))
    pack = tiny(n, edges)
    ext_steps = np.sort(rng.integers(0, 4000, 80))
    ext_idx = rng.integers(0, 4, 80)
    ext_dv = np.full(80, KICK)
    eng = LIFEngine(pack, eps_mv=0.0)
    eng.set_external(ext_steps, ext_idx, ext_dv)
    rec = eng.run(500.0)
    bi, bs = run_brian2(n, pre, post, w, 500.0, ext_steps=ext_steps, ext_idx=ext_idx, ext_dv_mv=ext_dv)
    ours = sorted(zip(rec.step.tolist(), rec.idx.tolist()))
    ref = sorted(zip(bs.tolist(), bi.tolist()))
    assert len(ours) > 20, "a rede de teste deveria disparar bastante"
    assert ours == ref


def test_poisson_targets_have_no_refractory():
    """model.py de Shiu: alvos de Poisson com rfc = 0 -> taxa ~ Poisson (99 Hz), ISI minimo 0,2 ms."""
    eng = LIFEngine(tiny(2), eps_mv=0.0, seed=3)
    eng.set_poisson([0], 100.0)
    rec = eng.run(20000.0)
    s = rec.of(0)
    rate = len(s) / 20.0
    assert 92 < rate < 106, rate
    assert np.diff(s).min() == 2  # kick no passo seguinte ao disparo e perdido pelo reset -> ISI minimo 2 passos
    eng2 = LIFEngine(tiny(2), eps_mv=0.0, seed=3)
    eng2.set_poisson([0], 100.0, no_refractory=False)
    rate2 = len(eng2.run(20000.0).of(0)) / 20.0
    assert 76 < rate2 < 88, rate2  # com refratario: r/(1 + r*t_rfc) ~ 82 Hz
