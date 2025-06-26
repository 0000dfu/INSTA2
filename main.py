import os
import random
import time
import schedule
import tempfile
from instagrapi import Client
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# الحسابات الثلاثة
ACCOUNTS = [
    {"username": os.getenv("IG_USERNAME1"), "password": os.getenv("IG_PASSWORD1")},
    {"username": os.getenv("IG_USERNAME2"), "password": os.getenv("IG_PASSWORD2")},
    {"username": os.getenv("IG_USERNAME3"), "password": os.getenv("IG_PASSWORD3")},
]

SERVICE_ACCOUNT_JSON = os.getenv("SERVICE_ACCOUNT_JSON")
if not SERVICE_ACCOUNT_JSON:
    raise Exception("❌ يرجى تعيين SERVICE_ACCOUNT_JSON في متغيرات البيئة.")

# إعداد Google Drive
with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as tmp_file:
    tmp_file.write(SERVICE_ACCOUNT_JSON)
    tmp_file.flush()
    SERVICE_ACCOUNT_FILE = tmp_file.name

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=credentials)

# وصف المنشورات
POST_CAPTIONS = [
    "🚀 انطلق بقوة كل يوم!",
    "🎯 هذا الفيديو فيه درس كبير.",
    "💡 شاركنا رأيك في التعليقات!",
    "🔥 محتوى مميز جدًا!"
]

STORY_CAPTIONS = [
    "✨ شاهد هذا الآن!",
    "🔥 لحظات لا تفوّت!",
    "🚀 المحتوى مستمر!",
    "📌 شوف الستوري الجديد!"
]

# مسارات سجل النشر لكل حساب
def posted_log_path(username):
    return f"posted_{username}.txt"

def load_posted(username):
    path = posted_log_path(username)
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def save_posted(username, filename):
    with open(posted_log_path(username), "a", encoding="utf-8") as f:
        f.write(filename + "\n")

# تحميل قائمة الفيديوهات من Drive
def get_videos_from_drive():
    query = "mimeType contains 'video/' and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    return results.get("files", [])

# تحميل فيديو مؤقتًا
def download_video(file):
    request = drive_service.files().get_media(fileId=file['id'])
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        downloader = MediaIoBaseDownload(tmp, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return tmp.name

# فحص صلاحية الفيديو للستوري (≤ 60 ثانية)
def is_valid_story_video(path):
    try:
        clip = VideoFileClip(path)
        duration = clip.duration
        clip.close()
        return duration <= 60
    except:
        return False

# نشر ريلز
def publish_post(client, file, username):
    caption = random.choice(POST_CAPTIONS)
    tmp_path = download_video(file)
    try:
        print(f"⬆️ [{username}] نشر ريلز: {file['name']} - {caption}")
        client.clip_upload(tmp_path, caption)
        save_posted(username, file['name'])
    except Exception as e:
        print(f"❌ [{username}] فشل نشر {file['name']}: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# نشر Story
def publish_story(client, file, username):
    caption = random.choice(STORY_CAPTIONS)
    tmp_path = download_video(file)
    try:
        if not is_valid_story_video(tmp_path):
            print(f"🚫 [{username}] الفيديو {file['name']} أطول من 60 ثانية، تم تخطيه.")
            return
        print(f"⬆️ [{username}] نشر ستوري: {file['name']} - {caption}")
        client.video_upload_to_story(tmp_path, caption)
        save_posted(username, file['name'])
    except Exception as e:
        print(f"❌ [{username}] فشل ستوري {file['name']}: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# تنفيذ المهام لحساب
def run_for_account(account, post_now=False, story_now=False):
    username = account['username']
    password = account['password']
    posted = load_posted(username)

    client = Client()
    try:
        session_path = f"{username}_session.json"
        if os.path.exists(session_path):
            client.load_settings(session_path)

        client.login(username, password)
        client.dump_settings(session_path)

        def pick_available_videos(n=1):
            all_files = get_videos_from_drive()
            available = [f for f in all_files if f['name'].lower().endswith('.mp4') and f['name'] not in posted]
            random.shuffle(available)
            return available[:n]

        if story_now:
            print(f"📲 [{username}] نشر ستوري")
            files = pick_available_videos()
            if files:
                publish_story(client, files[0], username)
                posted.add(files[0]['name'])
            time.sleep(random.randint(3, 6))

        if post_now:
            print(f"📸 [{username}] نشر منشورات")
            for file in pick_available_videos(2):
                publish_post(client, file, username)
                posted.add(file['name'])
                time.sleep(random.randint(30, 60))

    except Exception as e:
        print(f"❌ [{username}] فشل تسجيل الدخول أو النشر: {e}")

# المهام المجدولة
def main():
    def job_story():
        for account in ACCOUNTS:
            run_for_account(account, story_now=True)

    def job_posts():
        for i, account in enumerate(ACCOUNTS):
            time.sleep(i * 60)
            run_for_account(account, post_now=True)

    # جدولة المنشورات
    schedule.every().monday.at("09:00").do(job_posts)
    schedule.every().tuesday.at("09:00").do(job_posts)
    schedule.every().wednesday.at("09:00").do(job_posts)
    schedule.every().thursday.at("09:00").do(job_posts)
    schedule.every().friday.at("09:00").do(job_posts)

    schedule.every().monday.at("15:00").do(job_posts)
    schedule.every().tuesday.at("15:00").do(job_posts)
    schedule.every().wednesday.at("15:00").do(job_posts)
    schedule.every().thursday.at("15:00").do(job_posts)
    schedule.every().friday.at("15:00").do(job_posts)

    # ستوري يوميًا
    schedule.every().day.at("11:00").do(job_story)

    print("⏰ السكربت يعمل تلقائيًا الآن...")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("🛑 تم إيقاف السكربت.")

if __name__ == "__main__":
    main()
