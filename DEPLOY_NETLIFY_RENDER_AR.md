# نشر FOOTBALL AI ANALYZER على Netlify + Render

## لماذا منصتان؟
- Netlify يستضيف الواجهة الثابتة (HTML/CSS/JavaScript).
- Render يشغّل خادم Flask الذي يتصل بـ API-Football ويحمي مفتاحك.
- لا تضع API Key في `site/config.js` أو أي ملف داخل `site`.

## 1) ارفع المشروع إلى GitHub
1. أنشئ مستودعاً جديداً على GitHub.
2. ارفع محتويات هذا المجلد كاملة، مع مجلد `site`.
3. لا ترفع ملف `.env` أبداً؛ ملف `.gitignore` يستثنيه.

## 2) انشر Backend على Render
1. افتح https://render.com وسجّل الدخول عبر GitHub.
2. اختر New > Blueprint (أو Web Service إذا لم يظهر Blueprint).
3. اختر مستودع المشروع. ملف `render.yaml` يحدد إعدادات الخدمة.
4. في Environment أضف `API_FOOTBALL_KEY` وضع مفتاح API الجديد كقيمة سرية. لا تضعه في GitHub.
5. انتظر حتى تصبح الخدمة Live، ثم انسخ رابطها، مثل `https://football-ai-analyzer-api.onrender.com`.
6. اختبر `https://YOUR-RENDER-URL/api/status` ويجب أن ترى JSON وفيه `api_configured: true`.

## 3) اربط الواجهة بعنوان Render
1. افتح `site/config.js`.
2. استبدل `https://YOUR-RENDER-SERVICE.onrender.com` برابط Render الحقيقي.
3. احفظ الملف وارفع التعديل إلى GitHub.

## 4) انشر الواجهة على Netlify
1. افتح https://app.netlify.com.
2. اختر Add new site > Import an existing project.
3. اربط GitHub واختر نفس المستودع.
4. سيقرأ Netlify إعداد `netlify.toml` ويستخدم `site` كمجلد نشر. إذا طلب إعداداً يدوياً، اجعل Publish directory = `site`.
5. بعد النشر افتح رابط Netlify وجرب البحث عن فريق.

## 5) اختبار سريع
- افتح رابط Render ثم `/api/status`: يجب أن تكون `api_configured` مساوية لـ `true`.
- افتح موقع Netlify وابحث عن فريق مثل Arsenal.
- اختر فريقين واضغط بدء التحليل.

## ملاحظات مهمة
- الخطة المجانية في API-Football محدودة بـ 100 طلب يومياً. التحليل قد يستهلك عدة طلبات أول مرة، ويستخدم الخادم تخزيناً مؤقتاً في الذاكرة لتقليل التكرار.
- خدمات الاستضافة المجانية قد تدخل وضع السكون؛ أول طلب بعد السكون قد يستغرق وقتاً.
- تخزين Render المؤقت داخل الذاكرة يُمسح عند إعادة تشغيل الخدمة أو نشر نسخة جديدة.
- لا تتوفر كل الإحصائيات لكل دوري أو مباراة؛ القيم غير المتاحة ستظهر كغير متاحة.
- لا تنشر مفتاح API ولا ترسله في المحادثات. إذا سبق كشفه، أعد توليده.
