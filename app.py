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

# 巡回先URL
URL_FLOTRACK = "https://www.flotrack.org/articles"
URL_GETSURIKU = "https://www.rikujyokyogi.co.jp/archives/category/news/kokunai"
URL_WA_CALENDAR = "https://worldathletics.org/competitions/world-athletics-continental-tour/calendar-results"

def analyze_with_gemini(text, source_url):
    """
    抽出したテキストから、重要な好記録をすべてリスト形式で抽出する
    """
    if not text or len(text) < 100:
        return []

    prompt = f"""
    以下の陸上競技のニュースまたはリザルトデータから、重要な好記録（優勝、自己ベスト、日本新、世界新、好タイム）を【すべて】抽出し、必ずJSONのリスト形式で返してください。

    【抽出ルール】
    1. is_record: 記録の速報なら true。
    2. category: 「短距離」「ハードル」「中距離」「長距離」「跳躍」「投擲」「ロード」から選択。
    3. score: 記録の凄さを1〜10の整数で評価（10は世界記録級、9は日本記録級、7-8は非常に優れた記録）。
    4. event: 種目名（例：男子100m）。
    5. name: 選手名。
    6. time: 記録や順位（例：9.97 (+1.2)）。
    7. comment: 20文字以内で簡潔に解説。

    テキストデータ:
    {text[:5000]}

    出力形式（必ずこの配列形式のみで返して）:
    [
      {{"is_record": true, "category": "カテゴリ名", "event": "種目", "name": "選手名", "time": "記録", "score": int, "comment": "解説"}},
      ...
    ]
    """
    try:
        response = client_gemini.models.generate_content(
            model='gemini-3.1-flash-lite-preview',
            contents=prompt
        )
        res_text = response.text.replace('```json', '').replace('```', '').strip()
        results = json.loads(res_text)
        return results if isinstance(results, list) else [results]
    except Exception as e:
        print(f"Gemini Error: {e}")
        return []

def get_page_content(url, selector):
    """
    指定されたURLから、特定のセレクター内の本文テキストのみを取得する（トークン節約）
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'lxml')
        
        # 不要な要素を削除
        for s in soup(['nav', 'header', 'footer', 'script', 'style', 'aside', 'iframe', 'ads']):
            s.decompose()
            
        main_content = soup.select_one(selector)
        if main_content:
            return main_content.get_text(separator=' ', strip=True)
        return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        print(f"Content fetch error: {url} - {e}")
        return ""

def main():
    # 既存データの読み込み
    try:
        if os.path.exists('data.json'):
            with open('data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = []
    except:
        data = []
    
    # 既読URLの管理
    processed_urls = [item.get('source_url') for item in data if 'source_url' in item]
    
    # 今日の日付（World Athletics用: 例 "30 Mar 2026"）
    today_str = datetime.now().strftime("%d %b %Y").lstrip('0')

    # --- 1. ニュースサイト巡回 ---
    news_targets = [
        {"name": "FloTrack", "url": URL_FLOTRACK, "link_sel": 'a[href*="/articles/"]', "body_sel": "article, .article-body", "base": "https://www.flotrack.org"},
        {"name": "Getsuriku", "url": URL_GETSURIKU, "link_sel": ".post-list a", "body_sel": ".entry-content", "base": ""}
    ]

    for nt in news_targets:
        print(f"Checking {nt['name']}...")
        try:
            res = requests.get(nt['url'], timeout=10)
            soup = BeautifulSoup(res.text, 'lxml')
            links = soup.select(nt['link_sel'])
            
            # 最新の2記事をチェック
            for link in links[:2]:
                href = link['href']
                article_url = href if href.startswith('http') else nt['base'] + href
                
                if article_url not in processed_urls:
                    print(f"  Analysing Article: {article_url}")
                    content = get_page_content(article_url, nt['body_sel'])
                    extracted = analyze_with_gemini(content, article_url)
                    
                    for item in extracted:
                        if item.get('is_record'):
                            item.update({
                                "id": f"news_{int(time.time())}_{len(data)}",
                                "source_url": article_url,
                                "date": datetime.now().strftime("%Y/%m/%d %H:%M")
                            })
                            data.insert(0, item)
                    processed_urls.append(article_url)
        except Exception as e:
            print(f"Error at {nt['name']}: {e}")

    # --- 2. World Athletics Result巡回（今日のみ） ---
    print(f"Checking World Athletics for {today_str}...")
    try:
        res = requests.get(URL_WA_CALENDAR, timeout=15)
        soup = BeautifulSoup(res.text, 'lxml')
        rows = soup.select('table tbody tr')
        
        for row in rows:
            date_cell = row.find('td', {'data-th': 'Date'})
            # 「今日」が含まれているか判定
            if not date_cell or today_str not in date_cell.get_text():
                continue
            
            result_link_tag = row.find('a', string=lambda t: t and 'Result' in t)
            if not result_link_tag:
                continue

            r_url = result_link_tag['href']
            if not r_url.startswith('http'):
                r_url = "https://worldathletics.org" + r_url
            
            # 新しいリザルトなら解析
            if r_url not in processed_urls:
                print(f"  Found Today's Result: {r_url}")
                content = get_page_content(r_url, '.results-table, main, table')
                extracted = analyze_with_gemini(content, r_url)
                
                for item in extracted:
                    if item.get('is_record'):
                        item.update({
                            "id": f"wa_{int(time.time())}_{len(data)}",
                            "source_url": r_url,
                            "date": datetime.now().strftime("%Y/%m/%d %H:%M")
                        })
                        data.insert(0, item)
                processed_urls.append(r_url)
    except Exception as e:
        print(f"World Athletics Error: {e}")

    # 保存（最新150件）
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data[:150], f, ensure_ascii=False, indent=2)
    print(f"Process complete. Total items: {len(data)}")

if __name__ == "__main__":
    main()
