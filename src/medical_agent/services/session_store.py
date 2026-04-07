from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

import pymysql
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from medical_agent.config import MysqlSettings, get_settings


@dataclass
class SessionRecord:
    thread_id: str
    role: str
    content: str
    created_at: datetime | None = None


@dataclass
class ThreadRecord:
    thread_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    message_count: int = 0


class SessionStore(ABC):
    @abstractmethod
    def load_history(self, thread_id: str) -> list[BaseMessage]:
        raise NotImplementedError

    @abstractmethod
    def append_exchange(self, thread_id: str, question: str, answer: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_threads(self, limit: int = 50) -> list[ThreadRecord]:
        raise NotImplementedError

    @abstractmethod
    def get_thread_messages(self, thread_id: str, limit: int = 100) -> list[SessionRecord]:
        raise NotImplementedError


class InMemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self._memory: dict[str, list[SessionRecord]] = defaultdict(list)

    def load_history(self, thread_id: str) -> list[BaseMessage]:
        messages: list[BaseMessage] = []
        for record in self._memory.get(thread_id, []):
            if record.role == "human":
                messages.append(HumanMessage(content=record.content))
            elif record.role == "ai":
                messages.append(AIMessage(content=record.content))
        return messages[-12:]

    def append_exchange(self, thread_id: str, question: str, answer: str) -> None:
        now = datetime.now()
        records = self._memory[thread_id]
        records.append(SessionRecord(thread_id=thread_id, role="human", content=question, created_at=now))
        records.append(SessionRecord(thread_id=thread_id, role="ai", content=answer, created_at=now))
        self._memory[thread_id] = records[-100:]

    def list_threads(self, limit: int = 50) -> list[ThreadRecord]:
        threads: list[ThreadRecord] = []
        for thread_id, records in self._memory.items():
            if not records:
                continue
            threads.append(
                ThreadRecord(
                    thread_id=thread_id,
                    created_at=records[0].created_at,
                    updated_at=records[-1].created_at,
                    message_count=len(records),
                )
            )
        threads.sort(key=lambda item: item.updated_at or datetime.min, reverse=True)
        return threads[:limit]

    def get_thread_messages(self, thread_id: str, limit: int = 100) -> list[SessionRecord]:
        return list(self._memory.get(thread_id, []))[-limit:]


class MysqlSessionStore(SessionStore):
    def __init__(self, settings: MysqlSettings) -> None:
        self.settings = settings
        self._ensure_tables()

    def _connect(self):
        return pymysql.connect(
            host=self.settings.host,
            port=self.settings.port,
            user=self.settings.user,
            password=self.settings.password,
            database=self.settings.database,
            charset=self.settings.charset,
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )

    def _ensure_tables(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agent_threads (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        thread_id VARCHAR(128) NOT NULL UNIQUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agent_messages (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        thread_id VARCHAR(128) NOT NULL,
                        role VARCHAR(32) NOT NULL,
                        content MEDIUMTEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_thread_created (thread_id, created_at),
                        CONSTRAINT fk_agent_messages_thread
                            FOREIGN KEY (thread_id) REFERENCES agent_threads(thread_id)
                            ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )

    def load_history(self, thread_id: str) -> list[BaseMessage]:
        rows = self.get_thread_messages(thread_id, limit=12)
        messages: list[BaseMessage] = []
        for row in rows:
            if row.role == "human":
                messages.append(HumanMessage(content=row.content))
            elif row.role == "ai":
                messages.append(AIMessage(content=row.content))
        return messages

    def append_exchange(self, thread_id: str, question: str, answer: str) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO agent_threads (thread_id)
                    VALUES (%s)
                    ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP
                    """,
                    (thread_id,),
                )
                cursor.executemany(
                    """
                    INSERT INTO agent_messages (thread_id, role, content)
                    VALUES (%s, %s, %s)
                    """,
                    [
                        (thread_id, "human", question),
                        (thread_id, "ai", answer),
                    ],
                )

    def list_threads(self, limit: int = 50) -> list[ThreadRecord]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        t.thread_id,
                        t.created_at,
                        t.updated_at,
                        COUNT(m.id) AS message_count
                    FROM agent_threads t
                    LEFT JOIN agent_messages m ON m.thread_id = t.thread_id
                    GROUP BY t.thread_id, t.created_at, t.updated_at
                    ORDER BY t.updated_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cursor.fetchall()

        return [
            ThreadRecord(
                thread_id=row["thread_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                message_count=int(row["message_count"] or 0),
            )
            for row in rows
        ]

    def get_thread_messages(self, thread_id: str, limit: int = 100) -> list[SessionRecord]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT thread_id, role, content, created_at
                    FROM (
                        SELECT thread_id, role, content, created_at, id
                        FROM agent_messages
                        WHERE thread_id = %s
                        ORDER BY id DESC
                        LIMIT %s
                    ) recent_messages
                    ORDER BY id ASC
                    """,
                    (thread_id, limit),
                )
                rows = cursor.fetchall()

        return [
            SessionRecord(
                thread_id=row["thread_id"],
                role=row["role"],
                content=row["content"],
                created_at=row["created_at"],
            )
            for row in rows
        ]


@lru_cache(maxsize=1)
def get_session_store() -> SessionStore:
    settings = get_settings()
    if settings.mysql:
        return MysqlSessionStore(settings.mysql)
    return InMemorySessionStore()
