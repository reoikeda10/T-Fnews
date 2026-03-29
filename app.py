import os
import json
import google.generativeai as genai
from datetime import datetime

# --- 設定 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash") # 3.1 Flash LiteもこのSDKで動きます

def analyze_with_gemini(text):
    prompt = f"""
    以下の陸上競技の速報ツイートを解析し、JSON形式で返してください。
    【判定基準】
    - 記録の速報（タイムや順位）なら is_record: true
    - 凄さの評価(score): 1(普通)〜5(歴史的/日本新/大会新)
    - 解説(comment): 20文字程度で専門的な凄さを補足

    ツイート内容: {text}
    出力形式: {{"is_record": bool, "event": "種目", "name": "選手名", "time": "記録", "score": int, "comment": "解説"}}
    """
    try:
        response = model.generate_content(prompt)
        # JSONを抽出
        res_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(res_text)
    except:
        return None

def main():
    # 本来はここでXから取得しますが、まずはデモ用の擬似データで流れを作ります
    # Xの取得部分は後述の「スクレイピング対策」で補足します
    sample_tweets = [
        "日本選手権 男子100m 決勝 サニブラウン 9.99 (+0.5) 優勝！",
        "今日は競技会日和ですね！頑張りましょう。"
    ]
    
    # 既存データの読み込み
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        data = []

    for tweet in sample_tweets:
        result = analyze_with_gemini(tweet)
        if result and result['is_record']:
            result['date'] = datetime.now().strftime("%m/%d %H:%M")
            data.insert(0, result) # 最新を上に
    
    # 保存（最大50件程度に制限）
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data[:50], f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
