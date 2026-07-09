import sqlite3
import time

def drop_column():
    db_path = "db.sqlite3"
    print(f"Connecting to {db_path}...")
    # 60 second timeout to wait for any locks to release
    conn = sqlite3.connect(db_path, timeout=60.0)
    cursor = conn.cursor()
    
    print("Checking if column exists...")
    cursor.execute("PRAGMA table_info(transcription_transcript)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "has_diarization" in columns:
        print("Column 'has_diarization' found. Dropping...")
        try:
            cursor.execute("ALTER TABLE transcription_transcript DROP COLUMN has_diarization")
            conn.commit()
            print("Successfully dropped column 'has_diarization'.")
        except Exception as e:
            print(f"Error dropping column: {e}")
            # Fallback for old sqlite versions that don't support DROP COLUMN
            print("Attempting fallback rebuild...")
            cursor.execute("BEGIN TRANSACTION")
            cursor.execute("CREATE TABLE transcription_transcript_backup AS SELECT id, raw_text, word_timestamps, session_id, has_edits, created_at FROM transcription_transcript")
            cursor.execute("DROP TABLE transcription_transcript")
            cursor.execute("CREATE TABLE transcription_transcript (id INTEGER PRIMARY KEY AUTOINCREMENT, raw_text TEXT NOT NULL, word_timestamps JSON NOT NULL, session_id char(32) NOT NULL REFERENCES uploads_session(id), has_edits BOOLEAN NOT NULL, created_at DATETIME NOT NULL)")
            cursor.execute("INSERT INTO transcription_transcript SELECT * FROM transcription_transcript_backup")
            cursor.execute("DROP TABLE transcription_transcript_backup")
            conn.commit()
            print("Fallback rebuild complete.")
    else:
        print("Column 'has_diarization' not found. It may have already been dropped.")
        
    conn.close()

if __name__ == "__main__":
    drop_column()
