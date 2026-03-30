import os
import json
import time
import requests
import datetime
import urllib.parse  # 日本語URL対策
from bs4 import BeautifulSoup
from google import genai

# --- 設定 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client_gemini = genai.Client(api_key=GEMINI_API_KEY)

# 巡回先URL（日本語部分はquoteで変換）
URL_FLOTRACK = "https://www.flotrack.org/articles"
URL_GETSURIKU_NEWS = "https://www.rikujyokyogi.co.jp/archives/category/news/kokunai"
# 「大会結果」の部分を安全なURL形式に変換
target_cat = urllib.parse.quote("大会結果")
URL_GETSURIKU_RESULTS = f"https://www.rikujyokyogi.co.jp/archives/category/news/{target_cat}/"
URL_WA_CALENDAR = "https://worldathletics.org/competitions/world-athletics-continental-tour/calendar-results"

def analyze_with_gemini(text, source_url):
    if not text or len(text) < 100:
        return []
    prompt = f"""
    あなたはプロの陸上競技ライターです。以下のデータから【選手名と具体的な記録】をすべて抽出し、JSONリストで出力してください。
    【ルール】
    - is_record: 記録データがあれば true。
    - category: 「短距離」「長距離」「中距離」「ハードル」「跳躍」「投擲」「ロード」から選択。
    - score: 1〜10で評価。
    - 記事内の全選手・全種目を個別に抽出してください。
    テキスト: {text[:5000]}
    出力形式:
    [ {{"is_record": true, "category": "...", "event": "...", "name": "...", "time": "...", "score": 10, "nationality": "...", "age": "...", "location": "...", "wind": "...", "comment": "..."}} ]
    """
    try:
        response = client_gemini.models.generate_content(model='gemini-3.1-flash-lite-preview', contents=prompt)
        res_text = response.text.replace('```json', '').replace('```', '').strip()
        results = json.loads(res_text)
        return results if isinstance(results, list) else [results]
    except:
        return []

def get_page_content(url, selector):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'lxml')
        for s in soup(['nav', 'header', 'footer', 'script', 'style', 'aside']):
            s.decompose()
        main_content = soup.select_one(selector)
        return main_content.get_text(separator=' ', strip=True) if main_content else soup.get_text(separator=' ', strip=True)
    except:
        return ""

def main():
    try:
        if os.path.exists('data.json'):
            with open('data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = []
    except:
        data = []
    
    processed_urls = [item.get('source_url') for item in data if 'source_url' in item]

    news_targets = [
        {"name": "FloTrack", "url": URL_FLOTRACK, "link_sel": 'a[href*="/articles/"]', "body_sel": "article", "base": "https://www.flotrack.org"},
        {"name": "月陸ニュース", "url": URL_GETSURIKU_NEWS, "link_sel": "article a, .post-list a", "body_sel": ".entry-content", "base": ""},
        {"name": "月陸大会結果", "url": URL_GETSURIKU_RESULTS, "link_sel": "article a, .post-list a", "body_sel": ".entry-content", "base": ""}
    ]

    for nt in news_targets:
        print(f"Checking {nt['name']}...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(nt['url'], headers=headers, timeout=15)
            soup = BeautifulSoup(res.text, 'lxml')
            
            # リンク取得をより柔軟に（href属性があるaタグを抽出）
            links = soup.select(nt['link_sel'])
            valid_links = []
            for l in links:
                if l.has_attr('href') and "/archives/" in l['href']:
                    valid_links.append(l['href'])
            
            # 重複を除去して最新5件
            unique_links = list(dict.fromkeys(valid_links))[:5]
            
            for article_url in unique_links:
                if not article_url.startswith('http'):
                    article_url = nt['base'] + article_url
                
                if article_url not in processed_urls:
                    print(f"  Analysing: {article_url}")
                    content = get_page_content(article_url, nt['body_sel'])
                    extracted = analyze_with_gemini(content, article_url)
                    if extracted:
                        for item in extracted:
                            if item.get('is_record'):
                                item.update({"id": f"n_{int(time.time())}_{len(data)}", "source_url": article_url, "date": datetime.datetime.now().strftime("%Y/%m/%d %H:%M")})
                                data.insert(0, item)
                        processed_urls.append(article_url)
        except Exception as e:
            print(f"  Error at {nt['name']}: {e}")

    # World Athletics（略）
    base_date = datetime.datetime.now()
    target_days = [(base_date + datetime.timedelta(days=i)).strftime("%d %b %Y").lstrip('0') for i in range(-1, 2)]
    print(f"Checking WA for: {target_days}")
    try:
        res = requests.get(URL_WA_CALENDAR, timeout=15)
        soup = BeautifulSoup(res.text, 'lxml')
        for row in soup.select('table tbody tr'):
            date_cell = row.find('td', {'data-th': 'Date'})
            if date_cell and any(day in date_cell.get_text() for day in target_days):
                btn = row.find('a', string=lambda t: t and 'Result' in t)
                if btn:
                    r_url = btn['href'] if btn['href'].startswith('http') else "https://worldathletics.org" + btn['href']
                    if r_url not in processed_urls:
                        print(f"  Found WA: {r_url}")
                        content = get_page_content(r_url, '.results-table, table')
                        extracted = analyze_with_gemini(content, r_url)
                        for item in extracted:
                            if item.get('is_record'):
                                item.update({"id": f"wa_{int(time.time())}_{len(data)}", "source_url": r_url, "date": datetime.datetime.now().strftime("%Y/%m/%d %H:%M")})
                                data.insert(0, item)
                        processed_urls.append(r_url)
    except Exception as e: print(f"  WA Error: {e}")

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data[:300], f, ensure_ascii=False, indent=2)
    print(f"Process finished. Total items: {len(data)}")

if __name__ == "__main__":
    main()
