import os
import json
import asyncio
import google.generativeai as genai
from datetime import datetime
from twikit import Client

# --- 設定 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
X_USERNAME = os.getenv("X_USERNAME")
X_EMAIL = os.getenv("X_EMAIL")
X_PASSWORD = os.getenv("X_PASSWORD")

TARGET_ACCOUNTS = [
    "travismillerx13",
    "FloTrack",
    "TrackGazette",
    "Getsuriku"
]

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

def analyze_with_gemini(text):
    prompt = f"""
    以下の陸上競技の速報ツイートを解析し、JSON形式で返してください。
    【判定基準】
    - 記録の速報（タイムや順位）なら is_record: true
    - 凄さの評価(score): 1〜5
    - 解説(comment): 20文字程度で補足

    ツイート内容: {text}
    出力形式: {{"is_record": bool, "event": "種目", "name": "選手名", "time": "記録", "score": int, "comment": "解説"}}
    """
    try:
        response = model.generate_content(prompt)
        res_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(res_text)
    except:
        return None

async def main(): # asyncを追加
    client = Client('ja-JP')
    
    # ログイン (awaitを追加)
    await client.login(auth_info_1=X_USERNAME, auth_info_2=X_EMAIL, password=X_PASSWORD)

    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        data = []

    existing_ids = [item.get('id') for item in data]

    for screen_name in TARGET_ACCOUNTS:
        print(f"Checking @{screen_name}...")
        try:
            user = await client.get_user_by_screen_name(screen_name) # awaitを追加
            tweets = await user.get_tweets('Tweets', count=5) # awaitを追加

            for tweet in tweets:
                if tweet.id in existing_ids:
                    continue

                result = analyze_with_gemini(tweet.text)
                if result and result['is_record']:
                    result['id'] = tweet.id
                    result['account'] = screen_name
                    result['date'] = datetime.now().strftime("%m/%d %H:%M")
                    data.insert(0, result)
                    print(f"New record found: {result['event']} {result['time']}")
        except Exception as e:
            print(f"Error checking {screen_name}: {e}")

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data[:100], f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main()) # 実行方法を変更
