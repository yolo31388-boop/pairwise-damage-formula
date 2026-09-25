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
    # 100%抗性应该减伤到0或接近0
    assert r["damage"] <= 0  # 至少不能是100


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
    """吸收部分不触发暴击效果。"""
    df = DamageFormula(seed=1)
    atk = Unit("A", attack=100, defense=0, crit_rate=100, crit_dmg=150, dodge_rate=0)
    dfn = Unit("B", attack=10, defense=0, crit_rate=0, crit_dmg=100, dodge_rate=0, shield=1000)
    r = df.calc(atk, dfn)
    assert r["absorbed"] == 150  # 暴击后150全被吸收
    assert r["damage"] == 0


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
