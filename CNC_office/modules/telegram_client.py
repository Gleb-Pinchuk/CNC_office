import asyncio
import logging
from typing import Optional, List, Dict
from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
import os
import tempfile
from config import (
    TELEGRAM_API_ID, TELEGRAM_API_HASH, PROXY_URL, 
    REQUEST_TIMEOUT, DATA_DIR
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TelegramClient:
    """Клиент для подключения к Telegram через прокси"""
    
    def __init__(self):
        self.client = None
        self.proxy = self._parse_proxy(PROXY_URL) if PROXY_URL else None
    
    def _parse_proxy(self, proxy_url: str) -> tuple:
        """Разобрать строку прокси"""
        try:
            # Формат: http://user:pass@ip:port или socks5://ip:port
            if '@' in proxy_url:
                protocol, rest = proxy_url.split('://')
                auth, address = rest.split('@')
                ip, port = address.split(':')
                username, password = auth.split(':')
                return (protocol, ip, int(port), username, password)
            else:
                protocol, rest = proxy_url.split('://')
                ip, port = rest.split(':')
                return (protocol, ip, int(port), None, None)
        except Exception as e:
            logger.error(f"Ошибка разбора прокси: {e}")
            return None
    
    async def connect(self):
        """Подключиться к Telegram"""
        if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
            raise ValueError("Необходимо настроить TELEGRAM_API_ID и TELEGRAM_API_HASH")
        
        session_file = os.path.join(DATA_DIR, "telegram_session.session")
        
        self.client = TelegramClient(
            session_file,
            int(TELEGRAM_API_ID),
            TELEGRAM_API_HASH,
            proxy=self.proxy
        )
        
        await self.client.connect()
        
        if not await self.client.is_user_authorized():
            logger.warning("Требуется авторизация. Запустите скрипт авторизации.")
            return False
        
        logger.info("Успешное подключение к Telegram")
        return True
    
    async def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Получить информацию о пользователе по нику"""
        try:
            if not username.startswith('@'):
                username = '@' + username
            
            user = await self.client.get_entity(username)
            return {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'bio': getattr(user, 'about', ''),
                'photo_count': await self._count_photos(user),
                'recent_posts': await self._get_recent_media(user)
            }
        except Exception as e:
            logger.error(f"Ошибка получения пользователя {username}: {e}")
            return None
    
    async def _count_photos(self, user) -> int:
        """Посчитать количество фото у пользователя"""
        count = 0
        async for message in self.client.iter_messages(user, filter=lambda m: m.media):
            if isinstance(message.media, MessageMediaPhoto):
                count += 1
        return count
    
    async def _get_recent_media(self, user, limit: int = 10) -> List[Dict]:
        """Получить последние медиафайлы"""
        media_list = []
        async for message in self.client.iter_messages(user, limit=limit):
            if message.media:
                media_info = {
                    'message_id': message.id,
                    'date': message.date,
                    'text': message.text,
                    'type': 'photo' if isinstance(message.media, MessageMediaPhoto) else 'document'
                }
                media_list.append(media_info)
        return media_list
    
    async def download_media(self, username: str, output_dir: str = None, limit: int = 20) -> List[str]:
        """Скачать медиафайлы пользователя"""
        if output_dir is None:
            output_dir = os.path.join(DATA_DIR, "downloads", username.replace('@', ''))
        
        os.makedirs(output_dir, exist_ok=True)
        
        downloaded_files = []
        
        try:
            user = await self.client.get_entity(username)
            count = 0
            
            async for message in self.client.iter_messages(user, limit=limit):
                if message.media and count < limit:
                    try:
                        path = await self.client.download_media(
                            message.media,
                            file=os.path.join(output_dir, f"{message.id}_{count}"),
                            timeout=REQUEST_TIMEOUT
                        )
                        if path:
                            downloaded_files.append(path)
                            count += 1
                    except Exception as e:
                        logger.warning(f"Не удалось скачать медиа {message.id}: {e}")
            
            logger.info(f"Скачано {len(downloaded_files)} файлов для {username}")
            return downloaded_files
            
        except Exception as e:
            logger.error(f"Ошибка скачивания медиа для {username}: {e}")
            return []
    
    async def disconnect(self):
        """Отключиться от Telegram"""
        if self.client:
            await self.client.disconnect()
            logger.info("Отключено от Telegram")
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
