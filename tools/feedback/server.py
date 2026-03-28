#!/usr/bin/env python3
"""
Human Door Server for Ceramics Instagram Caption Testing
Interactive dashboard for reviewing AI-generated captions
"""

import json
import sqlite3
import os
import mimetypes
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from contextlib import contextmanager
import re
from datetime import datetime
from typing import Optional

# Add scripts directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

PORT = 8766
DB_PATH = os.path.join(os.path.dirname(__file__), 'feedback.db')
TEST_DATA_PATH = os.path.join(os.path.dirname(__file__), 'test_data.json')
PHOTOS_PATH = os.path.join(os.path.dirname(__file__), '..', 'output', 'ab_test_photos')
FRAMED_PATH = os.path.join(os.path.dirname(__file__), '..', 'output', 'framed')

# Initialize database
def init_db():
    with get_db() as conn:
        c = conn.cursor()

        # Feedback table
        c.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo TEXT NOT NULL,
                model TEXT NOT NULL,
                vision_correct INTEGER,
                caption_rating INTEGER,
                preferred_model TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Vision corrections table
        c.execute('''
            CREATE TABLE IF NOT EXISTS vision_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo TEXT NOT NULL,
                ai_piece_type TEXT,
                ai_glaze_type TEXT,
                correct_piece_type TEXT,
                correct_glaze_type TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Caption ratings table
        c.execute('''
            CREATE TABLE IF NOT EXISTS caption_ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo TEXT NOT NULL,
                model TEXT NOT NULL,
                hook_rating INTEGER,
                body_rating INTEGER,
                cta_rating INTEGER,
                voice_authentic INTEGER,
                preferred INTEGER,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Idea seeds table - user's creative associations for photos
        c.execute('''
            CREATE TABLE IF NOT EXISTS idea_seeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo TEXT NOT NULL,
                seed_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP DEFAULT NULL
            )
        ''')
        # Migration: add deleted_at column to existing DBs
        try:
            c.execute('ALTER TABLE idea_seeds ADD COLUMN deleted_at TIMESTAMP DEFAULT NULL')
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Creative director table - strong thematic guidance for series/concepts
        c.execute('''
            CREATE TABLE IF NOT EXISTS creative_director (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo TEXT NOT NULL UNIQUE,
                direction_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Series table - named collections of pieces
        c.execute('''
            CREATE TABLE IF NOT EXISTS series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                naming_system TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Series pieces - links photos to series with worldbuilding data
        c.execute('''
            CREATE TABLE IF NOT EXISTS series_pieces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_id INTEGER NOT NULL,
                photo TEXT NOT NULL,
                planet_name TEXT,
                orbital_data TEXT,
                surface_geology TEXT,
                formation_history TEXT,
                inhabitants TEXT,
                generated_caption TEXT,
                order_index INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (series_id) REFERENCES series(id),
                UNIQUE(series_id, photo)
            )
        ''')

        # Caption selections - stores which caption was selected for each photo
        c.execute('''
            CREATE TABLE IF NOT EXISTS caption_selections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo TEXT NOT NULL UNIQUE,
                selected_model TEXT NOT NULL,
                selected_caption TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Photos table - stores metadata and post format for photos
        c.execute('''
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                post_format TEXT DEFAULT 'photo',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

def migrate_db():
    """Run schema migrations for new columns."""
    with get_db() as conn:
        c = conn.cursor()

        # Add frame_style column to series table (default: 'planetary')
        try:
            c.execute("ALTER TABLE series ADD COLUMN frame_style TEXT DEFAULT 'planetary'")
        except sqlite3.OperationalError:
            pass  # Column already exists

def sync_photos():
    """Sync photos table with ab_test_photos directory on disk."""
    if not os.path.isdir(PHOTOS_PATH):
        return
    fs_photos = set(f for f in os.listdir(PHOTOS_PATH)
                    if not f.startswith('.') and f.lower().endswith(('.jpg', '.jpeg', '.png', '.heic')))
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT filename FROM photos')
        db_photos = set(r[0] for r in c.fetchall())

    # Add missing photos
    for f in sorted(fs_photos - db_photos):
        with get_db() as conn:
            conn.execute('INSERT OR IGNORE INTO photos (filename) VALUES (?)', (f,))

    # Remove photos not on disk
    for f in db_photos - fs_photos:
        with get_db() as conn:
            conn.execute('DELETE FROM photos WHERE filename = ?', (f,))

@contextmanager
def get_db():
    """Context manager for DB connections. Auto-commits and closes."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress logging

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == '/' or path == '/pipeline' or path == '/pipeline.html':
            self.serve_pipeline()
        elif path == '/legacy':
            self.serve_index()
        elif path == '/api/test-data':
            self.get_test_data()
        elif path == '/api/pipeline-data':
            self.get_pipeline_data()
        elif path == '/api/comparison-data':
            self.get_comparison_data()
        elif path == '/api/feedback':
            self.get_feedback()
        elif path == '/api/feedback/stats':
            self.get_feedback_stats()
        elif path == '/api/vision-corrections':
            self.get_vision_corrections()
        elif path == '/api/caption-ratings':
            self.get_caption_ratings()
        elif path == '/api/idea-seeds':
            self.get_idea_seeds(query)
        elif path == '/api/creative-director':
            self.get_creative_director(query)
        elif path == '/api/series':
            self.get_series()
        elif path.startswith('/api/series/'):
            series_id = path.split('/')[-1]
            self.get_series_pieces(series_id)
        elif path == '/api/caption-winners':
            self.get_caption_winners()
        elif path.startswith('/images/'):
            self.serve_image(path.split('/')[-1])
        elif path.startswith('/framed/'):
            self.serve_framed_image(path.split('/')[-1])
        elif path == '/api/framed-status':
            self.get_framed_status(query)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length else '{}'
        data = json.loads(body) if body else {}

        if path == '/api/feedback':
            self.save_feedback(data)
        elif path == '/api/vision-correction':
            self.save_vision_correction(data)
        elif path == '/api/caption-rating':
            self.save_caption_rating(data)
        elif path == '/api/idea-seeds':
            self.save_idea_seed(data)
        elif path == '/api/creative-director':
            self.save_creative_director(data)
        elif path == '/api/series':
            self.create_series(data)
        elif path == '/api/series-piece':
            self.add_series_piece(data)
        elif path == '/api/post-format':
            self.set_post_format(data)
        elif path == '/api/select-caption':
            self.select_caption_winner(data)
        elif path == '/api/regenerate-caption':
            self.regenerate_caption(data)
        elif path == '/api/generate-missing-captions':
            self.generate_missing_captions(data)
        else:
            self.send_error(404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Handle DELETE /api/idea-seeds/<id>
        if path.startswith('/api/idea-seeds/'):
            seed_id = path.split('/')[-1]
            self.delete_idea_seed(seed_id)
        # Handle DELETE /api/series-piece/<id>
        elif path.startswith('/api/series-piece/'):
            piece_id = path.split('/')[-1]
            self.delete_series_piece(piece_id)
        else:
            self.send_error(404)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith('/api/idea-seeds/'):
            seed_id = path.split('/')[-1]
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self.send_json({'error': 'Invalid JSON'}, 400)
                return
            self.update_idea_seed(seed_id, data)
        else:
            self.send_error(404)

    def serve_index(self):
        index_path = os.path.join(os.path.dirname(__file__), 'index.html')
        with open(index_path, 'rb') as f:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(f.read())

    def serve_pipeline(self):
        """Serve the pipeline dashboard"""
        pipeline_path = os.path.join(os.path.dirname(__file__), 'pipeline.html')
        with open(pipeline_path, 'rb') as f:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(f.read())

    def serve_image(self, filename):
        """Serve an image from the ab_test_photos directory"""
        # Security: prevent directory traversal
        safe = os.path.normpath(os.path.join(PHOTOS_PATH, filename))
        if not safe.startswith(os.path.normpath(PHOTOS_PATH)):
            self.send_error(403, 'Forbidden')
            return

        # First, try the filename as-is (it may already have extension)
        if os.path.exists(safe):
            mime_type, _ = mimetypes.guess_type(safe)
            if mime_type is None:
                mime_type = 'application/octet-stream'
            with open(safe, 'rb') as f:
                self.send_response(200)
                self.send_header('Content-Type', mime_type)
                self.send_header('Cache-Control', 'max-age=3600')
                self.end_headers()
                self.wfile.write(f.read())
            return

        # Try common extensions if no extension provided
        for ext in ['.jpg', '.jpeg', '.png', '.heic', '.JPG', '.JPEG', '.PNG', '.HEIC']:
            candidate = os.path.normpath(os.path.join(PHOTOS_PATH, filename + ext))
            if candidate.startswith(os.path.normpath(PHOTOS_PATH)) and os.path.exists(candidate):
                mime_type, _ = mimetypes.guess_type(candidate)
                if mime_type is None:
                    mime_type = 'application/octet-stream'
                with open(candidate, 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-Type', mime_type)
                    self.send_header('Cache-Control', 'max-age=3600')
                    self.end_headers()
                    self.wfile.write(f.read())
                return

        # Image not found
        self.send_error(404, 'Image not found')

    def find_framed_image(self, photo_filename: str) -> Optional[str]:
        """
        Find a framed version of a photo in output/framed/.

        Args:
            photo_filename: Original photo filename (e.g., "IMG_4759.JPG")

        Returns:
            Path to framed image or None if not found
        """
        # Security check
        normed = os.path.normpath(photo_filename)
        if normed != photo_filename or normed.startswith('/') or normed.startswith('..'):
            return None

        base_name = os.path.splitext(photo_filename)[0]
        framed_names = [f"{base_name}_planetary.jpg", f"{base_name}_minimal.jpg", f"{base_name}_frame.jpg"]

        # Search all date subdirectories for the framed image
        if os.path.exists(FRAMED_PATH):
            for date_dir in sorted(os.listdir(FRAMED_PATH), reverse=True):
                date_path = os.path.join(FRAMED_PATH, date_dir)
                if os.path.isdir(date_path):
                    for framed_name in framed_names:
                        framed_path = os.path.join(date_path, framed_name)
                        if os.path.exists(framed_path):
                            return framed_path

                    # Also try test directory
                    if date_dir == 'test':
                        for framed_name in framed_names:
                            test_path = os.path.join(date_path, framed_name)
                            if os.path.exists(test_path):
                                return test_path

        return None

    def serve_framed_image(self, filename):
        """Serve a framed image from output/framed/ directory."""
        # Security: prevent directory traversal
        framed_root = os.path.normpath(FRAMED_PATH)
        if not os.path.normpath(os.path.join(framed_root, filename)).startswith(framed_root + os.sep) and \
           os.path.normpath(os.path.join(framed_root, filename)) != framed_root:
            self.send_error(403, 'Forbidden')
            return

        # Try to find the framed image in date subdirectories
        if os.path.exists(FRAMED_PATH):
            for date_dir in sorted(os.listdir(FRAMED_PATH), reverse=True):
                date_path = os.path.join(FRAMED_PATH, date_dir)
                if os.path.isdir(date_path):
                    image_path = os.path.join(date_path, filename)
                    if os.path.exists(image_path):
                        mime_type, _ = mimetypes.guess_type(image_path)
                        if mime_type is None:
                            mime_type = 'image/jpeg'
                        with open(image_path, 'rb') as f:
                            self.send_response(200)
                            self.send_header('Content-Type', mime_type)
                            self.send_header('Cache-Control', 'max-age=3600')
                            self.end_headers()
                            self.wfile.write(f.read())
                        return

        self.send_error(404, 'Framed image not found')

    def get_framed_status(self, query):
        """Check if framed versions exist for photos."""
        photo = query.get('photo', [None])[0]
        if not photo:
            self.send_json({'error': 'Photo parameter required'}, 400)
            return

        framed_path = self.find_framed_image(photo)
        if framed_path:
            # Return URL path to framed image
            rel_path = os.path.relpath(framed_path, FRAMED_PATH)
            self.send_json({
                'has_framed': True,
                'framed_url': f'/framed/{os.path.basename(framed_path)}',
                'framed_path': framed_path
            })
        else:
            self.send_json({'has_framed': False})

    def get_test_data(self):
        try:
            with open(TEST_DATA_PATH) as f:
                data = json.load(f)
            self.send_json(data)
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def get_pipeline_data(self):
        """Get all pipeline data from the database — the authoritative source."""
        try:
            with get_db() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()

                # All photos
                c.execute('SELECT * FROM photos ORDER BY created_at DESC')
                photos = [dict(r) for r in c.fetchall()]

                # Vision results — get latest per photo (prefer Kimi)
                c.execute('''
                    SELECT p.filename, vr.model, vr.piece_type, vr.glaze_type,
                           vr.primary_colors, vr.secondary_colors,
                           vr.surface_qualities, vr.mood, vr.technique,
                           vr.form_attributes, vr.firing_state, vr.content_type,
                           vr.piece_count, vr.hypotheses, vr.vision_reasoning,
                           vr.created_at as vision_created_at,
                           vr.color_appearance, vr.brief_description,
                           vr.clay_type, vr.purpose, vr.product_family,
                           vr.dimensions_visible
                    FROM vision_results vr
                    JOIN photos p ON vr.photo_id = p.id
                    ORDER BY p.filename, vr.created_at DESC
                ''')
                vision_rows = c.fetchall()

                # Build vision map: filename -> list of results (dedupe, keep latest per model)
                vision_map = {}
                for r in vision_rows:
                    fname = r['filename']
                    if fname not in vision_map:
                        vision_map[fname] = []
                    # Keep only latest result per model
                    existing = [v for v in vision_map[fname] if v['model'] == r['model']]
                    if not existing:
                        vision_map[fname].append(dict(r))

                # Caption results from database
                c.execute('''
                    SELECT p.filename, cr.model, cr.hook, cr.body, cr.cta,
                           cr.full_caption, cr.caption_reasoning
                    FROM caption_results cr
                    JOIN photos p ON cr.photo_id = p.id
                ''')
                caption_rows = [dict(r) for r in c.fetchall()]

                # Also load captions from test_data.json (they have actual generated captions)
                captions_from_json = {}
                try:
                    with open(TEST_DATA_PATH) as f:
                        td = json.load(f)
                    for r in td.get('results', []):
                        caps = r.get('captions', {})
                        if caps and caps.get('hook') and not caps['hook'].startswith('=== STEP') and not caps['hook'].startswith('1. '):
                            captions_from_json[r['photo']] = caps
                except:
                    pass

                # Build caption map: filename -> {model: caption_data}
                caption_map = {}
                # Build caption reasoning map: filename -> {model: reasoning}
                caption_reasoning_map = {}
                for r in caption_rows:
                    fname = r['filename']
                    if fname not in caption_reasoning_map:
                        caption_reasoning_map[fname] = {}
                    if r.get('caption_reasoning'):
                        caption_reasoning_map[fname][r['model']] = r['caption_reasoning']

                for r in caption_rows:
                    fname = r['filename']
                    if fname not in caption_map:
                        caption_map[fname] = {}
                    caption_map[fname][r['model']] = {
                        'hook': r['hook'], 'body': r['body'], 'cta': r['cta'],
                        'full_caption': r['full_caption']
                    }
                # Merge JSON captions — add as new entries if model not already present
                for fname, caps in captions_from_json.items():
                    if fname not in caption_map:
                        caption_map[fname] = {}
                    if 'Kimi' not in caption_map[fname]:
                        caption_map[fname]['Kimi'] = caps

                # Add series_piece generated captions as the authoritative caption source
                c.execute('''
                    SELECT sp.photo, sp.generated_caption
                    FROM series_pieces sp
                    WHERE sp.generated_caption IS NOT NULL AND sp.generated_caption != ''
                ''')
                for r in c.fetchall():
                    fname = r['photo']
                    caption_text = r['generated_caption']
                    if fname not in caption_map:
                        caption_map[fname] = {}
                    # Set as Kimi caption (the model that generated the vision data)
                    if 'Kimi' not in str(caption_map[fname]):
                        caption_map[fname]['Kimi'] = {
                            'hook': caption_text[:100],
                            'body': caption_text,
                            'cta': '',
                            'full_caption': caption_text
                        }
                    elif not caption_map[fname].get('Kimi', {}).get('hook'):
                        caption_map[fname]['Kimi'] = {
                            'hook': caption_text[:100],
                            'body': caption_text,
                            'cta': '',
                            'full_caption': caption_text
                        }

                # Series
                c.execute('''
                    SELECT s.*, COUNT(sp.id) as piece_count
                    FROM series s
                    LEFT JOIN series_pieces sp ON s.id = sp.series_id
                    GROUP BY s.id
                    ORDER BY s.created_at DESC
                ''')
                series_list = [dict(r) for r in c.fetchall()]

                # Series pieces
                c.execute('''
                    SELECT sp.*, p.filename
                    FROM series_pieces sp
                    JOIN photos p ON sp.photo = p.filename
                    ORDER BY sp.series_id, sp.order_index
                ''')
                series_pieces = [dict(r) for r in c.fetchall()]

                # Caption selections
                c.execute('SELECT * FROM caption_selections')
                selections = {r['photo']: r['selected_model'] for r in c.fetchall()}

                # Idea seeds
                c.execute('SELECT * FROM idea_seeds WHERE deleted_at IS NULL ORDER BY created_at DESC, id DESC')
                idea_seeds = [dict(r) for r in c.fetchall()]

                # Vision corrections
                c.execute('SELECT * FROM vision_corrections ORDER BY created_at DESC')
                vision_corrections = [dict(r) for r in c.fetchall()]

            # Build the results array in the format pipeline.html expects
            results = []
            for photo in photos:
                fname = photo['filename']
                visions = vision_map.get(fname, [])
                captions = caption_map.get(fname, {})

                for vision in visions:
                    model = vision['model']
                    result = {
                        'photo': fname,
                        'model': model,
                        'vision': {
                            'piece_type': vision.get('piece_type'),
                            'glaze_type': vision.get('glaze_type') if vision.get('glaze_type') and vision.get('glaze_type') != 'None' else None,
                            'primary_colors': json.loads(vision['primary_colors']) if vision.get('primary_colors') else [],
                            'secondary_colors': json.loads(vision['secondary_colors']) if vision.get('secondary_colors') else [],
                            'surface_qualities': json.loads(vision['surface_qualities']) if vision.get('surface_qualities') else [],
                            'mood': vision.get('mood'),
                            'technique': vision.get('technique'),
                            'form_attributes': json.loads(vision['form_attributes']) if vision.get('form_attributes') else [],
                            'firing_state': vision.get('firing_state'),
                            'content_type': vision.get('content_type'),
                            'piece_count': vision.get('piece_count'),
                            'hypotheses': json.loads(vision['hypotheses']) if vision.get('hypotheses') else [],
                            'color_appearance': vision.get('color_appearance'),
                            'brief_description': vision.get('brief_description'),
                            'clay_type': vision.get('clay_type'),
                            'purpose': vision.get('purpose'),
                            'product_family': vision.get('product_family'),
                            'dimensions_visible': vision.get('dimensions_visible'),
                        },
                        'vision_reasoning': vision.get('vision_reasoning'),
                        'caption': captions.get(model, captions.get('Kimi K2.5', captions.get('Kimi', {}))),
                        'caption_reasoning': caption_reasoning_map.get(fname, {}).get(model),
                        'selected': selections.get(fname) == model,
                        'series': next((sp for sp in series_pieces if sp['filename'] == fname), None),
                    }
                    results.append(result)

            # Build framed image URL map (once per photo)
            framed_map = {}
            for photo in photos:
                framed_path = self.find_framed_image(photo['filename'])
                if framed_path:
                    framed_map[photo['filename']] = f"/framed/{os.path.basename(framed_path)}"

            self.send_json({
                'results': results,
                'photos': photos,
                'series': series_list,
                'series_pieces': series_pieces,
                'idea_seeds': idea_seeds,
                'vision_corrections': vision_corrections,
                'selections': selections,
                'framed': framed_map,
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json({'error': str(e)}, 500)

    def get_comparison_data(self):
        """Get side-by-side vision comparison across all models."""
        try:
            with get_db() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()

                MODELS = ['Kimi K2.5 (Ollama)', 'Kimi K2.5 (OpenRouter)', 'Gemini 3 Flash']

                c.execute('''
                    SELECT p.filename, vr.model, vr.piece_type, vr.primary_colors,
                           vr.secondary_colors, vr.mood, vr.color_appearance,
                           vr.surface_qualities, vr.color_distribution,
                           vr.lighting, vr.uncertainties, vr.photo_quality,
                           vr.clay_type, vr.form_attributes, vr.hypotheses,
                           vr.firing_state, vr.content_type, vr.piece_count,
                           vr.brief_description, vr.technique, vr.purpose,
                           vr.product_family
                    FROM vision_results vr
                    JOIN photos p ON vr.photo_id = p.id
                    WHERE vr.model IN (?, ?, ?)
                    ORDER BY p.filename, vr.model
                ''', MODELS)

                rows = [dict(r) for r in c.fetchall()]

                # Also get caption data
                c.execute('''
                    SELECT p.filename, cr.model, cr.hook, cr.body, cr.cta, cr.full_caption
                    FROM caption_results cr
                    JOIN photos p ON cr.photo_id = p.id
                    ORDER BY p.filename, cr.model
                ''')
                captions = [dict(r) for r in c.fetchall()]

                self.send_json({'vision': rows, 'captions': captions})
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def get_feedback(self):
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM feedback ORDER BY created_at DESC')
            rows = [dict(r) for r in c.fetchall()]
        self.send_json(rows)

    def get_feedback_stats(self):
        with get_db() as conn:
            c = conn.cursor()

            # Count feedback by photo
            c.execute('SELECT photo, COUNT(*) as count FROM feedback GROUP BY photo')
            by_photo = {r[0]: r[1] for r in c.fetchall()}

            # Preferred model counts
            c.execute('SELECT preferred_model, COUNT(*) as count FROM feedback WHERE preferred_model IS NOT NULL GROUP BY preferred_model')
            preferred = {r[0]: r[1] for r in c.fetchall()}

            # Average caption rating
            c.execute('SELECT AVG(caption_rating) FROM feedback WHERE caption_rating IS NOT NULL')
            avg_rating = c.fetchone()[0]

        self.send_json({
            'by_photo': by_photo,
            'preferred_model': preferred,
            'avg_caption_rating': avg_rating
        })

    def get_vision_corrections(self):
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM vision_corrections ORDER BY created_at DESC')
            rows = [dict(r) for r in c.fetchall()]
        self.send_json(rows)

    def get_caption_ratings(self):
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM caption_ratings ORDER BY created_at DESC')
            rows = [dict(r) for r in c.fetchall()]
        self.send_json(rows)

    def save_feedback(self, data):
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO feedback (photo, model, vision_correct, caption_rating, preferred_model, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                data.get('photo'),
                data.get('model'),
                data.get('vision_correct'),
                data.get('caption_rating'),
                data.get('preferred_model'),
                data.get('notes')
            ))
            last_row_id = c.lastrowid
        self.send_json({'success': True, 'id': last_row_id})

    def save_vision_correction(self, data):
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO vision_corrections (photo, ai_piece_type, ai_glaze_type, correct_piece_type, correct_glaze_type, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                data.get('photo'),
                data.get('ai_piece_type'),
                data.get('ai_glaze_type'),
                data.get('correct_piece_type'),
                data.get('correct_glaze_type'),
                data.get('notes')
            ))
            last_row_id = c.lastrowid
        self.send_json({'success': True, 'id': last_row_id})

    def save_caption_rating(self, data):
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO caption_ratings (photo, model, hook_rating, body_rating, cta_rating, voice_authentic, preferred, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('photo'),
                data.get('model'),
                data.get('hook_rating'),
                data.get('body_rating'),
                data.get('cta_rating'),
                data.get('voice_authentic'),
                data.get('preferred'),
                data.get('notes')
            ))
            last_row_id = c.lastrowid
        self.send_json({'success': True, 'id': last_row_id})

    def get_idea_seeds(self, query):
        """Get idea seeds, optionally filtered by photo"""
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            photo = query.get('photo', [None])[0]
            if photo:
                c.execute('SELECT * FROM idea_seeds WHERE photo = ? AND deleted_at IS NULL ORDER BY created_at DESC, id DESC', (photo,))
            else:
                c.execute('SELECT * FROM idea_seeds WHERE deleted_at IS NULL ORDER BY created_at DESC, id DESC')

            rows = [dict(r) for r in c.fetchall()]
        self.send_json(rows)

    def save_idea_seed(self, data):
        """Save a new idea seed for a photo"""
        with get_db() as conn:
            c = conn.cursor()
            # Dedup check
            c.execute('SELECT id FROM idea_seeds WHERE photo = ? AND seed_text = ? AND deleted_at IS NULL',
                      (data.get('photo'), data.get('seed_text')))
            if c.fetchone():
                self.send_json({'success': False, 'error': 'duplicate'}, 409)
                return
            c.execute('''
                INSERT INTO idea_seeds (photo, seed_text)
                VALUES (?, ?)
            ''', (
                data.get('photo'),
                data.get('seed_text')
            ))
            last_row_id = c.lastrowid
        self.send_json({'success': True, 'id': last_row_id})

    def update_idea_seed(self, seed_id, data):
        """Update an idea seed's text by ID"""
        new_text = data.get('seed_text', '').strip()
        if not new_text:
            self.send_json({'success': False, 'error': 'Empty text'}, 400)
            return
        with get_db() as conn:
            c = conn.cursor()
            c.execute('UPDATE idea_seeds SET seed_text = ? WHERE id = ? AND deleted_at IS NULL', (new_text, seed_id))
            updated = c.rowcount > 0
        if updated:
            self.send_json({'success': True})
        else:
            self.send_json({'success': False, 'error': 'Not found'}, 404)

    def delete_idea_seed(self, seed_id):
        """Soft-delete an idea seed by ID"""
        with get_db() as conn:
            c = conn.cursor()
            c.execute('UPDATE idea_seeds SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?', (seed_id,))
            deleted = c.rowcount > 0
        if deleted:
            self.send_json({'success': True})
        else:
            self.send_json({'success': False, 'error': 'Not found'}, 404)

    def delete_series_piece(self, piece_id):
        """Delete a series piece by ID"""
        with get_db() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM series_pieces WHERE id = ?', (piece_id,))
            deleted = c.rowcount > 0
        if deleted:
            self.send_json({'success': True})
        else:
            self.send_json({'success': False, 'error': 'Not found'}, 404)

    def get_creative_director(self, query):
        """Get creative director notes for a photo"""
        photo = query.get('photo', [None])[0]
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            if photo:
                c.execute('SELECT * FROM creative_director WHERE photo = ?', (photo,))
                row = c.fetchone()
                result = dict(row) if row else None
            else:
                c.execute('SELECT * FROM creative_director ORDER BY created_at DESC')
                result = [dict(r) for r in c.fetchall()]

        self.send_json(result)

    def save_creative_director(self, data):
        """Save or update creative director notes for a photo (one per photo)"""
        with get_db() as conn:
            c = conn.cursor()
            # Use REPLACE to update if exists
            c.execute('''
                INSERT OR REPLACE INTO creative_director (photo, direction_text, created_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (
                data.get('photo'),
                data.get('direction_text')
            ))
            last_row_id = c.lastrowid
        self.send_json({'success': True, 'id': last_row_id})

    def get_series(self):
        """Get all series"""
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('''
                SELECT s.*, COUNT(sp.id) as piece_count
                FROM series s
                LEFT JOIN series_pieces sp ON s.id = sp.series_id
                GROUP BY s.id
                ORDER BY s.created_at DESC
            ''')
            rows = [dict(r) for r in c.fetchall()]
        self.send_json(rows)

    def get_series_pieces(self, series_id):
        """Get all pieces in a series"""
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            if series_id == 'all':
                c.execute('SELECT * FROM series_pieces ORDER BY series_id, order_index')
            else:
                c.execute('SELECT * FROM series_pieces WHERE series_id = ? ORDER BY order_index', (series_id,))
            rows = [dict(r) for r in c.fetchall()]
        self.send_json(rows)

    def create_series(self, data):
        """Create a new series"""
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO series (name, description, naming_system, frame_style)
                VALUES (?, ?, ?, ?)
            ''', (
                data.get('name'),
                data.get('description'),
                data.get('naming_system'),
                data.get('frame_style', 'planetary')
            ))
            series_id = c.lastrowid
        self.send_json({'success': True, 'id': series_id})

    def add_series_piece(self, data):
        """Add a piece to a series with worldbuilding data"""
        with get_db() as conn:
            c = conn.cursor()

            # Get next order index
            c.execute('SELECT COALESCE(MAX(order_index), 0) + 1 FROM series_pieces WHERE series_id = ?',
                      (data.get('series_id'),))
            next_order = c.fetchone()[0]

            c.execute('''
                INSERT OR REPLACE INTO series_pieces
                (series_id, photo, planet_name, orbital_data, surface_geology,
                 formation_history, inhabitants, generated_caption, order_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('series_id'),
                data.get('photo'),
                data.get('planet_name'),
                data.get('orbital_data'),
                data.get('surface_geology'),
                data.get('formation_history'),
                data.get('inhabitants'),
                data.get('generated_caption'),
                data.get('order_index', next_order)
            ))
        self.send_json({'success': True})

    def set_post_format(self, data):
        """Set post format for a photo (photo/carousel/video)"""
        with get_db() as conn:
            c = conn.cursor()
            c.execute('UPDATE photos SET post_format = ? WHERE filename = ?',
                      (data.get('format'), data.get('photo')))
        self.send_json({'success': True})

    def regenerate_caption(self, data):
        """Regenerate a caption for a photo using the specified model.
        For photos in a series, generates a planetary caption instead."""
        try:
            photo = data.get('photo')
            model = data.get('model')
            seed_text = data.get('seed_text', '')
            if not seed_text:
                with get_db() as conn:
                    c = conn.cursor()
                    c.execute('SELECT seed_text FROM idea_seeds WHERE photo = ? AND deleted_at IS NULL ORDER BY created_at DESC, id DESC', (photo,))
                    seeds = [r[0] for r in c.fetchall()]
                    seed_text = "; ".join(seeds)

            # Check if photo is in a series — use planetary caption generator
            with get_db() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute('''
                    SELECT sp.id, sp.series_id, sp.planet_name, sp.orbital_data,
                           sp.surface_geology, sp.formation_history, sp.inhabitants
                    FROM series_pieces sp
                    WHERE sp.photo LIKE ?
                    LIMIT 1
                ''', (photo + '%',))
                series_piece = c.fetchone()

            if series_piece:
                # Use planetary caption generator for series pieces
                return self._regenerate_planetary_caption(photo, series_piece, seed_text=seed_text)

            # Regular caption flow for non-series photos
            # Load vision analysis from DB
            with get_db() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute('''
                    SELECT vr.* FROM vision_results vr
                    JOIN photos p ON vr.photo_id = p.id
                    WHERE p.filename = ? AND vr.model = ?
                ''', (photo, model))
                vr = c.fetchone()
                if not vr:
                    # Fallback: try any model for this photo (most recent first)
                    c.execute('''
                        SELECT vr.* FROM vision_results vr
                        JOIN photos p ON vr.photo_id = p.id
                        WHERE p.filename = ?
                        ORDER BY vr.created_at DESC LIMIT 1
                    ''', (photo,))
                    vr = c.fetchone()

            if not vr:
                self.send_json({'error': 'Vision data not found for photo in database'}, status=400)
                return

            vision_data = dict(vr)
            # Parse JSON-encoded list fields from DB
            for field in ('primary_colors', 'secondary_colors', 'surface_qualities',
                          'form_attributes', 'hypotheses', 'safety_flags'):
                raw = vision_data.get(field)
                if raw:
                    try:
                        vision_data[field] = json.loads(raw) if isinstance(raw, str) else raw
                    except (json.JSONDecodeError, TypeError):
                        vision_data[field] = [raw] if raw else []
                else:
                    vision_data[field] = []

            # Import caption generator
            from lib.caption_generator import PhotoAnalysis, generate_caption_with_ai

            # Create PhotoAnalysis object
            analysis = PhotoAnalysis(
                content_type=vision_data.get('content_type'),
                piece_type=vision_data.get('piece_type'),
                primary_colors=vision_data.get('primary_colors', []),
                secondary_colors=vision_data.get('secondary_colors', []),
                glaze_type=vision_data.get('glaze_type'),
                color_appearance=vision_data.get('color_appearance'),
                technique=vision_data.get('technique'),
                mood=vision_data.get('mood'),
                is_process=vision_data.get('is_process', False),
                dimensions_visible=vision_data.get('dimensions_visible', False),
                suggested_hook=vision_data.get('suggested_hook'),
                firing_state=vision_data.get('firing_state'),
                surface_qualities=vision_data.get('surface_qualities', []),
                piece_count=vision_data.get('piece_count', 1),
                clay_type=vision_data.get('clay_type'),
                form_attributes=vision_data.get('form_attributes', []),
                purpose=vision_data.get('purpose'),
                product_family=vision_data.get('product_family'),
                hypotheses=vision_data.get('hypotheses', []),
                safety_flags=vision_data.get('safety_flags', [])
            )

            # Build voice rules with seed text if provided
            voice_rules = None
            if seed_text:
                voice_rules = f"Creative direction from the artist: {seed_text}. Weave these themes into the caption naturally."

            # Generate caption - generate_caption_with_ai handles both backends
            caption_result = generate_caption_with_ai(analysis, voice_rules=voice_rules)

            # Strip brainstorm step headers from the parsed caption
            hook = self._clean_caption_line(caption_result.hook)
            body = self._clean_caption_line(caption_result.body)
            cta = self._clean_caption_line(caption_result.cta)
            full = self._clean_full_caption(caption_result.full_caption)

            # If cleaning removed everything, extract from brainstorm output
            if not hook and not body:
                hook, body, cta = self._extract_best_caption(caption_result.full_caption)
                full = hook

            # Convert GeneratedCaption to dict for JSON response
            result = {
                'photo': photo,
                'model': model,
                'caption': {
                    'hook': hook,
                    'body': body,
                    'cta': cta,
                    'hashtags': caption_result.hashtags,
                    'full_caption': full
                },
                'regenerated': True
            }

            # Persist to caption_results table
            with get_db() as conn:
                c = conn.cursor()
                c.execute('SELECT id FROM photos WHERE filename = ?', (photo,))
                row = c.fetchone()
                if row:
                    photo_id = row[0]
                    c.execute('''
                        INSERT INTO caption_results (photo_id, model, hook, body, cta, full_caption)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(photo_id, model) DO UPDATE SET
                            hook = excluded.hook,
                            body = excluded.body,
                            cta = excluded.cta,
                            full_caption = excluded.full_caption
                    ''', (photo_id, model, hook, body, cta, full))

            self.send_json(result)

        except Exception as e:
            print(f"Error regenerating caption: {e}")
            import traceback
            traceback.print_exc()
            self.send_json({'error': str(e)}, status=500)

    def _regenerate_planetary_caption(self, photo, series_piece, seed_text=""):
        """Generate a planetary caption for a series piece."""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
        from generate_planetary_captions import generate_caption_openrouter, get_vision_data

        DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'human-door', 'feedback.db')
        db_path = type('obj', (object,), {'db_path': DB_PATH})()

        # Load seeds from DB if not passed
        if not seed_text:
            with get_db() as conn:
                c = conn.cursor()
                c.execute('SELECT seed_text FROM idea_seeds WHERE photo = ? AND deleted_at IS NULL ORDER BY created_at DESC, id DESC', (photo,))
                seeds = [r[0] for r in c.fetchall()]
                seed_text = "; ".join(seeds)

        # Get planet data as dict
        planet_data = dict(series_piece)

        # Get vision data
        vision = get_vision_data(DB_PATH, photo)

        if not vision:
            self.send_json({'error': 'No vision data found for this photo'}, status=400)
            return

        # Build creative direction for the prompt
        creative_direction = ""
        if seed_text:
            creative_direction = f"\nCREATIVE DIRECTION FROM THE ARTIST (must weave these themes into the caption):\n{seed_text}\n"

        # Generate planetary caption
        caption = generate_caption_openrouter(planet_data, vision, creative_direction=creative_direction)

        # Update series_pieces table
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                UPDATE series_pieces SET generated_caption = ? WHERE id = ?
            ''', (caption, series_piece['id']))

        # Return in format the frontend expects
        self.send_json({
            'photo': photo,
            'model': 'planetary',
            'caption': {
                'hook': '',
                'body': '',
                'cta': '',
                'hashtags': '',
                'full_caption': caption
            },
            'regenerated': True
        })

    def generate_missing_captions(self, data):
        """Generate captions for all photos that have vision data but no caption."""
        from lib.caption_generator import PhotoAnalysis, generate_caption_with_ai

        generated = 0
        errors = []
        skipped_no_vision = []

        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Find photos with vision data but no caption in caption_results
            c.execute('''
                SELECT p.id as photo_id, p.filename,
                       (SELECT vr.model FROM vision_results vr
                        WHERE vr.photo_id = p.id
                        ORDER BY vr.created_at DESC LIMIT 1) as vision_model
                FROM photos p
                WHERE EXISTS (
                    SELECT 1 FROM vision_results vr WHERE vr.photo_id = p.id
                )
                AND NOT EXISTS (
                    SELECT 1 FROM caption_results cr WHERE cr.photo_id = p.id
                )
                ORDER BY p.filename
            ''')
            missing = c.fetchall()

        if not missing:
            self.send_json({'generated': 0, 'errors': [], 'message': 'All photos with vision data already have captions'})
            return

        for row in missing:
            filename = row['filename']
            vision_model = row['vision_model']
            photo_id = row['photo_id']

            try:
                # Load vision data from DB (prefer Gemini, fallback to any model)
                with get_db() as conn:
                    conn.row_factory = sqlite3.Row
                    c = conn.cursor()
                    c.execute('''
                        SELECT vr.* FROM vision_results vr
                        WHERE vr.photo_id = ? AND vr.model = 'Gemini'
                    ''', (photo_id,))
                    vr = c.fetchone()
                    if not vr:
                        c.execute('''
                            SELECT vr.* FROM vision_results vr
                            WHERE vr.photo_id = ?
                            ORDER BY vr.created_at DESC LIMIT 1
                        ''', (photo_id,))
                        vr = c.fetchone()

                if not vr:
                    skipped_no_vision.append(filename)
                    continue

                vision_data = dict(vr)
                # Parse JSON-encoded list fields
                for field in ('primary_colors', 'secondary_colors', 'surface_qualities',
                              'form_attributes', 'hypotheses', 'safety_flags'):
                    raw = vision_data.get(field)
                    if raw:
                        try:
                            vision_data[field] = json.loads(raw) if isinstance(raw, str) else raw
                        except (json.JSONDecodeError, TypeError):
                            vision_data[field] = [raw] if raw else []
                    else:
                        vision_data[field] = []

                # Load idea seeds for this photo
                seeds = []
                with get_db() as conn:
                    conn.row_factory = sqlite3.Row
                    c2 = conn.cursor()
                    c2.execute('SELECT seed_text FROM idea_seeds WHERE photo = ? AND deleted_at IS NULL ORDER BY created_at DESC, id DESC', (filename,))
                    seeds = [r['seed_text'] for r in c2.fetchall()]

                voice_rules = None
                if seeds:
                    voice_rules = "Creative direction from the artist: " + "; ".join(seeds) + ". Weave these themes into the caption naturally."

                # Build PhotoAnalysis
                analysis = PhotoAnalysis(
                    content_type=vision_data.get('content_type'),
                    piece_type=vision_data.get('piece_type'),
                    primary_colors=vision_data.get('primary_colors', []),
                    secondary_colors=vision_data.get('secondary_colors', []),
                    glaze_type=vision_data.get('glaze_type'),
                    color_appearance=vision_data.get('color_appearance'),
                    technique=vision_data.get('technique'),
                    mood=vision_data.get('mood'),
                    is_process=vision_data.get('is_process', False),
                    dimensions_visible=vision_data.get('dimensions_visible', False),
                    suggested_hook=vision_data.get('suggested_hook'),
                    firing_state=vision_data.get('firing_state'),
                    surface_qualities=vision_data.get('surface_qualities', []),
                    piece_count=vision_data.get('piece_count', 1),
                    clay_type=vision_data.get('clay_type'),
                    form_attributes=vision_data.get('form_attributes', []),
                    purpose=vision_data.get('purpose'),
                    product_family=vision_data.get('product_family'),
                    hypotheses=vision_data.get('hypotheses', []),
                    safety_flags=vision_data.get('safety_flags', [])
                )

                caption_result = generate_caption_with_ai(analysis, voice_rules=voice_rules)

                hook = self._clean_caption_line(caption_result.hook)
                body = self._clean_caption_line(caption_result.body)
                cta = self._clean_caption_line(caption_result.cta)
                full = self._clean_full_caption(caption_result.full_caption)

                # If cleaning removed everything, extract from brainstorm output
                if not hook and not body:
                    hook, body, cta = self._extract_best_caption(caption_result.full_caption)
                    full = hook

                # Persist to caption_results
                with get_db() as conn:
                    c3 = conn.cursor()
                    c3.execute('''
                        INSERT INTO caption_results (photo_id, model, hook, body, cta, full_caption)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (photo_id, vision_data['model'], hook, body, cta, full))

                generated += 1
                print(f"Generated caption for {filename} (model: {vision_data['model']})")

            except Exception as e:
                print(f"Error generating caption for {filename}: {e}")
                import traceback
                traceback.print_exc()
                errors.append(f"{filename}: {str(e)}")

        self.send_json({
            'generated': generated,
            'errors': errors,
            'skipped_no_vision': skipped_no_vision,
            'total_missing': len(missing)
        })

    def _clean_caption_line(self, text):
        """Strip brainstorm step headers and numbering from a caption line."""
        if not text:
            return text
        lines = text.split('\n')
        cleaned = []
        for line in lines:
            stripped = line.strip()
            # Skip step headers like "=== STEP 1: ..." or "**STEP..."
            if stripped.startswith('===') or stripped.startswith('**STEP'):
                continue
            # Skip numbered items like "1. **The..."
            if re.match(r'^\d+\.\s+\*\*', stripped):
                continue
            # Skip empty lines
            if not stripped:
                continue
            # Strip leading/trailing markdown bold
            cleaned.append(re.sub(r'^\*\*|\*\*$', '', stripped).strip())
        return '\n'.join(cleaned) if cleaned else ''

    def _extract_best_caption(self, full_caption):
        """Extract the best caption from brainstorm-style AI output.

        Handles multi-step output like:
          === STEP 1: BRAINSTORM ===
          1. idea...
          === STEP 2: SELECT 3 ===
          CAPTIONS:
          1. [caption 1]
          2. [caption 2]
          3. [caption 3]

        Also handles structured output:
          1. **Hook:** text
          **Body:** text
          **Question:** text
        """
        if not full_caption:
            return '', '', ''

        text = full_caption.strip()

        # Handle structured Hook/Body/Question format
        hook_match = re.search(r'(?:^|\d+\.\s+)\*\*Hook:\*\*\s*(.+?)(?:\n|$)', text, re.MULTILINE)
        body_match = re.search(r'\*\*Body:\*\*\s*(.+?)(?=\*\*|\n\n|\n\d+\.|$)', text, re.DOTALL)
        cta_match = re.search(r'\*\*(?:Question|CTA):\*\*\s*(.+?)(?:\n|$)', text, re.MULTILINE)

        if hook_match:
            hook = hook_match.group(1).strip()
            body = body_match.group(1).strip().replace('\n', ' ') if body_match else ''
            cta = cta_match.group(1).strip() if cta_match else ''
            return hook, body, cta

        # If output has STEP 2 / CAPTIONS section, extract from there
        step2_match = re.search(
            r'(?:===\s*STEP\s*2.*?===)\s*\n([\s\S]*?)$',
            text, re.IGNORECASE
        )
        if step2_match:
            candidates = re.findall(r'^\d+\.\s+(.+)$', step2_match.group(1), re.MULTILINE)
            if candidates:
                hook = candidates[0].strip()
                return hook, '', ''

        # Look for CAPTIONS: header followed by numbered list
        captions_match = re.search(r'\*\*?CAPTIONS:\*?\s*\n([\s\S]*?)$', text, re.IGNORECASE)
        if captions_match:
            candidates = re.findall(r'^\d+\.\s+(.+)$', captions_match.group(1), re.MULTILINE)
            if candidates:
                hook = candidates[0].strip()
                return hook, '', ''

        # Fallback: look for quoted draft lines (from chain-of-thought output)
        # These look like: Draft: "Three layers of..."
        draft_match = re.search(r'Draft:\s*["\u201c](.+?)["\u201d]', text)
        if draft_match:
            return draft_match.group(1).strip(), '', ''

        # Look for any line in quotes that ends with a question mark (caption-like)
        quoted_lines = re.findall(r'["\u201c]([^"\u201d]{20,}?\?)["\u201d]', text)
        if quoted_lines:
            return quoted_lines[0].strip(), '', ''

        # Fallback: return first non-header, non-empty line
        lines = [l.strip() for l in text.split('\n')
                 if l.strip()
                 and not l.strip().startswith('===')
                 and not l.strip().startswith('**STEP')
                 and not l.strip().upper().startswith('**CAPTIONS')
                 and not re.match(r'^\d+\.\s+\*\*', l.strip())]
        if lines:
            hook = re.sub(r'^\*\*|\*\*$', '', lines[0]).strip()
            return hook, '', ''
        return '', '', ''

    def _clean_full_caption(self, text):
        """Clean the full_caption by removing brainstorm artifacts."""
        if not text:
            return text
        lines = text.split('\n')
        cleaned = []
        in_brainstorm = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('=== STEP'):
                in_brainstorm = True
                continue
            if in_brainstorm and (stripped.startswith('===') or stripped.startswith('**STEP')):
                continue
            if in_brainstorm and re.match(r'^\d+\.\s+\*\*', stripped):
                continue
            if not in_brainstorm:
                cleaned.append(line)
        return '\n'.join(cleaned).strip() if cleaned else text

    def get_caption_winners(self):
        """Get all caption winners (selected captions for each photo)"""
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Get photo -> model mapping from caption_selections
            c.execute('SELECT photo, selected_model FROM caption_selections')

            winners = {r['photo']: r['selected_model'] for r in c.fetchall()}
        self.send_json(winners)

    def select_caption_winner(self, data):
        """Select a caption as the winner for a photo"""
        photo = data.get('photo')
        model = data.get('model')

        if not photo or not model:
            self.send_json({'success': False, 'error': 'Missing photo or model'}, 400)
            return

        try:
            with get_db() as conn:
                c = conn.cursor()

                # Insert or replace the selection
                c.execute('''
                    INSERT OR REPLACE INTO caption_selections (photo, selected_model, selected_caption)
                    VALUES (?, ?, ?)
                ''', (photo, model, None))

            self.send_json({'success': True})
        except Exception as e:
            self.send_json({'success': False, 'error': str(e)}, 500)

if __name__ == '__main__':
    init_db()
    migrate_db()
    sync_photos()
    print(f"🚪 Human Door running at http://localhost:{PORT}")
    server = HTTPServer(('', PORT), Handler)
    server.serve_forever()
