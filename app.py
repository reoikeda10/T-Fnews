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
    prompt = f"""
    以下の陸上競技データから、重要な記録を【すべて】抽出し、必ずJSONのリスト形式で返してください。
    
    【抽出項目】
    - category: 「短距離」「長距離」など
    - event: 種目名
    - name: 選手名
    - time: 記録
    - score: 1-10の評価
    - nationality: 国籍（不明なら空文字）
    - age: 年齢または生年（不明なら空文字）
    - location: 大会名や開催地
    - wind: 風速（+1.2等、必要な種目のみ。不要なら空文字）
    - comment: 簡潔な解説

    テキスト: {text[:5000]}
    
    出力形式:
    [
      {{"is_record": true, "category": "...", "event": "...", "name": "...", "time": "...", "score": 10, "nationality": "...", "age": "...", "location": "...", "wind": "...", "comment": "..."}},
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
    except:
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
