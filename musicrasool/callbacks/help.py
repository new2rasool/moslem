"""
Help panel callbacks: سرچ و پخش خودکار / ارتقا و عزل / پخش ها /
کاربردی / تیوی و لیست پخش - with full Persian (original) and
English translations.
"""
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

import i18n
import utils


def _back(uid):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(i18n.t(uid, "• بازگشت", "• Back"), callback_data="backhelp")]]
    )


HELP_VIDEO_FA = """⊹ با این دستور میتوانید موزیک مورد نظر خود را دریافت نمایید.

**📌 به فارسی :**

 ✧ سرچ` { نام موزیک و خواننده }`

**📌 To English :**

 ✧ `search` { نام موزیک و خواننده }

⊹ مثال : سرچ حمید هیراد نیمه جانم

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ با این دستور میتوانید موزیک مورد نظر خود را به صورت خودکار پخش نمایید.

**📌 به فارسی :**

 ✧ پخش خودکار` { نام موزیک و خواننده }`

**📌 To English :**

 ✧ `AutoPlay` { نام موزیک و خواننده }

⊹ مثال : پخش خودکار حمید هیراد نیمه جانم

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ با این قابلیت میتوانید ویدئو مورد نظر خود را از یوتیوب جستجو و به صورت خودکار در ویس کال پخش نمایید.

**📌 به فارسی :**

 ✧ سرچ یوتیوب` { نام ویدئو مورد نظر }`

**📌 To English :**

 ✧ `YoutubeSearch` { نام ویدئو مورد نظر }

⊹ مثال : سرچ یوتیوب آموزش گیتار

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ با این قابلیت میتوانید با استفاده از لینک یوتیوب ، ویدئو مورد نظر خود را به صورت خودکار پخش نمایید.

**📌 به فارسی :**

 ✧ پخش یوتیوب` { لینک یوتیوب }`

**📌 To English :**

 ✧ `YoutubePlay` { لینک یوتیوب }

⊹ مثال : پخش یوتیوب https://www.youtube.com/watch?v=DLly1iiNY

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ با این قابلیت میتوانید با استفاده از لینک دانلود موزیک ، موزیک مورد نظر خود را به صورت خودکار پخش نمایید.

⊹ از تمامی سایت های معتبر ، پخش موزیک امکان پذیر میباشد.

**📌 به فارسی :**

 ✧ پخش لینک` { لینک }`

**📌 To English :**

 ✧ `PlayLink` { لینک }

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ با این قابلیت میتوانید با استفاده از لینک دانلود ویدیو ، ویدیو مورد نظر خود را به صورت خودکار پخش نمایید.

⊹ از تمامی سایت های معتبر ، پخش ویدیو امکان پذیر میباشد.

**📌 به فارسی :**

✧ پخش لینک ویدیو` { لینک }`

**📌 To English :**

  ✧ `PlayLinkVideo` { لینک }
"""

HELP_VIDEO_EN = """⊹ With this command you can get the song you want.

**📌 In Persian :**

 ✧ `سرچ` { song name and singer }

**📌 In English :**

 ✧ `search` { song name and singer }

⊹ Example : search Hamid Hiraad Nimejanam

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ With this command you can automatically play the song you want.

**📌 In Persian :**

 ✧ `پخش خودکار` { song name and singer }

**📌 In English :**

 ✧ `AutoPlay` { song name and singer }

⊹ Example : AutoPlay Hamid Hiraad Nimejanam

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ With this feature you can search a video on YouTube and play it automatically in the voice chat.

**📌 In Persian :**

 ✧ `سرچ یوتیوب` { video name }

**📌 In English :**

 ✧ `YoutubeSearch` { video name }

⊹ Example : YoutubeSearch guitar lesson

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ With this feature you can play a video using a YouTube link automatically.

**📌 In Persian :**

 ✧ `پخش یوتیوب` { youtube link }

**📌 In English :**

 ✧ `YoutubePlay` { youtube link }

⊹ Example : YoutubePlay https://www.youtube.com/watch?v=DLly1iiNY

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ With this feature you can play music using a music download link.

⊹ Playing music from all trusted sites is possible.

**📌 In Persian :**

 ✧ `پخش لینک` { link }

**📌 In English :**

 ✧ `PlayLink` { link }

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ With this feature you can play a video using a video download link.

⊹ Playing video from all trusted sites is possible.

**📌 In Persian :**

 ✧ `پخش لینک ویدیو` { link }

**📌 In English :**

  ✧ `PlayLinkVideo` { link }
"""

HELP_MUSIC_FA = """⊹ با این دستور میتوانید فرد مورد نظر را به لیست مدیران ویدیو اضافه نمایید.
⊹ فقط دسترسی به بخش ویدیو را دارا میباشد.

❪ ریپلای ، یوزرنیم ، آیدی عددی ❫

**📌 به فارسی :**

 ✧ `ترفیع ویدیو`
 ✧ `عزل ویدیو`

**📌 To English :**

 ✧ `PromoteVideo`
 ✧ `DemoteVideo`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈
⊹ با این دستور میتوانید کاربر مورد نظر خود را به لیست مدیران موزیک اضافه نمایید.
⊹ فقط دسترسی به بخش موزیک را دارا می‌باشد.

❪ ریپلای ، یوزرنیم ، آیدی عددی ❫

**📌 به فارسی :**

 ✧ `ترفیع موزیک`
 ✧ `عزل موزیک`

**📌 To English :**

 ✧ `PromoteMusic`
 ✧ `DemoteMusic`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈
⊹ با این دستور میتوانید تمامی مدیران گروه را به لیست مدیران موزیک اضافه نمایید.

**📌 به فارسی :**

 ✧ `پیکربندی موزیک`
 ✧ `پاکسازی مدیران موزیک`
 ✧ `لیست مدیران موزیک`

**📌 To English :**

 ✧ `ConfigMusic`
 ✧ `DelConfigMusic`
 ✧ `ListMusic`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈
⊹ با این دستور میتوانید تمامی مدیران گروه را به لیست مدیران ویدیو اضافه نمایید.

**📌 به فارسی :**

 ✧ `پیکربندی ویدیو`
 ✧ `پاکسازی مدیران ویدیو`
 ✧ `لیست مدیران ویدیو`

**📌 To English :**

 ✧ `ConfigVideo`
 ✧ `DelConfigVideo`
 ✧ `ListVideo`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ با این دستور میتوانید فرد مورد نظر را به مالک ربات ترفیع دهید.

**📌 به فارسی :**

 ✧ `ترفیع مالک`
 ✧ `عزل مالک`
 ✧ `لیست مالکان`

**📌 To English :**

 ✧ `SetCreator`
 ✧ `DelCreator`
 ✧ `CreatorsList`
"""

HELP_MUSIC_EN = """⊹ With this command you can add a person to the video admins list.
⊹ Only video section access is granted.

❪ reply, username, numeric id ❫

**📌 In Persian :**

 ✧ `ترفیع ویدیو`
 ✧ `عزل ویدیو`

**📌 In English :**

 ✧ `PromoteVideo`
 ✧ `DemoteVideo`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈
⊹ With this command you can add a user to the music admins list.
⊹ Only music section access is granted.

❪ reply, username, numeric id ❫

**📌 In Persian :**

 ✧ `ترفیع موزیک`
 ✧ `عزل موزیک`

**📌 In English :**

 ✧ `PromoteMusic`
 ✧ `DemoteMusic`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈
⊹ With this command you can add all group admins to the music admins list.

**📌 In Persian :**

 ✧ `پیکربندی موزیک`
 ✧ `پاکسازی مدیران موزیک`
 ✧ `لیست مدیران موزیک`

**📌 In English :**

 ✧ `ConfigMusic`
 ✧ `DelConfigMusic`
 ✧ `ListMusic`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈
⊹ With this command you can add all group admins to the video admins list.

**📌 In Persian :**

 ✧ `پیکربندی ویدیو`
 ✧ `پاکسازی مدیران ویدیو`
 ✧ `لیست مدیران ویدیو`

**📌 In English :**

 ✧ `ConfigVideo`
 ✧ `DelConfigVideo`
 ✧ `ListVideo`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ With this command you can promote a person to the group owner (creator).

**📌 In Persian :**

 ✧ `ترفیع مالک`
 ✧ `عزل مالک`
 ✧ `لیست مالکان`

**📌 In English :**

 ✧ `SetCreator`
 ✧ `DelCreator`
 ✧ `CreatorsList`
"""

HELP_PLAY_FA = """⊹ با این دستور میتوانید موزیک مورد نظر خود را در ویس کال پخش نمایید.

⊹ این دستور به صورت ریپلای میباشد.

**📌 به فارسی :**

 ✧ `پخش`
 ✧ `توقف پخش`

**📌 To English :**

 ✧ `Play`
 ✧ `StopMusic`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ با این دستور میتوانید ویدیو مورد نظر خود را پخش نمایید.

⊹ این دستور به صورت ریپلای میباشد.

**📌 به فارسی :**

 ✧ `پخش ویدیو`
 ✧ `توقف ویدیو`

**📌 To English :**

 ✧ `PlayVideo`
 ✧ `StopVideo`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ با این قابلیت میتوانید موزیک خود را به کاربر مورد نظر تقدیم کنید.

**📌 به فارسی :**

 ✧ پخش` { یوزرنیم ، آیدی عددی }`

**📌 To English :**

 ✧ `Play` { یوزرنیم ، آیدی عددی }

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ با این قابلیت میتوانید ویدیو خود را به کاربر مورد نظر تقدیم نمایید.

**📌 به فارسی :**

✧ پخش ویدیو` { یوزرنیم ، آیدی عددی }`

**📌 To English :**

 ✧ `PlayVideo` { یوزرنیم ، آیدی عددی }

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ با این دو دستور میتوانید فرایند پخش خود را مکث و مجدد ازسرگیری نمایید.

**📌 به فارسی :**

 ✧ `مکث`
 ✧ `ازسرگیری`

**📌 To English :**

 ✧ `Pause`
 ✧ `Resume`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ با این قابلیت میتوانید فرایند پخش را بیصدا و مجدد باصدا نمایید.

**📌 به فارسی :**

 ✧ `بیصدا`
 ✧ `باصدا`

**📌 To English :**

 ✧ `silent`
 ✧ `unsilent`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ با این دستور میتوانید مقدار صدای موزیک را تنظیم کنید.

**📌 به فارسی :**

✧ صدای موزیک` { مقدار }`

**📌 To English :**

✧ `MusicSound` { مقدار }

⊹ مثال : صدای موزیک 160

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ با این دستور میتوانید مقدار صدای ویدیو را تنظیم کنید.

**📌 به فارسی :**

✧ صدای ویدیو` { مقدار }`

**📌 To English :**

✧ `VideoSound` { مقدار }

⊹ مثال : صدای ویدیو 160
"""

HELP_PLAY_EN = """⊹ With this command you can play the song you want in the voice chat.

⊹ This command works by replying to an audio.

**📌 In Persian :**

 ✧ `پخش`
 ✧ `توقف پخش`

**📌 In English :**

 ✧ `Play`
 ✧ `StopMusic`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ With this command you can play the video you want.

⊹ This command works by replying to a video.

**📌 In Persian :**

 ✧ `پخش ویدیو`
 ✧ `توقف ویدیو`

**📌 In English :**

 ✧ `PlayVideo`
 ✧ `StopVideo`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ With this feature you can dedicate your music to a user.

**📌 In Persian :**

 ✧ `پخش` { username, numeric id }

**📌 In English :**

 ✧ `Play` { username, numeric id }

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ With this feature you can dedicate your video to a user.

**📌 In Persian :**

 ✧ `پخش ویدیو` { username, numeric id }

**📌 In English :**

 ✧ `PlayVideo` { username, numeric id }

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ With these two commands you can pause and resume playback.

**📌 In Persian :**

 ✧ `مکث`
 ✧ `ازسرگیری`

**📌 In English :**

 ✧ `Pause`
 ✧ `Resume`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ With this feature you can mute and unmute playback.

**📌 In Persian :**

 ✧ `بیصدا`
 ✧ `باصدا`

**📌 In English :**

 ✧ `silent`
 ✧ `unsilent`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ With this command you can set the music volume.

**📌 In Persian :**

 ✧ `صدای موزیک` { value }

**📌 In English :**

 ✧ `MusicSound` { value }

⊹ Example : MusicSound 160

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ With this command you can set the video volume.

**📌 In Persian :**

 ✧ `صدای ویدیو` { value }

**📌 In English :**

 ✧ `VideoSound` { value }

⊹ Example : VideoSound 160
"""

HELP_MANAGE_FA = """⊹ با این قابلیت میتوانید موزیک های مورد نظر خود را به لیست پخش اضافه نمایید.

**📌 به فارسی :**

 ✧ `افزودن به لیست`

 ✧ `پخش لیست`

 ✧ `توقف لیست`

 ✧ `لیست پخش`

 ✧ `حذف از لیست`

 ✧ `پاکسازی لیست پخش`

**📌 To English :**

 ✧ `AddToPlayList`

 ✧ `PlayList`

 ✧ `StopList`

 ✧ `ListPlayList`

 ✧ `DelFromPlayList`

 ✧ `CleanPlayList`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ با این دستور میتوانید شبکه های داخلی ( تلویزیون ) و شبکه های بیرون مرزی ( ماهواره ) را تماشا کنید.

⊹ میتوانید شبکه های اصلی صدا سیما یا همان دیجیتال را مانند شبکه های یک ، دو ، سه ، خبر ، ورزش ، تماشا ، نسیم و... به صورت زنده در ویس کال تماشا کنید.

**📌 به فارسی :**

 ✧ `پخش تیوی`

 ✧ `توقف تیوی`

**📌 To English :**

 ✧ `PlayTv`

 ✧ `StopTv`
"""

HELP_MANAGE_EN = """⊹ With this feature you can add songs to the playlist.

**📌 In Persian :**

 ✧ `افزودن به لیست`

 ✧ `پخش لیست`

 ✧ `توقف لیست`

 ✧ `لیست پخش`

 ✧ `حذف از لیست`

 ✧ `پاکسازی لیست پخش`

**📌 In English :**

 ✧ `AddToPlayList`

 ✧ `PlayList`

 ✧ `StopList`

 ✧ `ListPlayList`

 ✧ `DelFromPlayList`

 ✧ `CleanPlayList`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ With this command you can watch domestic (TV) and international (satellite) channels.

⊹ You can watch IRIB channels like Channel 1, 2, 3, News, Varzesh, Tamasha, Nasim and more live in the voice chat.

**📌 In Persian :**

 ✧ `پخش تیوی`

 ✧ `توقف تیوی`

**📌 In English :**

 ✧ `PlayTv`

 ✧ `StopTv`
"""

HELP_UTIL_FA = """⊹ با این دستور میتوانید از آنلاینی ربات های خود اطلاع داشته باشید.

**📌 به فارسی :**

✧ `پینگ`

**📌 To English :**

 ✧ `Ping`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ با این دستور میتوانید از آنلاینی ربات ها مطلع شوید.

**📌 به فارسی :**

 ✧ `ربات`

**📌 To English :**

 ✧ `bot`

 ✧ `robot`
"""

HELP_UTIL_EN = """⊹ With this command you can check whether the bots are online.

**📌 In Persian :**

 ✧ `پینگ`

**📌 In English :**

 ✧ `Ping`

┈┅━─━─━─━─•◈•─━─━─━─━┅┈

⊹ With this command you can check the online status of the bots.

**📌 In Persian :**

 ✧ `ربات`

**📌 In English :**

 ✧ `bot`

 ✧ `robot`
"""


async def handle_help(client, m: CallbackQuery, data: str):
    uid = m.from_user.id
    if data == "helpvideo":
        await m.edit_message_text(i18n.t(uid, HELP_VIDEO_FA, HELP_VIDEO_EN), reply_markup=_back(uid))
        return True
    if data == "helpmusic":
        await m.edit_message_text(i18n.t(uid, HELP_MUSIC_FA, HELP_MUSIC_EN), reply_markup=_back(uid))
        return True
    if data == "inlinefun":
        await m.edit_message_text(i18n.t(uid, HELP_PLAY_FA, HELP_PLAY_EN), reply_markup=_back(uid))
        return True
    if data == "inlinemanage":
        await m.edit_message_text(i18n.t(uid, HELP_MANAGE_FA, HELP_MANAGE_EN), reply_markup=_back(uid))
        return True
    if data == "karbordi":
        await m.edit_message_text(i18n.t(uid, HELP_UTIL_FA, HELP_UTIL_EN), reply_markup=_back(uid))
        return True
    if data == "backhelp":
        await m.edit_message_text(
            i18n.t(uid, "• یکی از گزینه های زیر را انتخاب نمایید : \n┈┅┅━┃صفحه اصلی┃━┅┅┈", "• Choose one of the options below : \n┈┅┅━┃Home┃━┅┅┈"),
            reply_markup=utils.help_keyboard(uid),
        )
        return True
    if data == "closehelp":
        await m.edit_message_text(i18n.t(uid, "• پنل راهنما با موفقیت بسته شد !", "• The help panel was closed successfully !"))
        return True
    return False
