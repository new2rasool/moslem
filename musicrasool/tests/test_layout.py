"""
Layout parity test: verifies every panel / button row and its ORDER
matches the original GitHub source (new2rasool/musicrasool main1.py).
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

with open(".env", "w", encoding="utf-8") as f:
    f.write("API_ID=1234567\nAPI_HASH=0123456789abcdef0123456789abcdef\n")
    f.write("BOT_TOKEN=123456:TESTTOKEN\nOWNER_ID=6173234874\nSUDO_ID=6173234874\n")
    f.write("DEFAULT_LANG=fa\nDOWNLOAD_DIR=downloads\n")

import config  # noqa: E402
import database  # noqa: E402

config.load_config()
database.init_db()

import utils  # noqa: E402
import i18n  # noqa: E402

UID = 6173234874
results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), "-", name)


def rows_of(markup):
    """Extract [(text, callback_data|url), ...] rows from an InlineKeyboardMarkup."""
    out = []
    for row in markup.inline_keyboard:
        out.append([(b.text, b.callback_data or b.url) for b in row])
    return out


# ----------------------------------------------------------------------
# 1. /start inline keyboard (original: 4 rows, same order)
# ----------------------------------------------------------------------
info = {"groupp": "+NFHJK4757FDSDF", "adminpv": "bdchvjndchvj", "payamresan": "dbgchjnebdh"}
kb = rows_of(utils.start_keyboard(UID, info, "https://t.me/xyz"))
expected_start = [
    [("📚 اطلاعات بیشتر", "aboutus")],
    [("💻 خرید مستقیم از سازنده", "https://t.me/bdchvjndchvj")],
    [("▪️ کانال ربات", "https://t.me/xyz"), ("▪️ گروه پشتیبانی", "https://t.me/+NFHJK4757FDSDF")],
    [("📮 خرید غیر مستقیم", "https://t.me/dbgchjnebdh")],
]
check("start keyboard matches original (4 rows)", kb == expected_start)

# ----------------------------------------------------------------------
# 2. Install panel (original order)
# ----------------------------------------------------------------------
kb = rows_of(utils.install_keyboard(UID))
expected_install = [
    [("• نصب ویدیو", "installvideo"), ("• نصب موزیک", "installmusic")],
    [("• پیکربندی", "config")],
    [("• تنظیم شارژ", "charge"), ("• افزودن هلپر", "addcli")],
    [("• بستن پنل", "closepannel")],
]
check("install panel matches original", kb == expected_install)

# ----------------------------------------------------------------------
# 3. Charge menu (original order)
# ----------------------------------------------------------------------
kb = rows_of(utils.charge_menu_keyboard(UID))
expected_charge = [
    [("• شارژ ویدیو", "chargevideo"), ("• شارژ موزیک", "chargemusic")],
    [("• بازگشت", "back1")],
    [("• بستن پنل", "closepannel")],
]
check("charge menu matches original", kb == expected_charge)

# ----------------------------------------------------------------------
# 4. Months keyboards (video = mah1 / music = mah2)
# ----------------------------------------------------------------------
kb = rows_of(utils.months_keyboard(UID, "1"))
expected_months1 = [
    [("• 1 ماه", "1mah1"), ("• 2 ماه", "2mah1")],
    [("• 3 ماه", "3mah1"), ("• 4 ماه", "4mah1")],
    [("• بازگشت", "back2")],
]
check("video months keyboard matches original", kb == expected_months1)
kb = rows_of(utils.months_keyboard(UID, "2"))
expected_months2 = [
    [("• 1 ماه", "1mah2"), ("• 2 ماه", "2mah2")],
    [("• 3 ماه", "3mah2"), ("• 4 ماه", "4mah2")],
    [("• بازگشت", "back2")],
]
check("music months keyboard matches original", kb == expected_months2)

# ----------------------------------------------------------------------
# 5. Delete panel (original order)
# ----------------------------------------------------------------------
kb = rows_of(utils.delete_keyboard(UID))
expected_delete = [
    [("• حذف موزیک", "delmus"), ("• حذف ویدیو", "delvid")],
    [("• حذف کلی", "delboth")],
    [("• خروج ربات", "left")],
    [("• بستن پنل", "closedel")],
]
check("delete panel matches original", kb == expected_delete)

# ----------------------------------------------------------------------
# 6. TV menu + national channels (telev)
# ----------------------------------------------------------------------
kb = rows_of(utils.tv_menu_keyboard(UID))
expected_tvmenu = [
    [("• ماهواره", "mahvare"), ("• تلویزیون", "telev")],
    [("• بستن پنل", "closetv")],
]
check("tv menu matches original", kb == expected_tvmenu)

kb = rows_of(utils.tv_ir_keyboard(UID))
expected_telev = [
    [("• شبکه 2", "tv2"), ("• شبکه 1", "tv1")],
    [("• شبکه 5", "tv5"), ("• شبکه 3", "tv3")],
    [("• شبکه آی‌فیلم", "ifilm"), ("• شبکه خبر", "news")],
    [("• شبکه نمایش", "namayesh"), ("• شبکه نسیم", "nasim")],
    [("• شبکه تماشا", "hdtest"), ("• شبکه ورزش", "varzesh")],
    [("• بستن پنل", "closetv"), ("• بازگشت", "backahura")],
]
check("telev panel matches original", kb == expected_telev)

# ----------------------------------------------------------------------
# 7. Satellite panel (mahvare) - full original order
# ----------------------------------------------------------------------
kb = rows_of(utils.tv_sat_keyboard(UID))
expected_mahvare = [
    [("• BBC", "bbc"), ("• ManotoTv", "manoto")],
    [("• AvaFamily", "avafamily"), ("• AvaSeries", "avaseries")],
    [("• FarsiTv", "farsitv"), ("• PMC", "pmc")],
    [("• Vox 2", "vox2"), ("• Vox 1", "vox1")],
    [("• NavahangMusic", "navahang"), ("• RadioJavan", "radiojavan")],
    [("• IranInternational", "iraninternational"), ("• ITN", "itn")],
    [("• GemTv", "gemtv"), ("• OxirTv", "owirtv")],
    [("• GemRubix", "gemrubix"), ("• GemRiver", "gemriver")],
    [("• GemBollywood", "gembollywood"), ("• GemSeries", "gemseries")],
    [("• GemJunior", "gemjunior"), ("• GemDrama", "gemdrama")],
    [("• GemFilm", "gemfilm"), ("• GemMaxx", "gemmaxx")],
    [("• BBC Persian", "bbcpersian"), ("• MBC Persia", "mbcpersia")],
    [("• Tapesh 1", "tapesh1"), ("• Tapesh 2", "tapesh2")],
    [("• PersianaTv", "persiana"), ("• PMC Royale", "pmcr")],
    [("• بستن پنل", "closetv"), ("• بازگشت", "backahura")],
]
check("mahvare panel matches original", kb == expected_mahvare)

# ----------------------------------------------------------------------
# 8. Player keyboards (music / video / playlist) - original order
# ----------------------------------------------------------------------
kb = rows_of(utils.player_keyboard(UID, "music"))
expected_music = [
    [("• در حال پخش", "a")],
    [("⏸ مکث", "pausee"), ("⏹ توقف", "closee"), ("▶️ ازسرگیری", "resumee")],
    [("🔇 بیصدا", "mutemus"), ("🔊 باصدا", "unmutemus")],
    [("• بستن", "cls")],
]
check("music player keyboard matches original", kb == expected_music)

kb = rows_of(utils.player_keyboard(UID, "video"))
expected_video = [
    [("• در حال پخش", "a")],
    [("⏸ مکث", "pauseeee"), ("⏹ توقف", "closeeee"), ("▶️ ازسرگیری", "resumeeee")],
    [("🔇 بیصدا", "mutevid"), ("🔊 باصدا", "unmutevid")],
    [("• بستن", "clls")],
]
check("video player keyboard matches original", kb == expected_video)

kb = rows_of(utils.player_keyboard(UID, "playlist"))
expected_playlist = [
    [("• در حال پخش", "a")],
    [("⏸ مکث", "pauseee"), ("⏹ توقف", "closeee"), ("▶️ ازسرگیری", "resumeee")],
    [("🔇 بیصدا", "mutemus"), ("🔊 باصدا", "unmutemus")],
    [("• بستن", "cls")],
]
check("playlist player keyboard matches original", kb == expected_playlist)

# ----------------------------------------------------------------------
# 9. Help panel (original order)
# ----------------------------------------------------------------------
kb = rows_of(utils.help_keyboard(UID))
expected_help = [
    [("• سرچ و پخش خودکار", "helpvideo")],
    [("• ارتقا و عزل", "helpmusic")],
    [("• پخش ها", "inlinefun"), ("• کاربردی", "karbordi")],
    [("• تیوی و لیست پخش", "inlinemanage")],
    [("• بستن", "closehelp")],
]
check("help panel matches original", kb == expected_help)

# ----------------------------------------------------------------------
# 10. Owner / sudo reply-keyboard panels (exact rows & order)
# ----------------------------------------------------------------------
from handlers.private import panel_fa_owner, panel_fa_sudo

expected_owner = [
    ["📊 وضعیت"],
    ["📑 دریافت فاکتور", "📆 میزان اعتبار"],
    ["تنظیم نرخ پایه"],
    ["تنظیم نرخ ویدیو", "تنظیم نرخ موزیک"],
    ["نرخ فروش موزیک", "نرخ فروش ویدیو"],
    ["📨 ارسال همگانی", "📨 ارسال همگانی گروه ها"],
    ["▪️اجبار ورود فعال", "▫️اجبار ورود غیرفعال"],
    ["📋 لیست گروه های فعال موزیک"],
    ["📁 لیست گروه های تمدید موزیک"],
    ["📋 لیست گروه های فعال ویدیو"],
    ["📁 لیست گروه های تمدید ویدیو"],
    ["⚠️ لیست گروه های فاقد اعتبار"],
    ["❌ حذف سودو", "📌 تنظیم سودو"],
    ["❌ حذف ادمین", "📌 تنظیم ادمین"],
    ["👥 لیست سودو های ربات"],
    ["🗑 حذف گروه ویدیو", "🗑 حذف گروه موزیک"],
    ["📬 ارسال به سودو"],
    ["✏️ تنظیم استارت", "📚 تنظیم درباره ما"],
    ["📬 تنظیم پیامرسان", "📥 تنظیم پی وی"],
    ["📢 تنظیم کانال", "👥 تنظیم گروه"],
    ["تنظیم محدودیت 🔏", "✏️ تنظیم استارت هلپر"],
    ["محدودیت نصب فعال ⚠️", "محدودیت نصب غیرفعال ♻️"],
    ["▪️ خروج خودکار فعال", "▫️ خروج خودکار غیرفعال"],
]
check("owner panel matches original (23 rows)", panel_fa_owner == expected_owner)

expected_sudo = [
    ["📊 وضعیت"],
    ["📑 دریافت فاکتور", "📆 میزان اعتبار"],
    ["📨 ارسال همگانی", "📨 ارسال همگانی گروه ها"],
    ["▪️اجبار ورود فعال", "▫️اجبار ورود غیرفعال"],
    ["📋 لیست گروه های فعال موزیک"],
    ["📁 لیست گروه های تمدید موزیک"],
    ["📋 لیست گروه های فعال ویدیو"],
    ["📁 لیست گروه های تمدید ویدیو"],
    ["⚠️ لیست گروه های فاقد اعتبار"],
    ["❌ حذف سودو", "📌 تنظیم سودو"],
    ["❌ حذف ادمین", "📌 تنظیم ادمین"],
    ["👥 لیست سودو های ربات"],
    ["🗑 حذف گروه ویدیو", "🗑 حذف گروه موزیک"],
    ["▪️ خروج خودکار فعال", "▫️ خروج خودکار غیرفعال"],
]
check("sudo panel matches original (15 rows)", panel_fa_sudo == expected_sudo)

# ----------------------------------------------------------------------
# summary
# ----------------------------------------------------------------------
failed = [r for r in results if not r[1]]
print("\n========================================")
print(f"RESULT: {len(results) - len(failed)}/{len(results)} layout checks passed")
if failed:
    print("FAILED:", [r[0] for r in failed])
    sys.exit(1)
print("=== LAYOUT TEST PASSED ===")

if __name__ == "__main__":
    os._exit(0 if all(r[1] for r in results) else 1)
