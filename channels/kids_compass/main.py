import os
import sys
import json
import time
import re
import requests
import subprocess
import asyncio
import shutil
import random
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
KNOWLEDGE_DIR = "../../knowledge/kids_compass"
DATA_DIR = "data"

os.makedirs(DATA_DIR, exist_ok=True)

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
        client_id = os.environ.get("KIDS_YOUTUBE_CLIENT_ID")
        client_secret = os.environ.get("KIDS_YOUTUBE_CLIENT_SECRET")
        refresh_token = os.environ.get("KIDS_YOUTUBE_REFRESH_TOKEN")
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
    
    def extract_knowledge_key(self, filename):
        """
        JKC_001_commute.mp4
        ↓
        commute
        """

        base = os.path.splitext(filename)[0]
        parts = base.split("_")

        if len(parts) >= 3:
            return "_".join(parts[2:]).lower()

        return base.lower()

    def load_knowledge(self, knowledge_key):

        knowledge_path = os.path.join(
            KNOWLEDGE_DIR,
            f"{knowledge_key}.json"
        )

        if not os.path.exists(knowledge_path):
            raise FileNotFoundError(
                f"Knowledge file not found: {knowledge_path}"
            )

        with open(
            knowledge_path,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)

    def choose_story_angle(self, knowledge):

        angles = knowledge.get(
            "story_angles",
            []
        )

        if not angles:
            return {
                "angle": "General",
                "path": []
            }

        return random.choice(angles)

    def build_story_brief(
        self,
        knowledge,
        selected_angle
    ):

        hook = random.choice(
            knowledge.get(
                "hook_questions",
                ["What can children learn from everyday life?"]
            )
        )

        topic = random.choice(
            knowledge.get(
                "possible_topics",
                ["Japanese education"]
            )
        )

        fact = random.choice(
            knowledge.get(
                "observable_facts",
                []
            )
        )

        meaning = random.choice(
            knowledge.get(
                "deeper_meanings",
                []
            )
        )

        social = random.choice(
            knowledge.get(
                "social_connections_extended",
                knowledge.get(
                    "social_connections",
                    []
                )
            )
        )

        takeaway = random.choice(
            knowledge.get(
                "american_parent_takeaways",
                []
            )
        )

        outcome = random.choice(
            knowledge.get(
                "long_term_societal_outcomes",
                []
            )
        )

        return {
            "scene": knowledge.get("scene", ""),
            "topic": topic,
            "hook": hook,
            "fact": fact,
            "meaning": meaning,
            "social": social,
            "takeaway": takeaway,
            "outcome": outcome,
            "angle": selected_angle.get("angle", "General"),
            "path": selected_angle.get("path", []),
            "forbidden_claims": knowledge.get(
                "forbidden_claims",
                []
            )
        }

    def run_rendering_pipeline(self):
        print("🎬 [Japan Kids Compass] 自動スキャンモード起動")
        
        template_files = [f for f in os.listdir(TEMPLATE_DIR) if f.endswith(".mp4")]
        if not template_files:
            print("❌ テンプレートが見つかりません。")
            return False

        day_of_year = datetime.now(jst).timetuple().tm_yday
        chosen_filename = template_files[day_of_year % len(template_files)]
        theme_name = os.path.splitext(chosen_filename)[0].replace("-", " ")
                knowledge_key = self.extract_knowledge_key(
            chosen_filename
        )

        print(
            f"📚 Knowledge Selected: {knowledge_key}"
        )

        knowledge = self.load_knowledge(
            knowledge_key
        )

        selected_angle = self.choose_story_angle(
            knowledge
        )

        story_brief = self.build_story_brief(
            knowledge,
            selected_angle
        )

        print(
            f"🎯 Story Angle: {selected_angle['angle']}"
        )
        input_template_path = os.path.join(TEMPLATE_DIR, chosen_filename)

        if not self.validate_template(input_template_path):
            sys.exit(1)

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

        video_title = data.get("title", f"Japan Kids Compass: {theme_name}")
        video_desc = data.get("description", "Discover insights into Japanese school life with Japan Kids Compass.")

        # 💡 【追加機能】生成されたタイトル・概要欄・ナレーション原稿をテキストファイルに保存
        script_txt_path = os.path.join(WORKSPACE_DIR, f"{current_date}_script.txt")
        with open(script_txt_path, "w", encoding="utf-8") as f:
            f.write(f"=== THEME ===\n{theme_name}\n\n")
            f.write(f"=== TITLE ===\n{video_title}\n\n")
            f.write(f"=== DESCRIPTION ===\n{video_desc}\n\n")
            f.write("=== SUBTITLES & NARRATION SCRIPTS ===\n")
            for i in range(1, 6):
                f.write(f"[Slide {i}]\n")
                f.write(f"  Subtitle (Screen Text): {data.get(f'slide_{i}_text', '')}\n")
                f.write(f"  Narration (Voice): {data.get(f'slide_{i}_voice', '')}\n\n")
        print(f"📝 確認用スクリプトファイルを保存しました: {script_txt_path}")

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
