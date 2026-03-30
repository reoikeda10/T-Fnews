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

# 巡回URL
URL_FLOTRACK = "https://www.flotrack.org/articles"
URL_GETSURIKU = "https://www.rikujyokyogi.co.jp/archives/category/news/kokunai"
URL_WORLD_ATHLETICS = "https://worldathletics.org/competitions/world-athletics-continental-tour/calendar-results"

def analyze_with_gemini(text, source_url):
    """
    記事から【すべての】好記録をリスト形式で抽出する
    """
    prompt = f"""
    以下の陸上競技ニュースから、重要な好記録や速報を【すべて】抽出し、JSONのリスト形式で返してください。
    
    【抽出ルール】
    - 記録（タイム、距離、順位など）が含まれるもののみ抽出。
    - category: 「短距離」「ハードル」「中距離」「長距離」「跳躍」「投擲」「ロード」から選択。
    - score: 記録の凄さを1〜10で評価。
    - 記事に複数の選手や種目の記録がある場合は、それらをすべて個別の要素としてリストに入れてください。

    テキスト: {text[:4000]} 
    
    出力形式（必ずこの配列形式で）:
    [
      {{"is_record": true, "category": "カテゴリ名", "event": "種目", "name": "選手名", "time": "記録", "score": int, "comment": "簡潔な解説"}},
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

def get_article_content(url, selector):
    """本文抽出（余計な要素を排除）"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'lxml')
        for s in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
            s.decompose()
        
        # セレクターで見つからなければbody全体から取る
        main_content = soup.select_one(selector)
        if main_content:
            return main_content.get_text(separator=' ', strip=True)
        return soup.find('body').get_text(separator=' ', strip=True)
    except:
        return ""

def main():
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        data = []
    
    processed_urls = [item.get('source_url') for item in data if 'source_url' in item]

    # サイトごとの設定（URL, CSSセレクタ）
    targets = [
        {"name": "FloTrack", "url": URL_FLOTRACK, "link_sel": 'a[href*="/articles/"]', "body_sel": "article"},
        {"name": "Getsuriku", "url": URL_GETSURIKU, "link_sel": ".post-list a", "body_sel": ".entry-content"}
    ]

    for target in targets:
        print(f"Checking {target['name']}...")
        try:
            res = requests.get(target['url'], timeout=10)
            soup = BeautifulSoup(res.text, 'lxml')
            links = soup.select(target['link_sel'])
            
            # 最新の3記事程度をチェック
            for link in links[:3]:
                url = link['href'] if link['href'].startswith('http') else target['url'].split('/articles')[0] + link['href']
                if url not in processed_urls:
                    print(f"  Analysing: {url}")
                    content = get_article_content(url, target['body_sel'])
                    extracted_list = analyze_with_gemini(content, url)
                    
                    for res_item in extracted_list:
                        if res_item.get('is_record'):
                            res_item.update({
                                "id": f"news_{int(time.time())}_{data.__len__()}",
                                "source_url": url,
                                "date": datetime.now().strftime("%Y/%m/%d %H:%M")
                            })
                            data.insert(0, res_item)
                    # 1サイトにつき1つの新URLを処理したら一度保存（レート制限対策）
                    processed_urls.append(url)
        except Exception as e:
            print(f"Error at {target['name']}: {e}")

    # World Athletics の Result ボタンチェック
    print("Checking World Athletics Results...")
    try:
        res = requests.get(URL_WORLD_ATHLETICS, timeout=10)
        soup = BeautifulSoup(res.text, 'lxml')
        # "Result" または "Results" というテキストを持つリンクを探す
        result_links = [a for a in soup.find_all('a', href=True) if 'result' in a.get_text(strip=True).lower()]
        
        for link in result_links[:3]:
            r_url = link['href'] if link['href'].startswith('http') else "https://worldathletics.org" + link['href']
            if r_url not in processed_urls:
                print(f"  Analysing Results: {r_url}")
                content = get_article_content(r_url, '.results-table, main')
                extracted_list = analyze_with_gemini(content, r_url)
                for res_item in extracted_list:
                    if res_item.get('is_record'):
                        res_item.update({
                            "id": f"wa_{int(time.time())}_{data.__len__()}",
                            "source_url": r_url,
                            "date": datetime.now().strftime("%Y/%m/%d %H:%M")
                        })
                        data.insert(0, res_item)
                processed_urls.append(r_url)
    except Exception as e:
        print(f"WA error: {e}")

    # 保存（最新150件程度保持）
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data[:150], f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
