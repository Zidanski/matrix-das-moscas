"""Parametros do LIF de Shiu et al. 2024 (Nature 634:210).

Valores conferidos em model.py do repositorio philshiu/Drosophila_brain_model
(MIT). Sao os UNICOS parametros do neuronio; foram ajustados ao FlyWire e sao
reutilizados no MaleCNS como premissa (ver README, secao "premissas").
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import math


@dataclass(frozen=True)
class LIFParams:
    v_rest_mv: float = -52.0     # v_0
    v_reset_mv: float = -52.0    # v_rst
    v_th_mv: float = -45.0       # v_th
    tau_m_ms: float = 20.0       # t_mbr
    tau_syn_ms: float = 5.0      # tau
    t_refrac_ms: float = 2.2     # t_rfc
    t_delay_ms: float = 1.8      # t_dly
    w_syn_mv: float = 0.275      # w_syn (por sinapse)
    poisson_weight_factor: float = 250.0  # f_poi: cada evento Poisson soma w_syn*f_poi em v
    dt_ms: float = 0.1

    @property
    def refrac_steps(self) -> int:
        return int(round(self.t_refrac_ms / self.dt_ms))

    @property
    def delay_steps(self) -> int:
        return int(round(self.t_delay_ms / self.dt_ms))

    @property
    def poisson_weight_mv(self) -> float:
        return self.w_syn_mv * self.poisson_weight_factor

    def exact_coefficients(self) -> tuple[float, float, float]:
        """Coeficientes da solucao exata do sistema linear por passo dt.

        dv/dt = (v0 - v + g)/tau_m ; dg/dt = -g/tau_s
        v(t+dt) = v0 + (v-v0)*e_m + g*coef ; g(t+dt) = g*e_s
        coef = tau_s/(tau_m - tau_s) * (e_m - e_s)
        Identico ao metodo 'linear' do Brian2 (exponencial de matriz).
        """
        e_m = math.exp(-self.dt_ms / self.tau_m_ms)
        e_s = math.exp(-self.dt_ms / self.tau_syn_ms)
        coef = self.tau_syn_ms / (self.tau_m_ms - self.tau_syn_ms) * (e_m - e_s)
        return e_m, e_s, coef

    def to_dict(self) -> dict:
        return asdict(self)


SHIU = LIFParams()
