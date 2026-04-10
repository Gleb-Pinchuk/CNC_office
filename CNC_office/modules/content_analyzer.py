import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
import cv2
import numpy as np
from typing import List, Dict, Tuple
from config import MODEL_PATH, DEVICE, FORBIDDEN_CATEGORIES, CONFIDENCE_THRESHOLD
import os

class ContentAnalyzer:
    """Анализ изображений и видео на запрещенный контент"""
    
    def __init__(self, model_path: str = None):
        self.model_path = model_path or MODEL_PATH
        self.device = DEVICE
        self.categories = FORBIDDEN_CATEGORIES
        
        # Трансформации для изображений
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                               std=[0.229, 0.224, 0.225])
        ])
        
        # Загрузка модели
        self.model = self._load_model()
    
    def _load_model(self) -> nn.Module:
        """Загрузить модель классификации"""
        # Используем предобученную ResNet18 как базовую
        model = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
        
        # Заменяем последний слой для нашей задачи
        num_features = model.fc.in_features
        model.fc = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(num_features, len(self.categories))
        )
        
        # Пытаемся загрузить наши веса
        if os.path.exists(self.model_path):
            try:
                model.load_state_dict(torch.load(self.model_path, map_location=self.device))
                print(f"Модель загружена из {self.model_path}")
            except Exception as e:
                print(f"Не удалось загрузить веса модели: {e}")
                print("Используется предобученная модель")
        else:
            print(f"Модель не найдена в {self.model_path}")
            print("Будет использоваться предобученная модель (требуется дообучение)")
        
        model = model.to(self.device)
        model.eval()
        
        return model
    
    def analyze_image(self, image_path: str) -> Dict:
        """Анализировать изображение"""
        try:
            image = Image.open(image_path).convert('RGB')
            image_tensor = self.transform(image).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(image_tensor)
                probabilities = torch.sigmoid(outputs).cpu().numpy()[0]
            
            results = {}
            violations = []
            
            for i, category in enumerate(self.categories):
                prob = float(probabilities[i])
                results[category] = {
                    'probability': prob,
                    'is_violation': prob > CONFIDENCE_THRESHOLD
                }
                
                if prob > CONFIDENCE_THRESHOLD:
                    violations.append({
                        'category': category,
                        'confidence': prob
                    })
            
            return {
                'file': image_path,
                'violations': violations,
                'all_scores': results,
                'is_safe': len(violations) == 0
            }
            
        except Exception as e:
            print(f"Ошибка анализа изображения {image_path}: {e}")
            return {
                'file': image_path,
                'error': str(e),
                'violations': [],
                'is_safe': True
            }
    
    def analyze_video(self, video_path: str, frames_to_analyze: int = 10) -> Dict:
        """Анализировать видео по ключевым кадрам"""
        try:
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                return {
                    'file': video_path,
                    'error': 'Не удалось открыть видео',
                    'violations': [],
                    'is_safe': True
                }
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps if fps > 0 else 0
            
            # Выбираем кадры для анализа (равномерно по видео)
            frame_indices = np.linspace(0, total_frames - 1, frames_to_analyze, dtype=int)
            
            all_violations = []
            frame_results = []
            
            for frame_idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                
                if ret:
                    # Сохраняем кадр во временный файл
                    temp_path = f"/tmp/frame_{frame_idx}.jpg"
                    cv2.imwrite(temp_path, frame)
                    
                    # Анализируем кадр
                    result = self.analyze_image(temp_path)
                    frame_results.append({
                        'frame': frame_idx,
                        'timestamp': frame_idx / fps if fps > 0 else 0,
                        'result': result
                    })
                    
                    all_violations.extend(result.get('violations', []))
                    
                    # Удаляем временный файл
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            
            cap.release()
            
            # Агрегируем результаты
            violation_summary = {}
            for v in all_violations:
                cat = v['category']
                if cat not in violation_summary:
                    violation_summary[cat] = []
                violation_summary[cat].append(v['confidence'])
            
            # Усредняем置信度 по каждой категории
            final_violations = []
            for cat, confidences in violation_summary.items():
                avg_confidence = sum(confidences) / len(confidences)
                if avg_confidence > CONFIDENCE_THRESHOLD:
                    final_violations.append({
                        'category': cat,
                        'confidence': avg_confidence,
                        'frames_detected': len(confidences)
                    })
            
            return {
                'file': video_path,
                'duration': duration,
                'frames_analyzed': len(frame_results),
                'violations': final_violations,
                'frame_details': frame_results,
                'is_safe': len(final_violations) == 0
            }
            
        except Exception as e:
            print(f"Ошибка анализа видео {video_path}: {e}")
            return {
                'file': video_path,
                'error': str(e),
                'violations': [],
                'is_safe': True
            }
    
    def analyze_file(self, file_path: str) -> Dict:
        """Анализировать файл (изображение или видео)"""
        if not os.path.exists(file_path):
            return {
                'file': file_path,
                'error': 'Файл не найден',
                'violations': [],
                'is_safe': True
            }
        
        ext = os.path.splitext(file_path)[1].lower()
        image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        video_exts = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
        
        if ext in image_exts:
            return self.analyze_image(file_path)
        elif ext in video_exts:
            return self.analyze_video(file_path)
        else:
            return {
                'file': file_path,
                'error': f'Неподдерживаемый формат: {ext}',
                'violations': [],
                'is_safe': True
            }
    
    def batch_analyze(self, file_paths: List[str]) -> List[Dict]:
        """Пакетный анализ файлов"""
        results = []
        for path in file_paths:
            result = self.analyze_file(path)
            results.append(result)
        return results


if __name__ == "__main__":
    # Тестирование анализатора
    analyzer = ContentAnalyzer()
    
    # Пример использования
    test_image = "test.jpg"  # Замените на путь к тестовому изображению
    if os.path.exists(test_image):
        result = analyzer.analyze_image(test_image)
        print(f"Результаты анализа: {result}")
    else:
        print(f"Тестовый файл {test_image} не найден")
        print("Создайте тестовое изображение для проверки")
