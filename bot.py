import os, re, json, asyncio, logging, time, uuid, subprocess
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import yt_dlp
BOT_TOKEN = "8809196609:AAFzIZjMq18IkzuKb00M9XbMg_3_8HeWIs4"
ADMIN_ID = 8813907343
DEV_NAME = "محمد العربي"
BOT_NAME = "بوت محمد العربي"
DL = "downloads"; TMP = "temp"
MAX_MB = 50; MAX_ENHANCE_MB = 20
COOLDOWN = 5
os.makedirs(DL, exist_ok=True); os.makedirs(TMP, exist_ok=True)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
log = logging.getLogger("Bot")
logging.getLogger("httpx").setLevel(logging.WARNING)
def load(p, d):
    if os.path.exists(p):
        try:
            with open(p) as f: return json.load(f)
        except: return d
    return d
def save(p, d):
    with open(p, 'w') as f: json.dump(d, f, ensure_ascii=False, indent=2)
banned = set(load("banned.json", []))
users = set(load("users.json", []))
state = {}; cooldown = {}; busy = set()
stats = {'dl': 0, 'err': 0, 'enhance': 0}
start_time = datetime.now()
def is_admin(u): return u == ADMIN_ID
def is_banned(u): return u in banned
def check_cd(u):
    now = time.time()
    if u in cooldown:
        left = COOLDOWN - (now - cooldown[u])
        if left > 0: return int(left)
    cooldown[u] = now
    return 0
async def safe_edit(q, text, kb=None, reply_markup=None):
    if reply_markup is not None: kb = reply_markup
    try:
        if q.message.caption is not None:
            await q.edit_message_caption(caption=text, reply_markup=kb)
        else:
            await q.edit_message_text(text=text, reply_markup=kb)
    except Exception as e: log.error(f"Edit: {e}")
def cleanup_old():
    now = time.time()
    for folder in [DL, TMP]:
        for f in os.listdir(folder):
            p = os.path.join(folder, f)
            try:
                if os.path.isfile(p) and (now - os.path.getmtime(p)) > 3600: os.remove(p)
            except: pass
async def cmd_start(update, context):
    u = update.effective_user
    if is_banned(u.id) and not is_admin(u.id):
        await update.message.reply_text("🚫 محظور"); return
    if u.id not in users: users.add(u.id); save("users.json", list(users))
    await update.message.reply_text(
        f"👋 أهلاً {u.first_name}!\n\n🌟 {BOT_NAME}\n👨‍💻 {DEV_NAME}\n\n👇 اختار خدمة:",
        reply_markup=kb_main(u.id))

async def on_btn(update, context):
    q = update.callback_query; await q.answer()
    d = q.data; u = q.from_user.id
    if is_banned(u) and not is_admin(u): await safe_edit(q, "🚫 محظور"); return
    if d == "back":
        state.pop(u, None); await safe_edit(q, "🏠 الرئيسية", kb=kb_main(u)); return
    if d == "m_help":
        await safe_edit(q, "ℹ️ اختار خدمة من الأزرار", kb=kb_back()); return
    if d == "a_panel":
        if not is_admin(u): await q.answer("⛔", show_alert=True); return
        await safe_edit(q, f"👑 لوحة أدمن {DEV_NAME}", kb=kb_admin()); return
    if d == "a_stats":
        if not is_admin(u): return
        up = datetime.now() - start_time
        h, r = divmod(int(up.total_seconds()), 3600); m, s = divmod(r, 60)
        files = os.listdir(DL)
        sz = sum(os.path.getsize(os.path.join(DL, f)) for f in files if os.path.isfile(os.path.join(DL, f))) / (1024*1024)
        await safe_edit(q, f"📊 الإحصائيات\n👥 {len(users)}\n🚫 {len(banned)}\n📥 {stats['dl']}\n✨ {stats['enhance']}\n⚠️ {stats['err']}\n📁 {len(files)} ({sz:.1f}MB)\n⏱️ {h}h {m}m", kb=kb_admin()); return
    if d == "a_users":
        if not is_admin(u): return
        t = f"👥 {len(users)}\n🚫 {len(banned)}\n\n"
        for i, x in enumerate(list(users)[-20:], 1): t += f"{'🚫' if x in banned else '✅'} {x}\n"
        await safe_edit(q, t, kb=kb_admin()); return
    if d == "a_banned":
        if not is_admin(u): return
        t = "✨ مفيش محظورين" if not banned else f"🚫 ({len(banned)}):"
        await safe_edit(q, t, kb=kb_ban()); return
    if d == "a_banp":
        if not is_admin(u): return
        state[u] = {'w': 'ban'}
        await safe_edit(q, "➕ ابعت الأيدي:", kb=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="a_banned")]])); return
    if d.startswith("unb_"):
        if not is_admin(u): return
        t = int(d.replace("unb_", "")); banned.discard(t); save("banned.json", list(banned))
        await safe_edit(q, f"✅ فك {t}", kb=kb_ban()); return
    if d == "a_unban_all":
        if not is_admin(u): return
        banned.clear(); save("banned.json", list(banned))
        await safe_edit(q, "✅ فك الكل", kb=kb_ban()); return
    if d == "a_bc":
        if not is_admin(u): return
        state[u] = {'w': 'bc'}
        await safe_edit(q, "📢 ابعت الرسالة:", kb=kb_admin()); return
    if d == "a_clean":
        if not is_admin(u): return
        c = 0
        for folder in [DL, TMP]:
            for f in os.listdir(folder):
                try: os.remove(os.path.join(folder, f)); c += 1
                except: pass
        await safe_edit(q, f"🗑️ اتحذف {c}", kb=kb_admin()); return
    if d == "a_export":
        if not is_admin(u): return
        try:
            with open("u.txt", "w") as f:
                for x in users: f.write(f"{x}\n")
            with open("u.txt", "rb") as f:
                await q.message.reply_document(document=f, filename="users.txt", caption=f"📤 {len(users)}")
            os.remove("u.txt")
        except: pass
        return
    if d == "m_dl":
        state[u] = {'w': 'plat'}
        await safe_edit(q, "🎬 اختار المنصة:", kb=kb_plat()); return
    if d == "m_search":
        state[u] = {'w': 'search'}
        await safe_edit(q, "🔍 اكتب الاسم:", kb=kb_back()); return
    if d.startswith("s_"):
        idx = int(d.replace("s_", ""))
        results = state.get(u, {}).get('search_results', [])
        if idx >= len(results): await safe_edit(q, "⚠️", kb=kb_back()); return
        r = results[idx]
        url = r.get('url') or f"https://youtube.com/watch?v={r.get('id')}"
        state[u] = {'w': 'q', 'url': url}
        title = (r.get('title') or 'فيديو')[:80]; ch = r.get('uploader') or 'غير معروف'
        dur = int(r.get('duration') or 0)
        cap = f"🎬 {title}\n👤 {ch}\n⏱️ {dur//60}:{dur%60:02d}\n\n📌 اختار الجودة:"
        th = r.get('thumbnail')
        try:
            if q.message.caption is not None:
                await q.edit_message_caption(caption=cap, reply_markup=kb_qual())
            else:
                await q.message.delete()
                if th: await context.bot.send_photo(chat_id=u, photo=th, caption=cap, reply_markup=kb_qual())
                else: await context.bot.send_message(chat_id=u, text=cap, reply_markup=kb_qual())
        except: pass
        return
    if d == "m_music":
        state[u] = {'w': 'link', 'audio_only': True}
        await safe_edit(q, "🎵 ابعت الرابط:", kb=kb_back()); return
    if d == "m_enhance":
        state[u] = {'w': 'enhance'}
        await safe_edit(q, "✨ ابعت الفيديو (حتى 20MB):", kb=kb_back()); return
    if d.startswith("p_"):
        state[u] = {'w': 'link'}
        await safe_edit(q, "📎 ابعت الرابط:", kb=kb_back()); return
    if d.startswith("q_"):
        qq = d.replace("q_", "")
        url = state.get(u, {}).get('url')
        if not url: await safe_edit(q, "⚠️ ابعت الرابط", kb=kb_back()); return
        if u in busy: await q.answer("⏳", show_alert=True); return
        busy.add(u)
        await safe_edit(q, "⏳ جاري التحميل...")
        try:
            loop = asyncio.get_event_loop()
            fp = await asyncio.wait_for(loop.run_in_executor(None, dl_vid, url, qq), timeout=300)
            if not fp or not os.path.exists(fp): raise Exception("fail")
            sz = os.path.getsize(fp) / (1024*1024)
            if sz > MAX_MB:
                await safe_edit(q, f"❌ كبير ({sz:.1f}MB)", kb=kb_qual())
                os.remove(fp); busy.discard(u); return
            await safe_edit(q, "📤 جاري الرفع...")
            with open(fp, 'rb') as f:
                if qq == 'audio':
                    await q.message.reply_audio(audio=f, caption=f"🎵 تم ({sz:.1f}MB)\n👨‍💻 {DEV_NAME}")
                else:
                    await q.message.reply_video(video=f, caption=f"✅ تم ({sz:.1f}MB)\n🎬 بدون علامة\n👨‍💻 {DEV_NAME}", supports_streaming=True)
            os.remove(fp); stats['dl'] += 1
            state.pop(u, None); busy.discard(u)
            await q.message.reply_text("🎬 تاني؟", reply_markup=kb_main(u))
        except Exception as e:
            log.error(f"DL: {e}"); stats['err'] += 1; busy.discard(u)
            await safe_edit(q, "❌ فشل", kb=kb_qual())
        return
    if d.startswith("e_"):
        mode = d.replace("e_", "")
        info = state.get(u, {})
        if not info.get('file_id'): await safe_edit(q, "⚠️ ابعت الفيديو", kb=kb_back()); return
        if u in busy: await q.answer("⏳", show_alert=True); return
        busy.add(u)
        await safe_edit(q, "✨ جاري التحسين...")
        try:
            out = await asyncio.wait_for(process_enhance(context, mode, info['file_id']), timeout=600)
            if not out or not os.path.exists(out): raise Exception("fail")
            sz = os.path.getsize(out) / (1024*1024)
            if sz > MAX_MB:
                await safe_edit(q, f"❌ كبير ({sz:.1f}MB)")
                os.remove(out); busy.discard(u); return
            with open(out, 'rb') as f:
                await q.message.reply_video(video=f, caption=f"✅ تم التحسين ({sz:.1f}MB)\n👨‍💻 {DEV_NAME}", supports_streaming=True)
            os.remove(out); stats['enhance'] += 1
            state.pop(u, None); busy.discard(u)
            await q.message.reply_text("🎬 تاني؟", reply_markup=kb_main(u))
        except Exception as e:
            log.error(f"Enh: {e}"); stats['err'] += 1; busy.discard(u)
            await safe_edit(q, "❌ فشل التحسين")
        return

async def on_msg(update, context):
    u = update.effective_user.id
    msg = update.message
    t = msg.text.strip() if msg.text else ""
    if is_banned(u) and not is_admin(u): await msg.reply_text("🚫"); return
    if msg.video or msg.document:
        v = msg.video or msg.document
        sz = (v.file_size or 0) / (1024*1024)
        if state.get(u, {}).get('w') == 'enhance':
            if sz > MAX_ENHANCE_MB: await msg.reply_text(f"⚠️ كبير ({sz:.1f}MB)"); return
            state[u] = {'w': 'enhance', 'file_id': v.file_id, 'size': sz}
            await msg.reply_text(f"🎬 استلمت ({sz:.1f}MB)\n✨ اختار:", reply_markup=kb_enhance())
        return
    if state.get(u, {}).get('w') == 'ban':
        state.pop(u, None)
        if not t.isdigit(): await msg.reply_text("⚠️ أرقام"); return
        x = int(t)
        if is_admin(x): await msg.reply_text("😅"); return
        banned.add(x); save("banned.json", list(banned))
        await msg.reply_text(f"🚫 حظر {x}", reply_markup=kb_admin()); return
    if state.get(u, {}).get('w') == 'bc':
        state.pop(u, None); s = 0; f2 = 0
        for x in users:
            if x in banned: continue
            try:
                await context.bot.send_message(chat_id=x, text=f"📢 من {DEV_NAME}\n\n{t}")
                s += 1; await asyncio.sleep(0.05)
            except: f2 += 1
        await msg.reply_text(f"✅ {s} ❌ {f2}", reply_markup=kb_admin()); return
    if state.get(u, {}).get('w') == 'search':
        if not t: await msg.reply_text("✍️ اكتب"); return
        cd = check_cd(u)
        if cd > 0: await msg.reply_text(f"⏳ {cd}s"); return
        m = await msg.reply_text("🔍 جاري البحث...")
        try:
            loop = asyncio.get_event_loop()
            results = await asyncio.wait_for(loop.run_in_executor(None, search_youtube, t), timeout=60)
            if not results: await m.edit_text("❌ مفيش نتايج"); return
            state[u] = {'w': 'pick', 'search_results': results}
            await m.edit_text(f"🔍 {t}\n\n👇 اختار:", reply_markup=kb_search(results))
        except Exception as e: log.error(f"S: {e}"); await m.edit_text("❌ فشل")
        return
    if state.get(u, {}).get('w') == 'link':
        if not re.match(r'https?://', t): await msg.reply_text("⚠️ رابط غلط"); return
        cd = check_cd(u)
        if cd > 0: await msg.reply_text(f"⏳ {cd}s"); return
        m = await msg.reply_text("🔍 جاري الفحص...")
        try:
            loop = asyncio.get_event_loop()
            info = await asyncio.wait_for(loop.run_in_executor(None, get_info, t), timeout=60)
            title = (info.get('title') or 'فيديو')[:80]
            up = info.get('uploader') or 'غير معروف'
            th = info.get('thumbnail')
            dur = int(info.get('duration') or 0)
            state[u] = {'w': 'q', 'url': t}
            cap = f"🎬 {title}\n👤 {up}\n⏱️ {dur//60}:{dur%60:02d}\n\n📌 اختار الجودة:"
            await m.delete()
            if th: await msg.reply_photo(photo=th, caption=cap, reply_markup=kb_qual())
            else: await msg.reply_text(cap, reply_markup=kb_qual())
        except Exception as e: log.error(f"I: {e}"); await m.edit_text("❌ فشل")
        return
    await msg.reply_text("👋 اضغط /start", reply_markup=kb_main(u))

def search_youtube(q):
    opts = {'quiet': True, 'no_warnings': True, 'noplaylist': True, 'skip_download': True, 'extract_flat': True}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(f"ytsearch5:{q}", download=False)
    if not info or 'entries' not in info: return []
    return list(info['entries'])[:5]

def get_info(url):
    o = {'quiet': True, 'no_warnings': True, 'noplaylist': True, 'skip_download': True}
    with yt_dlp.YoutubeDL(o) as y: return y.extract_info(url, download=False)

def dl_vid(url, q):
    fmts = {'best': 'b/bv*+ba/b', '1080': 'bv*[height<=1080]+ba/b[height<=1080]/b', '720': 'bv*[height<=720]+ba/b[height<=720]/b', '480': 'bv*[height<=480]+ba/b[height<=480]/b', '360': 'bv*[height<=360]+ba/b[height<=360]/b', 'audio': 'ba/b'}
    o = {'outtmpl': os.path.join(DL, '%(id)s.%(ext)s'), 'quiet': True, 'no_warnings': True, 'noplaylist': True, 'format': fmts.get(q, 'b/bv*+ba/b'), 'merge_output_format': 'mp4', 'retries': 5, 'socket_timeout': 30}
    if q == 'audio': o['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
    with yt_dlp.YoutubeDL(o) as y:
        i = y.extract_info(url, download=True)
        fp = y.prepare_filename(i)
        b, _ = os.path.splitext(fp)
        for e in ['.mp4', '.mkv', '.webm', '.mp3', '.m4a']:
            if os.path.exists(b + e): return b + e
        return fp

def run_ffmpeg(args, timeout=300):
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout)
        return r.returncode == 0
    except: return False

async def process_enhance(context, mode, file_id):
    inp = os.path.join(TMP, f"in_{uuid.uuid4().hex[:8]}.mp4")
    out = os.path.join(TMP, f"out_{uuid.uuid4().hex[:8]}.mp4")
    tg = await context.bot.get_file(file_id)
    await tg.download_to_drive(inp)
    vf_map = {'full': "scale=iw*2:ih*2:flags=lanczos,unsharp=5:5:1.0,eq=contrast=1.1:saturation=1.15", 'up2x': "scale=iw*2:ih*2:flags=lanczos", 'color': "eq=contrast=1.15:saturation=1.25:gamma=1.1", 'clean': "hqdn3d=4:3:6:4.5,unsharp=3:3:0.5", 'fps': "minterpolate=fps=60:mi_mode=mci"}
    vf = vf_map.get(mode, "null")
    loop = asyncio.get_event_loop()
    ok = await loop.run_in_executor(None, run_ffmpeg, ["ffmpeg", "-y", "-i", inp, "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out], 300)
    try: os.remove(inp)
    except: pass
    return out if ok and os.path.exists(out) else None

async def err_h(update, context): log.warning(f"Err: {context.error}")

def main():
    cleanup_old()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_btn))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_msg))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_msg))
    app.add_error_handler(err_h)
    print("=" * 45)
    print(f"Bot: {BOT_NAME}")
    print(f"Dev: {DEV_NAME}")
    print("=" * 45)
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True, stop_signals=None)

async def cmd_start(update, context):
    u = update.effective_user
    if is_banned(u.id) and not is_admin(u.id):
        await update.message.reply_text("🚫 محظور"); return
    if u.id not in users: users.add(u.id); save("users.json", list(users))
    await update.message.reply_text(
        f"👋 أهلاً {u.first_name}!\n\n🌟 {BOT_NAME}\n👨‍💻 {DEV_NAME}\n\n👇 اختار خدمة:",
        reply_markup=kb_main(u.id))

async def on_btn(update, context):
    q = update.callback_query; await q.answer()
    d = q.data; u = q.from_user.id
    if is_banned(u) and not is_admin(u): await safe_edit(q, "🚫 محظور"); return
    if d == "back":
        state.pop(u, None); await safe_edit(q, "🏠 الرئيسية", kb=kb_main(u)); return
    if d == "m_help":
        await safe_edit(q, "ℹ️ اختار خدمة من الأزرار", kb=kb_back()); return
    if d == "a_panel":
        if not is_admin(u): await q.answer("⛔", show_alert=True); return
        await safe_edit(q, f"👑 لوحة أدمن {DEV_NAME}", kb=kb_admin()); return
    if d == "a_stats":
        if not is_admin(u): return
        up = datetime.now() - start_time
        h, r = divmod(int(up.total_seconds()), 3600); m, s = divmod(r, 60)
        files = os.listdir(DL)
        sz = sum(os.path.getsize(os.path.join(DL, f)) for f in files if os.path.isfile(os.path.join(DL, f))) / (1024*1024)
        await safe_edit(q, f"📊 الإحصائيات\n👥 {len(users)}\n🚫 {len(banned)}\n📥 {stats['dl']}\n✨ {stats['enhance']}\n⚠️ {stats['err']}\n📁 {len(files)} ({sz:.1f}MB)\n⏱️ {h}h {m}m", kb=kb_admin()); return
    if d == "a_users":
        if not is_admin(u): return
        t = f"👥 {len(users)}\n🚫 {len(banned)}\n\n"
        for i, x in enumerate(list(users)[-20:], 1): t += f"{'🚫' if x in banned else '✅'} {x}\n"
        await safe_edit(q, t, kb=kb_admin()); return
    if d == "a_banned":
        if not is_admin(u): return
        t = "✨ مفيش محظورين" if not banned else f"🚫 ({len(banned)}):"
        await safe_edit(q, t, kb=kb_ban()); return
    if d == "a_banp":
        if not is_admin(u): return
        state[u] = {'w': 'ban'}
        await safe_edit(q, "➕ ابعت الأيدي:", kb=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="a_banned")]])); return
    if d.startswith("unb_"):
        if not is_admin(u): return
        t = int(d.replace("unb_", "")); banned.discard(t); save("banned.json", list(banned))
        await safe_edit(q, f"✅ فك {t}", kb=kb_ban()); return
    if d == "a_unban_all":
        if not is_admin(u): return
        banned.clear(); save("banned.json", list(banned))
        await safe_edit(q, "✅ فك الكل", kb=kb_ban()); return
    if d == "a_bc":
        if not is_admin(u): return
        state[u] = {'w': 'bc'}
        await safe_edit(q, "📢 ابعت الرسالة:", kb=kb_admin()); return
    if d == "a_clean":
        if not is_admin(u): return
        c = 0
        for folder in [DL, TMP]:
            for f in os.listdir(folder):
                try: os.remove(os.path.join(folder, f)); c += 1
                except: pass
        await safe_edit(q, f"🗑️ اتحذف {c}", kb=kb_admin()); return
    if d == "a_export":
        if not is_admin(u): return
        try:
            with open("u.txt", "w") as f:
                for x in users: f.write(f"{x}\n")
            with open("u.txt", "rb") as f:
                await q.message.reply_document(document=f, filename="users.txt", caption=f"📤 {len(users)}")
            os.remove("u.txt")
        except: pass
        return
    if d == "m_dl":
        state[u] = {'w': 'plat'}
        await safe_edit(q, "🎬 اختار المنصة:", kb=kb_plat()); return
    if d == "m_search":
        state[u] = {'w': 'search'}
        await safe_edit(q, "🔍 اكتب الاسم:", kb=kb_back()); return
    if d.startswith("s_"):
        idx = int(d.replace("s_", ""))
        results = state.get(u, {}).get('search_results', [])
        if idx >= len(results): await safe_edit(q, "⚠️", kb=kb_back()); return
        r = results[idx]
        url = r.get('url') or f"https://youtube.com/watch?v={r.get('id')}"
        state[u] = {'w': 'q', 'url': url}
        title = (r.get('title') or 'فيديو')[:80]; ch = r.get('uploader') or 'غير معروف'
        dur = int(r.get('duration') or 0)
        cap = f"🎬 {title}\n👤 {ch}\n⏱️ {dur//60}:{dur%60:02d}\n\n📌 اختار الجودة:"
        th = r.get('thumbnail')
        try:
            if q.message.caption is not None:
                await q.edit_message_caption(caption=cap, reply_markup=kb_qual())
            else:
                await q.message.delete()
                if th: await context.bot.send_photo(chat_id=u, photo=th, caption=cap, reply_markup=kb_qual())
                else: await context.bot.send_message(chat_id=u, text=cap, reply_markup=kb_qual())
        except: pass
        return
    if d == "m_music":
        state[u] = {'w': 'link', 'audio_only': True}
        await safe_edit(q, "🎵 ابعت الرابط:", kb=kb_back()); return
    if d == "m_enhance":
        state[u] = {'w': 'enhance'}
        await safe_edit(q, "✨ ابعت الفيديو (حتى 20MB):", kb=kb_back()); return
    if d.startswith("p_"):
        state[u] = {'w': 'link'}
        await safe_edit(q, "📎 ابعت الرابط:", kb=kb_back()); return
    if d.startswith("q_"):
        qq = d.replace("q_", "")
        url = state.get(u, {}).get('url')
        if not url: await safe_edit(q, "⚠️ ابعت الرابط", kb=kb_back()); return
        if u in busy: await q.answer("⏳", show_alert=True); return
        busy.add(u)
        await safe_edit(q, "⏳ جاري التحميل...")
        try:
            loop = asyncio.get_event_loop()
            fp = await asyncio.wait_for(loop.run_in_executor(None, dl_vid, url, qq), timeout=300)
            if not fp or not os.path.exists(fp): raise Exception("fail")
            sz = os.path.getsize(fp) / (1024*1024)
            if sz > MAX_MB:
                await safe_edit(q, f"❌ كبير ({sz:.1f}MB)", kb=kb_qual())
                os.remove(fp); busy.discard(u); return
            await safe_edit(q, "📤 جاري الرفع...")
            with open(fp, 'rb') as f:
                if qq == 'audio':
                    await q.message.reply_audio(audio=f, caption=f"🎵 تم ({sz:.1f}MB)\n👨‍💻 {DEV_NAME}")
                else:
                    await q.message.reply_video(video=f, caption=f"✅ تم ({sz:.1f}MB)\n🎬 بدون علامة\n👨‍💻 {DEV_NAME}", supports_streaming=True)
            os.remove(fp); stats['dl'] += 1
            state.pop(u, None); busy.discard(u)
            await q.message.reply_text("🎬 تاني؟", reply_markup=kb_main(u))
        except Exception as e:
            log.error(f"DL: {e}"); stats['err'] += 1; busy.discard(u)
            await safe_edit(q, "❌ فشل", kb=kb_qual())
        return
    if d.startswith("e_"):
        mode = d.replace("e_", "")
        info = state.get(u, {})
        if not info.get('file_id'): await safe_edit(q, "⚠️ ابعت الفيديو", kb=kb_back()); return
        if u in busy: await q.answer("⏳", show_alert=True); return
        busy.add(u)
        await safe_edit(q, "✨ جاري التحسين...")
        try:
            out = await asyncio.wait_for(process_enhance(context, mode, info['file_id']), timeout=600)
            if not out or not os.path.exists(out): raise Exception("fail")
            sz = os.path.getsize(out) / (1024*1024)
            if sz > MAX_MB:
                await safe_edit(q, f"❌ كبير ({sz:.1f}MB)")
                os.remove(out); busy.discard(u); return
            with open(out, 'rb') as f:
                await q.message.reply_video(video=f, caption=f"✅ تم التحسين ({sz:.1f}MB)\n👨‍💻 {DEV_NAME}", supports_streaming=True)
            os.remove(out); stats['enhance'] += 1
            state.pop(u, None); busy.discard(u)
            await q.message.reply_text("🎬 تاني؟", reply_markup=kb_main(u))
        except Exception as e:
            log.error(f"Enh: {e}"); stats['err'] += 1; busy.discard(u)
            await safe_edit(q, "❌ فشل التحسين")
        return

async def on_msg(update, context):
    u = update.effective_user.id
    msg = update.message
    t = msg.text.strip() if msg.text else ""
    if is_banned(u) and not is_admin(u): await msg.reply_text("🚫"); return
    if msg.video or msg.document:
        v = msg.video or msg.document
        sz = (v.file_size or 0) / (1024*1024)
        if state.get(u, {}).get('w') == 'enhance':
            if sz > MAX_ENHANCE_MB: await msg.reply_text(f"⚠️ كبير ({sz:.1f}MB)"); return
            state[u] = {'w': 'enhance', 'file_id': v.file_id, 'size': sz}
            await msg.reply_text(f"🎬 استلمت ({sz:.1f}MB)\n✨ اختار:", reply_markup=kb_enhance())
        return
    if state.get(u, {}).get('w') == 'ban':
        state.pop(u, None)
        if not t.isdigit(): await msg.reply_text("⚠️ أرقام"); return
        x = int(t)
        if is_admin(x): await msg.reply_text("😅"); return
        banned.add(x); save("banned.json", list(banned))
        await msg.reply_text(f"🚫 حظر {x}", reply_markup=kb_admin()); return
    if state.get(u, {}).get('w') == 'bc':
        state.pop(u, None); s = 0; f2 = 0
        for x in users:
            if x in banned: continue
            try:
                await context.bot.send_message(chat_id=x, text=f"📢 من {DEV_NAME}\n\n{t}")
                s += 1; await asyncio.sleep(0.05)
            except: f2 += 1
        await msg.reply_text(f"✅ {s} ❌ {f2}", reply_markup=kb_admin()); return
    if state.get(u, {}).get('w') == 'search':
        if not t: await msg.reply_text("✍️ اكتب"); return
        cd = check_cd(u)
        if cd > 0: await msg.reply_text(f"⏳ {cd}s"); return
        m = await msg.reply_text("🔍 جاري البحث...")
        try:
            loop = asyncio.get_event_loop()
            results = await asyncio.wait_for(loop.run_in_executor(None, search_youtube, t), timeout=60)
            if not results: await m.edit_text("❌ مفيش نتايج"); return
            state[u] = {'w': 'pick', 'search_results': results}
            await m.edit_text(f"🔍 {t}\n\n👇 اختار:", reply_markup=kb_search(results))
        except Exception as e: log.error(f"S: {e}"); await m.edit_text("❌ فشل")
        return
    if state.get(u, {}).get('w') == 'link':
        if not re.match(r'https?://', t): await msg.reply_text("⚠️ رابط غلط"); return
        cd = check_cd(u)
        if cd > 0: await msg.reply_text(f"⏳ {cd}s"); return
        m = await msg.reply_text("🔍 جاري الفحص...")
        try:
            loop = asyncio.get_event_loop()
            info = await asyncio.wait_for(loop.run_in_executor(None, get_info, t), timeout=60)
            title = (info.get('title') or 'فيديو')[:80]
            up = info.get('uploader') or 'غير معروف'
            th = info.get('thumbnail')
            dur = int(info.get('duration') or 0)
            state[u] = {'w': 'q', 'url': t}
            cap = f"🎬 {title}\n👤 {up}\n⏱️ {dur//60}:{dur%60:02d}\n\n📌 اختار الجودة:"
            await m.delete()
            if th: await msg.reply_photo(photo=th, caption=cap, reply_markup=kb_qual())
            else: await msg.reply_text(cap, reply_markup=kb_qual())
        except Exception as e: log.error(f"I: {e}"); await m.edit_text("❌ فشل")
        return
    await msg.reply_text("👋 اضغط /start", reply_markup=kb_main(u))

def search_youtube(q):
    opts = {'quiet': True, 'no_warnings': True, 'noplaylist': True, 'skip_download': True, 'extract_flat': True}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(f"ytsearch5:{q}", download=False)
    if not info or 'entries' not in info: return []
    return list(info['entries'])[:5]

def get_info(url):
    o = {'quiet': True, 'no_warnings': True, 'noplaylist': True, 'skip_download': True}
    with yt_dlp.YoutubeDL(o) as y: return y.extract_info(url, download=False)

def dl_vid(url, q):
    fmts = {'best': 'b/bv*+ba/b', '1080': 'bv*[height<=1080]+ba/b[height<=1080]/b', '720': 'bv*[height<=720]+ba/b[height<=720]/b', '480': 'bv*[height<=480]+ba/b[height<=480]/b', '360': 'bv*[height<=360]+ba/b[height<=360]/b', 'audio': 'ba/b'}
    o = {'outtmpl': os.path.join(DL, '%(id)s.%(ext)s'), 'quiet': True, 'no_warnings': True, 'noplaylist': True, 'format': fmts.get(q, 'b/bv*+ba/b'), 'merge_output_format': 'mp4', 'retries': 5, 'socket_timeout': 30}
    if q == 'audio': o['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
    with yt_dlp.YoutubeDL(o) as y:
        i = y.extract_info(url, download=True)
        fp = y.prepare_filename(i)
        b, _ = os.path.splitext(fp)
        for e in ['.mp4', '.mkv', '.webm', '.mp3', '.m4a']:
            if os.path.exists(b + e): return b + e
        return fp

def run_ffmpeg(args, timeout=300):
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout)
        return r.returncode == 0
    except: return False

async def process_enhance(context, mode, file_id):
    inp = os.path.join(TMP, f"in_{uuid.uuid4().hex[:8]}.mp4")
    out = os.path.join(TMP, f"out_{uuid.uuid4().hex[:8]}.mp4")
    tg = await context.bot.get_file(file_id)
    await tg.download_to_drive(inp)
    vf_map = {'full': "scale=iw*2:ih*2:flags=lanczos,unsharp=5:5:1.0,eq=contrast=1.1:saturation=1.15", 'up2x': "scale=iw*2:ih*2:flags=lanczos", 'color': "eq=contrast=1.15:saturation=1.25:gamma=1.1", 'clean': "hqdn3d=4:3:6:4.5,unsharp=3:3:0.5", 'fps': "minterpolate=fps=60:mi_mode=mci"}
    vf = vf_map.get(mode, "null")
    loop = asyncio.get_event_loop()
    ok = await loop.run_in_executor(None, run_ffmpeg, ["ffmpeg", "-y", "-i", inp, "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out], 300)
    try: os.remove(inp)
    except: pass
    return out if ok and os.path.exists(out) else None

async def err_h(update, context): log.warning(f"Err: {context.error}")

def main():
    cleanup_old()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_btn))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_msg))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_msg))
    app.add_error_handler(err_h)
    print("=" * 45)
    print(f"Bot: {BOT_NAME}")
    print(f"Dev: {DEV_NAME}")
    print("=" * 45)
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True, stop_signals=None)

def kb_admin():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="a_stats"), InlineKeyboardButton("👥 المستخدمين", callback_data="a_users")],
        [InlineKeyboardButton("🚫 المحظورين", callback_data="a_banned"), InlineKeyboardButton("📢 رسالة جماعية", callback_data="a_bc")],
        [InlineKeyboardButton("📤 تصدير", callback_data="a_export"), InlineKeyboardButton("🗑️ تنظيف", callback_data="a_clean")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="back")],
    ])


def kb_ban():
    kb = [[InlineKeyboardButton(f"✅ فك {u}", callback_data=f"unb_{u}")] for u in list(banned)[:20]]
    kb.append([InlineKeyboardButton("➕ حظر", callback_data="a_banp")])
    if banned:
        kb.append([InlineKeyboardButton("🗑️ فك الكل", callback_data="a_unban_all")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="a_panel")])
    return InlineKeyboardMarkup(kb)


def kb_main(u):
    kb = [
        [InlineKeyboardButton("🎬 تحميل فيديو", callback_data="m_dl"), InlineKeyboardButton("🔍 بحث يوتيوب", callback_data="m_search")],
        [InlineKeyboardButton("🎵 صوت MP3", callback_data="m_music"), InlineKeyboardButton("✨ تحسين فيديو", callback_data="m_enhance")],
        [InlineKeyboardButton("ℹ️ مساعدة", callback_data="m_help")],
    ]
    if is_admin(u):
        kb.append([InlineKeyboardButton("👑 لوحة الأدمن", callback_data="a_panel")])
    return InlineKeyboardMarkup(kb)


def kb_plat():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ YouTube", callback_data="p_youtube"), InlineKeyboardButton("🎵 TikTok", callback_data="p_tiktok")],
        [InlineKeyboardButton("📸 Instagram", callback_data="p_instagram"), InlineKeyboardButton("🐦 Twitter/X", callback_data="p_twitter")],
        [InlineKeyboardButton("📘 Facebook", callback_data="p_facebook"), InlineKeyboardButton("👽 Reddit", callback_data="p_reddit")],
        [InlineKeyboardButton("📌 Pinterest", callback_data="p_pinterest"), InlineKeyboardButton("🎬 Vimeo", callback_data="p_vimeo")],
        [InlineKeyboardButton("📺 Dailymotion", callback_data="p_dailymotion"), InlineKeyboardButton("🎥 Twitch", callback_data="p_twitch")],
        [InlineKeyboardButton("🎧 SoundCloud", callback_data="p_soundcloud"), InlineKeyboardButton("💬 Snapchat", callback_data="p_snapchat")],
        [InlineKeyboardButton("🎞️ Likee", callback_data="p_likee"), InlineKeyboardButton("👥 LinkedIn", callback_data="p_linkedin")],
        [InlineKeyboardButton("🌐 منصة أخرى", callback_data="p_other")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back")],
    ])


def kb_qual():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎥 أفضل جودة", callback_data="q_best")],
        [InlineKeyboardButton("📺 1080p", callback_data="q_1080"), InlineKeyboardButton("📱 720p", callback_data="q_720")],
        [InlineKeyboardButton("💾 480p", callback_data="q_480"), InlineKeyboardButton("🔻 360p", callback_data="q_360")],
        [InlineKeyboardButton("🎵 MP3", callback_data="q_audio")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back")],
    ])


def kb_enhance():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ تحسين شامل", callback_data="e_full")],
        [InlineKeyboardButton("🔍 تكبير 2x", callback_data="e_up2x"), InlineKeyboardButton("🎨 ألوان", callback_data="e_color")],
        [InlineKeyboardButton("🧹 ضوضاء", callback_data="e_clean"), InlineKeyboardButton("🎬 60fps", callback_data="e_fps")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back")],
    ])


def kb_back():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back")]])


def kb_search(results):
    kb = [[InlineKeyboardButton(f"{i+1}. {(r.get('title') or 'فيديو')[:45]}", callback_data=f"s_{i}")] for i, r in enumerate(results)]
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="back")])
    return InlineKeyboardMarkup(kb)


if __name__ == '__main__':
    main()
