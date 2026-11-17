import os
import json
import requests
import google.generativeai as genai

# إعداد المتغيرات من GitHub Secrets
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
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

def generate_content(history_list):
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    history_str = ", ".join(history_list[-30:]) # نبعت آخر 30 موضوع عشان منستهلكش التوكنز
    
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
    
    # تنظيف الرد لو فيه علامات Markdown
    json_text = response.text.strip().replace('```json', '').replace('```', '')
    return json.loads(json_text)

def get_pexels_image(query):
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"
    res = requests.get(url, headers=headers).json()
    if res.get("photos"):
        return res["photos"][0]["src"]["large"]
    return None # لو ملقاش صورة

def post_to_facebook(message, image_url):
    # استخدام Photos API للنشر بصورة
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
    
    image_url = get_pexels_image(keyword)
    
    # لو Pexels ملقاش صورة، هينشر البوست كنص فقط على نقطة نهاية Feed
    if image_url:
        post_to_facebook(message, image_url)
    else:
        print("لم يتم العثور على صورة، جاري نشر نص فقط...")
        text_url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/feed"
        requests.post(text_url, data={"message": message, "access_token": FB_PAGE_TOKEN})
        
    save_to_history(topic)

if __name__ == "__main__":
    main()
