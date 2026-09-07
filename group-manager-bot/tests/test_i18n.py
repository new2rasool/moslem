"""تست‌های i18n — بارگذاری، fallback و قالب‌بندی."""

from bot.i18n.loader import Translator


def test_locales_loadable(translator):
    available = translator.available()
    assert "fa" in available and "en" in available
    fa = translator.load("fa")
    assert fa["start_user"] and fa["help_header"]


def test_fa_text(translator):
    text = translator.t("fa", "start_user", name="علی")
    assert "علی" in text and "سلام" in text


def test_en_text(translator):
    text = translator.t("en", "cmd_denied", level="Admin")
    assert text == "⛔ Access denied. This command requires level «Admin» or higher."


def test_fallback_to_en(translator, tmp_path):
    # لوکال آزمایشی: کلیدی فقط در en هست → fa باید از en بگیرد
    locales = tmp_path / "locales"
    locales.mkdir()
    (locales / "en.json").write_text('{"only_en": "Hello {name}"}', encoding="utf-8")
    (locales / "fa.json").write_text('{}', encoding="utf-8")
    custom = Translator(locales)
    assert custom.t("fa", "only_en", name="Ali") == "Hello Ali"


def test_missing_key_returns_key(translator):
    assert translator.t("fa", "no_such_key_xyz") == "no_such_key_xyz"


def test_unknown_lang_falls_back(translator):
    # زبان نامعتبر → en
    assert "Bot help" in translator.t("de", "help_header", count=1, plugins=1)


def test_missing_format_var_is_safe(translator):
    # جای‌نگهدار گم‌شده خطا نمی‌دهد و به‌جای خودش می‌ماند
    text = translator.t("en", "start_user")  # بدون name
    assert "{name}" in text


def test_text_no_format(translator):
    assert translator.text("fa", "cmd_unknown") == translator.t("fa", "cmd_unknown")


def test_all_en_keys_exist_in_fa(translator):
    en = set(translator.load("en"))
    fa = set(translator.load("fa"))
    assert fa >= en, f"کلیدهای گم‌شده در fa: {sorted(en - fa)}"
