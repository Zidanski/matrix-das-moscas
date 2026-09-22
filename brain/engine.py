"""Motor LIF event-driven (CPU, Numba) para um cerebro inteiro.

Reimplementacao do modelo de Shiu et al. 2024 (Brian2) com as mesmas equacoes:
    dv/dt = (v0 - v + g)/tau_m      (congelado no refratario)
    dg/dt = -g/tau_s                (congelado no refratario)
    limiar v > v_th ; reset v = v_rst, g = 0 ; refratario t_rfc ; atraso t_dly
    on_pre: g += w  (w = contagem de sinapses com sinal * w_syn * ganho[pos])
    entrada Poisson: v += w_syn * f_poi por evento (direto em v, como no original)

Ordem por passo (igual ao escalonador do Brian2: groups -> thresholds ->
synapses -> resets):
    1. integra so os neuronios ATIVOS (v != v0 ou g != 0 ou refratarios),
       com a solucao exata do sistema linear (equivale ao metodo 'linear');
       testa limiar.
    2. empurra os disparos para o anel de atraso (D passos) e grava.
    3. entrega os disparos que venceram o atraso: percorre a linha CSR do
       pre-sinaptico e soma em g dos alvos (ativando-os). Poisson e eventos
       externos tambem entram aqui.
    4. reset dos que dispararam neste passo.
Nunca ha multiplicacao esparsa por passo: o custo escala com a atividade.

Detalhe fiel ao Brian2 (verificado experimentalmente, brian2 2.9, e no codigo
neurongroup.py: set_conditional_write): variaveis '(unless refractory)' so
aceitam escrita quando not_refractory. Logo, entrada sinaptica, Poisson ou
externa que chega a um neuronio REFRATARIO e descartada, nao acumulada.
Excecao (tambem do model.py original): alvos de Poisson tem refratario 0, logo
disparam ~ a taxa do Poisson; os demais neuronios seguem t_rfc = 2,2 ms.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numba import njit

from .params import LIFParams, SHIU
from .pack import ConnectomePack


@njit(cache=True)
def _seed(seed):
    np.random.seed(seed)


@njit(cache=True, nogil=True)
def _run_chunk(n_steps, step0,
               v, g, rfc_end, active, act_list, n_act_arr,
               ring, ring_n,
               indptr, indices, weights, gain, pre_gain, w_syn,
               poi_idx, poi_p, poi_w,
               ext_step, ext_idx, ext_w, ext_ptr_arr,
               out_idx, out_step, out_n_arr, counts,
               v0, vrst, vth, rfc_steps, D, eps, e_m, e_s, coef):
    n_act = n_act_arr[0]
    # Lista de ativos ordenada por indice: acesso sequencial a v/g/rfc_end (cache).
    # Nao muda resultado nenhum: cada neuronio e atualizado de forma independente
    # dentro do passo e a entrega dos disparos segue a ordem do anel. Medido:
    # 1,4-2x mais rapido com contagens de disparo identicas (docs/F6_ao_vivo.md).
    act_list[:n_act] = np.sort(act_list[:n_act])
    out_n = out_n_arr[0]
    ext_ptr = ext_ptr_arr[0]
    nslots = D + 1
    spikers = np.empty(v.shape[0], np.int32)
    for s in range(n_steps):
        step = step0 + s
        # 1. integracao dos ativos + limiar
        wr = 0
        n_spk = 0
        for k in range(n_act):
            i = act_list[k]
            if step < rfc_end[i]:
                act_list[wr] = i
                wr += 1
                continue
            vi = v[i]
            gi = g[i]
            vi = v0 + (vi - v0) * e_m + gi * coef
            gi = gi * e_s
            if vi > vth:
                spikers[n_spk] = i
                n_spk += 1
                v[i] = vi
                g[i] = gi
                act_list[wr] = i
                wr += 1
            elif abs(vi - v0) <= eps and abs(gi) <= eps:
                v[i] = v0
                g[i] = 0.0
                active[i] = 0
            else:
                v[i] = vi
                g[i] = gi
                act_list[wr] = i
                wr += 1
        n_act = wr
        # 2. disparos -> anel (entregues em step + D) e gravacao
        slot = (step + D) % nslots
        base = ring_n[slot]
        for k in range(n_spk):
            i = spikers[k]
            ring[slot, base + k] = i
            out_idx[out_n] = i
            out_step[out_n] = step
            out_n += 1
            counts[i] += 1
        ring_n[slot] = base + n_spk
        # 3. entrega dos disparos que venceram o atraso
        slot = step % nslots
        for k in range(ring_n[slot]):
            i = ring[slot, k]
            wi = w_syn * pre_gain[i]
            if wi == 0.0:
                continue
            for e in range(indptr[i], indptr[i + 1]):
                j = indices[e]
                if step < rfc_end[j]:
                    continue  # refratario: escrita descartada (semantica 'unless refractory' do Brian2)
                g[j] += weights[e] * wi * gain[j]
                if active[j] == 0:
                    active[j] = 1
                    act_list[n_act] = j
                    n_act += 1
        ring_n[slot] = 0
        # 3b. entrada Poisson (direto em v, como PoissonInput do Brian2)
        for k in range(poi_idx.shape[0]):
            if np.random.random() < poi_p[k]:
                j = poi_idx[k]
                if step < rfc_end[j]:
                    continue
                v[j] += poi_w[k]
                if active[j] == 0:
                    active[j] = 1
                    act_list[n_act] = j
                    n_act += 1
        # 3c. eventos externos deterministicos (ordenados por passo)
        while ext_ptr < ext_step.shape[0] and ext_step[ext_ptr] == step:
            j = ext_idx[ext_ptr]
            if step < rfc_end[j]:
                ext_ptr += 1
                continue
            v[j] += ext_w[ext_ptr]
            if active[j] == 0:
                active[j] = 1
                act_list[n_act] = j
                n_act += 1
            ext_ptr += 1
        # 4. reset
        for k in range(n_spk):
            i = spikers[k]
            v[i] = vrst
            g[i] = 0.0
            rfc_end[i] = step + rfc_steps[i]
    n_act_arr[0] = n_act
    out_n_arr[0] = out_n
    ext_ptr_arr[0] = ext_ptr


@dataclass
class SpikeRecord:
    idx: np.ndarray    # int32, neuronio
    step: np.ndarray   # int64, passo (t = step * dt)

    def times_ms(self, dt_ms: float) -> np.ndarray:
        return self.step * dt_ms

    def of(self, neuron: int) -> np.ndarray:
        return self.step[self.idx == neuron]


class LIFEngine:
    """Um cerebro. Estado persistente entre chamadas de run()."""

    def __init__(self, pack: ConnectomePack, params: LIFParams = SHIU, seed: int = 0,
                 gain: np.ndarray | None = None, eps_mv: float = 1e-2, chunk_steps: int = 150,
                 pre_gain: np.ndarray | None = None):
        self.pack = pack
        self.p = params
        self.n = pack.n
        self.seed = int(seed)
        self.eps = float(eps_mv)
        self.chunk_steps = int(chunk_steps)
        self.gain = np.ones(self.n, dtype=np.float64) if gain is None else np.asarray(gain, dtype=np.float64)
        assert self.gain.shape == (self.n,)
        # ganho por neuronio PRE-sinaptico (multiplica todas as suas saidas); 0 = silencia as saidas
        self.pre_gain = np.ones(self.n, dtype=np.float64) if pre_gain is None else np.asarray(pre_gain, dtype=np.float64)
        assert self.pre_gain.shape == (self.n,)
        self.indptr = np.ascontiguousarray(pack.indptr, dtype=np.int64)
        self.indices = np.ascontiguousarray(pack.indices, dtype=np.int32)
        self.weights = np.ascontiguousarray(pack.weights, dtype=np.int16)
        self.D = params.delay_steps
        self.R = params.refrac_steps
        self.e_m, self.e_s, self.coef = params.exact_coefficients()
        self.reset()
        self.set_poisson(np.zeros(0, np.int32), np.zeros(0))
        self.set_external([], [], [])

    def reset(self) -> None:
        n = self.n
        self.v = np.full(n, self.p.v_rest_mv, dtype=np.float64)
        self.g = np.zeros(n, dtype=np.float64)
        self.rfc_end = np.zeros(n, dtype=np.int64)
        self.rfc_steps = np.full(n, self.R, dtype=np.int64)
        self.active = np.zeros(n, dtype=np.uint8)
        self.act_list = np.zeros(n, dtype=np.int32)
        self.n_act = np.zeros(1, dtype=np.int64)
        self.ring = np.zeros((self.D + 1, n), dtype=np.int32)
        self.ring_n = np.zeros(self.D + 1, dtype=np.int64)
        self.counts = np.zeros(n, dtype=np.int64)
        self.step = 0
        _seed(self.seed)

    # ---- estimulos ----
    def set_poisson(self, idx, rate_hz, no_refractory: bool = True) -> None:
        """Define o conjunto de neuronios com entrada Poisson (substitui o anterior).

        Como em model.py de Shiu (`neu[i].rfc = 0*ms  # no refractory period for
        Poisson targets`), os alvos de Poisson ficam SEM refratario: disparam a taxa
        do Poisson (~99 Hz a 100 Hz; ISI minimo 0,2 ms). Os demais mantem 2,2 ms.
        """
        self.rfc_steps[:] = self.R
        idx = np.asarray(idx, dtype=np.int32).ravel()
        if no_refractory:
            self.rfc_steps[idx] = 0
        rate = np.broadcast_to(np.asarray(rate_hz, dtype=np.float64), idx.shape).copy()
        self.poi_idx = idx
        self.poi_p = rate * (self.p.dt_ms / 1000.0)
        self.poi_w = np.full(idx.shape, self.p.poisson_weight_mv, dtype=np.float64)

    def set_external(self, steps, idx, dv_mv) -> None:
        """Eventos deterministicos (passo, neuronio, delta v). Usado em testes e no mundo."""
        steps = np.asarray(steps, dtype=np.int64).ravel()
        order = np.argsort(steps, kind="stable")
        self.ext_step = steps[order]
        self.ext_idx = np.asarray(idx, dtype=np.int32).ravel()[order]
        self.ext_w = np.asarray(dv_mv, dtype=np.float64).ravel()[order]
        self.ext_ptr = np.zeros(1, dtype=np.int64)
        # avanca ate o passo atual
        self.ext_ptr[0] = int(np.searchsorted(self.ext_step, self.step))

    # ---- execucao ----
    def run(self, duration_ms: float, record: bool = True) -> SpikeRecord:
        n_total = int(round(duration_ms / self.p.dt_ms))
        out_i, out_s = [], []
        done = 0
        while done < n_total:
            k = min(self.chunk_steps, n_total - done)
            cap = (k // self.R + 2) * self.n
            oi = np.empty(cap, dtype=np.int32)
            os_ = np.empty(cap, dtype=np.int64)
            on = np.zeros(1, dtype=np.int64)
            _run_chunk(k, self.step, self.v, self.g, self.rfc_end, self.active, self.act_list, self.n_act,
                       self.ring, self.ring_n, self.indptr, self.indices, self.weights, self.gain, self.pre_gain,
                       self.p.w_syn_mv, self.poi_idx, self.poi_p, self.poi_w,
                       self.ext_step, self.ext_idx, self.ext_w, self.ext_ptr,
                       oi, os_, on, self.counts,
                       self.p.v_rest_mv, self.p.v_reset_mv, self.p.v_th_mv, self.rfc_steps, self.D, self.eps,
                       self.e_m, self.e_s, self.coef)
            self.step += k
            done += k
            if record and on[0] > 0:
                out_i.append(oi[:on[0]].copy())
                out_s.append(os_[:on[0]].copy())
        if out_i:
            return SpikeRecord(np.concatenate(out_i), np.concatenate(out_s))
        return SpikeRecord(np.zeros(0, np.int32), np.zeros(0, np.int64))

    @property
    def n_active(self) -> int:
        return int(self.n_act[0])

    @property
    def t_ms(self) -> float:
        return self.step * self.p.dt_ms

# eps_mv = 1e-2 mV: limiar de desativacao. Medido em docs/F1_validacao/eps_sensitivity.json:
# ate 1e-2 mV os trens de disparo sao IDENTICOS aos de eps = 1e-4 (FlyWire e MaleCNS,
# 2 sementes); em 5e-2 mV comecam a divergir. O limiar fica 700x abaixo da distancia
# repouso -> limiar (7 mV).
