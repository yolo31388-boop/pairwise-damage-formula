"""伤害公式引擎：抗性、暴击、闪避、吸收盾、治疗。

核心不变量（固定计算顺序）：
1. 闪避优先判定：闪避后直接返回，不再判定暴击。
2. 基础伤害（含确定性伤害浮动）。
3. 抗性修正（真实伤害跳过；减伤/增伤均有明确上下限）。
4. 暴击修正（基础暴伤与各暴伤加成乘法叠加）。
5. 伤害钳制为非负数。
6. 吸收盾在最终伤害结算前扣除，吸收量不再单独触发暴击。
治疗只受治疗加成影响，不受抗性影响。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Unit:
    uid: str
    attack: int
    defense: int  # 抗性百分比 0-100，允许负值
    crit_rate: int  # 0-100
    crit_dmg: int  # 基础150
    dodge_rate: int  # 0-100
    shield: int = 0


class DamageFormula:
    # 抗性减伤上限：100% 减伤（伤害倍率最低 0，不会出现负伤害）
    MAX_DAMAGE_REDUCTION = 1.00
    # 负抗性增伤上限：最多多受 75% 伤害（伤害倍率最高 1.75）
    MAX_DAMAGE_AMPLIFY = 0.75

    def __init__(self, seed: int = 42):
        self.rng_state = seed

    def _rng(self) -> int:
        """确定性 LCG，返回 [0, 99] 的整数。"""
        self.rng_state = (self.rng_state * 1103515245 + 12345) & 0x7FFFFFFF
        return self.rng_state % 100

    def _variance_factor(self, variance: float) -> float:
        """根据确定性随机数返回 [1-variance, 1+variance] 的浮动系数。"""
        if variance <= 0:
            return 1.0
        roll = self._rng() / 99.0  # [0, 1]，端点可达
        return 1.0 - variance + 2.0 * variance * roll

    def _apply_resistance(self, amount: float, defense: int) -> float:
        """抗性修正。伤害倍率被钳制在 [0, 1.75]：

        - 减伤上限 MAX_DAMAGE_REDUCTION（100%，100 以上抗性伤害为 0）
        - 增伤上限 MAX_DAMAGE_AMPLIFY（负抗性最多 +75%）
        """
        multiplier = 1.0 - defense / 100.0
        lowest_multiplier = 1.0 - self.MAX_DAMAGE_REDUCTION
        highest_multiplier = 1.0 + self.MAX_DAMAGE_AMPLIFY
        multiplier = max(lowest_multiplier, min(highest_multiplier, multiplier))
        return amount * multiplier

    def _crit_multiplier(self, is_crit: bool, base_crit_dmg: int,
                         crit_bonuses: List[int]) -> float:
        """暴伤倍率。乘法叠加：基础暴伤 × (1+加成1) × (1+加成2) ..."""
        if not is_crit:
            return 1.0
        multiplier = base_crit_dmg / 100.0
        for bonus in crit_bonuses:
            multiplier *= 1.0 + bonus / 100.0
        return multiplier

    def calc_damage(self, attacker: Unit, defender: Unit,
                    raw_damage: Optional[int] = None,
                    crit_bonuses: Optional[List[int]] = None,
                    is_true_damage: bool = False,
                    variance: float = 0.0) -> dict:
        """按固定顺序计算伤害：闪避 → 基础 → 抗性 → 暴击 → 非负 → 吸收盾。"""
        if raw_damage is None:
            raw_damage = attacker.attack
        if crit_bonuses is None:
            crit_bonuses = []

        result = {"dodge": False, "crit": False, "damage": 0, "absorbed": 0}

        # 1. 闪避优先：闪避了就不暴击，也不产生任何伤害/吸收
        if self._rng() < defender.dodge_rate:
            result["dodge"] = True
            return result

        # 2. 暴击判定（仅在未闪避时进行）
        is_crit = self._rng() < attacker.crit_rate

        # 3. 基础伤害（确定性浮动）
        damage = float(max(0, raw_damage))
        damage *= self._variance_factor(variance)

        # 4. 抗性修正（真实伤害无视抗性/护甲）
        if not is_true_damage:
            damage = self._apply_resistance(damage, defender.defense)
        damage = int(damage)

        # 5. 暴击修正（乘法叠加）
        damage = int(damage * self._crit_multiplier(
            is_crit, attacker.crit_dmg, crit_bonuses))

        # 6. 伤害始终非负
        damage = max(0, damage)
        if is_crit:
            result["crit"] = True

        # 7. 吸收盾在最终伤害结算前扣除；吸收量就是最终伤害的一部分，
        #    不会在全局暴击倍率之外再单独触发一次暴击。
        absorbed = min(defender.shield, damage)
        result["absorbed"] = absorbed
        result["damage"] = max(0, damage - absorbed)
        return result

    # 向后兼容旧调用名
    calc = calc_damage

    def calc_heal(self, amount: int, healing_bonus: int = 0,
                  target: Optional[Unit] = None) -> dict:
        """治疗量：受治疗加成影响，无视目标抗性/护甲，且不会为负。"""
        base = max(0, int(amount))
        healed = int(base * (1.0 + healing_bonus / 100.0))
        return {"heal": max(0, healed)}
