import os
import sys
import json
import time
import re
import requests
import subprocess
import asyncio
import shutil
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont

# 外部ライブラリのチェック
try:
    import edge_tts
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

try:
    import google.oauth2.credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    YOUTUBE_API_AVAILABLE = True
except ImportError:
    YOUTUBE_API_AVAILABLE = False

# 設定・ディレクトリ構成
jst = timezone(timedelta(hours=9))
current_date = datetime.now(jst).strftime("%Y-%m-%d")
TEMPLATE_DIR = "../../templates/kids_compass"
WORKSPACE_DIR = "workspace"
TEMP_DIR = "temp_assets"

# 実行前にワークスペースをクリーンアップ
if os.path.exists(WORKSPACE_DIR):
    shutil.rmtree(WORKSPACE_DIR)
if os.path.exists(TEMP_DIR):
    shutil.rmtree(TEMP_DIR)
os.makedirs(WORKSPACE_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

class JapanKidsCompassEngine:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent"

    def validate_template(self, path):
        """動画ファイルがLFSポインタ（数KB）ではなく実体（MB単位）かを確認"""
        if not os.path.exists(path):
            print(f"❌ ファイルが存在しません: {path}")
            return False
        size_mb = os.path.getsize(path) / (1024 * 1024)
        if size_mb < 1.0:
            print(f"❌ 致命的エラー: {path} はLFSポインタ（{size_mb:.2f}MB）です。同期失敗です。")
            return False
        return True

    def ask_gemini(self, prompt, system_instruction=""):
        if not self.api_key:
            return "⚠️ API KEY MISSING"
        headers = {"Content-Type": "application/json"}
        combined_prompt = f"[Role Instruction]\n{system_instruction}\n\n[Task]\n{prompt}" if system_instruction else prompt
        payload = {"contents": [{"parts": [{"text": combined_prompt}]}]}
        url = f"{self.base_url}?key={self.api_key}"
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=60)
            if res.status_code == 200:
                return res.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"Gemini Error: {e}")
        return "⚠️ API ERROR"

    def generate_subtitle_image(self, text, output_path, width=1080, height=1920):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font = ImageFont.truetype(font_path, 54) if os.path.exists(font_path) else ImageFont.load_default()
        
        words = text.split()
        lines, current_line = [], []
        for word in words:
            current_line.append(word)
            if len(" ".join(current_line)) > 16:
                lines.append(" ".join(current_line))
                current_line = []
        if current_line:
            lines.append(" ".join(current_line))
        lines = lines[:3]

        line_widths = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_widths.append(bbox[2] - bbox[0])

        max_line_width = max(line_widths) if line_widths else 200
        box_width = min(max_line_width + 100, width - 100)
        box_height = (len(lines) * 80) + 70
        box_x1 = (width - box_width) // 2
        box_y1 = 1250
        
        draw.rounded_rectangle([box_x1, box_y1, box_x1+box_width, box_y1+box_height], radius=20, fill=(15, 23, 36, 220))
        current_y = box_y1 + 35
        for i, line in enumerate(lines):
            text_x = box_x1 + (box_width - line_widths[i]) // 2
            draw.text((text_x, current_y), line, fill=(255, 255, 255, 255), font=font)
            current_y += 80
        img.save(output_path, "PNG")

    def create_narration(self, voice_texts, output_path):
        if not TTS_AVAILABLE:
            return False
        async def amain():
            full_script = " . ".join(voice_texts)
            communicate = edge_tts.Communicate(full_script, "en-US-EmmaNeural", rate="-10%")
            await communicate.save(output_path)
        asyncio.run(amain())
        return True

    def get_youtube_service(self):
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
        
        # 💡 チャンネル診断: どのチャンネルに接続しているか確認する
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
                "tags": ["Shorts", "Japan", "KidsCompass", "Education"],
                "categoryId": "27"
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
        print("🎬 [Japan Kids Compass] 自動スキャンモード起動")
        
        template_files = [f for f in os.listdir(TEMPLATE_DIR) if f.endswith(".mp4")]
        if not template_files:
            print("❌ テンプレートが見つかりません。")
            return False

        day_of_year = datetime.now(jst).timetuple().tm_yday
        chosen_filename = template_files[day_of_year % len(template_files)]
        theme_name = os.path.splitext(chosen_filename)[0].replace("-", " ")
        input_template_path = os.path.join(TEMPLATE_DIR, chosen_filename)

        if not self.validate_template(input_template_path):
            sys.exit(1)

        # 💡 新規：タイトル・概要欄生成のプロンプト
        prompt = f"""
        Generate content for a 30s Short about: '{theme_name}'.
        1. YouTube Video Title (Catchy, English, max 100 chars).
        2. Video Description (Engaging, English, including hashtags).
        3. 5 slide subtitles and narration scripts.
        
        CRITICAL RULES:
        - Do NOT include the theme name, file ID, or 'v1' in the slide text.
        - Focus only on educational, child-friendly insights.
        - Output ONLY pure JSON format: {{"title": "...", "description": "...", "slide_1_text": "...", "slide_1_voice": "...", "slide_2_text": "...", "slide_2_voice": "...", "slide_3_text": "...", "slide_3_voice": "...", "slide_4_text": "...", "slide_4_voice": "...", "slide_5_text": "...", "slide_5_voice": "..."}}
        """
        raw_json = self.ask_gemini(prompt, "You are a YouTube expert. Output ONLY JSON.")
        
        try:
            json_match = re.search(r'\{.*\}', raw_json, re.DOTALL)
            data = json.loads(json_match.group(0)) if json_match else json.loads(raw_json)
        except Exception as e:
            print(f"JSON Error: {e}")
            return False

        # タイトルと概要欄の抽出
        video_title = data.get("title", f"Japan Kids Compass: {theme_name}")
        video_desc = data.get("description", "Discover insights into Japanese school life with Japan Kids Compass.")

        sub_image_paths = []
        for i in range(1, 6):
            img_path = os.path.join(TEMP_DIR, f"slide_{i}.png")
            text = data.get(f"slide_{i}_text", "Insight")
            self.generate_subtitle_image(text, img_path)
            sub_image_paths.append(img_path)

        output_voice_path = os.path.join(TEMP_DIR, "narration.mp3")
        voice_texts = [data.get(f"slide_{i}_voice", "") for i in range(1, 6)]
        self.create_narration(voice_texts, output_voice_path)

        output_video_path = os.path.join(WORKSPACE_DIR, f"{current_date}_completed.mp4")
        
        # duration=longest に修正（音声が途切れないように）
        filter_complex = (
            "[0:v][1:v]overlay=0:0:enable='between(t,0,6)'[v1];"
            "[v1][2:v]overlay=0:0:enable='between(t,6,12)'[v2];"
            "[v2][3:v]overlay=0:0:enable='between(t,12,18)'[v3];"
            "[v3][4:v]overlay=0:0:enable='between(t,18,24)'[v4];"
            "[v4][5:v]overlay=0:0:enable='between(t,24,30)'[v5];"
            "[0:a]volume=0.25[bg];"  
            "[6:a]volume=1.5[voice];" 
            "[bg][voice]amix=inputs=2:duration=longest[a]"
        )

        ffmpeg_cmd = ["ffmpeg", "-y", "-i", input_template_path]
        for p in sub_image_paths:
            ffmpeg_cmd.extend(["-i", p])
        ffmpeg_cmd.extend([
            "-i", output_voice_path, 
            "-filter_complex", filter_complex, 
            "-map", "[v5]", 
            "-map", "[a]", 
            "-c:v", "libx264", 
            "-c:a", "aac", 
            output_video_path
        ])

        try:
            subprocess.run(ffmpeg_cmd, check=True)
            print(f"✅ 動画生成完了: {output_video_path}")
            
            # YouTubeへのアップロードを確実に呼び出す
            self.upload_video_to_youtube(
                output_video_path, 
                video_title, 
                video_desc
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpegエラー: {e}")
            return False

if __name__ == "__main__":
    api_key = os.environ.get("GEMINI_API_KEY_MEDIA")
    engine = JapanKidsCompassEngine(api_key)
    success = engine.run_rendering_pipeline()
    if not success:
        sys.exit(1)
