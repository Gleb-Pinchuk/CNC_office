import asyncio
import logging
import os
import tempfile
from typing import Optional, List, Dict
import aiohttp
from config import PROXY_URL, REQUEST_TIMEOUT, DATA_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TikTokClient:
    """Клиент для подключения к TikTok через прокси"""
    
    def __init__(self):
        self.session = None
        self.proxy = PROXY_URL
        self.base_url = "https://www.tiktok.com"
    
    async def connect(self):
        """Подключиться к TikTok"""
        connector = None
        
        if self.proxy:
            # Настройка прокси для aiohttp
            connector = aiohttp.TCPConnector(ssl=False)
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json, text/plain, */*',
            }
        )
        
        logger.info("TikTok клиент инициализирован")
        return True
    
    async def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Получить информацию о пользователе по нику"""
        try:
            url = f"{self.base_url}/@{username}"
            
            async with self.session.get(url, timeout=REQUEST_TIMEOUT) as response:
                if response.status == 200:
                    # Парсинг страницы (упрощённо)
                    html = await response.text()
                    
                    # Извлечение данных из HTML (в реальности нужно использовать BeautifulSoup)
                    user_data = {
                        'username': username,
                        'url': url,
                        'followers': 0,  # Нужно парсить из HTML
                        'following': 0,
                        'likes': 0,
                        'video_count': 0,
                        'bio': ''
                    }
                    
                    return user_data
                else:
                    logger.warning(f"Пользователь {username} не найден или ошибка доступа")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка получения пользователя {username}: {e}")
            return None
    
    async def get_user_videos(self, username: str, limit: int = 20) -> List[Dict]:
        """Получить список видео пользователя"""
        videos = []
        
        try:
            # В реальности нужно использовать TikTok API или парсинг
            # Это упрощённая реализация
            url = f"{self.base_url}/api/recommend/item_list/"
            params = {
                'secUid': '',  # Нужно получить из профиля пользователя
                'count': limit
            }
            
            async with self.session.get(url, params=params, timeout=REQUEST_TIMEOUT) as response:
                if response.status == 200:
                    data = await response.json()
                    videos = data.get('itemList', [])
            
            logger.info(f"Получено {len(videos)} видео для {username}")
            return videos
            
        except Exception as e:
            logger.error(f"Ошибка получения видео для {username}: {e}")
            return []
    
    async def download_video(self, video_url: str, output_dir: str = None) -> Optional[str]:
        """Скачать видео"""
        if output_dir is None:
            output_dir = os.path.join(DATA_DIR, "downloads", "tiktok")
        
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            async with self.session.get(video_url, timeout=REQUEST_TIMEOUT) as response:
                if response.status == 200:
                    filename = os.path.join(output_dir, f"video_{hash(video_url)}.mp4")
                    
                    with open(filename, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                    
                    logger.info(f"Видео скачано: {filename}")
                    return filename
                else:
                    logger.warning(f"Не удалось скачать видео: {video_url}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка скачивания видео: {e}")
            return None
    
    async def download_user_videos(self, username: str, limit: int = 10, output_dir: str = None) -> List[str]:
        """Скачать видео пользователя"""
        downloaded_files = []
        
        videos = await self.get_user_videos(username, limit=limit)
        
        for video in videos:
            video_url = video.get('video', {}).get('downloadAddr', '')
            if video_url:
                filepath = await self.download_video(video_url, output_dir)
                if filepath:
                    downloaded_files.append(filepath)
        
        logger.info(f"Скачано {len(downloaded_files)} видео для {username}")
        return downloaded_files
    
    async def disconnect(self):
        """Отключиться от TikTok"""
        if self.session:
            await self.session.close()
            logger.info("TikTok сессия закрыта")
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()


# Утилита для авторизации Telegram
async def authorize_telegram():
    """Скрипт для первоначальной авторизации в Telegram"""
    from modules.telegram_client import TelegramClient as TGClient
    
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        print("Настройте TELEGRAM_API_ID и TELEGRAM_API_HASH в .env файле")
        return
    
    client = TGClient()
    await client.connect()
    
    if not await client.client.is_user_authorized():
        print("Требуется авторизация!")
        phone = input("Введите ваш номер телефона: ")
        await client.client.send_code_request(phone)
        
        code = input("Введите код из Telegram: ")
        await client.client.sign_in(phone, code)
        
        print("Авторизация успешна!")
    else:
        print("Уже авторизовано!")
    
    await client.disconnect()


if __name__ == "__main__":
    # Запуск авторизации
    asyncio.run(authorize_telegram())
