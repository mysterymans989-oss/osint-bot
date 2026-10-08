#!/usr/bin/env python3
# ---------------------------------------------------------------
#  Data Utility Bot — Render deployment
# ---------------------------------------------------------------
import os, threading, json, time, logging, html, random, string
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("Bot")

# ── Health server for Render (starts before anything else) ──
def _health_server():
    port = int(os.environ.get("PORT", 8080))
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        def log_message(self, *a): pass
    srv = HTTPServer(("0.0.0.0", port), H)
    log.info(f"health server on :{port}")
    srv.serve_forever()

threading.Thread(target=_health_server, daemon=True).start()

# ── Deps ──
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest

# ── Config ──
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "8725590551:AAG37rx90JtWahwfE0vojk7-Qyff85ycWWA")
MAIN_OWNER     = int(os.environ.get("MAIN_OWNER", "6426979067"))
SUPER_ADMINS   = [int(x) for x in os.environ.get("SUPER_ADMINS", "8769965268").split(",")]
LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", "-1003995553773"))

SUPER_ADMIN_NAME = "@HACKERXWHITE"
SUPER_ADMIN_LINK = "https://t.me/HACKERXWHITE"

MY_CHANNELS = [
    {"id": "-1004483741432", "link": "https://t.me/+KYUYK9pEOlg1MWY1", "title": "OSINT MASTER"},
    {"id": "-1003030513943", "link": "https://t.me/+Lo-NASnm0D1jYjJl", "title": "NUMBER TO INFORMATION"},
    {"id": "-1004295471175", "link": "https://t.me/BUILDWITHAPI",       "title": "BUILD WITH API"},
    {"id": "-1003995553773", "link": "https://t.me/the_leaker_cyber",   "title": "THE LEAKER CYBER"},
]

API_BASE = "https://api.sarkariallupdates.com/api"
API_KEY  = os.environ.get("API_KEY", "30day")

RATE_LIMIT_SEC   = 5
VERIFY_TTL_SEC   = 86400
FREE_CREDITS     = 3
LOOKUP_COST      = 1
REFERRAL_CREDITS = 2
DAILY_CLAIM      = 1
DAILY_COOLDOWN   = 86400
DATA_FILE        = "data.json"

VERIFIED_USERS = {}
USER_PAGE = {}

# ── Emoji map ──
E = {
    "fire":("5289722755871162900","🔥"),"star":("5372849966689566579","⭐"),
    "rocket":("5359664288241829619","🚀"),"crown":("6237927637906364256","👑"),
    "shield":("6235476345451716705","🛡"),"money":("6244678063775289843","💰"),
    "phone":("6239930832128056797","📱"),"check":("4958689671950369798","✅"),
    "cross":("4958900559139570572","❌"),"warn":("4958526153955476488","⚠️"),
    "lock":("4956719506027185156","🔒"),"gift":("5084613633418199991","🎁"),
    "bell":("5098265504796115765","🔔"),"gear":("5116414868357907335","⚙️"),
    "id":("5346053564679790988","🆔"),"search":("5231012362145514761","🔍"),
    "pin":("5312361253610475393","📍"),"bank":("5260450153463183867","🏦"),
    "user":("5372981976623366968","👤"),"people":("5372849966689566579","👥"),
    "info":("5282843764451195532","ℹ️"),"back":("5415790371573793226","🔙"),
    "chart":("5348125954244719135","📊"),"clipboard":("5359543312895150983","📋"),
    "trash":("5445166225618490890","🗑"),"plus":("5391112412403435263","➕"),
    "link":("5289763021089105327","🔗"),"key":("5413482869984596798","🔑"),
    "card":("5332361253610475393","💳"),"auto":("5386441443712919850","🚗"),
    "clock":("5346053564679790988","🕐"),"spark":("5312361253610475393","✨"),
    "scroll":("5397558519973609028","📜"),
}

def tg(k):
    e, f = E.get(k, ("", "⭐"))
    return f'<tg-emoji emoji-id="{e}">{f}</tg-emoji>' if e else f

def eid(k): return E.get(k, ("", ""))[0]
def esc(s): return html.escape(str(s))

def sc(t):
    return t.translate(str.maketrans(
        "abcdefghijklmnopqrstuvwxyz",
        "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    ))

def ibtn(t, d, k=None):
    kw = {"text": t, "callback_data": d}
    if k and eid(k): kw["icon_custom_emoji_id"] = eid(k)
    return InlineKeyboardButton(**kw)

def iurl(t, u, k=None):
    kw = {"text": t, "url": u}
    if k and eid(k): kw["icon_custom_emoji_id"] = eid(k)
    return InlineKeyboardButton(**kw)

def rbtn(t, s="primary", k=None):
    kw = {"text": t, "style": s}
    if k and eid(k): kw["icon_custom_emoji_id"] = eid(k)
    return KeyboardButton(**kw)

# ── Store ──
def _def():
    return {
        "users": {}, "banned": [],
        "stats": {"total_queries": 0, "per_endpoint": {}, "credits_spent": 0},
        "redeem_codes": {},
        "settings": {"free_credits": FREE_CREDITS, "lookup_cost": LOOKUP_COST},
    }

def load():
    if not os.path.exists(DATA_FILE):
        d = _def(); save(d); return d
    try:
        with open(DATA_FILE) as f: d = json.load(f)
        for k, v in _def().items(): d.setdefault(k, v)
        return d
    except Exception:
        return _def()

def save(d):
    with open(DATA_FILE, "w") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)

U = load()

def reg(uid, nm, un):
    k = str(uid)
    if k not in U["users"]:
        U["users"][k] = {
            "name": nm, "username": un, "joined": int(time.time()),
            "uses": 0, "rich": True, "credits": FREE_CREDITS,
            "ref_code": None, "referred_by": None, "last_daily": 0,
            "phone": None, "policy_accepted": False, "policy_accepted_at": 0,
        }
        save(U); return True
    for f, v in [("rich",True),("credits",0),("last_daily",0),
                 ("phone",None),("policy_accepted",False),("policy_accepted_at",0)]:
        U["users"][k].setdefault(f, v)
    return False

def crd(uid): return U["users"].get(str(uid), {}).get("credits", 0)

def acr(uid, n):
    k = str(uid)
    if k not in U["users"]:
        U["users"][k] = {"credits":0,"uses":0,"rich":True,"joined":int(time.time()),
                         "name":"User","username":"","ref_code":None,
                         "referred_by":None,"last_daily":0,"phone":None,
                         "policy_accepted":False,"policy_accepted_at":0}
    U["users"][k]["credits"] = U["users"][k].get("credits", 0) + n
    save(U); return U["users"][k]["credits"]

def dcr(uid, n):
    k = str(uid)
    if k not in U["users"]: return False
    c = U["users"][k].get("credits", 0)
    if c < n: return False
    U["users"][k]["credits"] = c - n; save(U); return True

def rich_on(uid): return U["users"].get(str(uid), {}).get("rich", True)

def set_rich(uid, v):
    if str(uid) in U["users"]:
        U["users"][str(uid)]["rich"] = v; save(U)

def get_ph(uid): return U["users"].get(str(uid), {}).get("phone")

def set_ph(uid, p):
    if str(uid) in U["users"]:
        U["users"][str(uid)]["phone"] = p; save(U)

def pol_ok(uid): return U["users"].get(str(uid), {}).get("policy_accepted", False)

def set_pol(uid):
    if str(uid) in U["users"]:
        U["users"][str(uid)]["policy_accepted"] = True
        U["users"][str(uid)]["policy_accepted_at"] = int(time.time())
        save(U)

def bump(uid, ep):
    k = str(uid)
    if k in U["users"]:
        U["users"][k]["uses"] = U["users"][k].get("uses", 0) + 1
    U["stats"]["total_queries"] = U["stats"].get("total_queries", 0) + 1
    U["stats"]["credits_spent"] = U["stats"].get("credits_spent", 0) + LOOKUP_COST
    U["stats"].setdefault("per_endpoint", {})
    U["stats"]["per_endpoint"][ep] = U["stats"]["per_endpoint"].get(ep, 0) + 1
    save(U)

def banned(uid): return uid in U.get("banned", [])
def isadm(uid): return uid == MAIN_OWNER or uid in SUPER_ADMINS

def refcode(uid):
    k = str(uid)
    if k in U["users"] and U["users"][k].get("ref_code"):
        return U["users"][k]["ref_code"]
    while True:
        c = "REF" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if not any(u.get("ref_code") == c for u in U["users"].values()): break
    if k in U["users"]:
        U["users"][k]["ref_code"] = c; save(U)
    return c

def proc_ref(nu, code):
    ref = None
    for us, u in U["users"].items():
        if u.get("ref_code") == code: ref = int(us); break
    if not ref: return False, "Invalid code.", None
    if ref == nu: return False, "Own code not allowed.", None
    k = str(nu)
    if U["users"].get(k, {}).get("referred_by"): return False, "Already referred.", None
    acr(nu, REFERRAL_CREDITS); acr(ref, REFERRAL_CREDITS)
    U["users"][k]["referred_by"] = ref; save(U)
    return True, f"+{REFERRAL_CREDITS} credits!", ref

def claim(uid):
    k = str(uid)
    if k not in U["users"]: return False, 0, 0
    lst = U["users"][k].get("last_daily", 0)
    now = int(time.time())
    if now - lst < DAILY_COOLDOWN: return False, 0, DAILY_COOLDOWN - (now - lst)
    U["users"][k]["last_daily"] = now
    return True, acr(uid, DAILY_CLAIM), 0

# ── Force-join ──
async def mem_ok(bot, uid, cid):
    try:
        m = await bot.get_chat_member(chat_id=int(cid), user_id=uid)
        return m.status in ("member", "administrator", "creator")
    except Exception: return False

async def all_join(bot, uid):
    if isadm(uid): return True, []
    now = time.time()
    if uid in VERIFIED_USERS and (now - VERIFIED_USERS[uid]) < VERIFY_TTL_SEC:
        return True, []
    miss = [c for c in MY_CHANNELS if not await mem_ok(bot, uid, c["id"])]
    if not miss:
        VERIFIED_USERS[uid] = now; return True, []
    return False, miss

def jtext(miss):
    L = [f"{tg('cross')} <b>{sc('join all channels')}</b>\n",
         f"{tg('bell')} <i>Required:</i>\n"]
    for c in miss: L.append(f"• {tg('bell')} <b>{c['title']}</b>")
    L.append(f"\n{tg('warn')} <i>Then tap CHECK JOIN.</i>")
    return "\n".join(L)

def jkb(miss):
    rows = [[iurl(f"JOIN {c['title']}", c["link"], "bell")] for c in miss]
    rows.append([ibtn("CHECK JOIN", "fj:check", "check")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ── Phone gate ──
def ptext():
    return (
        f"{tg('phone')} <b>{sc('verify your number')}</b>\n\n"
        f"{tg('shield')} One-time phone verification is required.\n\n"
        f"{tg('lock')} <b>Your number:</b>\n"
        f"• Stored privately\n• Visible only to owner and admins\n"
        f"• Never shared externally\n\n"
        f"{tg('warn')} <i>Tap the button below.</i>"
    )

def pkb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 SHARE MY NUMBER", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True,
    )

# ── Policy ──
POLICY = (
    f"{tg('scroll')} <b>TERMS OF SERVICE — FAIR USE POLICY</b>\n"
    f"<b>Data Utility Bot</b>\n"
    f"<i>Last updated: October 2026</i>\n"
    f"━━━━━━━━━━━━━━━━━━━━\n\n"
    f"{tg('warn')} <b>1. ACCEPTANCE</b>\n"
    f"Tapping <b>I ACCEPT</b> binds you to every clause. Declining ends access.\n\n"
    f"{tg('shield')} <b>2. NATURE OF SERVICE</b>\n"
    f"This bot aggregates public data via third-party APIs. Research and "
    f"educational tool only — not a private investigation service, not legal "
    f"advisory, not an authority.\n\n"
    f"{tg('lock')} <b>3. LAWFUL USE</b>\n"
    f"Lawful purposes only, under the IT Act 2000, DPDP Act 2023, and all "
    f"applicable law.\n\nForbidden:\n"
    f"• Stalking, harassment, intimidation\n"
    f"• Fraud, identity theft, impersonation\n"
    f"• Privacy or data rights violations\n"
    f"• Assistance in criminal activity\n"
    f"• Unauthorized surveillance\n"
    f"• Targeting minors\n\n"
    f"{tg('cross')} <b>4. OWNER DISCLAIMER — NO LIABILITY</b>\n"
    f"Owner, developer, maintainer, host, admins and moderators (\"Operators\") "
    f"disclaim all liability for:\n\n"
    f"• Any misuse of data obtained\n"
    f"• Any harm, loss or damage caused by user actions\n"
    f"• Any legal consequence of user conduct\n"
    f"• Any inaccuracy in third-party API data\n"
    f"• Any unauthorized access or leak of user data\n"
    f"• Any service interruption or data loss\n"
    f"• Any third-party claims\n\n"
    f"Operators act solely as passive technical intermediaries. All queries "
    f"are user-initiated. No knowledge of, control over, or responsibility "
    f"for user intent.\n\n"
    f"{tg('warn')} <b>5. USER RESPONSIBILITY</b>\n"
    f"You alone are responsible for how you use the data and any consequence. "
    f"You are the sole offender if your use violates law.\n\n"
    f"{tg('lock')} <b>6. DATA COLLECTED</b>\n"
    f"Telegram ID, name, username, phone, join date, query count, credit "
    f"balance, lookup metadata. Visible only to owner and admins.\n\n"
    f"{tg('cross')} <b>7. NO WARRANTY</b>\n"
    f"Provided AS IS, AS AVAILABLE, without warranty of any kind.\n\n"
    f"{tg('gear')} <b>8. MODIFICATIONS</b>\n"
    f"Service and policy may change at any time. Continued use = acceptance.\n\n"
    f"{tg('crown')} <b>9. GOVERNING LAW</b>\n"
    f"Exclusive jurisdiction of the courts of India.\n\n"
    f"{tg('warn')} <b>10. INDEMNIFICATION</b>\n"
    f"You hold Operators harmless against all claims arising from your use "
    f"of the bot or your violation of these terms.\n\n"
    f"━━━━━━━━━━━━━━━━━━━━\n"
    f"{tg('fire')} <b>Tapping I ACCEPT confirms:</b>\n\n"
    f"{tg('check')} Age 18+\n"
    f"{tg('check')} Lawful use only\n"
    f"{tg('check')} Full responsibility accepted\n"
    f"{tg('check')} Operators not liable for misuse\n"
    f"{tg('check')} Jurisdiction clause accepted\n\n"
    f"<i>Do not use if you disagree with any part.</i>"
)

def pkb_policy():
    return InlineKeyboardMarkup(inline_keyboard=[
        [ibtn("✅ I ACCEPT", "policy:accept", "check")],
        [ibtn("❌ I DECLINE", "policy:decline", "cross")],
    ])

# ── Endpoints ──
ENDPOINTS = {
    "num_info": {"label":"NUMBER INFO","emoji":"phone","desc":"Mobile full info",
                 "param":"num","example":"9162516577","hint":"10-digit mobile"},
    "vehicle_full": {"label":"VEHICLE FULL","emoji":"auto","desc":"RC details",
                     "param":"xr","example":"KL41V3504","hint":"Vehicle reg no."},
    "vehicle_to_number": {"label":"VEHICLE TO NUMBER","emoji":"auto","desc":"Owner mobile from RC",
                          "param":"xr","example":"KL41V3504","hint":"Vehicle reg no."},
    "pan2dob_name": {"label":"PAN TO NAME","emoji":"id","desc":"Name + DOB",
                     "param":"pan2dob_name","example":"cnkpk7230d","hint":"10-char code"},
    "aadhaar2pan": {"label":"AADHAAR TO PAN","emoji":"id","desc":"Linked PAN",
                    "param":"aadhaar2pan","example":"123456789012","hint":"12-digit"},
    "imei": {"label":"IMEI INFO","emoji":"phone","desc":"IMEI lookup",
             "param":"imei","example":"123456789012345","hint":"15-digit IMEI"},
    "pincode": {"label":"PINCODE INFO","emoji":"pin","desc":"Pincode details",
                "param":"pincode","example":"110001","hint":"6-digit"},
    "ifse": {"label":"IFSC INFO","emoji":"bank","desc":"Bank branch",
             "param":"ifse","example":"SBIN0001234","hint":"11-char IFSC"},
    "tg": {"label":"TELEGRAM TO NUMBER","emoji":"user","desc":"TG to number",
           "param":"q","example":"@Perfectamit65","hint":"TG username with @"},
    "addhaar2num": {"label":"AADHAAR TO NUMBER","emoji":"id","desc":"Mobile from Aadhaar",
                    "param":"q","example":"123456789012","hint":"12-digit"},
}

# ── Reply keyboard pages ──
KB_PAGES = [
    [
        [("📱 NUMBER INFO","primary","phone"),("🚗 VEHICLE FULL","primary","auto")],
        [("🔁 VEHICLE→NUM","primary","auto"),("🆔 PAN 2 NAME","primary","id")],
        [("🪪 AADHAAR 2 PAN","primary","id"),("🔢 AADHAAR 2 NUM","primary","id")],
        [("◀️ PREV","danger","back"),("NEXT ▶️","primary","rocket")],
    ],
    [
        [("💬 TG TO NUMBER","primary","user"),("📲 IMEI INFO","primary","phone")],
        [("📍 PINCODE INFO","primary","pin"),("🏦 IFSC INFO","primary","bank")],
        [("◀️ PREV","danger","back"),("NEXT ▶️","primary","rocket")],
    ],
    [
        [("🎁 DAILY CLAIM","success","gift"),("🎁 REDEEM CODE","success","gift")],
        [("💰 BALANCE","success","money"),("👥 REFER","success","people")],
        [("🛒 BUY CREDITS","success","card"),("📊 MY STATS","success","chart")],
        [("◀️ PREV","danger","back"),("NEXT ▶️","primary","rocket")],
    ],
    [
        [("🎴 RICH: TOGGLE","primary","gear"),("ℹ️ HELP","primary","info")],
        [("👑 OWNER PANEL","primary","crown")],
        [("◀️ PREV","danger","back"),("HOME 🏠","primary","back")],
    ],
]

def pgkb(p):
    p = max(0, min(p, len(KB_PAGES) - 1))
    grid = [[rbtn(l, s, e) for (l, s, e) in row] for row in KB_PAGES[p]]
    return ReplyKeyboardMarkup(
        keyboard=grid, resize_keyboard=True, is_persistent=True,
        input_field_placeholder=f"Page {p+1}/{len(KB_PAGES)} — tap a tool",
    )

L2E = {
    "📱 NUMBER INFO": "num_info",
    "🚗 VEHICLE FULL": "vehicle_full",
    "🔁 VEHICLE→NUM": "vehicle_to_number",
    "🆔 PAN 2 NAME": "pan2dob_name",
    "🪪 AADHAAR 2 PAN": "aadhaar2pan",
    "🔢 AADHAAR 2 NUM": "addhaar2num",
    "💬 TG TO NUMBER": "tg",
    "📲 IMEI INFO": "imei",
    "📍 PINCODE INFO": "pincode",
    "🏦 IFSC INFO": "ifse",
}

# ── API ──
async def api_call(ep, pn, val):
    url = f"{API_BASE}?={ep}&key={API_KEY}&{pn}={val}"
    to = aiohttp.ClientTimeout(total=20)
    try:
        async with aiohttp.ClientSession(timeout=to) as s:
            async with s.get(url) as r:
                t = await r.text()
                if r.status != 200:
                    return {"ok": False, "err": f"HTTP {r.status}: {t[:200]}"}
                try: return {"ok": True, "data": json.loads(t)}
                except Exception:
                    return {"ok": False, "err": f"Bad JSON: {t[:200]}"}
    except asyncio.TimeoutError:
        return {"ok": False, "err": "Timeout"}
    except Exception as e:
        return {"ok": False, "err": str(e)[:200]}

# ── Format ──
def pj(d, ind=0, mx=8):
    pad = "  " * ind
    if ind > mx: return f"{pad}…"
    if d is None: return f"{pad}<i>null</i>"
    if isinstance(d, bool): return f"{pad}<b>{'true' if d else 'false'}</b>"
    if isinstance(d, (int, float)): return f"{pad}<b>{d}</b>"
    if isinstance(d, str): return f"{pad}{esc(d) if d.strip() else '<i>-</i>'}"
    if isinstance(d, list):
        if not d: return f"{pad}<i>[]</i>"
        o = []
        for i, x in enumerate(d):
            if isinstance(x, (dict, list)):
                o.append(f"{pad}<b>[{i}]</b>\n{pj(x, ind+1, mx)}")
            else:
                o.append(f"{pad}• {pj(x, 0, mx)}")
        return "\n".join(o)
    if isinstance(d, dict):
        if not d: return f"{pad}<i>{{}}</i>"
        o = []
        for k, v in d.items():
            key = esc(str(k)).replace("_", " ")
            if isinstance(v, (dict, list)):
                o.append(f"{pad}{tg('gear')} <b>{key.upper()}</b>\n{pj(v, ind+1, mx)}")
            else:
                o.append(f"{pad}{tg('gear')} <b>{key.upper()}</b> : {pj(v, 0, mx)}")
        return "\n".join(o)
    return f"{pad}{esc(d)}"

def trunc(s, lim=3900):
    if len(s) <= lim: return s
    c = s[:lim]; nl = c.rfind("\n")
    if nl > 200: c = c[:nl]
    o = c + "\n<i>…truncated</i>"
    for t in ("i", "b", "code", "pre"):
        a = o.count(f"<{t}>"); b = o.count(f"</{t}>")
        if a > b: o += f"</{t}>" * (a - b)
    return o

# ── Rich message ──
async def send_rich(tok, chat, hc):
    url = f"https://api.telegram.org/bot{tok}/sendRichMessage"
    payload = {"chat_id": chat, "rich_message": {"html": hc}}
    to = aiohttp.ClientTimeout(total=15)
    try:
        async with aiohttp.ClientSession(timeout=to) as s:
            async with s.post(url, json=payload) as r:
                d = await r.json(content_type=None)
                if d.get("ok"): return {"ok": True, "result": d["result"]}
                return {"ok": False, "err": d.get("description", "?")}
    except Exception as e:
        return {"ok": False, "err": str(e)[:200]}

def rcard(lbl, val, d):
    L = []
    def add(k, v, dep=0):
        if dep > 2 or len(L) >= 14: return
        key = esc(str(k)).replace("_", " ").title()
        if isinstance(v, dict):
            for kk, vv in v.items(): add(kk, vv, dep+1)
        elif isinstance(v, list):
            if v and not isinstance(v[0], (dict, list)):
                L.append(f"<p><b>{key}:</b> {esc(', '.join(str(x) for x in v[:8]))}</p>")
            else:
                for x in v[:4]:
                    if isinstance(x, dict):
                        for kk, vv in x.items(): add(kk, vv, dep+1)
        elif v is None or str(v).strip() == "": return
        else:
            L.append(f"<p><b>{key}:</b> <code>{esc(v)}</code></p>")
    if isinstance(d, dict):
        for k, v in d.items(): add(k, v)
    elif isinstance(d, list):
        for i, x in enumerate(d[:8]): add(f"item_{i+1}", x)
    body = "\n".join(L) if L else "<p><i>No fields</i></p>"
    return f"""<h2>{lbl}</h2>
<blockquote>Query: <code>{esc(val)}</code><cite>DATA BOT</cite></blockquote>
{body}
<tg-button-row>
  <tg-button type="callback_data" data="osint:home" style="primary">Back</tg-button>
  <tg-button type="url" url="{SUPER_ADMIN_LINK}" style="success">Owner</tg-button>
</tg-button-row>
""".strip()

# ── Inline keyboards ──
def bkb(tgt="osint:home"):
    return InlineKeyboardMarkup(inline_keyboard=[[ibtn("BACK", tgt, "back")]])

def ckb():
    return InlineKeyboardMarkup(inline_keyboard=[[ibtn("CANCEL", "osint:home", "cross")]])

def akb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [ibtn("ADD CREDITS","admin:credits_add","money"),
         ibtn("DEDUCT CREDITS","admin:credits_deduct","cross")],
        [ibtn("ADD TO ALL","admin:credits_add_all","money"),
         ibtn("DEDUCT ALL","admin:credits_deduct_all","cross")],
        [ibtn("GEN REDEEM","admin:redeem_gen","gift"),
         ibtn("DEL REDEEM","admin:redeem_del","trash")],
        [ibtn("LIST REDEEM","admin:redeem_list","clipboard")],
        [ibtn("USER LIST","admin:users_list","people")],
        [ibtn("BAN","admin:ban","cross"),ibtn("UNBAN","admin:unban","check")],
        [ibtn("BROADCAST","admin:broadcast","bell")],
        [ibtn("BACK","osint:home","back")],
    ])

# ── Texts ──
def htext(uid):
    u = U["users"].get(str(uid), {})
    nm = esc(u.get("name", "User"))
    us = u.get("uses", 0)
    cr = u.get("credits", 0)
    role = (f"{tg('crown')} OWNER" if uid == MAIN_OWNER else
            (f"{tg('shield')} ADMIN" if uid in SUPER_ADMINS else
             f"{tg('user')} USER"))
    rs = f"{tg('check')} ON" if rich_on(uid) else f"{tg('cross')} OFF"
    return (
        f"{tg('fire')} <b>{sc('data utility bot')}</b>\n"
        f"<b>Owner:</b> {SUPER_ADMIN_NAME}\n\n"
        f"{tg('user')} <b>Name :</b> {nm}\n"
        f"{tg('shield')} <b>Role :</b> {role}\n"
        f"{tg('money')} <b>Credits :</b> {cr}\n"
        f"{tg('rocket')} <b>Uses :</b> {us}\n"
        f"{tg('gear')} <b>Rich cards :</b> {rs}\n"
        f"{tg('gear')} <b>Cost/lookup :</b> {LOOKUP_COST}\n\n"
        f"<i>{sc('tap a tool below')}</i>"
    )

def help_txt():
    L = [f"{tg('fire')} <b>{sc('help')}</b>\n",
         f"{tg('money')} <b>Economy:</b>",
         f"• New users get <b>{FREE_CREDITS} credits</b>",
         f"• Each lookup costs <b>{LOOKUP_COST} credit</b>",
         f"• Daily claim: <b>+{DAILY_CLAIM}</b> every 24h",
         f"• Referral bonus: <b>+{REFERRAL_CREDITS}</b>",
         "",
         f"{tg('gear')} <b>Tools:</b>"]
    for k, e in ENDPOINTS.items():
        L.append(f"• {tg(e['emoji'])} <b>{e['label']}</b> — {e['desc']}")
    L.append(f"\n{tg('bell')} <b>Force-join:</b> all {len(MY_CHANNELS)} channels")
    L.append(f"{tg('phone')} <b>Phone share:</b> required")
    L.append(f"{tg('scroll')} <b>Policy:</b> required")
    L.append(f"{tg('warn')} <i>Rate limit: {RATE_LIMIT_SEC}s</i>")
    L.append(f"\n{tg('crown')} Contact: {SUPER_ADMIN_NAME}")
    return "\n".join(L)

def stats_txt(uid):
    u = U["users"].get(str(uid), {})
    j = datetime.fromtimestamp(u.get("joined", 0)).strftime('%d/%m/%Y %H:%M') if u.get("joined") else '-'
    return (
        f"{tg('chart')} <b>{sc('your stats')}</b>\n\n"
        f"{tg('user')} Name : {esc(u.get('name','User'))}\n"
        f"{tg('phone')} Phone : <code>{u.get('phone','—')}</code>\n"
        f"{tg('money')} Credits : <b>{u.get('credits',0)}</b>\n"
        f"{tg('rocket')} Uses : <b>{u.get('uses',0)}</b>\n"
        f"{tg('gear')} Joined : {j}"
    )

def admin_txt():
    tot = U["stats"].get("total_queries", 0)
    sp = U["stats"].get("credits_spent", 0)
    per = U["stats"].get("per_endpoint", {})
    cd = len(U.get("redeem_codes", {}))
    L = [
        f"{tg('crown')} <b>{sc('admin panel')}</b>\n",
        f"{tg('people')} Users : <b>{len(U['users'])}</b>",
        f"{tg('cross')} Banned : <b>{len(U.get('banned',[]))}</b>",
        f"{tg('gift')} Codes : <b>{cd}</b>",
        f"{tg('rocket')} Queries : <b>{tot}</b>",
        f"{tg('money')} Credits spent : <b>{sp}</b>\n",
        f"<b>Per endpoint:</b>",
    ]
    if not per: L.append("  <i>-</i>")
    else:
        for k, v in sorted(per.items(), key=lambda x: -x[1])[:10]:
            e = ENDPOINTS.get(k, {})
            L.append(f"  • {tg(e.get('emoji','gear'))} {e.get('label',k)} : <b>{v}</b>")
    return "\n".join(L)

# ── FSM ──
class St(StatesGroup):
    inp = State()
    rc = State()
    ab = State()
    au = State()
    ac1 = State()
    ac2 = State()
    dc1 = State()
    dc2 = State()
    aa = State()
    da = State()
    rg1 = State()
    rg2 = State()
    rd = State()
    bc = State()

R = Router()
LAST = {}

# ── Log helper ──
async def logch(bot, uid, name, un, ep, val, ok, rch, cr=None, ph=None):
    e = ENDPOINTS.get(ep, {})
    lbl = e.get("label", ep)
    ek = e.get("emoji", "gear")
    st = f"{tg('check')} OK" if ok else f"{tg('cross')} FAIL"
    rt = f"{tg('spark')} rich" if rch else f"{tg('phone')} plain"
    cl = f"{tg('money')} Bal : <b>{cr}</b>\n" if cr is not None else ""
    pl = f"{tg('phone')} Ph : <code>{esc(ph)}</code>\n" if ph else ""
    try:
        await bot.send_message(LOG_CHANNEL_ID,
            f"{tg('fire')} <b>LOOKUP</b>\n\n"
            f"{tg('user')} {esc(name)} ({esc(un)})\n"
            f"{tg('id')} UID : <code>{uid}</code>\n"
            f"{pl}"
            f"{tg(ek)} Tool : <b>{lbl}</b>\n"
            f"{tg('search')} Input : <code>{esc(val)}</code>\n"
            f"{tg('gear')} Result : <b>{st}</b>\n"
            f"{cl}"
            f"{tg('gear')} Delivery : {rt}\n"
            f"{tg('clock')} {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            parse_mode="HTML")
    except Exception as e: log.warning(f"logch: {e}")

# ── Gate ──
async def gate(bot, uid, chat):
    if isadm(uid): return True
    j, m = await all_join(bot, uid)
    if not j:
        await bot.send_message(chat, jtext(m), reply_markup=jkb(m),
                               parse_mode="HTML", disable_web_page_preview=True)
        return False
    if not get_ph(uid):
        await bot.send_message(chat, ptext(), reply_markup=pkb(), parse_mode="HTML")
        return False
    if not pol_ok(uid):
        await bot.send_message(chat, POLICY, reply_markup=pkb_policy(), parse_mode="HTML")
        return False
    return True

# ── /start ──
@R.message(CommandStart())
async def cstart(msg: Message, state: FSMContext):
    await state.clear()
    uid = msg.from_user.id
    nm = msg.from_user.full_name or "User"
    un = f"@{msg.from_user.username}" if msg.from_user.username else "no username"
    if banned(uid):
        await msg.answer(f"{tg('cross')} <b>Banned.</b>\nContact {SUPER_ADMIN_NAME}", parse_mode="HTML")
        return
    isnew = reg(uid, nm, un)
    a = msg.text.split()
    if len(a) > 1 and a[1].startswith("REF") and isnew:
        ok, t, ref = proc_ref(uid, a[1])
        if ok and ref:
            try:
                await msg.bot.send_message(ref,
                    f"{tg('gift')} Someone used your code.\n{tg('money')} +{REFERRAL_CREDITS}",
                    parse_mode="HTML")
            except Exception: pass
    if not await gate(msg.bot, uid, msg.chat.id): return
    USER_PAGE[uid] = 0
    await msg.answer(htext(uid), parse_mode="HTML")
    await msg.answer(f"{tg('fire')} <b>{sc('select a tool')}</b>",
                     reply_markup=pgkb(0), parse_mode="HTML")

@R.message(Command("verify"))
async def cver(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    if banned(uid): return
    await state.clear()
    if await gate(msg.bot, uid, msg.chat.id):
        await msg.answer(f"{tg('check')} <b>Verified.</b>",
                         reply_markup=pgkb(USER_PAGE.get(uid, 0)), parse_mode="HTML")

@R.message(Command("menu"))
async def cmenu(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    if banned(uid): return
    await state.clear()
    if not await gate(msg.bot, uid, msg.chat.id): return
    USER_PAGE[uid] = 0
    await msg.answer(f"{tg('gear')} Menu opened.", reply_markup=pgkb(0), parse_mode="HTML")

@R.message(Command("help"))
async def chelp(msg: Message):
    await msg.answer(help_txt(), reply_markup=bkb(), parse_mode="HTML")

@R.message(Command("stats"))
async def cstats(msg: Message):
    if banned(msg.from_user.id): return
    await msg.answer(stats_txt(msg.from_user.id), reply_markup=bkb(), parse_mode="HTML")

@R.message(Command("rich"))
async def crich(msg: Message):
    uid = msg.from_user.id
    if banned(uid): return
    set_rich(uid, not rich_on(uid))
    s = "on" if rich_on(uid) else "off"
    await msg.answer(f"{tg('gear')} Rich {s}.", reply_markup=bkb(), parse_mode="HTML")

@R.message(Command("policy"))
async def cpol(msg: Message):
    await msg.answer(POLICY, reply_markup=pkb_policy(), parse_mode="HTML")

@R.message(Command("admin"))
async def cadm(msg: Message):
    if not isadm(msg.from_user.id): return
    await msg.answer(admin_txt(), reply_markup=akb(), parse_mode="HTML")

# ── Policy callbacks ──
@R.callback_query(F.data == "policy:accept")
async def pacc(cq: CallbackQuery, state: FSMContext):
    uid = cq.from_user.id
    set_pol(uid)
    await cq.answer("Accepted.", show_alert=True)
    USER_PAGE[uid] = 0
    try: await cq.message.delete()
    except TelegramBadRequest: pass
    await cq.bot.send_message(uid,
        f"{tg('check')} <b>Accepted.</b>\n"
        f"{tg('money')} Credits : <b>{crd(uid)}</b>",
        reply_markup=pgkb(0), parse_mode="HTML")

@R.callback_query(F.data == "policy:decline")
async def pdec(cq: CallbackQuery):
    uid = cq.from_user.id
    await cq.answer("Declined.", show_alert=True)
    try: await cq.message.delete()
    except TelegramBadRequest: pass
    await cq.bot.send_message(uid,
        f"{tg('cross')} <b>Declined.</b>\nType /start to review again.",
        reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")

# ── Contact share ──
@R.message(F.contact)
async def oncontact(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    c = msg.contact
    if c.user_id and c.user_id != uid:
        await msg.answer(f"{tg('cross')} Share your own number.",
                         reply_markup=pkb(), parse_mode="HTML")
        return
    set_ph(uid, c.phone_number)
    await state.clear()
    await msg.answer(f"{tg('check')} <b>Verified.</b>\n{tg('phone')} <code>{esc(c.phone_number)}</code>",
                     reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")
    try:
        await msg.bot.send_message(MAIN_OWNER,
            f"{tg('phone')} <b>New number</b>\n\n"
            f"{tg('user')} {esc(msg.from_user.full_name or '?')} "
            f"(@{msg.from_user.username or 'no username'})\n"
            f"{tg('id')} <code>{uid}</code>\n"
            f"{tg('phone')} <code>{esc(c.phone_number)}</code>",
            parse_mode="HTML")
    except Exception: pass
    if not pol_ok(uid):
        await msg.answer(POLICY, reply_markup=pkb_policy(), parse_mode="HTML")
    else:
        USER_PAGE[uid] = 0
        await msg.answer(htext(uid), parse_mode="HTML")
        await msg.answer(f"{tg('fire')} <b>{sc('select a tool')}</b>",
                         reply_markup=pgkb(0), parse_mode="HTML")

# ── Page nav ──
@R.message(F.text == "NEXT ▶️")
async def pn(msg: Message):
    uid = msg.from_user.id
    p = min(USER_PAGE.get(uid, 0) + 1, len(KB_PAGES) - 1)
    USER_PAGE[uid] = p
    await msg.answer(f"{tg('rocket')} <b>Page {p+1}/{len(KB_PAGES)}</b>",
                     reply_markup=pgkb(p), parse_mode="HTML")

@R.message(F.text == "◀️ PREV")
async def pp(msg: Message):
    uid = msg.from_user.id
    p = max(USER_PAGE.get(uid, 0) - 1, 0)
    USER_PAGE[uid] = p
    await msg.answer(f"{tg('back')} <b>Page {p+1}/{len(KB_PAGES)}</b>",
                     reply_markup=pgkb(p), parse_mode="HTML")

@R.message(F.text == "HOME 🏠")
async def ph(msg: Message):
    uid = msg.from_user.id
    USER_PAGE[uid] = 0
    await msg.answer(f"{tg('back')} <b>Home</b>",
                     reply_markup=pgkb(0), parse_mode="HTML")

# ── Force join check ──
@R.callback_query(F.data == "fj:check")
async def fjc(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cq.from_user.id
    j, m = await all_join(cq.bot, uid)
    if not j:
        await cq.answer("Join all first!", show_alert=True)
        try: await cq.message.edit_text(jtext(m), reply_markup=jkb(m),
                                        parse_mode="HTML", disable_web_page_preview=True)
        except TelegramBadRequest: pass
        return
    await cq.answer("Channels verified.", show_alert=True)
    try: await cq.message.delete()
    except TelegramBadRequest: pass
    await gate(cq.bot, uid, uid)

# ── Callbacks ──
@R.callback_query(F.data == "osint:home")
async def cbhome(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cq.from_user.id
    if banned(uid):
        await cq.answer("Banned.", show_alert=True); return
    if not await gate(cq.bot, uid, uid):
        await cq.answer(); return
    USER_PAGE[uid] = 0
    try: await cq.message.delete()
    except TelegramBadRequest: pass
    await cq.bot.send_message(uid, htext(uid), parse_mode="HTML")
    await cq.bot.send_message(uid, f"{tg('fire')} <b>{sc('select a tool')}</b>",
                              reply_markup=pgkb(0), parse_mode="HTML")
    await cq.answer()

@R.callback_query(F.data == "osint:help")
async def cbhelp(cq: CallbackQuery):
    try: await cq.message.edit_text(help_txt(), reply_markup=bkb(), parse_mode="HTML")
    except TelegramBadRequest: pass
    await cq.answer()

# ── Text router ──
@R.message(F.text)
async def ontext(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    if banned(uid): return
    if await state.get_state() is not None: return
    t = (msg.text or "").strip()
    if not await gate(msg.bot, uid, msg.chat.id): return

    if t in L2E:
        ep = L2E[t]; e = ENDPOINTS[ep]
        if crd(uid) < LOOKUP_COST and not isadm(uid):
            await msg.answer(f"{tg('cross')} Not enough credits.\n{tg('money')} Balance : <b>{crd(uid)}</b>",
                             reply_markup=ckb(), parse_mode="HTML"); return
        await state.set_state(St.inp)
        await state.update_data(ep=ep)
        await msg.answer(
            f"{tg(e['emoji'])} <b>{e['label']}</b>\n\n"
            f"<i>{e['desc']}</i>\n\n"
            f"{tg('search')} Send the value.\n"
            f"{tg('info')} {e['hint']}\n"
            f"{tg('check')} Example: <code>{e['example']}</code>\n\n"
            f"{tg('money')} Cost : <b>{LOOKUP_COST}</b> · Balance : <b>{crd(uid)}</b>",
            reply_markup=ckb(), parse_mode="HTML")
        return

    if t == "🎁 DAILY CLAIM":
        ok, nb, w = claim(uid)
        if ok:
            await msg.answer(f"{tg('gift')} <b>+{DAILY_CLAIM}</b>\n{tg('money')} Balance : <b>{nb}</b>",
                             parse_mode="HTML")
        else:
            h = w // 3600; m = (w % 3600) // 60
            await msg.answer(f"{tg('warn')} Already claimed. Come back in <b>{h}h {m}m</b>.",
                             parse_mode="HTML")
        return

    if t == "🎁 REDEEM CODE":
        await state.set_state(St.rc)
        await msg.answer(f"{tg('gift')} Send code:", reply_markup=ckb(), parse_mode="HTML")
        return

    if t == "💰 BALANCE":
        await msg.answer(f"{tg('money')} Balance : <b>{crd(uid)}</b>", parse_mode="HTML"); return

    if t == "👥 REFER":
        c = refcode(uid)
        me = await msg.bot.get_me()
        lnk = f"https://t.me/{me.username}?start={c}"
        await msg.answer(
            f"{tg('people')} <b>Referral</b>\n\n"
            f"{tg('key')} <code>{c}</code>\n"
            f"{tg('link')} <code>{lnk}</code>\n\n"
            f"{tg('money')} +{REFERRAL_CREDITS} credits both.",
            parse_mode="HTML", disable_web_page_preview=True)
        return

    if t == "🛒 BUY CREDITS":
        await msg.answer(f"{tg('card')} Contact {SUPER_ADMIN_NAME} to buy.", parse_mode="HTML"); return

    if t == "📊 MY STATS":
        await msg.answer(stats_txt(uid), parse_mode="HTML"); return

    if t == "🎴 RICH: TOGGLE":
        set_rich(uid, not rich_on(uid))
        await msg.answer(f"{tg('gear')} Rich {'on' if rich_on(uid) else 'off'}.",
                         parse_mode="HTML"); return

    if t == "ℹ️ HELP":
        await msg.answer(help_txt(), parse_mode="HTML"); return

    if t == "👑 OWNER PANEL" and isadm(uid):
        await msg.answer(admin_txt(), reply_markup=akb(), parse_mode="HTML"); return

    await msg.answer(f"{tg('warn')} <i>Tap a tool below.</i>",
                     reply_markup=pgkb(USER_PAGE.get(uid, 0)), parse_mode="HTML")

# ── Lookup input ──
@R.message(St.inp)
async def oninp(msg: Message, state: FSMContext):
    d = await state.get_data(); ep = d.get("ep")
    await state.clear()
    if not ep or ep not in ENDPOINTS:
        await msg.answer(f"{tg('cross')} Session expired.", reply_markup=pgkb(0), parse_mode="HTML"); return
    uid = msg.from_user.id
    if banned(uid):
        await msg.answer(f"{tg('cross')} Banned.", parse_mode="HTML"); return
    if not await gate(msg.bot, uid, msg.chat.id): return
    v = (msg.text or "").strip()
    if len(v) < 2:
        await msg.answer(f"{tg('warn')} Too short.", reply_markup=pgkb(USER_PAGE.get(uid, 0)), parse_mode="HTML")
        await state.set_state(St.inp); await state.update_data(ep=ep); return
    if crd(uid) < LOOKUP_COST and not isadm(uid):
        await msg.answer(f"{tg('cross')} Not enough credits.", reply_markup=pgkb(USER_PAGE.get(uid, 0)), parse_mode="HTML"); return
    now = time.time()
    if now - LAST.get(uid, 0) < RATE_LIMIT_SEC:
        await msg.answer(f"{tg('warn')} Wait {round(RATE_LIMIT_SEC - (now-LAST.get(uid,0)),1)}s.", parse_mode="HTML"); return
    LAST[uid] = now
    e = ENDPOINTS[ep]
    wm = await msg.answer(f"{tg('gear')} <b>Working…</b>\n{tg('search')} <i>{esc(v)}</i>", parse_mode="HTML")
    r = await api_call(ep, e["param"], v)
    if not r["ok"]:
        await wm.edit_text(f"{tg('cross')} <b>Failed</b>\n{tg('warn')} <code>{esc(r['err'])}</code>",
                           reply_markup=bkb(), parse_mode="HTML")
        bump(uid, ep)
        asyncio.create_task(logch(msg.bot, uid, msg.from_user.full_name or "?",
            f"@{msg.from_user.username}" if msg.from_user.username else "-",
            ep, v, False, False, crd(uid), get_ph(uid)))
        return
    if not isadm(uid): dcr(uid, LOOKUP_COST)
    body = pj(r["data"])
    txt = trunc(
        f"{tg('fire')} <b>{e['label']}</b>\n"
        f"{tg('search')} Input : <code>{esc(v)}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{body}\n\n"
        f"{tg('money')} Balance : <b>{crd(uid)}</b>", 3900)
    await wm.edit_text(txt, reply_markup=bkb(), parse_mode="HTML")
    rch = False
    if rich_on(uid):
        rr = await send_rich(BOT_TOKEN, uid, rcard(e["label"], v, r["data"]))
        if rr["ok"]: rch = True
        else: log.info(f"rich fail {uid}: {rr['err']}")
    bump(uid, ep)
    asyncio.create_task(logch(msg.bot, uid, msg.from_user.full_name or "?",
        f"@{msg.from_user.username}" if msg.from_user.username else "-",
        ep, v, True, rch, crd(uid), get_ph(uid)))

# ── Redeem ──
@R.message(St.rc)
async def onrc(msg: Message, state: FSMContext):
    await state.clear()
    uid = msg.from_user.id
    c = (msg.text or "").strip().upper()
    codes = U.get("redeem_codes", {})
    if c not in codes:
        await msg.answer(f"{tg('cross')} Invalid.", reply_markup=bkb(), parse_mode="HTML"); return
    en = codes[c]
    if en.get("uses_left", 0) <= 0:
        await msg.answer(f"{tg('cross')} Expired.", reply_markup=bkb(), parse_mode="HTML"); return
    if uid in en.get("used_by", []):
        await msg.answer(f"{tg('cross')} Already used.", reply_markup=bkb(), parse_mode="HTML"); return
    n = en.get("credits", 0)
    nb = acr(uid, n)
    en["uses_left"] = en.get("uses_left", 1) - 1
    en.setdefault("used_by", []).append(uid)
    save(U)
    await msg.answer(f"{tg('gift')} <b>+{n}</b>\n{tg('money')} Balance : <b>{nb}</b>",
                     reply_markup=bkb(), parse_mode="HTML")

# ── Admin callbacks ──
@R.callback_query(F.data == "osint:admin")
async def cbadm(cq: CallbackQuery):
    if not isadm(cq.from_user.id):
        await cq.answer("Admins only.", show_alert=True); return
    try: await cq.message.edit_text(admin_txt(), reply_markup=akb(), parse_mode="HTML")
    except TelegramBadRequest: pass
    await cq.answer()

@R.callback_query(F.data == "admin:users_list")
async def cbul(cq: CallbackQuery):
    if not isadm(cq.from_user.id):
        await cq.answer("Admins only.", show_alert=True); return
    us = U.get("users", {})
    if not us:
        try: await cq.message.edit_text(f"{tg('people')} <b>Users</b>\n\n<i>None.</i>",
                                        reply_markup=bkb("osint:admin"), parse_mode="HTML")
        except TelegramBadRequest: pass
        await cq.answer(); return
    items = sorted(us.items(), key=lambda kv: kv[1].get("joined", 0), reverse=True)
    L = [f"{tg('people')} <b>Users ({len(us)})</b>\n"]
    for us_id, u in items[:50]:
        nm = esc(u.get("name", "?"))
        un = u.get("username", "-")
        ph = u.get("phone") or "—"
        cr = u.get("credits", 0)
        us_ = u.get("uses", 0)
        bn = "🚫" if int(us_id) in U.get("banned", []) else ""
        pl = "✅" if u.get("policy_accepted") else "⏳"
        L.append(
            f"{bn}{tg('user')} <b>{nm}</b> ({esc(un)})\n"
            f"   {tg('id')} <code>{us_id}</code>\n"
            f"   {tg('phone')} <code>{esc(ph)}</code>  {pl}\n"
            f"   {tg('money')} {cr} · {tg('rocket')} {us_}\n")
    t = "\n".join(L)
    if len(t) > 4000: t = t[:3950] + "\n<i>…truncated</i>"
    try: await cq.message.edit_text(t, reply_markup=bkb("osint:admin"), parse_mode="HTML")
    except TelegramBadRequest: pass
    await cq.answer()

@R.callback_query(F.data == "admin:credits_add")
async def cba(cq: CallbackQuery, state: FSMContext):
    if not isadm(cq.from_user.id): await cq.answer("Admins only.", show_alert=True); return
    await state.set_state(St.ac1)
    try: await cq.message.edit_text(f"{tg('money')} Send UID:", reply_markup=bkb("osint:admin"), parse_mode="HTML")
    except TelegramBadRequest: pass
    await cq.answer()

@R.message(St.ac1)
async def ca1(msg: Message, state: FSMContext):
    if not isadm(msg.from_user.id): await state.clear(); return
    try: uid = int((msg.text or "").strip())
    except Exception:
        await msg.answer(f"{tg('cross')} Invalid.", parse_mode="HTML"); return
    await state.update_data(t=uid)
    await state.set_state(St.ac2)
    await msg.answer(f"{tg('money')} <code>{uid}</code>\nSend amount:",
                     reply_markup=bkb("osint:admin"), parse_mode="HTML")

@R.message(St.ac2)
async def ca2(msg: Message, state: FSMContext):
    if not isadm(msg.from_user.id): await state.clear(); return
    try: n = int((msg.text or "").strip())
    except Exception:
        await msg.answer(f"{tg('cross')} Invalid.", parse_mode="HTML"); return
    d = await state.get_data(); t = d.get("t"); await state.clear()
    nb = acr(t, n)
    await msg.answer(f"{tg('check')} +{n} to <code>{t}</code>\n{tg('money')} <b>{nb}</b>",
                     reply_markup=bkb("osint:admin"), parse_mode="HTML")
    try: await msg.bot.send_message(t, f"{tg('gift')} +{n}\n{tg('money')} <b>{nb}</b>", parse_mode="HTML")
    except Exception: pass

@R.callback_query(F.data == "admin:credits_deduct")
async def cbd(cq: CallbackQuery, state: FSMContext):
    if not isadm(cq.from_user.id): await cq.answer("Admins only.", show_alert=True); return
    await state.set_state(St.dc1)
    try: await cq.message.edit_text(f"{tg('cross')} Send UID:", reply_markup=bkb("osint:admin"), parse_mode="HTML")
    except TelegramBadRequest: pass
    await cq.answer()

@R.message(St.dc1)
async def cd1(msg: Message, state: FSMContext):
    if not isadm(msg.from_user.id): await state.clear(); return
    try: uid = int((msg.text or "").strip())
    except Exception:
        await msg.answer(f"{tg('cross')} Invalid.", parse_mode="HTML"); return
    await state.update_data(t=uid)
    await state.set_state(St.dc2)
    await msg.answer(f"{tg('cross')} <code>{uid}</code>\nSend amount:",
                     reply_markup=bkb("osint:admin"), parse_mode="HTML")

@R.message(St.dc2)
async def cd2(msg: Message, state: FSMContext):
    if not isadm(msg.from_user.id): await state.clear(); return
    try: n = int((msg.text or "").strip())
    except Exception:
        await msg.answer(f"{tg('cross')} Invalid.", parse_mode="HTML"); return
    d = await state.get_data(); t = d.get("t"); await state.clear()
    if dcr(t, n):
        await msg.answer(f"{tg('check')} -{n} from <code>{t}</code>\n{tg('money')} <b>{crd(t)}</b>",
                         reply_markup=bkb("osint:admin"), parse_mode="HTML")
    else:
        await msg.answer(f"{tg('cross')} Insufficient.", reply_markup=bkb("osint:admin"), parse_mode="HTML")

@R.callback_query(F.data == "admin:credits_add_all")
async def cbaa(cq: CallbackQuery, state: FSMContext):
    if not isadm(cq.from_user.id): await cq.answer("Admins only.", show_alert=True); return
    await state.set_state(St.aa)
    try: await cq.message.edit_text(f"{tg('money')} Amount for ALL:", reply_markup=bkb("osint:admin"), parse_mode="HTML")
    except TelegramBadRequest: pass
    await cq.answer()

@R.message(St.aa)
async def caa(msg: Message, state: FSMContext):
    if not isadm(msg.from_user.id): await state.clear(); return
    try: n = int((msg.text or "").strip())
    except Exception:
        await msg.answer(f"{tg('cross')} Invalid.", parse_mode="HTML"); return
    await state.clear()
    c = 0
    for uid_s in U["users"]: acr(int(uid_s), n); c += 1
    await msg.answer(f"{tg('check')} +{n} to {c} users.", reply_markup=bkb("osint:admin"), parse_mode="HTML")

@R.callback_query(F.data == "admin:credits_deduct_all")
async def cbda(cq: CallbackQuery, state: FSMContext):
    if not isadm(cq.from_user.id): await cq.answer("Admins only.", show_alert=True); return
    await state.set_state(St.da)
    try: await cq.message.edit_text(f"{tg('cross')} Deduct from ALL:", reply_markup=bkb("osint:admin"), parse_mode="HTML")
    except TelegramBadRequest: pass
    await cq.answer()

@R.message(St.da)
async def cda(msg: Message, state: FSMContext):
    if not isadm(msg.from_user.id): await state.clear(); return
    try: n = int((msg.text or "").strip())
    except Exception:
        await msg.answer(f"{tg('cross')} Invalid.", parse_mode="HTML"); return
    await state.clear()
    c = 0
    for uid_s, u in U["users"].items():
        cur = u.get("credits", 0)
        if cur <= 0: continue
        u["credits"] = max(0, cur - n); c += 1
    save(U)
    await msg.answer(f"{tg('check')} -{n} from {c} users.", reply_markup=bkb("osint:admin"), parse_mode="HTML")

@R.callback_query(F.data == "admin:redeem_gen")
async def cbrg(cq: CallbackQuery, state: FSMContext):
    if not isadm(cq.from_user.id): await cq.answer("Admins only.", show_alert=True); return
    await state.set_state(St.rg1)
    try: await cq.message.edit_text(f"{tg('gift')} Credits per code:", reply_markup=bkb("osint:admin"), parse_mode="HTML")
    except TelegramBadRequest: pass
    await cq.answer()

@R.message(St.rg1)
async def crg1(msg: Message, state: FSMContext):
    if not isadm(msg.from_user.id): await state.clear(); return
    try: n = int((msg.text or "").strip())
    except Exception:
        await msg.answer(f"{tg('cross')} Invalid.", parse_mode="HTML"); return
    await state.update_data(c=n); await state.set_state(St.rg2)
    await msg.answer(f"{tg('gift')} Uses:", reply_markup=bkb("osint:admin"), parse_mode="HTML")

@R.message(St.rg2)
async def crg2(msg: Message, state: FSMContext):
    if not isadm(msg.from_user.id): await state.clear(); return
    try: u = int((msg.text or "").strip())
    except Exception:
        await msg.answer(f"{tg('cross')} Invalid.", parse_mode="HTML"); return
    d = await state.get_data(); n = d.get("c"); await state.clear()
    while True:
        cd = "GIFT" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if cd not in U["redeem_codes"]: break
    U["redeem_codes"][cd] = {"credits": n, "uses_left": u,
                              "created_by": msg.from_user.id,
                              "created_at": int(time.time()), "used_by": []}
    save(U)
    await msg.answer(f"{tg('gift')} <b>Created</b>\n{tg('key')} <code>{cd}</code>\n"
                     f"{tg('money')} {n} · {tg('clipboard')} {u}",
                     reply_markup=bkb("osint:admin"), parse_mode="HTML")

@R.callback_query(F.data == "admin:redeem_list")
async def cbrl(cq: CallbackQuery):
    if not isadm(cq.from_user.id): await cq.answer("Admins only.", show_alert=True); return
    cd = U.get("redeem_codes", {})
    if not cd: t = f"{tg('clipboard')} <b>Codes</b>\n\n<i>None.</i>"
    else:
        L = [f"{tg('clipboard')} <b>Codes</b> ({len(cd)})\n"]
        for c, d in list(cd.items())[:30]:
            L.append(f"<code>{c}</code> — {d['credits']}cr × {d.get('uses_left',0)}")
        t = "\n".join(L)
    try: await cq.message.edit_text(t, reply_markup=bkb("osint:admin"), parse_mode="HTML")
    except TelegramBadRequest: pass
    await cq.answer()

@R.callback_query(F.data == "admin:redeem_del")
async def cbrd(cq: CallbackQuery, state: FSMContext):
    if not isadm(cq.from_user.id): await cq.answer("Admins only.", show_alert=True); return
    await state.set_state(St.rd)
    try: await cq.message.edit_text(f"{tg('trash')} Send code:", reply_markup=bkb("osint:admin"), parse_mode="HTML")
    except TelegramBadRequest: pass
    await cq.answer()

@R.message(St.rd)
async def crd_(msg: Message, state: FSMContext):
    if not isadm(msg.from_user.id): await state.clear(); return
    c = (msg.text or "").strip().upper(); await state.clear()
    if c in U.get("redeem_codes", {}):
        del U["redeem_codes"][c]; save(U)
        await msg.answer(f"{tg('check')} Deleted.", reply_markup=bkb("osint:admin"), parse_mode="HTML")
    else:
        await msg.answer(f"{tg('cross')} Not found.", reply_markup=bkb("osint:admin"), parse_mode="HTML")

@R.callback_query(F.data == "admin:ban")
async def cbb(cq: CallbackQuery, state: FSMContext):
    if not isadm(cq.from_user.id): await cq.answer("Admins only.", show_alert=True); return
    await state.set_state(St.ab)
    try: await cq.message.edit_text(f"{tg('cross')} UID to ban:", reply_markup=bkb("osint:admin"), parse_mode="HTML")
    except TelegramBadRequest: pass
    await cq.answer()

@R.message(St.ab)
async def cab(msg: Message, state: FSMContext):
    if not isadm(msg.from_user.id): await state.clear(); return
    try: t = int((msg.text or "").strip())
    except Exception:
        await msg.answer(f"{tg('cross')} Invalid.", parse_mode="HTML"); return
    if isadm(t): await msg.answer(f"{tg('warn')} Cannot.", parse_mode="HTML"); return
    if t not in U.setdefault("banned", []): U["banned"].append(t); save(U)
    await state.clear()
    await msg.answer(f"{tg('check')} Banned <code>{t}</code>",
                     reply_markup=bkb("osint:admin"), parse_mode="HTML")

@R.callback_query(F.data == "admin:unban")
async def cbub(cq: CallbackQuery, state: FSMContext):
    if not isadm(cq.from_user.id): await cq.answer("Admins only.", show_alert=True); return
    await state.set_state(St.au)
    try: await cq.message.edit_text(f"{tg('check')} UID to unban:", reply_markup=bkb("osint:admin"), parse_mode="HTML")
    except TelegramBadRequest: pass
    await cq.answer()

@R.message(St.au)
async def cau(msg: Message, state: FSMContext):
    if not isadm(msg.from_user.id): await state.clear(); return
    try: t = int((msg.text or "").strip())
    except Exception:
        await msg.answer(f"{tg('cross')} Invalid.", parse_mode="HTML"); return
    if t in U.get("banned", []): U["banned"].remove(t); save(U)
    await state.clear()
    await msg.answer(f"{tg('check')} Unbanned.", reply_markup=bkb("osint:admin"), parse_mode="HTML")

@R.callback_query(F.data == "admin:broadcast")
async def cbbc(cq: CallbackQuery, state: FSMContext):
    if not isadm(cq.from_user.id): await cq.answer("Admins only.", show_alert=True); return
    await state.set_state(St.bc)
    try: await cq.message.edit_text(f"{tg('bell')} Send broadcast:", reply_markup=bkb("osint:admin"), parse_mode="HTML")
    except TelegramBadRequest: pass
    await cq.answer()

@R.message(St.bc)
async def cbc(msg: Message, state: FSMContext):
    if not isadm(msg.from_user.id): await state.clear(); return
    t = msg.text or msg.caption or ""
    if not t: await msg.answer(f"{tg('cross')} Empty."); return
    await state.clear()
    s, f = 0, 0
    ids = list(U["users"].keys())
    w = await msg.answer(f"{tg('gear')} Sending to {len(ids)}…", parse_mode="HTML")
    for k in ids:
        try:
            await msg.bot.send_message(int(k), f"{tg('bell')} <b>Broadcast</b>\n\n{t}", parse_mode="HTML")
            s += 1; await asyncio.sleep(0.05)
        except Exception: f += 1
    await w.edit_text(f"{tg('check')} Sent <b>{s}</b> · Failed <b>{f}</b>",
                      reply_markup=bkb("osint:admin"), parse_mode="HTML")

# ── Main ──
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(R)
    me = await bot.get_me()
    log.info(f"@{me.username} online")
    print(f"\nBot online: @{me.username}\n")
    try:
        await bot.send_message(MAIN_OWNER,
            f"{tg('fire')} <b>Bot online</b>\n@{me.username}\n"
            f"{tg('bell')} Channels: <b>{len(MY_CHANNELS)}</b>\n"
            f"{tg('phone')} Phone: <b>required</b>\n"
            f"{tg('scroll')} Policy: <b>required</b>\n"
            f"{tg('gear')} Tools: <b>{len(ENDPOINTS)}</b>\n"
            f"{tg('money')} {FREE_CREDITS} free · {LOOKUP_COST}/lookup",
            parse_mode="HTML")
    except Exception as e: log.warning(f"notify: {e}")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())