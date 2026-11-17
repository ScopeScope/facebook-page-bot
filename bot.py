import os
import re
import json
import requests
import google.generativeai as genai

# إعداد المتغيرات
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN") # ده بقى توكن الصفحة المباشر
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
    genai.configure(api_key=GEMINI_API_KEY)
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
            
            match_flash = re.match(r'^models/gemini-(\d+(?:\.\d+)?)-flash$', name)
            if match_flash:
                version = float(match_flash.group(1))
                standard_flash.append((version, m.name))
                continue
                
            if 'flash' in name:
                other_flash.append(m.name)
                continue
                
            match_pro = re.match(r'^models/gemini-(\d+(?:\.\d+)?)-pro$', name)
            if match_pro:
                version = float(match_pro.group(1))
                pro_models.append((version, m.name))
                continue
                
            fallback_models.append(m.name)
            
    except Exception as e:
        pass

    standard_flash.sort(key=lambda x: x[0], reverse=True)
    pro_models.sort(key=lambda x: x[0], reverse=True)
    other_flash.sort(reverse=True)
    fallback_models.sort(reverse=True)
    
    candidates = (
        [m[1] for m in standard_flash] +
        other_flash +
        [m[1] for m in pro_models] +
        fallback_models
    )
    
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
            last_error = e
            continue
            
    raise RuntimeError(f"فشلت جميع الموديلات المتاحة. آخر خطأ: {last_error}")

def get_pexels_image(query):
    if not PEXELS_API_KEY:
        return None
    headers = {"Authorization": PEXELS_API_KEY.strip()}
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
    url = f"https://pixabay.com/api/?key={PIXABAY_API_KEY.strip()}&q={query}&image_type=photo&per_page=3"
    try:
        res = requests.get(url, timeout=15).json()
        if res.get("hits"):
            return res["hits"][0]["largeImageURL"]
    except Exception:
        pass
    return None

def post_to_facebook(message, image_url):
    # استخدام توكن الصفحة المباشر
    token = FB_PAGE_TOKEN.strip()
    page_id = FB_PAGE_ID.strip()
    
    if image_url:
        try:
            # تحميل الصورة ورفعها مباشرة لفيسبوك لتجنب أخطاء الروابط
            img_res = requests.get(image_url, timeout=20)
            img_res.raise_for_status()
            
            url = f"https://graph.facebook.com/v19.0/{page_id}/photos"
            files = {"source": ("post.jpg", img_res.content, "image/jpeg")}
            data = {"caption": message, "access_token": token}
            
            res = requests.post(url, data=data, files=files, timeout=30)
            res.raise_for_status()
            print("تم النشر بالصورة بنجاح على فيسبوك!")
            return
        except Exception as e:
            print(f"تعذر رفع الصورة، جاري النشر كنص...")

    # النشر كنص فقط في حالة فشل الصورة
    text_url = f"https://graph.facebook.com/v19.0/{page_id}/feed"
    res = requests.post(text_url, data={"message": message, "access_token": token}, timeout=30)
    res.raise_for_status()
    print("تم نشر النص بنجاح على فيسبوك!")

def main():
    history = load_history()
    print("Generating content...")
    content = generate_content(history)
    topic = content["topic_title"]
    message = content["post_body"]
    keyword = content["search_keyword"]
    
    print(f"Topic: {topic}")
    print(f"Searching image for: {keyword}")
    
    image_url = get_pexels_image(keyword)
    if not image_url:
        image_url = get_pixabay_image(keyword)
    
    post_to_facebook(message, image_url)
    save_to_history(topic)

if __name__ == "__main__":
    main()
