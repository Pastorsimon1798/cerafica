# Instagram Intelligence Scripts Library

from dotenv import load_dotenv
from pathlib import Path

# Load .env before any other imports that need env vars
_env_path = Path(__file__).parent.parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

from .photo_export import (
    PhotoInfo,
    create_albums,
    get_photos_from_album,
    export_photo,
    export_photo_by_index,
    move_to_album,
    move_photo_by_index,
    get_photo_count,
    get_temp_export_dir,
    clear_temp_exports,
    ensure_photos_app_running,
)

try:
    from .caption_generator import (
        ContentType,
        PhotoAnalysis,
        GeneratedCaption,
        analyze_photo,
        analyze_photo_basic,
        generate_caption,
        select_hashtags,
        caption_length_ok,
    )
except ImportError:
    # caption_generator has heavy deps (openai, etc.) — allow graceful degradation
    ContentType = None
    PhotoAnalysis = None
    GeneratedCaption = None
    analyze_photo = None
    analyze_photo_basic = None
    generate_caption = None
    select_hashtags = None
    caption_length_ok = None

try:
    from .instagram_scheduler import (
        ScheduledPost,
        InstagramScheduler,
        get_posting_schedule,
        login_to_meta,
        schedule_post,
        schedule_week,
        close_browser,
    )
except ImportError:
    ScheduledPost = None
    InstagramScheduler = None
    get_posting_schedule = None
    login_to_meta = None
    schedule_post = None
    schedule_week = None
    close_browser = None
