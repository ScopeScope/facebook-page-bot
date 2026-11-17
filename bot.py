import os
import re
import json
import requests
import google.generativeai as genai

# إعداد المتغيرات
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID")

HISTORY_FILE = "history.txt"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return f.read().splitlines()
    return []

def save_to_history(topic):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{topic}\n")

def get_candidate_models():
    """ترتيب كل الموديلات المتاحة من الأفضل للأقل، مع استبعاد الموديلات المدفوعة أو غير النصية"""
    genai.configure(api_key=GEMINI_API_KEY)
    
    # كلمات بتدل إن الموديل مخصص لباقات مدفوعة أو صوت وصورة بس
    excluded_keywords = ['omni', 'ultra', 'vision', 'embedding', 'imagen', 'veo', 'tts', 'audio', 'live', 'aqa']
    
    standard_flash = []
    other_flash = []
    pro_models = []
    fallback_models = []
    
    try:
        for m in genai.list_models():
            if 'generateContent' not in m.supported_generation_methods:
                continue
                
            name = m.name.lower()
            if any(bad_word in name for bad_word in excluded_keywords):
                continue
            
            # 1. الأولوية القصوى للموديلات القياسية المرقمة مثل gemini-3.8-flash أو gemini-4.0-flash
            match_flash = re.match(r'^models/gemini-(\d+(?:\.\d+)?)-flash$', name)
            if match_flash:
                version = float(match_flash.group(1))
                standard_flash.append((version, m.name))
                continue
                
            # 2. الأولوية التانية لأي موديل فلاش فرعي (مثل flash-lite)
            if 'flash' in name:
                other_flash.append(m.name)
                continue
                
            # 3. الأولوية التالتة لموديلات pro القياسية
            match_pro = re.match(r'^models/gemini-(\d+(?:\.\d+)?)-pro$', name)
            if match_pro:
                version = float(match_pro.group(1))
                pro_models.append((version, m.name))
                continue
                
            # 4. أي موديل نصي تاني لو جوجل غيرت الأسماء مستقبلاً
            fallback_models.append(m.name)
            
    except Exception as e:
        print(f"تحذير أثناء جلب قائمة الموديلات: {e}")

    # ترتيب الموديلات المرقمة من الإصدار الأحدث للأقدم
    standard_flash.sort(key=lambda x: x[0], reverse=True)
    pro_models.sort(key=lambda x: x[0], reverse=True)
    other_flash.sort(reverse=True)
    fallback_models.sort(reverse=True)
    
    # تجميع الطابور النهائي بالترتيب
    candidates = (
        [m[1] for m in standard_flash] +
        other_flash +
        [m[1] for m in pro_models] +
        fallback_models
    )
    
    # إضافة موديل احتياطي أخير لو القائمة رجعت فاضية لأي سبب
    if "models/gemini-3.8-flash" not in candidates:
        candidates.insert(0, "models/gemini-3.8-flash")
        
    return candidates

def generate_content(history_list):
    candidates = get_candidate_models()
    history_str = ", ".join(history_list[-30:])
    
    prompt = f"""
    أنت صانع محتوى لصفحة فيسبوك علمية شيقة اسمها "ما وراء المعلومة".
    اكتب بوست عن حقيقة علمية أو طبيعية صادمة (مثل نبض الطنان، ثقوب سوداء، إلخ).
    تجنب تماماً هذه المواضيع التي تم نشرها سابقاً: [{history_str}]
    
    هيكل البوست:
    1. خطاف (Hook) صادم.
    2. شرح علمي مبسط.
    3. إسقاط (ماذا لو حدث هذا للبشر أو في حياتنا اليومية؟).
    
    أريد الرد بصيغة JSON فقط بهذا الشكل:
    {{
        "topic_title": "عنوان قصير للموضوع",
        "post_body": "نص البوست بالكامل مع الإيموجيز",
        "search_keyword": "كلمة واحدة أو اثنتين بالإنجليزية للبحث عن صورة مناسبة (مثل: hummingbird, volcano)"
    }}
    """
    
    # تجربة الموديلات واحداً تلو الآخر لحد ما واحد يشتغل بنجاح
    last_error = None
    for model_name in candidates:
        try:
            print(f"جاري تجربة الموديل: {model_name} ...")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            
            json_text = response.text.strip().replace('```json', '').replace('```', '').strip()
            data = json.loads(json_text)
            print(f"نجح التوليد باستخدام: {model_name}")
            return data
            
        except Exception as e:
            print(f"الموديل {model_name} غير متاح حالياً أو باقته صفر، جاري تجربة الموديل التالي...")
            last_error = e
            continue
            
    raise RuntimeError(f"فشلت جميع الموديلات المتاحة. آخر خطأ: {last_error}")

def get_pexels_image(query):
    if not PEXELS_API_KEY:
        return None
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"
    try:
        res = requests.get(url, headers=headers, timeout=15).json()
        if res.get("photos"):
            return res["photos"][0]["src"]["large"]
    except Exception:
        pass
    return None

def get_pixabay_image(query):
    if not PIXABAY_API_KEY:
        return None
    url = f"https://pixabay.com/api/?key={PIXABAY_API_KEY}&q={query}&image_type=photo&per_page=3"
    try:
        res = requests.get(url, timeout=15).json()
        if res.get("hits"):
            return res["hits"][0]["largeImageURL"]
    except Exception:
        pass
    return None

def post_to_facebook(message, image_url):
    url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/photos"
    payload = {
        "url": image_url,
        "caption": message,
        "access_token": FB_PAGE_TOKEN
    }
    res = requests.post(url, data=payload, timeout=30)
    res.raise_for_status()
    print("تم النشر بنجاح على فيسبوك!")

def main():
    history = load_history()
    
    print("Generating content...")
    content = generate_content(history)
    topic = content["topic_title"]
    message = content["post_body"]
    keyword = content["search_keyword"]
    
    print(f"Topic: {topic}")
    print(f"Searching image for: {keyword}")
    
    # المحاولة في Pexels أولاً
    image_url = get_pexels_image(keyword)
    
    # لو ملقاش، يحاول في Pixabay
    if not image_url:
        print("الصورة غير موجودة في Pexels، جاري البحث في Pixabay...")
        image_url = get_pixabay_image(keyword)
    
    # النشر
    if image_url:
        post_to_facebook(message, image_url)
    else:
        print("لم يتم العثور على صورة في الموقعين، جاري نشر نص فقط...")
        text_url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/feed"
        res = requests.post(text_url, data={"message": message, "access_token": FB_PAGE_TOKEN}, timeout=30)
        res.raise_for_status()
        
    save_to_history(topic)

if __name__ == "__main__":
    main()
