"""Referencia em Brian2: o modelo de Shiu et al. 2024 tal como em model.py.

Usado so para validar o motor event-driven (testes e docs/F1). Reimplementado
a partir da leitura do model.py (MIT); as equacoes sao as publicadas.
Alvo numpy (sem compilador C no Windows): lento, mas exato.
"""

from __future__ import annotations

import numpy as np

from .params import LIFParams, SHIU


def run_brian2(n: int, pre: np.ndarray, post: np.ndarray, w_count: np.ndarray, t_run_ms: float,
               params: LIFParams = SHIU, poisson_idx=None, poisson_rate_hz: float = 0.0,
               ext_steps=None, ext_idx=None, ext_dv_mv=None, seed: int = 0, gain: np.ndarray | None = None):
    """Roda o LIF de Shiu no Brian2 e devolve (idx, step) dos disparos.

    pre/post/w_count: lista de arestas (contagem de sinapses com sinal).
    poisson_idx: neuronios com PoissonInput direto em v (peso w_syn*f_poi).
    ext_*: eventos deterministicos via SpikeGeneratorGroup (kick em v).
    """
    import brian2 as b2
    b2.prefs.codegen.target = "numpy"
    b2.start_scope()
    b2.seed(seed)
    b2.defaultclock.dt = params.dt_ms * b2.ms
    eqs = """
    dv/dt = (v_0 - v + g) / t_mbr : volt (unless refractory)
    dg/dt = -g / tau               : volt (unless refractory)
    rfc                            : second
    """
    ns = dict(v_0=params.v_rest_mv * b2.mV, t_mbr=params.tau_m_ms * b2.ms, tau=params.tau_syn_ms * b2.ms,
              v_th=params.v_th_mv * b2.mV, v_rst=params.v_reset_mv * b2.mV)
    neu = b2.NeuronGroup(n, eqs, threshold="v > v_th", reset="v = v_rst; g = 0 * mV",
                         refractory="rfc", method="linear", namespace=ns, name="neu")
    neu.v = params.v_rest_mv * b2.mV
    neu.g = 0 * b2.mV
    neu.rfc = params.t_refrac_ms * b2.ms
    objs = [neu]
    if len(pre):
        syn = b2.Synapses(neu, neu, "w : volt", on_pre="g += w", delay=params.t_delay_ms * b2.ms, name="syn")
        syn.connect(i=np.asarray(pre, int), j=np.asarray(post, int))
        gj = np.ones(n) if gain is None else np.asarray(gain, float)
        syn.w = np.asarray(w_count, float) * params.w_syn_mv * gj[np.asarray(post, int)] * b2.mV
        objs.append(syn)
    if poisson_idx is not None and len(poisson_idx):
        idx = np.asarray(poisson_idx, int)
        # Brian2 exige subgrupo contiguo; para conjuntos arbitrarios usamos PoissonGroup + Synapses sem atraso
        pg = b2.PoissonGroup(len(idx), rates=poisson_rate_hz * b2.Hz, name="pg")
        ps = b2.Synapses(pg, neu, on_pre="v += w_poi", namespace={"w_poi": params.poisson_weight_mv * b2.mV}, name="ps")
        ps.connect(i=np.arange(len(idx)), j=idx)
        neu.rfc[idx] = 0 * b2.ms  # como em model.py: alvos de Poisson sem refratario
        objs += [pg, ps]
    if ext_steps is not None and len(ext_steps):
        ext_steps = np.asarray(ext_steps, int)
        ext_idx = np.asarray(ext_idx, int)
        ext_dv = np.asarray(ext_dv_mv, float)
        gen = b2.SpikeGeneratorGroup(len(ext_steps), np.arange(len(ext_steps)), ext_steps * params.dt_ms * b2.ms, name="gen")
        es = b2.Synapses(gen, neu, "wk : volt", on_pre="v += wk", name="es")
        es.connect(i=np.arange(len(ext_steps)), j=ext_idx)
        es.wk = ext_dv * b2.mV
        objs += [gen, es]
    mon = b2.SpikeMonitor(neu, name="mon")
    objs.append(mon)
    net = b2.Network(*objs)
    net.run(t_run_ms * b2.ms)
    idx = np.asarray(mon.i, dtype=np.int32)
    steps = np.rint(np.asarray(mon.t / b2.ms) / params.dt_ms).astype(np.int64)
    return idx, steps
