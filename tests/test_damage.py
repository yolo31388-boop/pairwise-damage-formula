from src import DamageFormula, Unit


def test_dodge_priority():
    """闪避优先于暴击。"""
    df = DamageFormula(seed=1)
    atk = Unit("A", attack=100, defense=0, crit_rate=100, crit_dmg=150, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=100)
    r = df.calc(atk, dfn)
    assert r["dodge"]
    assert not r["crit"]  # 闪避了就不暴击
    assert r["damage"] == 0


def test_resistance_cap():
    """抗性减伤有上限。"""
    df = DamageFormula(seed=99)
    atk = Unit("A", attack=100, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=100, crit_rate=0, crit_dmg=100, dodge_rate=0)
    r = df.calc(atk, dfn)
    # 抗性减伤上限 75%：100 抗性被钳制为 75，伤害 = 100*0.25 = 25
    assert r["damage"] == 25


def test_high_resistance_floor():
    """远超上限的高抗性也只能减伤 75%，不会出现负伤害。"""
    df = DamageFormula(seed=99)
    atk = Unit("A", attack=100, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=9999, crit_rate=0, crit_dmg=100, dodge_rate=0)
    r = df.calc(atk, dfn)
    assert r["damage"] == 25


def test_boundary_resistance():
    """边界抗性：±75 恰好是上下限。"""
    df = DamageFormula(seed=99)
    atk = Unit("A", attack=100, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0)
    dfn75 = Unit("B", attack=10, defense=75, crit_rate=0, crit_dmg=100, dodge_rate=0)
    dfn_neg75 = Unit("B", attack=10, defense=-75, crit_rate=0, crit_dmg=100, dodge_rate=0)
    assert df.calc(atk, dfn75)["damage"] == 25
    assert df.calc(atk, dfn_neg75)["damage"] == 175


def test_negative_resistance_cap():
    """负抗性增伤有上限。"""
    df = DamageFormula(seed=99)
    atk = Unit("A", attack=100, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=-200, crit_rate=0, crit_dmg=100, dodge_rate=0)
    r = df.calc(atk, dfn)
    # BUG版本：-200%抗性导致3倍伤害=300
    assert r["damage"] < 300, "负抗性增伤应有上限，当前=%d" % r["damage"]


def test_crit_damage_multiplicative():
    """暴伤乘法叠加。"""
    df = DamageFormula(seed=1)  # 确保暴击
    atk = Unit("A", attack=100, defense=0, crit_rate=100, crit_dmg=150, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0)
    # 两个50%暴伤加成：乘法=150*1.5*1.5=337.5，加法=150+50+50=250
    r = df.calc(atk, dfn, crit_bonuses=[50, 50])
    assert r["crit"]
    # BUG版本：加法得到250
    assert r["damage"] == 337 or r["damage"] == 338, "暴伤应乘法叠加，当前=%d" % r["damage"]


def test_non_negative_damage():
    """伤害非负。"""
    df = DamageFormula(seed=99)
    atk = Unit("A", attack=10, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=200, crit_rate=0, crit_dmg=100, dodge_rate=0)
    r = df.calc(atk, dfn)
    assert r["damage"] >= 0


def test_true_damage_ignores_resistance():
    """真实伤害无视抗性。"""
    df = DamageFormula(seed=99)
    atk = Unit("A", attack=100, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=50, crit_rate=0, crit_dmg=100, dodge_rate=0)
    r = df.calc(atk, dfn, is_true_damage=True)
    assert r["damage"] == 100


def test_shield_absorbs():
    """吸收盾先扣除。"""
    df = DamageFormula(seed=99)
    atk = Unit("A", attack=100, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0, shield=30)
    r = df.calc(atk, dfn)
    assert r["absorbed"] == 30
    assert r["damage"] == 70


def test_shield_no_crit_on_absorbed():
    """吸收部分不触发暴击效果：盾在伤害计算前扣除，全吸收时不暴击。"""
    df = DamageFormula(seed=1)
    atk = Unit("A", attack=100, defense=0, crit_rate=100, crit_dmg=150, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0, shield=1000)
    r = df.calc(atk, dfn)
    assert not r["crit"]  # 伤害被盾完全吸收，不触发暴击
    assert r["absorbed"] == 100  # 吸收的是暴击前的基础伤害
    assert r["damage"] == 0


def test_shield_before_resistance():
    """吸收盾在抗性修正之前扣除。"""
    df = DamageFormula(seed=99)
    atk = Unit("A", attack=100, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0)
    # 盾 30 先吸基础伤害：剩 70 → 抗性 50% → 35
    dfn = Unit("B", attack=10, defense=50, crit_rate=0, crit_dmg=100, dodge_rate=0, shield=30)
    r = df.calc(atk, dfn)
    assert r["absorbed"] == 30
    assert r["damage"] == 35


def test_shield_partial_then_crit():
    """部分吸收后剩余伤害仍可暴击，吸收部分不吃暴伤。"""
    df = DamageFormula(seed=1)  # seed1: dodge roll=90 未闪避, crit roll=75 暴击
    atk = Unit("A", attack=100, defense=0, crit_rate=100, crit_dmg=200, dodge_rate=0)
    # 盾吸 40 → 剩 60 → 暴击 200% → 120（而不是 200-40=160）
    dfn = Unit("B", attack=10, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0, shield=40)
    r = df.calc(atk, dfn)
    assert r["crit"]
    assert r["absorbed"] == 40
    assert r["damage"] == 120


def test_damage_order():
    """伤害计算顺序：基础→抗性→暴击→盾。"""
    df = DamageFormula(seed=1)
    atk = Unit("A", attack=100, defense=0, crit_rate=100, crit_dmg=200, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=50, crit_rate=0, crit_dmg=100, dodge_rate=0, shield=10)
    r = df.calc(atk, dfn)
    # 基础100 → 抗性50%→50 → 暴击200%→100 → 盾10→90
    assert r["damage"] == 90


def test_zero_attack():
    """零攻击。"""
    df = DamageFormula(seed=99)
    atk = Unit("A", attack=0, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0)
    r = df.calc(atk, dfn)
    assert r["damage"] == 0


def test_zero_resistance():
    """零抗性不增不减。"""
    df = DamageFormula(seed=99)
    atk = Unit("A", attack=123, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0)
    r = df.calc(atk, dfn)
    assert r["damage"] == 123


def test_crit_three_bonuses_multiplicative():
    """多个暴伤加成严格乘法叠加。"""
    df = DamageFormula(seed=1)
    atk = Unit("A", attack=100, defense=0, crit_rate=100, crit_dmg=100, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0)
    # 100% 基础 × 1.1 × 1.2 × 1.3 = 171.6
    r = df.calc(atk, dfn, crit_bonuses=[10, 20, 30])
    assert r["crit"]
    assert r["damage"] == 171


def test_dodge_and_crit_both_rolled_dodge_wins():
    """闪避与暴击同时可能触发时，闪避优先且不暴击。"""
    df = DamageFormula(seed=7)  # dodge roll=16, crit roll=33
    atk = Unit("A", attack=100, defense=0, crit_rate=100, crit_dmg=200, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=50)
    r = df.calc(atk, dfn)
    assert r["dodge"]
    assert not r["crit"]
    assert r["damage"] == 0


def test_no_dodge_crit_proceeds():
    """未闪避且暴击骰命中时正常暴击。"""
    df = DamageFormula(seed=7)  # dodge roll=16 不闪避, crit roll=33 < 50 暴击
    atk = Unit("A", attack=100, defense=0, crit_rate=50, crit_dmg=150, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=10)
    r = df.calc(atk, dfn)
    assert not r["dodge"]
    assert r["crit"]
    assert r["damage"] == 150


def test_order_base_resistance_crit():
    """修正顺序：基础 → 抗性 → 暴击（数值上等价于该顺序的逐阶段结果）。"""
    df = DamageFormula(seed=1)
    atk = Unit("A", attack=200, defense=0, crit_rate=100, crit_dmg=200, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=50, crit_rate=0, crit_dmg=100, dodge_rate=0)
    r = df.calc(atk, dfn)
    assert r["base_damage"] == 200
    assert r["after_resistance"] == 100  # 200 * 0.5
    assert r["damage"] == 200  # 100 * 2.0


def test_true_damage_with_shield_and_negative_resistance():
    """真实伤害无视抗性和护甲：只受盾影响，负抗性也不增伤。"""
    df = DamageFormula(seed=99)
    atk = Unit("A", attack=100, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=-75, crit_rate=0, crit_dmg=100, dodge_rate=0, shield=20)
    r = df.calc(atk, dfn, is_true_damage=True)
    assert r["absorbed"] == 20
    assert r["damage"] == 80


def test_true_damage_crit_ignores_resistance():
    """真实伤害的暴击也不经过抗性。"""
    df = DamageFormula(seed=1)
    atk = Unit("A", attack=100, defense=0, crit_rate=100, crit_dmg=200, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=50, crit_rate=0, crit_dmg=100, dodge_rate=0)
    r = df.calc(atk, dfn, is_true_damage=True)
    assert r["damage"] == 200


def test_damage_variance_bounds_and_determinism():
    """伤害浮动在指定范围内且同种子结果确定。"""
    atk = Unit("A", attack=100, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0)
    for seed in range(200):
        r = DamageFormula(seed=seed).calc(atk, dfn, variance=10)
        assert 90 <= r["damage"] <= 110
        r2 = DamageFormula(seed=seed).calc(atk, dfn, variance=10)
        assert r["damage"] == r2["damage"]


def test_no_variance_default():
    """默认无浮动时伤害确定不变。"""
    df = DamageFormula(seed=99)
    atk = Unit("A", attack=100, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=25, crit_rate=0, crit_dmg=100, dodge_rate=0)
    assert df.calc(atk, dfn)["damage"] == 75


def test_heal_bonus_multiplicative_no_resistance():
    """治疗受治疗加成乘法影响，且与受治疗者抗性无关。"""
    df = DamageFormula(seed=99)
    caster = Unit("C", attack=100, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0)
    # 100 × 1.5 × 1.2 = 180
    assert df.calc_heal(caster, 100, heal_bonuses=[50, 20]) == 180


def test_heal_non_negative_and_ignores_defense():
    """治疗始终非负；防御再高也不影响治疗。"""
    df = DamageFormula(seed=99)
    caster = Unit("C", attack=100, defense=999, crit_rate=0, crit_dmg=100, dodge_rate=0)
    assert df.calc_heal(caster, 0) == 0
    assert df.calc_heal(caster, 80, heal_bonuses=[]) == 80


def test_mixed_modifiers_fixed_order():
    """混合修正按固定顺序：盾 → 抗性 → 暴击。"""
    df = DamageFormula(seed=1)
    atk = Unit("A", attack=100, defense=0, crit_rate=100, crit_dmg=200, dodge_rate=0)
    # 基础 100 → 盾 20 先吸 → 剩 80 → 抗性 60% 减伤: 80*0.4=32 → 暴击 200%: 64
    dfn = Unit("B", attack=10, defense=60, crit_rate=0, crit_dmg=100, dodge_rate=0, shield=20)
    r = df.calc(atk, dfn)
    assert r["base_damage"] == 100
    assert r["absorbed"] == 20
    assert r["after_resistance"] == 32
    assert r["crit"]
    assert r["damage"] == 64
