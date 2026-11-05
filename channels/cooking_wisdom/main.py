import os
import sys
import json
import time
import re
import requests
import subprocess
import asyncio
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont

# 外部ライブラリのチェック
try:
    import google.oauth2.credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    YOUTUBE_API_AVAILABLE = True
except ImportError:
    YOUTUBE_API_AVAILABLE = False

try:
    import edge_tts
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# ==========================================================
# ⚙️ 設定・ディレクトリ構成
# ==========================================================
jst = timezone(timedelta(hours=9))
current_date = datetime.now(jst).strftime("%Y-%m-%d")

TEMPLATE_DIR = "../../templates/cooking_wisdom"  
WORKSPACE_DIR = "workspace"      
TEMP_DIR = "temp_assets"

os.makedirs(WORKSPACE_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

class CookingWisdomEngine:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent"

    def ask_gemini(self, prompt, system_instruction=""):
        if not self.api_key: return "⚠️ API KEY MISSING"
        headers = {"Content-Type": "application/json"}
        
        combined_prompt = f"[Role Instruction]\n{system_instruction}\n\n[Task]\n{prompt}" if system_instruction else prompt
        
        payload = {
            "contents": [{"parts": [{"text": combined_prompt}]}]
        }
        url = f"{self.base_url}?key={self.api_key}"
        # 503（需要スパイク）や429は数分続くことがあるため、分単位のバックオフで粘る。
        # 400/401/403 等のリトライで直らないエラーは即終了する。
        retry_delays = [30, 60, 120, 240]
        attempts = len(retry_delays) + 1
        for attempt in range(attempts):
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=60)
                if res.status_code == 200:
                    return res.json()["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    print(f"⚠️ Gemini API Status Code: {res.status_code}")
                    print(f"⚠️ Gemini Error Response: {res.text}")
                    if res.status_code not in (429, 500, 503):
                        return "⚠️ API ERROR"
            except Exception as e:
                print(f"⚠️ Gemini Connection Error: {e}")
            if attempt < len(retry_delays):
                wait = retry_delays[attempt]
                print(f"⏳ {wait}秒待って再試行します ({attempt + 1}/{attempts})")
                time.sleep(wait)
        return "⚠️ API ERROR"

    def generate_cooking_gradient_placeholder(self, width=1080, height=1920):
        img = Image.new("RGB", (width, height), (54, 31, 20)) 
        draw = ImageDraw.Draw(img)
        for y in range(height):
            r = int(54 + (92 - 54) * (y / height))
            g = int(31 + (53 - 31) * (y / height))
            b = int(20 + (32 - 20) * (y / height))
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        draw.rectangle([40, 40, width-40, height-40], outline=(235, 180, 110), width=2)
        path = os.path.join(TEMP_DIR, "cooking_placeholder_bg.png")
        img.save(path)
        return path

    def generate_subtitle_image(self, text, output_path, width=1080, height=1920):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font_paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", "Arial"]
        font = None
        for path in font_paths:
            if os.path.exists(path):
                font = ImageFont.truetype(path, 52)
                break
        if not font: font = ImageFont.load_default()

        words = text.split()
        lines, current_line = [], []
        for word in words:
            current_line.append(word)
            if len(" ".join(current_line)) > 18:
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [word]
        if current_line: lines.append(" ".join(current_line))
        
        box_padding, line_height = 24, 65
        max_line_width = max([len(line) * 26 for line in lines]) if lines else 300
        box_width = min(max_line_width + box_padding * 2, 980)
        box_height = (len(lines) * line_height) + box_padding * 2
        box_x1, box_y1 = (width - box_width) // 2, 1300
        box_x2, box_y2 = box_x1 + box_width, box_y1 + box_height

        draw.rounded_rectangle([box_x1, box_y1, box_x2, box_y2], radius=15, fill=(28, 18, 14, 220))
        for idx, line in enumerate(lines[:2]):
            text_x = (width - (len(line) * 26)) // 2
            text_y = box_y1 + box_padding + (idx * line_height)
            draw.text((text_x, text_y), line, fill=(255, 248, 240), font=font)
        img.save(output_path, "PNG")

    def create_narration(self, voice_texts, output_path):
        if not TTS_AVAILABLE:
            print("⚠️ edge-tts が利用できません。")
            return False
        full_script = " . ".join(voice_texts)
        
        # 🎙️ 変更点: 落ち着いた信頼感のある男性の声（Christopher）を採用。
        voice = "en-US-ChristopherNeural" 
        
        async def amain():
            communicate = edge_tts.Communicate(full_script, voice, rate="0%")
            await communicate.save(output_path)
        asyncio.run(amain())
        return True

    def get_youtube_service(self):
        # ワークフロー（cooking_wisdom_schedule.yml）の env 名に合わせる
        client_id = os.environ.get("YOUTUBE_CLIENT_ID")
        client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
        refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")
        if not (client_id and client_secret and refresh_token):
            return None
        creds = google.oauth2.credentials.Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret
        )
        return build("youtube", "v3", credentials=creds)

    def upload_video_to_youtube(self, video_path, title, description):
        youtube = self.get_youtube_service()
        if not youtube:
            print("❌ YouTubeの認証情報が設定されていません")
            return False
        
        try:
            channels = youtube.channels().list(part="snippet", mine=True).execute()
            if channels.get("items"):
                channel_name = channels["items"][0]["snippet"]["title"]
                print(f"🔍 接続先チャンネル確認: {channel_name}")
            else:
                print("⚠️ チャンネルが見つかりません。認証アカウントを確認してください。")
        except Exception as e:
            print(f"⚠️ チャンネル確認エラー: {e}")
        
        body = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": ["Shorts", "JapaneseFood", "CookingWisdom", "Recipe"],
                "categoryId": "26" # Howto & Style
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }
        
        try:
            media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
            request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
            response = request.execute()
            print(f"🎉 YouTubeアップロード大成功! Video ID: {response.get('id')}")
            return True
        except Exception as e:
            print(f"❌ YouTubeアップロードエラー: {e}")
            return False

    def run_rendering_pipeline(self):
        print("🎬 [Cooking Wisdom] レンダーパイプライン始動")

        # テンプレート実ファイル（templates/cooking_wisdom/）に対応させたテーマ表
        cooking_concepts = {
            1: {"filename": "JCW_001_The_Science_of_Dashi.mp4", "theme": "The science of dashi: how kombu glutamates and bonito inosinates multiply umami, and why Japanese chefs never boil kombu."},
            2: {"filename": "JCW_002_The_Magic_of_Prep_Work.mp4", "theme": "The magic of prep work (shikomi): why Japanese chefs finish most of the cooking before any heat is applied."},
            3: {"filename": "JCW_003_The_Truth_About_Flash_Freezing.mp4", "theme": "The truth about flash freezing: fast freezing keeps ice crystals small, so cells survive and texture stays close to fresh."},
            4: {"filename": "JCW_004_Layering_Spices_Like_a_Pro.mp4", "theme": "Layering spices like a pro: the science of adding spices in stages, developed by some of Japan's brightest young curry researchers."},
            5: {"filename": "JCW_005_Perfect_Rice_Every_Time.mp4", "theme": "Perfect rice every time: washing, soaking, and resting - the three steps Japanese chefs never skip."},
            6: {"filename": "JCW_006_The_Sa-Shi-Su-Se-So_Order_Explained.mp4", "theme": "The sa-shi-su-se-so order explained: why Japanese seasoning sequence (sugar, salt, vinegar, soy sauce, miso) changes the final flavor."},
            7: {"filename": "JCW_007_Better_Than_Fresh_Frozen_Veggies_and_Fish.mp4", "theme": "Better than fresh: how vegetables and fish frozen at peak season can beat out-of-season 'fresh', and how to thaw them properly."},
            8: {"filename": "JCW_008_Curry_Without_Roux.mp4", "theme": "Curry without roux: building deep Japanese curry flavor from spices, dashi, and grated vegetables alone."},
            9: {"filename": "JCW_009_Mastering_Oil_Temperature.mp4", "theme": "Mastering oil temperature: reading bubbles and chopstick tests - the science of crispy tempura and fried chicken skin."},
            10: {"filename": "JCW_010_Freezing_to_Lock_in_Umami.mp4", "theme": "Freezing to lock in umami: how freezing mushrooms and other ingredients breaks cell walls and can actually deepen flavor."}
        }

        day_of_year = datetime.now(jst).timetuple().tm_yday
        concept_idx = (day_of_year % len(cooking_concepts)) + 1
        chosen = cooking_concepts[concept_idx]

        input_template_path = os.path.join(TEMPLATE_DIR, chosen["filename"])

        if not os.path.exists(input_template_path):
            print(f"ℹ️ 料理テンプレートがないため、専用の特製グラデーション背景を自動生成します。")
            bg_png = self.generate_cooking_gradient_placeholder()
            placeholder_mp4 = os.path.join(TEMP_DIR, "cooking_placeholder_bg_30s.mp4")
            ffmpeg_bg_cmd = ["ffmpeg", "-y", "-loop", "1", "-i", bg_png, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-c:v", "libx264", "-t", "30", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", placeholder_mp4]
            subprocess.run(ffmpeg_bg_cmd, capture_output=True, check=True)
            input_template_path = placeholder_mp4
        else:
            print(f"🎯 本物の料理動画テンプレートを検出: {chosen['filename']}")

        prompt = f"""
Create an engaging YouTube Short title, description, 5 short subtitles AND 5 matching spoken narration scripts about cooking.
[TOPIC]: "{chosen['theme']}"
[RULES]: 
- Provide a catchy YouTube title (max 100 chars).
- Provide a rich English description with hashtags.
- Subtitles under 8 words. 
- Narration under 15 words. 
- Deliver strictly in JSON format with keys "title", "description", "slide_1_text", "slide_1_voice" ... up to "slide_5_voice".
"""
        raw_json = self.ask_gemini(prompt, "You are an experienced traditional Japanese master chef and YouTube Shorts scriptwriter. Output pure JSON only.")
        
        if "⚠️" in raw_json:
            print(f"❌ Gemini APIが正常なレスポンスを返さなかったため、処理を中断します。")
            return False

        try:
            json_match = re.search(r'\{.*\}', raw_json, re.DOTALL)
            data = json.loads(json_match.group(0) if json_match else raw_json)
        except Exception as e:
            print(f"❌ JSONパース致命的エラー: {e}")
            return False

        video_title = data.get("title", f"Japanese Cooking Wisdom: {chosen['theme']}")
        video_desc = data.get("description", "Discover the secrets of traditional Japanese cuisine with Japanese Cooking Wisdom. #Shorts #JapaneseFood")

        # 📝 ナレーション確認用テキストファイルの出力
        script_txt_path = os.path.join(WORKSPACE_DIR, f"{current_date}_script.txt")
        with open(script_txt_path, "w", encoding="utf-8") as f:
            f.write(f"=== THEME ===\n{chosen['theme']}\n\n")
            f.write(f"=== TITLE ===\n{video_title}\n\n")
            f.write(f"=== DESCRIPTION ===\n{video_desc}\n\n")
            f.write("=== SUBTITLES & NARRATION SCRIPTS ===\n")
            for i in range(1, 6):
                f.write(f"[Slide {i}]\n")
                f.write(f"  Subtitle: {data.get(f'slide_{i}_text', '')}\n")
                f.write(f"  Narration: {data.get(f'slide_{i}_voice', '')}\n\n")
        print(f"📝 確認用スクリプトファイルを保存しました: {script_txt_path}")

        sub_image_paths = []
        for i in range(1, 6):
            slide_text = data.get(f"slide_{i}_text", f"Tip {i}")
            img_path = os.path.join(TEMP_DIR, f"slide_{i}.png")
            self.generate_subtitle_image(slide_text, img_path)
            sub_image_paths.append(img_path)

        voice_texts = [data.get(f"slide_{i}_voice", "") for i in range(1, 6)]
        output_voice_path = os.path.join(TEMP_DIR, "narration.mp3")
        self.create_narration(voice_texts, output_voice_path)

        output_video_path = os.path.join(WORKSPACE_DIR, f"{current_date}_completed_cooking_shorts.mp4")
        
        filter_complex = (
            "[0:v][1:v]overlay=0:0:enable='between(t,0,6)'[v1];"
            "[v1][2:v]overlay=0:0:enable='between(t,6,12)'[v2];"
            "[v2][3:v]overlay=0:0:enable='between(t,12,18)'[v3];"
            "[v3][4:v]overlay=0:0:enable='between(t,18,24)'[v4];"
            "[v4][5:v]overlay=0:0:enable='between(t,24,30)'[v5];"
            "[0:a]volume=0.20[bg];"  
            "[6:a]volume=1.6[voice];" 
            "[bg][voice]amix=inputs=2:duration=first[a]"
        )

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", input_template_path,        
            "-i", sub_image_paths[0],         
            "-i", sub_image_paths[1],         
            "-i", sub_image_paths[2],         
            "-i", sub_image_paths[3],         
            "-i", sub_image_paths[4],         
            "-i", output_voice_path,           
            "-filter_complex", filter_complex,
            "-map", "[v5]",
            "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast",
            "-c:a", "aac",
            output_video_path
        ]

        try:
            subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=True)
            print(f"✅ 【Cooking Wisdom 動画完成】 -> {output_video_path}")
            
            # YouTube自動アップロードの実行
            self.upload_video_to_youtube(
                output_video_path,
                video_title,
                video_desc
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpegエラー: {e.stderr}")
            return False

if __name__ == "__main__":
    api_key = os.environ.get("GEMINI_API_KEY_MEDIA")
    engine = CookingWisdomEngine(api_key)
    success = engine.run_rendering_pipeline()
    if not success:
        print("❌ パイプラインが失敗したため、プロセスを異常終了させます。")
        sys.exit(1)
