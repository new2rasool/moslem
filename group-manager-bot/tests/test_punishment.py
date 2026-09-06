"""تست‌های سیاست هشدار/تنبیه — domain/punishment.py"""

from bot.domain.punishment import PunishmentPolicy, default_policy


def test_default_policy_actions():
    policy = default_policy()
    assert policy.action_for(1) is None
    assert policy.action_for(2) is None
    assert policy.action_for(3) == ("mute", 3600)
    assert policy.action_for(4) == ("mute", 3600)
    assert policy.action_for(5) == ("mute", 86400)
    assert policy.action_for(6) == ("kick", None)
    assert policy.action_for(99) == ("kick", None)


def test_next_level():
    policy = default_policy()
    assert policy.next_level(1) == 3
    assert policy.next_level(2) == 3
    assert policy.next_level(3) == 5
    assert policy.next_level(5) == 6
    assert policy.next_level(9) is None  # بالاتر از همه


def test_custom_tiers():
    policy = PunishmentPolicy({2: ("mute", 300), 4: ("ban", None)})
    assert policy.action_for(1) is None
    assert policy.action_for(2) == ("mute", 300)
    assert policy.action_for(4) == ("ban", None)
