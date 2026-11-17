import os
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

def get_latest_gemini_model():
    """دالة مضادة لتحديثات جوجل: بتجيب أحدث موديل نصوص أياً كان اسمه"""
    genai.configure(api_key=GEMINI_API_KEY)
    text_models = []
    
    # 1. بنسحب كل الموديلات اللي بتدعم توليد النصوص
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            text_models.append(m.name)
            
    if not text_models:
        return "models/gemini-1.5-flash" # خط دفاع أخير لو السيرفر واقع
        
    text_models.sort() # بنرتبهم عشان الأحدث يكون في الآخر
    
    # الخطة أ: لو لسه بيستخدموا اسم فلاش
    flash_models = [m for m in text_models if 'flash' in m]
    if flash_models:
        return flash_models[-1]
        
    # الخطة ب: لو غيروا الاسم لـ برو
    pro_models = [m for m in text_models if 'pro' in m]
    if pro_models:
        return pro_models[-1]
        
    # الخطة ج: لو غيروا الأسامي كلها، هنختار أحدث موديل في القايمة
    return text_models[-1]

def generate_content(history_list):
    latest_model_name = get_latest_gemini_model()
    print(f"Using Gemini Model: {latest_model_name}")
    model = genai.GenerativeModel(latest_model_name)
    
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
    
    response = model.generate_content(prompt)
    json_text = response.text.strip().replace('```json', '').replace('```', '')
    return json.loads(json_text)

def get_pexels_image(query):
    if not PEXELS_API_KEY: return None
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"
    try:
        res = requests.get(url, headers=headers).json()
        if res.get("photos"):
            return res["photos"][0]["src"]["large"]
    except:
        pass
    return None

def get_pixabay_image(query):
    if not PIXABAY_API_KEY: return None
    url = f"https://pixabay.com/api/?key={PIXABAY_API_KEY}&q={query}&image_type=photo&per_page=3"
    try:
        res = requests.get(url).json()
        if res.get("hits"):
            return res["hits"][0]["largeImageURL"]
    except:
        pass
    return None

def post_to_facebook(message, image_url):
    url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/photos"
    payload = {
        "url": image_url,
        "caption": message,
        "access_token": FB_PAGE_TOKEN
    }
    res = requests.post(url, data=payload)
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
        requests.post(text_url, data={"message": message, "access_token": FB_PAGE_TOKEN})
        
    save_to_history(topic)

if __name__ == "__main__":
    main()
