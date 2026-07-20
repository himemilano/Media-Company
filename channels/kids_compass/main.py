import os
import sys
import json
import time
import re
import requests
import subprocess
import asyncio
import random
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont

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

TEMPLATE_DIR = "../../templates/kids_compass"  
WORKSPACE_DIR = "workspace"      
TEMP_DIR = "temp_assets"

os.makedirs(WORKSPACE_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

class JapanKidsCompassEngine:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent"

    def ask_gemini(self, prompt, system_instruction=""):
        if not self.api_key: return "⚠️ API KEY MISSING"
        headers = {"Content-Type": "application/json"}
        combined_prompt = f"[Role Instruction]\n{system_instruction}\n\n[Task]\n{prompt}" if system_instruction else prompt
        payload = {"contents": [{"parts": [{"text": combined_prompt}]}]}
        url = f"{self.base_url}?key={self.api_key}"
        for delay in [1, 2, 4]:
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=60)
                if res.status_code == 200:
                    return res.json()["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    time.sleep(delay)
            except Exception as e:
                time.sleep(delay)
        return "⚠️ API ERROR"

    def generate_gradient_placeholder(self, width=1080, height=1920):
        img = Image.new("RGB", (width, height), (26, 36, 43)) 
        draw = ImageDraw.Draw(img)
        for y in range(height):
            r = int(26 + (50 - 26) * (y / height))
            g = int(36 + (40 - 36) * (y / height))
            b = int(43 + (44 - 43) * (y / height))
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        draw.rectangle([40, 40, width-40, height-40], outline=(220, 195, 145), width=2)
        path = os.path.join(TEMP_DIR, "placeholder_bg.png")
        img.save(path)
        return path

    def generate_subtitle_image(self, text, output_path, width=1080, height=1920):
        """💡 テキストの正確なサイズを計測し、枠を自動可変させてはみ出しを絶対防ぐ関数"""
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # フォント設定
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 
            "Arial"
        ]
        font = None
        for path in font_paths:
            if os.path.exists(path):
                font = ImageFont.truetype(path, 54) # 少し視認性を上げるため54に微調整
                break
        if not font: 
            font = ImageFont.load_default()

        # 単語ごとに行をスマートに分割 (1行あたり最大16文字目安)
        words = text.split()
        lines, current_line = [], []
        for word in words:
            current_line.append(word)
            if len(" ".join(current_line)) > 16:
                if len(current_line) > 1:
                    current_line.pop()
                    lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    lines.append(" ".join(current_line))
                    current_line = []
        if current_line: 
            lines.append(" ".join(current_line))
        
        lines = lines[:3] # 最大3行までガード

        # 各行のピクセル幅と高さを正確に測定
        line_widths = []
        line_heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_widths.append(bbox[2] - bbox[0])
            line_heights.append(bbox[3] - bbox[1])

        max_line_width = max(line_widths) if line_widths else 200
        single_line_height = max(line_heights) if line_heights else 50
        line_spacing = 15

        # テキストボックス全体のサイズを動的に計算
        padding_x = 50  # 横方向の余白を十分に確保
        padding_y = 35  # 縦方向の余白
        
        box_width = max_line_width + (padding_x * 2)
        box_width = min(box_width, width - 100) # 画面端からはみ出さないようにガード
        
        box_height = (len(lines) * single_line_height) + ((len(lines) - 1) * line_spacing) + (padding_y * 2)
        
        # 画面下部中央に配置
        box_x1 = (width - box_width) // 2
        box_y1 = 1250
        box_x2 = box_x1 + box_width
        box_y2 = box_y1 + box_height

        # 半透明の角丸背景を描画
        draw.rounded_rectangle([box_x1, box_y1, box_x2, box_y2], radius=20, fill=(15, 23, 36, 220))
        
        # 各行を中央揃えで描画
        current_y = box_y1 + padding_y
        for i, line in enumerate(lines):
            line_w = line_widths[i]
            text_x = box_x1 + (box_width - line_w) // 2
            draw.text((text_x, current_y), line, fill=(255, 255, 255, 255), font=font)
            current_y += single_line_height + line_spacing

        img.save(output_path, "PNG")

    def create_narration(self, voice_texts, output_path):
        if not TTS_AVAILABLE: return False
        full_script = " . ".join(voice_texts)
        voice = "en-US-EmmaNeural" 
        async def amain():
            communicate = edge_tts.Communicate(full_script, voice, rate="+5%")
            await communicate.save(output_path)
        asyncio.run(amain())
        return True

    def get_youtube_service(self):
        """GitHub Actionsの環境変数からOAuth認証情報を復元する"""
        client_id = os.environ.get("YOUTUBE_CLIENT_ID")
        client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
        refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")

        if not (client_id and client_secret and refresh_token):
            print("⚠️ YouTubeの認証用環境変数が不足しているため、アップロードをスキップします。")
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
        """完成したShorts動画をYouTubeに直接アップロードする"""
        youtube = self.get_youtube_service()
        if not youtube:
            return False

        print(f"🚀 YouTubeへのアップロードを開始します: {title}")
        body = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": ["Shorts", "Japan", "JapaneseCulture", "Education"],
                "categoryId": "27"  # Education
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        try:
            request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
            response = request.execute()
            print(f"🎉 YouTubeアップロード大成功！ Video ID: {response.get('id')}")
            return True
        except Exception as e:
            print(f"❌ YouTubeアップロード中にエラーが発生しました: {e}")
            return False

    def run_rendering_pipeline(self):
        print("🎬 [Japan Kids Compass] レンダーパイプライン始動")

        video_concepts = {
            1: {"filename": "JKC-A-Commute-v1.mp4", "theme": "The secret behind Japan's independent primary school commuters."},
            2: {"filename": "JKC-B-Classroom-v1.mp4", "theme": "Why Japanese children clean their own classrooms every day."},
            3: {"filename": "JKC-C-Lunch-v1 .mp4", "theme": "How Japanese school lunches teach independence and nutrition."}, 
            4: {"filename": "JKC-D-Cleaning-v1.mp4", "theme": "The community mindset built through school cleaning time."},
            5: {"filename": "JKC-E-Gym-v1.mp4", "theme": "How physical education in Japan deeply emphasizes teamwork."},
            6: {"filename": "JKC-F-Library-v1.mp4", "theme": "Why independent reading habits are prioritized in Japanese schools."},
            7: {"filename": "JKC-G-SportsDay-v1.mp4", "theme": "The extreme passion and cooperation in Japanese 'Undokai'."},
            8: {"filename": "JKC-H-AfterSchool-v1.mp4", "theme": "How Japanese kids handle life and safety after the school bell rings."},
            9: {"filename": "JKC-I-DisasterPreparedness-v1.mp4", "theme": "How Japanese schools train children to stay calm and safe during disaster drills."},
            10: {"filename": "JKC-J-SafeNeighborhood-v1.mp4", "theme": "Why Japanese neighborhoods are safely designed for solo child walking."}
        }

        day_of_year = datetime.now(jst).timetuple().tm_yday
        concept_idx = (day_of_year % len(video_concepts)) + 1
        chosen = video_concepts[concept_idx]

        input_template_path = os.path.join(TEMPLATE_DIR, chosen["filename"])

        is_template_valid = False
        if os.path.exists(input_template_path):
            if os.path.getsize(input_template_path) > 100 * 1024:
                is_template_valid = True

        if not is_template_valid:
            print(f"⚠️ 有効な動画テンプレートを検出できなかったため、仮背景を自動生成します。")
            bg_png = self.generate_gradient_placeholder()
            placeholder_mp4 = os.path.join(TEMP_DIR, "placeholder_bg_30s.mp4")
            ffmpeg_bg_cmd = ["ffmpeg", "-y", "-loop", "1", "-i", bg_png, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-c:v", "libx264", "-t", "30", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", placeholder_mp4]
            subprocess.run(ffmpeg_bg_cmd, capture_output=True, check=True)
            input_template_path = placeholder_mp4
        else:
            print(f"🎯 本物の動画テンプレートを検出成功: {chosen['filename']}")

        prompt = f"""
Create 5 engaging slide subtitles AND 5 matching spoken narration scripts for a 30-second YouTube Shorts.
[TOPIC]: "{chosen['theme']}"
[RULES]: 
- Subtitles under 8 words. 
- Narration under 15 words. 
- Deliver strictly in JSON format with keys "slide_1_text", "slide_1_voice" ... up to "slide_5_voice".
"""
        raw_json = self.ask_gemini(prompt, "You are a professional YouTube Shorts scriptwriter. Output pure JSON only.")
        if "⚠️" in raw_json: return False

        try:
            json_match = re.search(r'\{.*\}', raw_json, re.DOTALL)
            data = json.loads(json_match.group(0)) if json_match else json.loads(raw_json)
        except Exception as e:
            return False

        sub_image_paths = []
        for i in range(1, 6):
            slide_text = data.get(f"slide_{i}_text", f"Insight {i}")
            img_path = os.path.join(TEMP_DIR, f"slide_{i}.png")
            self.generate_subtitle_image(slide_text, img_path)
            sub_image_paths.append(img_path)

        voice_texts = [data.get(f"slide_{i}_voice", "") for i in range(1, 6)]
        output_voice_path = os.path.join(TEMP_DIR, "narration.mp3")
        self.create_narration(voice_texts, output_voice_path)

        output_video_path = os.path.join(WORKSPACE_DIR, f"{current_date}_completed_kids_shorts.mp4")
        
        filter_complex = (
            "[0:v][1:v]overlay=0:0:enable='between(t,0,6)'[v1];"
            "[v1][2:v]overlay=0:0:enable='between(t,6,12)'[v2];"
            "[v2][3:v]overlay=0:0:enable='between(t,12,18)'[v3];"
            "[v3][4:v]overlay=0:0:enable='between(t,18,24)'[v4];"
            "[v4][5:v]overlay=0:0:enable='between(t,24,30)'[v5];"
            "[0:a]volume=0.25[bg];"  
            "[6:a]volume=1.5[voice];" 
            "[bg][voice]amix=inputs=2:duration=first[a]"
        )

        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", input_template_path,        
            "-i", sub_image_paths[0], "-i", sub_image_paths[1],         
            "-i", sub_image_paths[2], "-i", sub_image_paths[3],         
            "-i", sub_image_paths[4], "-i", output_voice_path,           
            "-filter_complex", filter_complex, "-map", "[v5]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", output_video_path
        ]

        try:
            subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=True)
            print(f"✅ 【Kids Compass 動画完成】 -> {output_video_path}")
            
            # 🚀 【復元】生成が成功したら、YouTubeへの直接アップロードを実行
            video_title = f"Japan's School Secrets: {chosen['theme']}"
            video_desc = f"Discover more about Japanese culture and education rules.\n\n#Shorts #Japan #Education"
            self.upload_video_to_youtube(output_video_path, video_title, video_desc)
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpegエラー: {e.stderr}")
            return False

if __name__ == "__main__":
    api_key = os.environ.get("GEMINI_API_KEY_MEDIA")
    engine = JapanKidsCompassEngine(api_key)
    success = engine.run_rendering_pipeline()
    if not success:
        sys.exit(1)
