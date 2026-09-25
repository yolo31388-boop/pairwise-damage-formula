"""伤害公式引擎：抗性、暴击、闪避、吸收盾、治疗。

核心不变量：
- 抗性减伤有明确上下限：减伤 0%-75%；负抗性增伤也有上限（最多 +75%）
- 暴伤乘法叠加：基础暴伤 ×(1+加成1)×(1+加成2)
- 闪避优先于暴击，闪避了就不暴击
- 伤害顺序：基础伤害 → 抗性修正 → 暴击修正 → 最终伤害
- 吸收盾在伤害计算前扣除，吸收部分不触发暴击
- 真实伤害无视抗性和护甲
- 伤害始终为非负数
- 治疗受治疗加成影响但不受抗性影响
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


# 抗性（defense，百分比）允许的上下限：减伤/增伤均最多 75%
MAX_RESISTANCE = 75
MIN_RESISTANCE = -75


@dataclass
class Unit:
    uid: str
    attack: int
    defense: int  # 抗性百分比 0-100
    crit_rate: int  # 0-100
    crit_dmg: int  # 基础150
    dodge_rate: int  # 0-100
    shield: int = 0


class DamageFormula:
    def __init__(self, seed: int = 42):
        self.rng_state = seed

    def _rng(self) -> int:
        """确定性 LCG 随机数，返回 [0, 99]。"""
        self.rng_state = (self.rng_state * 1103515245 + 12345) & 0x7FFFFFFF
        return self.rng_state % 100

    @staticmethod
    def _to_int(value: float) -> int:
        """截断取整，加极小 epsilon 抵消浮点误差，结果非负。"""
        return max(0, int(value + 1e-9))

    def _apply_resistance(self, defense: int) -> float:
        """抗性修正系数，钳制在 [0.25, 1.75]。

        defense 为正：减伤，最多减 75%（系数 0.25）。
        defense 为负：增伤，最多增 75%（系数 1.75）。
        """
        clamped = max(MIN_RESISTANCE, min(MAX_RESISTANCE, defense))
        return 1.0 - clamped / 100.0

    def _crit_multiplier(self, crit_dmg: int, crit_bonuses: list) -> float:
        """暴伤乘法叠加：基础暴伤 ×(1+加成1)×(1+加成2)……

        crit_dmg / crit_bonuses 均为百分比数值（如 150 表示 150%）。
        """
        multiplier = crit_dmg / 100.0
        for bonus in crit_bonuses:
            multiplier *= 1.0 + bonus / 100.0
        return multiplier

    def calc(self, attacker: Unit, defender: Unit, raw_damage: Optional[int] = None,
             crit_bonuses: list = None, is_true_damage: bool = False,
             variance: int = 0) -> dict:
        """计算伤害。

        顺序：基础伤害（含浮动）→ 吸收盾先扣 → 抗性修正 → 暴击修正 → 最终伤害。
        闪避优先判定；真实伤害无视抗性和护甲；吸收部分不触发暴击。

        :param variance: 伤害浮动范围（百分比，0-99），实际伤害落在
                         [base*(1-v), base*(1+v)]，由确定性 RNG 决定。
        """
        if raw_damage is None:
            raw_damage = attacker.attack
        if crit_bonuses is None:
            crit_bonuses = []

        result = {"dodge": False, "crit": False, "damage": 0, "absorbed": 0,
                  "base_damage": 0, "after_resistance": 0}

        # 1) 闪避优先于暴击：闪避了直接返回，不再判定/触发暴击
        dodge_roll = self._rng()
        if dodge_roll < defender.dodge_rate:
            result["dodge"] = True
            return result

        # 暴击骰子照常消耗以保证 RNG 序列确定；但暴击只在有伤害穿过盾时生效
        crit_roll = self._rng()
        crit_would_trigger = crit_roll < attacker.crit_rate

        # 2) 基础伤害 + 确定性浮动（浮动在指定范围内）
        base = max(0, raw_damage)
        if variance > 0 and base > 0:
            variance_roll = self._rng()  # [0,99] 映射到 [-v, +v]
            factor = 1.0 + ((variance_roll - 50) / 50.0) * (min(variance, 50) / 100.0)
            base = self._to_int(base * factor)
        base = max(0, base)
        result["base_damage"] = base

        # 3) 吸收盾在伤害计算前扣除，吸收部分不触发暴击
        absorbed = min(max(0, defender.shield), base)
        result["absorbed"] = absorbed
        remaining = base - absorbed

        # 4) 抗性修正（真实伤害无视抗性和护甲）
        if is_true_damage:
            after_resistance = float(remaining)
        else:
            after_resistance = remaining * self._apply_resistance(defender.defense)
        result["after_resistance"] = self._to_int(after_resistance)

        # 5) 暴击修正（乘法叠加）；被盾完全吸收时不触发暴击
        if crit_would_trigger and remaining > 0:
            result["crit"] = True
            after_resistance *= self._crit_multiplier(attacker.crit_dmg, crit_bonuses)

        # 6) 最终伤害：截断取整且始终非负
        result["damage"] = self._to_int(after_resistance)
        return result

    def calc_heal(self, caster: Unit, base_heal: int, heal_bonuses: list = None,
                  variance: int = 0) -> int:
        """计算治疗。

        治疗受治疗加成（乘法）影响，不受抗性/护甲影响，且始终非负。
        """
        if heal_bonuses is None:
            heal_bonuses = []

        amount = max(0, base_heal)
        if variance > 0 and amount > 0:
            variance_roll = self._rng()
            factor = 1.0 + ((variance_roll - 50) / 50.0) * (min(variance, 50) / 100.0)
            amount = self._to_int(amount * factor)

        multiplier = 1.0
        for bonus in heal_bonuses:
            multiplier *= 1.0 + bonus / 100.0
        return self._to_int(amount * multiplier)
