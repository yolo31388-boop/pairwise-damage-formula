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

    def calc(self, attacker: Unit, defender: Unit, raw_damage: Optional[int] = None,
             crit_bonuses: list = None, is_true_damage: bool = False) -> dict:
        """计算伤害。BUG：负抗性无上限，暴伤加法，闪避暴击优先级错。"""
        if raw_damage is None:
            raw_damage = attacker.attack
        if crit_bonuses is None:
            crit_bonuses = []

        result = {"dodge": False, "crit": False, "damage": 0, "absorbed": 0}

        # BUG：先判暴击再判闪避，应该先闪避
        crit_roll = self._rng()
        is_crit = crit_roll < attacker.crit_rate

        dodge_roll = self._rng()
        is_dodge = dodge_roll < defender.dodge_rate

        if is_dodge:
            result["dodge"] = True
            return result

        # 抗性减伤
        if is_true_damage:
            dmg = raw_damage
        else:
            # BUG：负抗性没有上限，可以无限增伤
            reduction = defender.defense / 100.0  # BUG：浮点
            dmg = int(raw_damage * (1 - reduction))

        # 暴击
        if is_crit:
            result["crit"] = True
            # BUG：暴伤加法叠加，应该乘法
            total_crit = attacker.crit_dmg
            for b in crit_bonuses:
                total_crit += b  # BUG：加法
            dmg = int(dmg * total_crit / 100)

        # 吸收盾
        if defender.shield > 0:
            absorbed = min(defender.shield, dmg)
            result["absorbed"] = absorbed
            dmg -= absorbed

        # BUG：没有确保非负
        result["damage"] = dmg
        return result
