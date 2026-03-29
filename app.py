import os
import json
import asyncio
import google.generativeai as genai
from datetime import datetime
from twikit import Client

# --- 設定 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
X_COOKIES = os.getenv("X_COOKIES") # Secretsから取得

TARGET_ACCOUNTS = ["travismillerx13", "FloTrack", "TrackGazette", "Getsuriku"]

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

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
        response = model.generate_content(prompt)
        res_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(res_text)
    except:
        return None

async def main():
    client = Client('ja-JP')
    
    # Secretsのクッキーをファイルとして一時保存して読み込む
    if X_COOKIES:
        with open('cookies.json', 'w') as f:
            f.write(X_COOKIES)
        client.load_cookies('cookies.json')
        print("Cookies loaded from Secrets.")
    else:
        print("Error: X_COOKIES not found.")
        return

    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        data = []

    existing_ids = [str(item.get('id')) for item in data]

    for screen_name in TARGET_ACCOUNTS:
        print(f"Checking @{screen_name}...")
        try:
            user = await client.get_user_by_screen_name(screen_name)
            tweets = await user.get_tweets('Tweets', count=5)
            for tweet in tweets:
                if str(tweet.id) in existing_ids:
                    continue
                result = analyze_with_gemini(tweet.text)
                if result and result.get('is_record'):
                    result['id'] = tweet.id
                    result['account'] = screen_name
                    result['date'] = datetime.now().strftime("%m/%d %H:%M")
                    data.insert(0, result)
                    print(f"New Record: {result['event']}")
        except Exception as e:
            print(f"Error at {screen_name}: {e}")

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data[:100], f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
