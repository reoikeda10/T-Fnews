import os
import json
import google.generativeai as genai
from datetime import datetime
from twikit import Client  # pip install twikit

# --- 設定 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Xのログイン用（後ほどGitHub Secretsに登録してください）
X_USERNAME = os.getenv("X_USERNAME")
X_EMAIL = os.getenv("X_EMAIL")
X_PASSWORD = os.getenv("X_PASSWORD")

# 監視したいアカウントのスクリーンネーム（@を除いたID）
TARGET_ACCOUNTS = [
    "travismillerx13",  # 日本陸連
    "FloTrack",    # 駅伝ニュース
    "TrackGazette",  
    "Getsuriku"# 記録速報系
]

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash") # Gemini 3.1 Flash Lite相当

def analyze_with_gemini(text):
    # (前回と同じGemini解析ロジック)
    prompt = f"以下の陸上速報を解析しJSONで返せ: {text}..."
    # ... 省略 ...
    return result

def main():
    client = Client('ja-JP')
    
    # ログイン処理（本来はCookie保存が望ましいですが、まずは簡易版）
    client.login(auth_info_1=X_USERNAME, auth_info_2=X_EMAIL, password=X_PASSWORD)

    # 既存データの読み込み
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        data = []

    existing_ids = [item.get('id') for item in data]

    for screen_name in TARGET_ACCOUNTS:
        print(f"Checking @{screen_name}...")
        try:
            user = client.get_user_by_screen_name(screen_name)
            tweets = user.get_tweets('Tweets', count=5) # 最新5件

            for tweet in tweets:
                # すでに保存済みのツイートはスキップ
                if tweet.id in existing_ids:
                    continue

                result = analyze_with_gemini(tweet.text)
                if result and result['is_record']:
                    result['id'] = tweet.id
                    result['account'] = screen_name
                    result['date'] = datetime.now().strftime("%m/%d %H:%M")
                    data.insert(0, result)
        except Exception as e:
            print(f"Error checking {screen_name}: {e}")

    # 保存（最大100件）
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data[:100], f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
