#!/usr/bin/env python3
"""
CNC Office - AI Content Moderator
Главный скрипт для проверки контента студентов
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    DATA_DIR, MODELS_DIR, LOGS_DIR, TRAINING_DATA_DIR,
    CONFIDENCE_THRESHOLD, FORBIDDEN_CATEGORIES
)
from modules.student_db import StudentDB
from modules.content_analyzer import ContentAnalyzer
from modules.trainer import ContentTrainer

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, 'moderator.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('CNC_Moderator')


class ContentModerator:
    """Основной класс системы модерации"""
    
    def __init__(self):
        self.db = StudentDB()
        self.analyzer = ContentAnalyzer()
        logger.info("Система модерации инициализирована")
    
    async def check_student(self, username: str, platform: str = 'telegram') -> dict:
        """Проверить контент конкретного студента"""
        
        student = None
        if platform == 'telegram':
            student = self.db.get_student_by_telegram(username)
        elif platform == 'tiktok':
            student = self.db.get_student_by_tiktok(username)
        else:
            student = self.db.get_student_by_username(username)
        
        if not student:
            logger.warning(f"Студент {username} не найден в базе")
            return {'error': 'Student not found', 'violations': []}
        
        logger.info(f"Проверка студента: {student.get('full_name', 'Unknown')} (@{username})")
        
        # Получение handle для платформы
        handle_key = f'{platform}_handle'
        handle = student.get(handle_key) or student.get('username')
        
        if not handle:
            return {'error': f'No {platform} handle found', 'violations': []}
        
        # Импорт клиента в зависимости от платформы
        if platform == 'telegram':
            from modules.telegram_client import TelegramClient as PlatformClient
        else:
            from modules.tiktok_client import TikTokClient as PlatformClient
        
        violations = []
        downloaded_files = []
        
        try:
            async with PlatformClient() as client:
                # Скачивание медиа
                if platform == 'telegram':
                    downloaded_files = await client.download_media(handle, limit=20)
                else:
                    downloaded_files = await client.download_user_videos(handle, limit=10)
                
                logger.info(f"Скачано {len(downloaded_files)} файлов для анализа")
                
                # Анализ каждого файла
                for file_path in downloaded_files:
                    result = self.analyzer.analyze_file(file_path)
                    
                    if result.get('violations'):
                        for violation in result['violations']:
                            violations.append({
                                'file': file_path,
                                'category': violation['category'],
                                'confidence': violation['confidence'],
                                'timestamp': datetime.now().isoformat()
                            })
                            
                            # Запись нарушения в базу
                            self.db.record_violation(
                                student['username'],
                                violation['category'],
                                f"File: {os.path.basename(file_path)}, Confidence: {violation['confidence']:.2f}"
                            )
                
                # Обновление последней проверки
                self.db.update_student(student['username'], {
                    'last_check': datetime.now().isoformat()
                })
                
        except Exception as e:
            logger.error(f"Ошибка проверки {username}: {e}")
            return {'error': str(e), 'violations': violations}
        
        result = {
            'student': student,
            'platform': platform,
            'files_checked': len(downloaded_files),
            'violations': violations,
            'is_clean': len(violations) == 0,
            'check_time': datetime.now().isoformat()
        }
        
        if violations:
            logger.warning(f"Найдено {len(violations)} нарушений у {username}")
        else:
            logger.info(f"Нарушений не найдено у {username}")
        
        return result
    
    async def check_all_students(self) -> list:
        """Проверить всех активных студентов"""
        students = self.db.get_students_for_check()
        results = []
        
        logger.info(f"Начало массовой проверки {len(students)} студентов")
        
        for student in students:
            username = student.get('username')
            
            # Проверка в Telegram
            if student.get('telegram_handle'):
                result = await self.check_student(username, 'telegram')
                results.append(result)
            
            # Проверка в TikTok
            if student.get('tiktok_handle'):
                result = await self.check_student(username, 'tiktok')
                results.append(result)
        
        total_violations = sum(len(r.get('violations', [])) for r in results)
        logger.info(f"Проверка завершена. Всего нарушений: {total_violations}")
        
        return results
    
    def train_model(self, data_dir: str, epochs: int = 10, batch_size: int = 16):
        """Обучить модель на новых данных"""
        trainer = ContentTrainer()
        
        logger.info(f"Начало обучения модели. Данные: {data_dir}")
        
        trainer.train(
            train_dir=data_dir,
            epochs=epochs,
            batch_size=batch_size
        )
        
        logger.info("Обучение завершено")
    
    def add_labeled_data(self, source_dir: str, category: str, is_forbidden: bool = True):
        """Добавить размеченные данные для обучения"""
        trainer = ContentTrainer()
        trainer.add_training_data(source_dir, category, is_forbidden)


def main():
    parser = argparse.ArgumentParser(description='CNC Office AI Content Moderator')
    
    parser.add_argument('--check-all', action='store_true', 
                       help='Проверить всех студентов')
    parser.add_argument('--username', type=str, 
                       help='Проверить конкретного студента по нику')
    parser.add_argument('--platform', type=str, choices=['telegram', 'tiktok'],
                       default='telegram', help='Платформа для проверки')
    parser.add_argument('--train', action='store_true',
                       help='Обучить модель')
    parser.add_argument('--data', type=str,
                       help='Путь к данным для обучения')
    parser.add_argument('--epochs', type=int, default=10,
                       help='Количество эпох обучения')
    parser.add_argument('--batch-size', type=int, default=16,
                       help='Размер батча для обучения')
    parser.add_argument('--add-labeled', action='store_true',
                       help='Добавить размеченные данные')
    parser.add_argument('--category', type=str, choices=FORBIDDEN_CATEGORIES,
                       help='Категория запрещенного контента')
    parser.add_argument('--path', type=str,
                       help='Путь к размеченным данным')
    parser.add_argument('--allowed', action='store_true',
                       help='Данные безопасного контента')
    
    args = parser.parse_args()
    
    moderator = ContentModerator()
    
    if args.check_all:
        asyncio.run(moderator.check_all_students())
    
    elif args.username:
        result = asyncio.run(moderator.check_student(args.username, args.platform))
        print(f"\nРезультаты проверки:")
        print(f"Студент: {result.get('student', {}).get('full_name', 'N/A')}")
        print(f"Файлов проверено: {result.get('files_checked', 0)}")
        print(f"Нарушений найдено: {len(result.get('violations', []))}")
        if result.get('violations'):
            print("\nНарушения:")
            for v in result['violations']:
                print(f"  - {v['category']} ({v['confidence']:.2f}): {v['file']}")
    
    elif args.train:
        if not args.data:
            print("Ошибка: укажите --data с путем к данным")
            sys.exit(1)
        moderator.train_model(args.data, args.epochs, args.batch_size)
    
    elif args.add_labeled:
        if not args.path or not args.category:
            print("Ошибка: укажите --path и --category")
            sys.exit(1)
        moderator.add_labeled_data(args.path, args.category, not args.allowed)
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
