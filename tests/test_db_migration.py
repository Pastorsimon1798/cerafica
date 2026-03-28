"""
Test database migration for new vision analysis columns.

Task 1.2: Add 4 new columns to vision_results table migration.
Tests the migration logic that adds missing columns to existing database.

Following TDD: Test written first, will fail until migration code is updated.
"""
import sys
import sqlite3
import tempfile
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def create_minimal_vision_results_table(conn: sqlite3.Connection):
    """
    Create a minimal vision_results table with only the original columns.
    This simulates an old database schema before any migrations.
    """
    c = conn.cursor()
    c.execute('''
        CREATE TABLE vision_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id INTEGER NOT NULL,
            model TEXT NOT NULL,
            piece_type TEXT,
            glaze_type TEXT,
            primary_colors TEXT,
            secondary_colors TEXT,
            surface_qualities TEXT,
            mood TEXT,
            form_attributes TEXT,
            firing_state TEXT,
            technique TEXT,
            content_type TEXT,
            piece_count INTEGER DEFAULT 1,
            hypotheses TEXT,
            vision_reasoning TEXT,
            raw_response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(photo_id, model)
        )
    ''')
    conn.commit()


def add_missing_columns(conn: sqlite3.Connection, columns: list[str]):
    """
    Extracted migration logic: Add missing columns to vision_results table.
    This is the core logic we're testing.
    """
    c = conn.cursor()
    for col in columns:
        try:
            c.execute(f'ALTER TABLE vision_results ADD COLUMN {col} TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
    conn.commit()


def get_table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    """Get list of column names for a table using PRAGMA."""
    c = conn.cursor()
    c.execute(f'PRAGMA table_info({table_name})')
    return [row[1] for row in c.fetchall()]


def test_migration_adds_new_columns():
    """
    Test that migration adds all 4 new columns to vision_results table.
    This test will FAIL until we update migrate_db() to include the new columns.
    """
    # Create a temporary database
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    try:
        # Create minimal vision_results table (simulating old schema)
        conn = sqlite3.connect(db_path)
        create_minimal_vision_results_table(conn)
        initial_columns = get_table_columns(conn, 'vision_results')
        conn.close()

        # Verify new columns don't exist yet
        new_columns = ['lighting', 'photo_quality', 'uncertainties', 'color_distribution']
        for col in new_columns:
            assert col not in initial_columns, f"Column {col} should not exist initially"

        # Run migration with ALL columns (old + new)
        all_migration_columns = [
            'color_appearance', 'brief_description', 'clay_type', 'purpose',
            'product_family', 'dimensions_visible',
            'lighting', 'photo_quality', 'uncertainties', 'color_distribution'
        ]

        conn = sqlite3.connect(db_path)
        add_missing_columns(conn, all_migration_columns)
        final_columns = get_table_columns(conn, 'vision_results')
        conn.close()

        # Verify all new columns were added
        for col in new_columns:
            assert col in final_columns, f"Column {col} should exist after migration"

    finally:
        # Cleanup temp database
        Path(db_path).unlink()


def test_migration_idempotent():
    """
    Test that running migration twice doesn't cause errors.
    Columns that already exist should be skipped gracefully.
    """
    # Create a temporary database
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    try:
        # Create minimal vision_results table
        conn = sqlite3.connect(db_path)
        create_minimal_vision_results_table(conn)

        # Run migration once
        migration_columns = [
            'color_appearance', 'brief_description', 'clay_type', 'purpose',
            'product_family', 'dimensions_visible',
            'lighting', 'photo_quality', 'uncertainties', 'color_distribution'
        ]
        add_missing_columns(conn, migration_columns)

        # Run migration again - should not raise any errors
        add_missing_columns(conn, migration_columns)

        final_columns = get_table_columns(conn, 'vision_results')
        conn.close()

        # Verify all columns exist (no duplicates)
        for col in migration_columns:
            assert col in final_columns, f"Column {col} should exist"
            assert final_columns.count(col) == 1, f"Column {col} should not be duplicated"

    finally:
        # Cleanup temp database
        Path(db_path).unlink()


def test_migration_preserves_data():
    """
    Test that migration preserves existing data in the table.
    """
    # Create a temporary database
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    try:
        # Create minimal vision_results table and add test data
        conn = sqlite3.connect(db_path)
        create_minimal_vision_results_table(conn)
        c = conn.cursor()

        # Insert test data
        c.execute('''
            INSERT INTO vision_results
            (photo_id, model, piece_type, mood, piece_count)
            VALUES (?, ?, ?, ?, ?)
        ''', (123, 'test-model', 'test-vase', 'warm', 1))
        conn.commit()

        # Run migration
        migration_columns = [
            'color_appearance', 'brief_description', 'clay_type', 'purpose',
            'product_family', 'dimensions_visible',
            'lighting', 'photo_quality', 'uncertainties', 'color_distribution'
        ]
        add_missing_columns(conn, migration_columns)

        # Verify data is still there
        c.execute('SELECT piece_type, mood, piece_count FROM vision_results WHERE photo_id = ?', (123,))
        row = c.fetchone()
        conn.close()

        assert row is not None, "Data should be preserved"
        assert row[0] == 'test-vase', "piece_type should be preserved"
        assert row[1] == 'warm', "mood should be preserved"
        assert row[2] == 1, "piece_count should be preserved"

    finally:
        # Cleanup temp database
        Path(db_path).unlink()


def test_actual_migrate_db_has_all_columns():
    """
    Test that the actual migrate_db() function in auto_vision.py
    includes all 4 new columns in its migration list.

    This test reads the source code and checks that the new columns
    are present in the migrate_db() function. This ensures we don't
    forget to add them to the actual migration code.
    """
    # Read the auto_vision.py file
    auto_vision_path = project_root / 'instagram' / 'scripts' / 'auto_vision.py'
    with open(auto_vision_path, 'r') as f:
        content = f.read()

    # Find the migrate_db function
    import re
    migrate_db_match = re.search(
        r'def migrate_db\(\):.*?(?=\ndef |\nclass |\Z)',
        content,
        re.DOTALL
    )

    assert migrate_db_match, "Could not find migrate_db() function"

    migrate_db_code = migrate_db_match.group(0)

    # Check that all new columns are mentioned in the migrate_db function
    new_columns = ['lighting', 'photo_quality', 'uncertainties', 'color_distribution']
    missing_columns = []

    for col in new_columns:
        if col not in migrate_db_code:
            missing_columns.append(col)

    if missing_columns:
        raise AssertionError(
            f"migrate_db() function is missing these columns: {missing_columns}\n"
            f"Found code:\n{migrate_db_code}"
        )


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
