import os
import json
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from google import genai

# --- 設定 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client_gemini = genai.Client(api_key=GEMINI_API_KEY)

URL_FLOTRACK = "https://www.flotrack.org/articles"
URL_GETSURIKU = "https://www.rikujyokyogi.co.jp/archives/category/news/kokunai"
URL_WA_CALENDAR = "https://worldathletics.org/competitions/world-athletics-continental-tour/calendar-results"

def analyze_with_gemini(text, source_url):
    if not text or len(text) < 100:
        return []

    # プロンプトをより強力に、かつ具体的に修正
    prompt = f"""
    あなたはプロの陸上競技ライターです。以下のニュース記事から【選手名と具体的な記録】が含まれる情報をすべて抽出し、JSONリストで出力してください。
    
    【抽出の優先順位】
    - 世界新、国内新、自己ベスト(PB)、大会新、標準記録突破、あるいは順位。
    - 記事の中に複数の種目や複数の選手の結果があれば、それらをすべて個別の要素にしてください。
    
    【出力項目】
    - is_record: 記録データがあれば必ず true。
    - category: 「短距離」「長距離」「中距離」「ハードル」「跳躍」「投擲」「ロード」から選択。
    - event: 種目（例: 男子10000m）。
    - name: 選手名（フルネーム）。
    - time: 記録数値（例: 26:33.84）。風速があれば (Wind: +1.2) のように含めてください。
    - score: 記録の凄さを1〜10で。世界記録級は10、国内記録級は9、好記録は7-8。
    - nationality: 国籍（略称可）。
    - age: 年齢または生年。
    - location: 大会名（例: The TEN）。
    - wind: 風速データがあれば。
    - comment: 20文字以内の短い解説。

    テキストデータ:
    {text[:5000]}

    出力形式（JSON配列のみ。説明不要）:
    [
      {{"is_record": true, "category": "...", "event": "...", "name": "...", "time": "...", "score": 10, "nationality": "...", "age": "...", "location": "...", "wind": "...", "comment": "..."}}
    ]
    """
    try:
        response = client_gemini.models.generate_content(
            model='gemini-3.1-flash-lite-preview',
            contents=prompt
        )
        res_text = response.text.replace('```json', '').replace('```', '').strip()
        
        # 稀にGeminiが配列で返さない場合のためのガード
        results = json.loads(res_text)
        if isinstance(results, dict):
            results = [results]
            
        # フィルタリング: 選手名とタイムがあるものだけ残す
        valid_results = [r for r in results if r.get('name') and r.get('time')]
        return valid_results
    except Exception as e:
        print(f"  Gemini parsing error: {e}")
        return []

def get_page_content(url, selector):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
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
    today_str = datetime.now().strftime("%d %b %Y").lstrip('0')

    # ニュースサイト巡回
    news_targets = [
        {"name": "FloTrack", "url": URL_FLOTRACK, "link_sel": 'a[href*="/articles/"]', "body_sel": "article", "base": "https://www.flotrack.org"},
        {"name": "Getsuriku", "url": URL_GETSURIKU, "link_sel": ".post-list a", "body_sel": ".entry-content", "base": ""}
    ]

    for nt in news_targets:
        print(f"Checking {nt['name']}...")
        try:
            res = requests.get(nt['url'], timeout=10)
            soup = BeautifulSoup(res.text, 'lxml')
            links = soup.select(nt['link_sel'])
            for link in links[:3]: # チェック範囲を少し広げる
                href = link['href']
                article_url = href if href.startswith('http') else nt['base'] + href
                if article_url not in processed_urls:
                    print(f"  Analysing Article: {article_url}")
                    content = get_page_content(article_url, nt['body_sel'])
                    extracted = analyze_with_gemini(content, article_url)
                    if extracted:
                        for item in extracted:
                            item.update({
                                "id": f"n_{int(time.time())}_{len(data)}",
                                "source_url": article_url,
                                "date": datetime.now().strftime("%Y/%m/%d %H:%M")
                            })
                            data.insert(0, item)
                        processed_urls.append(article_url) # 記事単位で既読にする
        except Exception as e: print(f"Error at {nt['name']}: {e}")

    # World Athletics巡回
    print(f"Checking World Athletics for {today_str}...")
    try:
        res = requests.get(URL_WA_CALENDAR, timeout=15)
        soup = BeautifulSoup(res.text, 'lxml')
        rows = soup.select('table tbody tr')
        for row in rows:
            date_cell = row.find('td', {'data-th': 'Date'})
            if not date_cell or today_str not in date_cell.get_text():
                continue
            btn = row.find('a', string=lambda t: t and 'Result' in t)
            if not btn: continue
            r_url = btn['href'] if btn['href'].startswith('http') else "https://worldathletics.org" + btn['href']
            if r_url not in processed_urls:
                print(f"  Found Today's Result: {r_url}")
                content = get_page_content(r_url, '.results-table, table')
                extracted = analyze_with_gemini(content, r_url)
                if extracted:
                    for item in extracted:
                        item.update({
                            "id": f"wa_{int(time.time())}_{len(data)}",
                            "source_url": r_url,
                            "date": datetime.now().strftime("%Y/%m/%d %H:%M")
                        })
                        data.insert(0, item)
                    processed_urls.append(r_url)
    except Exception as e: print(f"WA Error: {e}")

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data[:200], f, ensure_ascii=False, indent=2)
    print(f"Process complete. Total items added this run: {len(data)}")

if __name__ == "__main__":
    main()
