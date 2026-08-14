BotGuardian Enterprise — Merged Build (Defensive)
این بسته حاصل ادغام دو پروژه‌ی قبلی است:
پروژه‌ی پایه
پروژه‌ی افزودنی
BotGuardianEnterprise_defensive_build (Enterprise)
BotGuardian_Sections (Sections Pack)
Enterprise به‌عنوان هسته نگه داشته شده (config، messaging، keyboards، auto-mod، کپچا، لاگ ممیزی، دیتابیس SQLite) و روی آن ۱۵ سکشن با دکوراتور require(role)، جدول‌های risk/reputation/global_meta و پنل‌های اینلاین سوار شده‌اند.
نسخه‌ها و سازگاری
python-telegram-bot[httpx]==21.11.1
aiosqlite>=0.20.0
python-dotenv>=1.0.1
qrcode>=7.4, Pillow>=10.0
هر دو پروژه روی همین نسخه‌ها بودند پس ناسازگاری فریمورکی وجود ندارد.
رفع تداخل‌ها (Conflicts resolved)
تداخل
تصمیم
/settings /userinfo /warn /warnings /unwarn /warnlimit /welcome /captcha /antispam /report /dailyreport
سکشن‌ها مالک شدند (UI غنی‌تر، JSON، risk/rep، پنل گروه‌بندی‌شده). نسخه‌ی Enterprise از bot.py حذف شد تا دوبار ثبت نشود.
db.Database (Enterprise) و XDB (Sections)
ادغام در botguardian.db.Database با همه‌ی جدول‌ها؛ handlers/db_ext.xdb به همان نمونه‌ی واحد اشاره می‌کند (shim).
bot.core Callback dispatcher
handlers/callbacks.on_callback همه‌ی پیشوندها را می‌گیرد و به router.dispatch_callback واگذار می‌کند.
requirements.txt
ادغام = requirements هر دو.
.env.example
همان قبلی + خط AI_PROVIDER.
ساختار نهایی
BotGuardianEnterprise_Final/
├── .env.example
├── README.md
├── requirements.txt
├── termux_install.sh
└── botguardian/
    ├── __init__.py
    ├── bot.py            ← entry: bot.run / python -m botguardian.bot
    ├── config.py         ← Settings from .env (unchanged from Enterprise)
    ├── constants.py      ← constants merged
    ├── db.py             ← unified Database (enterprise + sections)
    ├── roles.py          ← OWNER/ADMIN/SPECIAL/PUBLIC
    ├── handlers/
    │   ├── __init__.py
    │   ├── callbacks.py  ← unified dispatcher
    │   ├── commands.py   ← enterprise commands kept
    │   ├── members.py    ← welcome/captcha (Enterprise)
    │   ├── messages.py   ← auto-mod (anti-spam/link/forward/burst/dup)
    │   ├── db_ext.py     ← re-export `xdb = db`
    │   ├── permission.py ← @require(role) decorator
    │   ├── router.py     ← register_all + dispatch_callback
    │   └── sections/     ← 15 section modules
    │       ├── admin_admin.py        (userinfo + inline panel)
    │       ├── admin_ai.py           (AI scan / summary / suggest)
    │       ├── admin_antipromo.py    (name/bio/links/raid/...)
    │       ├── admin_autolock.py     (schedule + auto open)
    │       ├── admin_cleanup.py      (intervals + media types)
    │       ├── admin_forcesub.py     (mandatory join)
    │       ├── admin_group.py        (/settings, /dashboard, backup)
    │       ├── admin_locks.py        (17 lock flags)
    │       ├── admin_members.py      (/welcome, /captcha, /raidlock)
    │       ├── admin_owner.py        (owner panel — license/subs/...)
    │       ├── admin_reports.py      (daily/weekly/monthly/secreport)
    │       ├── admin_reports_user.py (/report — public)
    │       ├── admin_security.py     (14 modules + level)
    │       ├── admin_tools.py        (QR / virus / ping / whois)
    │       ├── admin_warnings.py     (/warn /risk /reputation)
    │       └── sec_spam.py           (/antispam)
    └── utils/
        ├── __init__.py
        ├── keyboards.py  ← settings / captcha / admin panel
        ├── messaging.py  ← mute/ban/kick/links/delete helpers
        └── permissions.py ← admin / protected-target helpers
اجرا
python -m pip install -r requirements.txt
cp .env.example .env
# مقداردهی BOT_TOKEN و OWNER_IDS در .env
python -m botguardian.bot
نصب در Termux
bash termux_install.sh
نگاشت فرمان‌ها (خلاصه)
Enterprise core: /start /help /antilink /anti_forward /mute /unmute /kick /ban /unban /pin /stats /id
Settings group: /settings /dashboard /setowner /promote /demote /adminrights /vip /blacklist /whitelist /audit /adminlog /backup /restore /resetsettings /transfercfg
Locks: /lock, ۱۷ پرچم
Anti-promo: /antipromo /adscan /purgeads
Anti-spam: /antispam + خودکار در messages.py (burst/dup/link/forward)
Force-sub: /forcesub on|off|add|del|messages|...
Cleanup: /cleanup + ۱۲ پرچم
Autolock: /autolock on|off|mode|time|days|holiday|event
Warnings: /warn /warnings /unwarn /warnlimit /risk /reputation + اقدام خودکار در حد
Security: /security (۱۴ ماژول + sec_level)
AI: /ai /aiscan /aisummary /aisuggest
Members: /welcome /captcha /raidlock /lang
Reports: /dailyreport /weekly /monthly /secreport /adminreport /userstats /spamstats /riskstats /report
Tools: /qr /shorten /scanurl /virusscan /whois /iplookup /ping
Owner: /owner panel|license|monitor|plugins|update|users|groups|subs
Info: /userinfo (پنل اینلاین اخطار/میوت/کیک/بن/آنبن/ریست)
امنیت و محدوده
این بات صرفاً دفاعی است. هیچ قابلیت تهاجمی، استخراج IP کاربران، حمله به گروه‌های دیگر یا عملیات خارج از Bot API تلگرام در آن قرار داده نشده است. /iplookup و /whois صرفاً پاسخ stub محلی دارند.
