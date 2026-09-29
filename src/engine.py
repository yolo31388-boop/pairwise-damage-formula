"""伤害公式引擎：抗性、暴击、闪避、吸收盾。

核心不变量：
- 抗性减伤有上下限
- 暴伤乘法叠加
- 闪避优先于暴击
- 伤害非负
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


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
        self.rng_state = (self.rng_state * 1103515245 + 12345) & 0x7FFFFFFF
        return self.rng_state % 100

    # 抗性减伤比例上下限：100% 抗性全免，负抗性最多增伤 100%
    MIN_REDUCTION = -1.0
    MAX_REDUCTION = 1.0

    def calc(self, attacker: Unit, defender: Unit, raw_damage: Optional[int] = None,
             crit_bonuses: list = None, is_true_damage: bool = False) -> dict:
        """计算伤害：闪避优先于暴击，抗性有上下限，暴伤乘法叠加，伤害非负。"""
        if raw_damage is None:
            raw_damage = attacker.attack
        if crit_bonuses is None:
            crit_bonuses = []

        result = {"dodge": False, "crit": False, "damage": 0, "absorbed": 0}

        # 闪避优先于暴击：闪避成功则直接返回，不判定暴击
        dodge_roll = self._rng()
        if dodge_roll < defender.dodge_rate:
            result["dodge"] = True
            return result

        crit_roll = self._rng()
        is_crit = crit_roll < attacker.crit_rate

        # 抗性减伤（真实伤害无视抗性，但不无视护盾）
        if is_true_damage:
            dmg = raw_damage
        else:
            reduction = defender.defense / 100.0
            reduction = max(self.MIN_REDUCTION, min(self.MAX_REDUCTION, reduction))
            dmg = int(raw_damage * (1 - reduction))

        # 暴击：暴伤加成乘法叠加
        if is_crit:
            result["crit"] = True
            total_crit = attacker.crit_dmg / 100.0
            for b in crit_bonuses:
                total_crit *= 1 + b / 100.0
            dmg = int(dmg * total_crit)

        # 吸收盾
        if defender.shield > 0:
            absorbed = min(defender.shield, dmg)
            result["absorbed"] = absorbed
            dmg -= absorbed

        result["damage"] = max(0, dmg)
        return result
