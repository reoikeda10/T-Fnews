import os
import json
import asyncio
from datetime import datetime
from google import genai  # 最新の google-genai ライブラリを使用
from twikit import Client

# --- 設定 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
X_COOKIES = os.getenv("X_COOKIES")

# 取得対象のアカウント
TARGET_ACCOUNTS = ["travismillerx13", "FloTrack", "TrackGazette", "Getsuriku"]

# 最新の Gemini Client 初期化
client_gemini = genai.Client(api_key=GEMINI_API_KEY)

def analyze_with_gemini(text):
    prompt = f"""
    以下の陸上競技の速報ツイートを解析し、JSON形式で返してください。
    【判定基準】
    - 記録の速報（タイムや順位）なら is_record: true
    - 凄さの評価(score): 1〜5
    - 解説(comment): 20文字程度で簡潔に

    ツイート内容: {text}
    出力形式: {{"is_record": bool, "event": "種目", "name": "選手名", "time": "記録", "score": int, "comment": "解説"}}
    """
    try:
        # ★ここを Gemini 3.1 Flash-Lite に変更
        response = client_gemini.models.generate_content(
            model='gemini-3.1-flash-lite-preview',
            contents=prompt
        )
        res_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(res_text)
    except Exception as e:
        print(f"Gemini Error (Quota?): {e}")
        return None

async def main():
    # Xクライアントの準備 (User-Agentを偽装してエラー回避)
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    client_x = Client('ja-JP', user_agent=ua)
    
    # クッキーの読み込み
    if X_COOKIES:
        try:
            raw_cookies = json.loads(X_COOKIES)
            cookie_dict = {c['name']: c['value'] for c in raw_cookies if 'name' in c and 'value' in c}
            client_x.set_cookies(cookie_dict)
            print("Cookies loaded.")
        except Exception as e:
            print(f"Cookie Error: {e}")
            return
    else:
        print("Error: X_COOKIES not found.")
        return

    # 既存データの読み込み
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        data = []

    existing_ids = [str(item.get('id')) for item in data]

    for screen_name in TARGET_ACCOUNTS:
        print(f"Checking @{screen_name}...")
        try:
            # X側の負荷軽減のため少し待機
            await asyncio.sleep(3)
            user = await client_x.get_user_by_screen_name(screen_name)
            tweets = await user.get_tweets('Tweets', count=5)
            
            for tweet in tweets:
                if str(tweet.id) in existing_ids:
                    continue

                # Gemini 3.1 Flash-Lite で解析
                result = analyze_with_gemini(tweet.text)
                
                if result and result.get('is_record'):
                    result['id'] = tweet.id
                    result['account'] = screen_name
                    result['date'] = datetime.now().strftime("%m/%d %H:%M")
                    data.insert(0, result)
                    print(f"Added: {result['event']} {result['time']}")
        
        except Exception as e:
            # Xの仕様変更エラー(KEY_BYTE等)が出ても、プログラムを落とさず次へ
            print(f"Skipping @{screen_name}: {e}")
            continue

    # 保存
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data[:100], f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
