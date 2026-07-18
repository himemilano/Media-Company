import os
import sys
import json
import time
import requests
import subprocess
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont

# Google API公式ライブラリの読み込み
try:
    import google.oauth2.credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    YOUTUBE_API_AVAILABLE = True
except ImportError:
    YOUTUBE_API_AVAILABLE = False

# ==========================================================
# ⚙️ 1. 設定・ディレクトリ構成
# ==========================================================
jst = timezone(timedelta(hours=9))
current_date = datetime.now(jst).strftime("%Y-%m-%d")

TEMPLATE_DIR = "../../templates" # ルートの共通テンプレートフォルダを参照
WORKSPACE_DIR = "workspace"      # ローカルフォルダ
TEMP_DIR = "temp_assets"

os.makedirs(WORKSPACE_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

class JapanKidsCompassEngine:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

    def ask_gemini(self, prompt, system_instruction=""):
        if not self.api_key:
            return "⚠️ API KEY IS MISSING"
        
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_instruction}]}
        }
        url = f"{self.base_url}?key={self.api_key}"
        
        for delay in [1, 2, 4]:
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=60)
                if res.status_code == 200:
                    return res.json()["candidates"][0]["content"]["parts"][0]["text"]
                elif res.status_code == 429:
                    print(f"⚠️ API制限 (429)。{delay}秒待機して再試行します...")
                    time.sleep(delay)
            except Exception as e:
                print(f"⚠️ 接続エラー: {e}")
                time.sleep(delay)
        return "⚠️ APIエラーのため、ローカル復旧用テキストを自動生成します。"

    def generate_subtitle_image(self, text, output_path, width=1080, height=1920):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "Arial"
        ]
        font = None
        for path in font_paths:
            if os.path.exists(path):
                font = ImageFont.truetype(path, 54)
                break
        if not font:
            font = ImageFont.load_default()

        words = text.split()
        lines = []
        current_line = []
        for word in words:
            current_line.append(word)
            if len(" ".join(current_line)) > 18:
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [word]
        if current_line:
            lines.append(" ".join(current_line))
            
        final_text = "\n".join(lines[:2])

        box_padding = 24
        line_height = 65
        
        max_line_width = max([len(line) * 28 for line in lines]) if lines else 300
        box_width = min(max_line_width + box_padding * 2, 980)
        box_height = (len(lines) * line_height) + box_padding * 2
        
        box_x1 = (width - box_width) // 2
        box_y1 = 1300
        box_x2 = box_x1 + box_width
        box_y2 = box_y1 + box_height

        draw.rounded_rectangle(
            [box_x1, box_y1, box_x2, box_y2],
            radius=15,
            fill=(0, 0, 0, 190)
        )

        for idx, line in enumerate(lines[:2]):
            text_w = len(line) * 28
            text_x = (width - text_w) // 2
            text_y = box_y1 + box_padding + (idx * line_height)
            draw.text((text_x, text_y), line, fill=(255, 255, 255, 255), font=font)

        img.save(output_path, "PNG")

    def upload_to_youtube(self, file_path, title, description, tags):
        if not YOUTUBE_API_AVAILABLE:
            print("⚠️ [YouTube API] 必要なパッケージがインポートされていません。アップロードをスキップします。")
            return False

        client_id = os.getenv("YOUTUBE_CLIENT_ID")
        client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
        refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

        if not all([client_id, client_secret, refresh_token]):
            print("💡 [YouTube API] API認証トークンがSecretsに設定されていません。ローカルに完成動画を保存して終了します。")
            return False

        print("🚀 [YouTube API] 認証を確立し、自動アップロードプロセスを開始します...")
        try:
            creds = google.oauth2.credentials.Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret
            )
            youtube = build("youtube", "v3", credentials=creds)

            seo_title = f"{title[:80]} #Shorts #JapanKidsCompass"

            body = {
                "snippet": {
                    "title": seo_title,
                    "description": description,
                    "tags": tags + ["Shorts", "JapanKidsCompass"],
                    "categoryId": "27" 
                },
                "status": {
                    "privacyStatus": "public", 
                    "selfDeclaredMadeForKids": False
                }
            }

            media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/mp4")
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"   [アップロード中] {int(status.progress() * 100)}% 完了...")

            print(f"🎉 【YouTube投稿成功！】動画ID: {response.get('id')}")
            print(f"🔗 視聴リンク: https://youtu.be/{response.get('id')}")
            return True

        except Exception as e:
            print(f"❌ YouTubeアップロード中に重大なエラーが発生しました: {e}")
            return False

    def run_rendering_pipeline(self):
        print("🎬 [映像編集部] 自律レンダリングプロセスを開始します。")

        concepts = {
            1: {"code": "JKC-A-Commute-v1", "name": "Walking to School Together", "desc": "日本の集団登校：高学年が低学年を保護し、地域と挨拶する協調性と責任感の育成"},
            2: {"code": "JKC-B-Classroom-v1", "name": "Classroom Etiquette", "desc": "日本の授業風景：全員で起立、礼をして授業を開始し、相互の敬意と高い集中力を学ぶ環境"},
            3: {"code": "JKC-C-Lunch-v1", "name": "The School Lunch Cooperation", "desc": "日本の給食：自分たちで均等に配膳し、お互いに感謝して全員で同じ食事を食べる協力体制"},
            4: {"code": "JKC-D-Cleaning-v1", "name": "Cleaning Our School Space", "desc": "日本の学校掃除：自分たちの学び舎を全員で綺麗にし、公共の道具や環境を愛護・尊重する精神"},
            5: {"code": "JKC-E-Gym-v1", "name": "Gym Class & Cooperation", "desc": "日本の体育：技術向上だけでなく、チームメイトと安全を最優先に迅速に行動し助け合う姿勢"},
            6: {"code": "JKC-F-Library-v1", "name": "Library Manners & Silent Focus", "desc": "日本の図書室：公共の場で静粛を保ち、読書に没頭することで他者への配慮と自己内省を育む"},
            7: {"code": "JKC-G-SportsDay-v1", "name": "Undokai Sports Day Spirit", "desc": "日本の運動会：勝ち負けを超え、チーム全員が一枚岩となって最後まで団結する感動と忍耐力"},
            8: {"code": "JKC-H-AfterSchool-v1", "name": "Walking Home Safely", "desc": "日本の下校風景：交通安全を守り、防犯への高い規律意識を持って寄り道せず安全に帰る文化"},
            9: {"code": "JKC-I-DisasterPreparedness-v1", "name": "Disaster Preparedness", "desc": "日本の避難訓練：『おはしも』の精神に基づき、パニックを起こさず他者を思いやり、静かに避難する高度な規律"},
            10: {"code": "JKC-J-SafeNeighborhood-v1", "name": "Safe Neighborhood & Community", "desc": "日本の治安と地域見守り：鍵をかけずとも子供が安心して外で遊べる、誠実さと近隣住民による温かい防犯の輪"}
        }

        day_of_year = datetime.now(jst).timetuple().tm_yday
        concept_idx = (day_of_year % 10) + 1
        chosen = concepts[concept_idx]

        template_filename = f"{chosen['code']}.mp4"
        input_template_path = os.path.join(TEMPLATE_DIR, template_filename)

        print(f"🎬 本日のターゲット背景動画: {input_template_path} (テーマ: {chosen['name']})")

        if not os.path.exists(input_template_path):
            print(f"🛑 [自律スキップ] テンプレート動画 `{input_template_path}` がまだ `templates/` にアップロードされていません。")
            return False

        print("🤖 今日のビジュアルに完璧に一致する5枚のスライド字幕（英語）をGeminiに依頼中...")
        prompt = f"""
Create 5 highly engaging, short, punchy slide subtitles for a 30-second YouTube Shorts video.
The background video being shown is exactly about: "{chosen['desc']}".
The target audience is Western parents interested in Japanese discipline, empathy, and manners.

⚠️ STRICT COMPLIANCE RULE:
- Subtitles MUST perfectly match the theme "{chosen['name']}". Do NOT talk about other school events like lunch or cleaning if the theme is something else.
- Keep each slide text under 10 words (very short, high-converting).
- Deliver strictly in JSON format with keys "slide_1" to "slide_5".
"""
        raw_json = self.ask_gemini(prompt, "You are an elite YouTube Shorts subtitle producer.")
        
        try:
            cleaned_json = raw_json.replace("```json", "").replace("```", "").strip()
            subtitles_data = json.loads(cleaned_json)
        except Exception as e:
            print(f"⚠️ JSONパースに失敗したため、デフォルト字幕を自己修復生成します: {e}")
            subtitles_data = {
                "slide_1": f"Discover Japan's Beautiful {chosen['name']}",
                "slide_2": "Empathy and respect start at age six.",
                "slide_3": "Everyone works together as a team.",
                "slide_4": "Building responsibility for a lifetime.",
                "slide_5": "Would you try this? Subscribe for more!"
            }

        print("🎨 Pillowグラフィックエンジンを駆動。透過字幕カードを自動作成中...")
        sub_image_paths = []
        for i in range(1, 6):
            text_key = f"slide_{i}"
            slide_text = subtitles_data.get(text_key, "Japan Kids Compass")
            img_path = os.path.join(TEMP_DIR, f"slide_{i}.png")
            
            self.generate_subtitle_image(slide_text, img_path)
            sub_image_paths.append(img_path)

        output_video_path = os.path.join(WORKSPACE_DIR, f"{current_date}_completed_shorts.mp4")
        print(f"⚙️ FFmpeg動画合成エンジンを召喚。ミリ単位のタイムオーバーレイ（レンダリング）を実行中...")
        
        filter_complex = (
            "[0:v][1:v]overlay=0:0:enable='between(t,0,6)'[v1];"
            "[v1][2:v]overlay=0:0:enable='between(t,6,12)'[v2];"
            "[v2][3:v]overlay=0:0:enable='between(t,12,18)'[v3];"
            "[v3][4:v]overlay=0:0:enable='between(t,18,24)'[v4];"
            "[v4][5:v]overlay=0:0:enable='between(t,24,30)'[v5]"
        )

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", input_template_path,             
            "-i", sub_image_paths[0],               
            "-i", sub_image_paths[1],               
            "-i", sub_image_paths[2],               
            "-i", sub_image_paths[3],               
            "-i", sub_image_paths[4],               
            "-filter_complex", filter_complex,
            "-map", "[v5]",                        
            "-map", "0:a",                         
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-c:a", "copy",
            output_video_path
        ]

        try:
            subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=True)
            print(f"✅ 【レンダリング完了】テロップ・BGM入り完成版動画が完成しました！ -> {output_video_path}")
            
            for path in sub_image_paths:
                if os.path.exists(path):
                    os.remove(path)
                    
            seo_prompt = f"Create a viral YouTube Shorts Description for our video: '{chosen['name']}' using subtitles: {subtitles_data}"
            seo_info = self.ask_gemini(seo_prompt, "You are a professional YouTube growth hacker.")
            
            self.upload_to_youtube(
                file_path=output_video_path,
                title=f"{chosen['name']} in Japanese Schools 🇯🇵",
                description=seo_info,
                tags=["Japan", "JapaneseSchool", "MindfulParenting", "Independence", "MoralEducation"]
            )
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpegレンダリング中にエラーが発生しました: {e.stderr}")
            return False

def main():
    # 🔑 会長が定義された「メディア統一キー」で完璧に起動！
    api_key = os.getenv("GEMINI_API_KEY_MEDIA")
    
    if not api_key:
        print("❌ GEMINI_API_KEY_MEDIA がセットされていません。")
        sys.exit(1)

    engine = JapanKidsCompassEngine(api_key=api_key)
    engine.run_rendering_pipeline()

if __name__ == "__main__":
    main()
