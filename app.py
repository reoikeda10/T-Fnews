import os
import json
import asyncio
import google.generativeai as genai
from datetime import datetime
from twikit import Client

# --- 設定 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# クッキーを使うため、Xのパスワード等の環境変数は（バックアップ用以外）不要になります

TARGET_ACCOUNTS = [
    "travismillerx13",
    "FloTrack",
    "TrackGazette",
    "Getsuriku"
]

# Geminiの設定
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
        # JSON部分のみを抽出
        res_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(res_text)
    except Exception as e:
        print(f"Gemini Error: {e}")
        return None

async def main():
    client = Client('ja-JP')
    
    # 【重要】パスワードログインの代わりにクッキーファイルを読み込む
    try:
        if os.path.exists('cookies.json'):
            client.load_cookies('cookies.json')
            print("Successfully loaded cookies.")
        else:
            print("Error: cookies.json not found. Please upload it to your repository.")
            return
    except Exception as e:
        print(f"Failed to load cookies: {e}")
        return

    # 既存データの読み込み
    try:
        if os.path.exists('data.json'):
            with open('data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = []
    except Exception:
        data = []

    existing_ids = [item.get('id') for item in data]

    for screen_name in TARGET_ACCOUNTS:
        print(f"Checking @{screen_name}...")
        try:
            # スクリーンネームからユーザー情報を取得
            user = await client.get_user_by_screen_name(screen_name)
            # 最新のツイートを5件取得
            tweets = await user.get_tweets('Tweets', count=5)

            for tweet in tweets:
                # 重複チェック（保存済みならスキップ）
                if str(tweet.id) in [str(eid) for eid in existing_ids]:
                    continue

                # Geminiで解析
                result = analyze_with_gemini(tweet.text)
                
                if result and result.get('is_record'):
                    result['id'] = tweet.id
                    result['account'] = screen_name
                    result['date'] = datetime.now().strftime("%m/%d %H:%M")
                    # リストの先頭に追加
                    data.insert(0, result)
                    print(f"New Record Found: {result['event']} - {result['time']}")
        
        except Exception as e:
            print(f"Error checking {screen_name}: {e}")
            # 連続エラーを防ぐための短い休憩
            await asyncio.sleep(2)

    # 最大100件まで保存
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data[:100], f, ensure_ascii=False, indent=2)
    print("Update completed.")

if __name__ == "__main__":
    asyncio.run(main())
