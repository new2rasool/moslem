"""تست‌های نرمال‌سازی متن — domain/text_normalize.py"""

from bot.domain.text_normalize import collapse_repeats, normalize_text


def test_persian_arabic_unification():
    assert normalize_text("يک کافي") == "یک کافی"
    assert normalize_text("سلام عليکم") == "سلام علیکم"
    assert normalize_text("كيبرد") == "کیبرد"


def test_fake_spacing_and_tatweel():
    # کشیدگی و حرکت‌ها حذف می‌شوند
    assert normalize_text("بِسمِ اللهِ") == "بسم الله"
    assert normalize_text("ســـلام") == "سلام"
    assert normalize_text("قــوانین") == "قوانین"


def test_repeats_collapsed():
    assert collapse_repeats("بنننن") == "بن"
    assert collapse_repeats("بنن") == "بنن"  # تکرار دوتایی دست نمی‌خورد
    assert normalize_text("سلاممممم") == "سلام"
    assert normalize_text("بدوووون") == "بدون"
    # کلمات عادی با حرف دوتایی سالم می‌مانند
    assert normalize_text("HELLO World") == "hello world"


def test_hidden_chars_removed():
    # ZWJ / ZWNJ / Bidi حذف می‌شوند
    assert normalize_text("می\u200cرود") == "میرود"
    assert normalize_text("a\u200bb") == "ab"
    assert normalize_text("\u202eسلام\u202c") == "سلام"


def test_digits_and_case():
    assert normalize_text("نسخه ۱۲۳") == "نسخه 123"
    assert normalize_text("HELLO World") == "hello world"


def test_leet_optional():
    assert normalize_text("fr33", leet=True) == "free"
    assert normalize_text("fr33") != "free"  # پیش‌فرض خاموش
    assert normalize_text("h3llo", leet=True) == "hello"


def test_whitespace_collapse():
    assert normalize_text("  سلام    به   همه  ") == "سلام به همه"
