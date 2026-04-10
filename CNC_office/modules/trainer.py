import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms
from PIL import Image
import os
from typing import Tuple, List
from tqdm import tqdm
from config import (
    MODEL_PATH, DEVICE, FORBIDDEN_CATEGORIES, 
    TRAINING_DATA_DIR, MODELS_DIR
)

class ContentDataset(Dataset):
    """Датасет для обучения модели"""
    
    def __init__(self, root_dir: str, transform=None):
        self.root_dir = root_dir
        self.transform = transform or transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                               std=[0.229, 0.224, 0.225])
        ])
        
        self.categories = FORBIDDEN_CATEGORIES
        self.samples = []
        self.labels = []
        
        # Загрузка данных из структуры папок
        # root_dir/
        #   allowed/      - безопасный контент
        #   forbidden/
        #     violence/   - насилие
        #     adult/      - 18+
        #     drugs/      - наркотики
        #     ...
        
        self._load_samples()
    
    def _load_samples(self):
        """Загрузить все изображения из папок"""
        allowed_dir = os.path.join(self.root_dir, 'allowed')
        forbidden_dir = os.path.join(self.root_dir, 'forbidden')
        
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
        
        # Загрузка безопасных изображений (все категории = 0)
        if os.path.exists(allowed_dir):
            for filename in os.listdir(allowed_dir):
                ext = os.path.splitext(filename)[1].lower()
                if ext in image_extensions:
                    self.samples.append(os.path.join(allowed_dir, filename))
                    self.labels.append([0] * len(self.categories))
        
        # Загрузка запрещенных изображений по категориям
        if os.path.exists(forbidden_dir):
            for category in self.categories:
                category_dir = os.path.join(forbidden_dir, category)
                if os.path.exists(category_dir):
                    for filename in os.listdir(category_dir):
                        ext = os.path.splitext(filename)[1].lower()
                        if ext in image_extensions:
                            self.samples.append(os.path.join(category_dir, filename))
                            
                            # Создаем one-hot вектор для этой категории
                            label = [0] * len(self.categories)
                            category_idx = self.categories.index(category)
                            label[category_idx] = 1
                            self.labels.append(label)
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        img_path = self.samples[idx]
        label = torch.tensor(self.labels[idx], dtype=torch.float32)
        
        try:
            image = Image.open(img_path).convert('RGB')
            if self.transform:
                image = self.transform(image)
            return image, label
        except Exception as e:
            print(f"Ошибка загрузки изображения {img_path}: {e}")
            # Возвращаем случайное изображение если есть ошибка
            return self.__getitem__((idx + 1) % len(self))


class ContentTrainer:
    """Обучение модели классификации контента"""
    
    def __init__(self, model_path: str = None):
        self.model_path = model_path or MODEL_PATH
        self.device = DEVICE
        self.categories = FORBIDDEN_CATEGORIES
        
        # Инициализация модели
        self.model = self._create_model()
        
        # Критерий потерь и оптимизатор
        self.criterion = nn.BCEWithLogitsLoss()
        self.optimizer = None
    
    def _create_model(self) -> nn.Module:
        """Создать модель"""
        model = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
        
        # Замораживаем ранние слои
        for param in list(model.parameters())[:-20]:
            param.requires_grad = False
        
        # Заменяем последний слой
        num_features = model.fc.in_features
        model.fc = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(num_features, len(self.categories))
        )
        
        # Пытаемся загрузить существующие веса
        if os.path.exists(self.model_path):
            try:
                model.load_state_dict(torch.load(self.model_path, map_location=self.device))
                print(f"Загружены веса из {self.model_path}")
            except Exception as e:
                print(f"Не удалось загрузить веса: {e}")
        
        return model.to(self.device)
    
    def train(
        self, 
        train_dir: str, 
        epochs: int = 10, 
        batch_size: int = 16, 
        learning_rate: float = 0.001,
        val_dir: str = None
    ):
        """Обучение модели"""
        
        # Создание датасетов
        train_dataset = ContentDataset(train_dir)
        print(f"Загружено {len(train_dataset)} изображений для обучения")
        
        if len(train_dataset) == 0:
            print("Нет данных для обучения! Проверьте структуру папок.")
            return
        
        train_loader = DataLoader(
            train_dataset, 
            batch_size=batch_size, 
            shuffle=True,
            num_workers=0
        )
        
        val_loader = None
        if val_dir and os.path.exists(val_dir):
            val_dataset = ContentDataset(val_dir)
            if len(val_dataset) > 0:
                val_loader = DataLoader(
                    val_dataset, 
                    batch_size=batch_size, 
                    shuffle=False
                )
                print(f"Загружено {len(val_dataset)} изображений для валидации")
        
        # Оптимизатор
        self.optimizer = torch.optim.Adam(
            filter(lambda p: p.requires_grad, self.model.parameters()),
            lr=learning_rate
        )
        
        # Scheduler для уменьшения learning rate
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode='min', factor=0.5, patience=2
        )
        
        best_loss = float('inf')
        
        for epoch in range(epochs):
            print(f"\nЭпоха {epoch + 1}/{epochs}")
            
            # Обучение
            self.model.train()
            train_loss = 0.0
            
            for images, labels in tqdm(train_loader, desc="Training"):
                images = images.to(self.device)
                labels = labels.to(self.device)
                
                self.optimizer.zero_grad()
                
                outputs = self.model(images)
                loss = self.criterion(outputs, labels)
                
                loss.backward()
                self.optimizer.step()
                
                train_loss += loss.item()
            
            avg_train_loss = train_loss / len(train_loader)
            print(f"Train Loss: {avg_train_loss:.4f}")
            
            # Валидация
            if val_loader:
                self.model.eval()
                val_loss = 0.0
                
                with torch.no_grad():
                    for images, labels in tqdm(val_loader, desc="Validation"):
                        images = images.to(self.device)
                        labels = labels.to(self.device)
                        
                        outputs = self.model(images)
                        loss = self.criterion(outputs, labels)
                        val_loss += loss.item()
                
                avg_val_loss = val_loss / len(val_loader)
                print(f"Val Loss: {avg_val_loss:.4f}")
                
                scheduler.step(avg_val_loss)
                
                # Сохранение лучшей модели
                if avg_val_loss < best_loss:
                    best_loss = avg_val_loss
                    self.save_model()
                    print(f"Сохранена лучшая модель с loss={best_loss:.4f}")
            else:
                # Сохраняем каждую эпоху если нет валидации
                self.save_model()
        
        print("\nОбучение завершено!")
        print(f"Модель сохранена в {self.model_path}")
    
    def save_model(self):
        """Сохранить модель"""
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        torch.save(self.model.state_dict(), self.model_path)
        print(f"Модель сохранена в {self.model_path}")
    
    def add_training_data(self, source_dir: str, category: str, is_forbidden: bool = True):
        """Добавить новые данные для обучения"""
        if is_forbidden:
            dest_dir = os.path.join(TRAINING_DATA_DIR, 'forbidden', category)
        else:
            dest_dir = os.path.join(TRAINING_DATA_DIR, 'allowed')
        
        os.makedirs(dest_dir, exist_ok=True)
        
        # Копирование файлов
        import shutil
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
        
        copied = 0
        for filename in os.listdir(source_dir):
            ext = os.path.splitext(filename)[1].lower()
            if ext in image_extensions:
                src = os.path.join(source_dir, filename)
                dst = os.path.join(dest_dir, filename)
                shutil.copy2(src, dst)
                copied += 1
        
        print(f"Скопировано {copied} изображений в {dest_dir}")


if __name__ == "__main__":
    # Пример использования
    trainer = ContentTrainer()
    
    # Обучение
    # trainer.train(
    #     train_dir=TRAINING_DATA_DIR,
    #     epochs=10,
    #     batch_size=16
    # )
    
    print("Для обучения запустите:")
    print("python main.py --train --data path/to/training_data/")
