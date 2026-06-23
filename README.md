# 🎬 Video Theme Applier — مقاصد الثلاثة

أداة تلقائية لإضافة ثيم موحد على المقاطع الدينية القصيرة.

## ما تفعله الأداة
- ✅ تحوّل الصوت إلى نص (Captions) تلقائياً
- ✅ تضيف اللوقو أعلى يمين الفيديو
- ✅ تطبّق فونت Cairo Bold مع خلفية شفافة
- ✅ تدعم العربية والإنجليزية

## الاستخدام في Claude Code

### أول مرة:
```bash
git clone https://github.com/7ussienk/VideoEdit.git
cd VideoEdit
bash setup.sh
echo "OPENAI_API_KEY=sk-..." > .env
```

### كل session جديد:
```bash
cd VideoEdit
bash setup.sh
```

### تشغيل الأداة:
```bash
# بدون موزيك (افتراضي)
python process.py --input uploads/video.mp4

# مع موزيك
python process.py --input uploads/video.mp4 --music

# بالإنجليزية
python process.py --input uploads/video.mp4 --lang en
```

## الملفات المطلوبة قبل التشغيل
- `assets/logo.png`   ← لوقو القناة (PNG شفاف)
- `uploads/video.mp4` ← الفيديو المراد معالجته
- `.env`              ← مفتاح OpenAI API

## التكلفة
- Whisper API: $0.006 لكل دقيقة صوت
- فيديو دقيقتين = $0.012 فقط
