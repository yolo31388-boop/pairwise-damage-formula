"""不变量补充测试：抗性上下限、暴伤乘法、闪避优先、计算顺序等。"""

from src import DamageFormula, Unit


def make_units(defense=0, crit_rate=0, crit_dmg=150, dodge_rate=0,
               attack=100, shield=0):
    atk = Unit("A", attack=attack, defense=0, crit_rate=crit_rate,
               crit_dmg=crit_dmg, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=defense, crit_rate=0, crit_dmg=100,
               dodge_rate=dodge_rate, shield=shield)
    return atk, dfn


# ---------- 抗性上限 / 下限 ----------

def test_high_resistance_capped_to_zero():
    """高抗性减伤有上限，伤害最低为 0，不出现负值。"""
    df = DamageFormula(seed=99)
    for defense in (100, 150, 200, 500):
        atk, dfn = make_units(defense=defense)
        r = df.calc_damage(atk, dfn)
        assert r["damage"] == 0, "defense=%d 时伤害应为0" % defense
        assert r["damage"] >= 0


def test_negative_resistance_amplify_cap():
    """负抗性增伤有上限：最多 +75%（175），-200 也不能打出数倍伤害。"""
    df = DamageFormula(seed=99)
    atk, dfn = make_units(defense=-75)
    assert df.calc_damage(atk, dfn)["damage"] == 175
    for defense in (-76, -100, -200, -500):
        atk, dfn = make_units(defense=defense)
        r = df.calc_damage(atk, dfn)
        assert r["damage"] == 175, "defense=%d 应被钳制到+75%%增伤，当前=%d" % (
            defense, r["damage"])
        assert r["damage"] < 300


def test_resistance_boundaries_and_zero():
    """零抗性、普通抗性与边界抗性的精确结果。"""
    df = DamageFormula(seed=99)
    atk, dfn = make_units(defense=0)
    assert df.calc_damage(atk, dfn)["damage"] == 100  # 零抗性
    atk, dfn = make_units(defense=50)
    assert df.calc_damage(atk, dfn)["damage"] == 50
    atk, dfn = make_units(defense=75)
    assert df.calc_damage(atk, dfn)["damage"] == 25  # 减伤边界点
    atk, dfn = make_units(defense=-50)
    assert df.calc_damage(atk, dfn)["damage"] == 150  # 增伤区间内不被钳制


def test_apply_resistance_helper_bounds():
    """直接验证抗性修正函数的上下限。"""
    df = DamageFormula()
    assert df._apply_resistance(100.0, 0) == 100.0
    assert df._apply_resistance(100.0, 100) == 0.0
    assert df._apply_resistance(100.0, 300) == 0.0
    assert df._apply_resistance(100.0, -75) == 175.0
    assert df._apply_resistance(100.0, -300) == 175.0


# ---------- 暴伤乘法叠加 ----------

def test_crit_multiplier_helper_multiplicative():
    df = DamageFormula()
    assert df._crit_multiplier(False, 150, [50, 50]) == 1.0
    assert df._crit_multiplier(True, 150, []) == 1.5
    assert df._crit_multiplier(True, 150, [50]) == 2.25
    assert df._crit_multiplier(True, 150, [50, 50]) == 3.375
    assert df._crit_multiplier(True, 150, [100, 100]) == 6.0


def test_crit_bonus_combinations():
    df = DamageFormula(seed=1)
    atk, dfn = make_units(crit_rate=100, crit_dmg=150)
    assert df.calc_damage(atk, dfn, crit_bonuses=[50])["damage"] == 225
    atk, dfn = make_units(crit_rate=100, crit_dmg=150)
    assert df.calc_damage(atk, dfn, crit_bonuses=[100, 100])["damage"] == 600
    atk, dfn = make_units(crit_rate=100, crit_dmg=150)
    r = df.calc_damage(atk, dfn, crit_bonuses=[50, 50])
    assert r["crit"] and r["damage"] in (337, 338)  # 乘法而非加法(250)


# ---------- 闪避优先 ----------

def test_dodge_takes_priority_over_crit():
    # seed=4：第一次（闪避）roll=29<30，第二次（暴击）roll=78>=30
    df = DamageFormula(seed=4)
    atk, dfn = make_units(crit_rate=30, dodge_rate=30)
    r = df.calc_damage(atk, dfn)
    assert r["dodge"] is True
    assert r["crit"] is False
    assert r["damage"] == 0
    assert r["absorbed"] == 0  # 闪避不与吸收盾/暴击结算


def test_no_dodge_allows_crit_roll():
    # seed=0：闪避 roll=45>=30，暴击 roll=6<30
    df = DamageFormula(seed=0)
    atk, dfn = make_units(crit_rate=30, crit_dmg=150, dodge_rate=30)
    r = df.calc_damage(atk, dfn)
    assert r["dodge"] is False
    assert r["crit"] is True
    assert r["damage"] == 150


# ---------- 计算顺序：基础→抗性→暴击→最终 ----------

def test_modifier_order_resistance_before_crit():
    """能区分先暴击后抗性（错误顺序=154）与先抗性后暴击（正确=155）。"""
    df = DamageFormula(seed=1)
    atk, dfn = make_units(defense=10, crit_rate=100, crit_dmg=150)
    r = df.calc_damage(atk, dfn, crit_bonuses=[15])
    assert r["damage"] == 155  # int(90) * 1.5 * 1.15 = 155.25 → 155


def test_full_order_with_shield():
    df = DamageFormula(seed=1)
    atk, dfn = make_units(defense=50, crit_rate=100, crit_dmg=200, shield=10)
    r = df.calc_damage(atk, dfn)
    # 100 → 抗性50 → 50 → 暴击200% → 100 → 盾10 → 90
    assert r["absorbed"] == 10
    assert r["damage"] == 90


# ---------- 真实伤害 ----------

def test_true_damage_ignores_defense():
    df = DamageFormula(seed=99)
    for defense in (50, 100, 200, 500):
        atk, dfn = make_units(defense=defense)
        assert df.calc_damage(atk, dfn, is_true_damage=True)["damage"] == 100
    atk, dfn = make_units(defense=-200)
    assert df.calc_damage(atk, dfn, is_true_damage=True)["damage"] == 100


def test_true_damage_still_crits_and_shields():
    """真实伤害只跳过抗性，暴击与吸收盾仍正常结算。"""
    df = DamageFormula(seed=1)
    atk, dfn = make_units(defense=80, crit_rate=100, crit_dmg=150, shield=40)
    r = df.calc_damage(atk, dfn, is_true_damage=True)
    assert r["crit"] is True
    assert r["absorbed"] == 40
    assert r["damage"] == 110  # 100 → 无视抗性 → 暴击150 → 盾40


# ---------- 非负伤害 ----------

def test_damage_always_non_negative():
    df = DamageFormula(seed=99)
    atk, dfn = make_units(defense=999, attack=1)
    assert df.calc_damage(atk, dfn)["damage"] == 0
    atk, dfn = make_units(shield=50, attack=0)
    r = df.calc_damage(atk, dfn)
    assert r["damage"] == 0 and r["absorbed"] == 0
    assert df.calc_damage(atk, dfn, raw_damage=-50)["damage"] >= 0


# ---------- 吸收盾 ----------

def test_shield_partial_absorb_order():
    df = DamageFormula(seed=1)
    atk, dfn = make_units(defense=50, crit_rate=100, crit_dmg=200, shield=30)
    r = df.calc_damage(atk, dfn)
    # 50(抗性后) → 100(暴击后) → 盾吸收30 → 70
    assert r["absorbed"] == 30
    assert r["damage"] == 70


# ---------- 伤害浮动（确定性、范围） ----------

def test_variance_bounds_and_determinism():
    # seed=36 浮动到 +10%，seed=25 浮动到 -10%
    atk, dfn = make_units()
    assert DamageFormula(seed=36).calc_damage(atk, dfn, variance=0.1)["damage"] == 110
    assert DamageFormula(seed=25).calc_damage(atk, dfn, variance=0.1)["damage"] == 90
    assert DamageFormula(seed=99).calc_damage(atk, dfn, variance=0.0)["damage"] == 100
    # 同种子重复计算结果完全一致
    r1 = DamageFormula(seed=7).calc_damage(atk, dfn, variance=0.1)
    r2 = DamageFormula(seed=7).calc_damage(atk, dfn, variance=0.1)
    assert r1["damage"] == r2["damage"]
    # 任意种子都必须落在 [1-v, 1+v] 区间内
    for seed in range(100):
        dmg = DamageFormula(seed=seed).calc_damage(atk, dfn, variance=0.5)["damage"]
        assert 50 <= dmg <= 150, "seed=%d 浮动越界: %d" % (seed, dmg)


# ---------- 治疗 ----------

def test_healing_bonus_without_resistance():
    df = DamageFormula()
    assert df.calc_heal(100)["heal"] == 100
    assert df.calc_heal(100, healing_bonus=50)["heal"] == 150
    assert df.calc_heal(80, healing_bonus=25)["heal"] == 100
    _, dfn = make_units(defense=90)
    # 目标 90% 抗性对治疗无影响
    assert df.calc_heal(100, healing_bonus=50, target=dfn)["heal"] == 150
    assert df.calc_heal(-20)["heal"] >= 0


# ---------- 混合修正 ----------

def test_mixed_negative_resistance_crit_shield():
    df = DamageFormula(seed=1)
    atk, dfn = make_units(defense=-200, crit_rate=100, crit_dmg=150, shield=100)
    r = df.calc_damage(atk, dfn, crit_bonuses=[50])
    # 100 → 增伤上限 175 → 暴击 1.5×1.5 → 393 → 盾100 → 293
    assert r["crit"] is True
    assert r["absorbed"] == 100
    assert r["damage"] == 293
