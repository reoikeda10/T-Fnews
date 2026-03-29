import os
import json
import asyncio
from datetime import datetime
from google import genai
from twikit import Client

# --- 設定 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
X_COOKIES = os.getenv("X_COOKIES")

# 監視対象のアカウント
TARGET_ACCOUNTS = ["travismillerx13", "FloTrack", "TrackGazette", "Getsuriku"]

# Gemini Client 初期化
client_gemini = genai.Client(api_key=GEMINI_API_KEY)

def analyze_with_gemini(text):
    """
    ツイート内容を解析し、10段階評価とカテゴリ分けを行う
    """
    prompt = f"""
    以下の陸上競技のツイートを解析し、必ず指定のJSON形式で返してください。
    
    【判定・分類ルール】
    1. is_record: 記録の速報、大会結果なら true。それ以外（単なる意気込みや宣伝）は false。
    2. category: 以下のいずれかに分類してください。
       「短距離」「ハードル」「中距離」「長距離」「跳躍」「投擲」「ロード」
    3. score: 記録の凄さを1〜10の整数で評価。
       - 10: 世界新記録、歴史的な快挙
       - 9: 日本新記録、世界最高峰の大会での優勝
       - 7-8: 非常に高いレベルの自己ベストや好記録
       - 4-6: 一般的な大会の優勝や標準的な記録
       - 1-3: 記録ではあるが、凄さは控えめ
    4. comment: 20文字以内で簡潔に解説（例：追い風参考ながら驚異のタイム）

    ツイート内容: {text}

    出力形式:
    {{"is_record": bool, "category": "カテゴリ名", "event": "種目", "name": "選手名", "time": "記録", "score": int, "comment": "解説"}}
    """
    try:
        # Gemini 3.1 Flash-Lite を使用
        response = client_gemini.models.generate_content(
            model='gemini-3.1-flash-lite-preview',
            contents=prompt
        )
        # JSON部分を抽出
        res_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(res_text)
    except Exception as e:
        print(f"Gemini Analysis Error: {e}")
        return None

async def main():
    # Xクライアントの準備
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    client_x = Client('ja-JP', user_agent=ua)
    
    # クッキーの読み込みと変換
    if X_COOKIES:
        try:
            raw_cookies = json.loads(X_COOKIES)
            cookie_dict = {c['name']: c['value'] for c in raw_cookies if 'name' in c and 'value' in c}
            client_x.set_cookies(cookie_dict)
            print("Cookies loaded successfully.")
        except Exception as e:
            print(f"Cookie Processing Error: {e}")
            return
    else:
        print("X_COOKIES not found in environment variables.")
        return

    # 既存データの読み込み
    try:
        if os.path.exists('data.json'):
            with open('data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = []
    except:
        data = []

    # 重複判定用のIDリスト
    existing_ids = [str(item.get('id')) for item in data]

    for screen_name in TARGET_ACCOUNTS:
        print(f"Scanning @{screen_name}...")
        try:
            # X側の負荷制限を考慮して待機
            await asyncio.sleep(5)
            user = await client_x.get_user_by_screen_name(screen_name)
            tweets = await user.get_tweets('Tweets', count=5)
            
            if not tweets:
                continue

            for tweet in tweets:
                # 既に保存済みならスキップ
                if str(tweet.id) in existing_ids:
                    continue

                # Geminiで解析（10段階評価）
                result = analyze_with_gemini(tweet.text)
                
                if result and result.get('is_record'):
                    result['id'] = tweet.id
                    result['account'] = screen_name
                    # 検索や固定表示に使うため日付に年を入れる
                    result['date'] = datetime.now().strftime("%Y/%m/%d %H:%M")
                    
                    # リストの先頭に追加
                    data.insert(0, result)
                    print(f"-> New Record: [{result['category']}] {result['name']} ({result['score']}/10)")
        
        except Exception as e:
            print(f"Failed to fetch from @{screen_name}: {e}")
            continue

    # 最新100件を保存
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data[:100], f, ensure_ascii=False, indent=2)
    print("Update process finished.")

if __name__ == "__main__":
    asyncio.run(main())
