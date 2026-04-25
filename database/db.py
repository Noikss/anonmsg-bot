import aiosqlite
import os

DB_PATH = "anonmsg.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                full_name   TEXT,
                link_token  TEXT UNIQUE,
                is_blocked  INTEGER DEFAULT 0,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                receiver_id INTEGER,
                sender_hash TEXT,
                content     TEXT,
                media_type  TEXT,
                file_id     TEXT,
                is_read     INTEGER DEFAULT 0,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (receiver_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blocked_senders (
                receiver_id INTEGER,
                sender_hash TEXT,
                PRIMARY KEY (receiver_id, sender_hash)
            )
        """)
        await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            return await cursor.fetchone()


async def create_user(user_id: int, username: str, full_name: str, token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, full_name, link_token) VALUES (?, ?, ?, ?)",
            (user_id, username, full_name, token)
        )
        await db.commit()


async def get_user_by_token(token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE link_token = ?", (token,)
        ) as cursor:
            return await cursor.fetchone()


async def save_message(receiver_id: int, sender_hash: str, content: str, media_type: str = None, file_id: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (receiver_id, sender_hash, content, media_type, file_id) VALUES (?, ?, ?, ?, ?)",
            (receiver_id, sender_hash, content, media_type, file_id)
        )
        await db.commit()


async def is_sender_blocked(receiver_id: int, sender_hash: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM blocked_senders WHERE receiver_id = ? AND sender_hash = ?",
            (receiver_id, sender_hash)
        ) as cursor:
            return await cursor.fetchone() is not None


async def block_sender(receiver_id: int, sender_hash: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO blocked_senders (receiver_id, sender_hash) VALUES (?, ?)",
            (receiver_id, sender_hash)
        )
        await db.commit()


async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            users = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM messages") as cur:
            msgs = (await cur.fetchone())[0]
        return users, msgs
