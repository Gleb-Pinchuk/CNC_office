import pandas as pd
from typing import List, Dict, Optional
import os
from config import STUDENTS_FILE, DATA_DIR

class StudentDB:
    """Работа с базой данных студентов"""
    
    def __init__(self, students_file: str = None):
        self.students_file = students_file or STUDENTS_FILE
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Создать файл если не существует"""
        if not os.path.exists(self.students_file):
            df = pd.DataFrame(columns=[
                'id', 'username', 'telegram_handle', 'tiktok_handle', 
                'full_name', 'group', 'status', 'last_check', 'violations'
            ])
            df.to_csv(self.students_file, index=False)
    
    def load_students(self) -> pd.DataFrame:
        """Загрузить всех студентов"""
        return pd.read_csv(self.students_file)
    
    def get_student_by_username(self, username: str) -> Optional[Dict]:
        """Найти студента по нику"""
        df = self.load_students()
        student = df[df['username'] == username]
        if len(student) > 0:
            return student.iloc[0].to_dict()
        return None
    
    def get_student_by_telegram(self, telegram_handle: str) -> Optional[Dict]:
        """Найти студента по Telegram handle"""
        df = self.load_students()
        student = df[df['telegram_handle'] == telegram_handle]
        if len(student) > 0:
            return student.iloc[0].to_dict()
        return None
    
    def get_student_by_tiktok(self, tiktok_handle: str) -> Optional[Dict]:
        """Найти студента по TikTok handle"""
        df = self.load_students()
        student = df[df['tiktok_handle'] == tiktok_handle]
        if len(student) > 0:
            return student.iloc[0].to_dict()
        return None
    
    def add_student(self, student_data: Dict) -> bool:
        """Добавить нового студента"""
        try:
            df = self.load_students()
            new_row = pd.DataFrame([student_data])
            df = pd.concat([df, new_row], ignore_index=True)
            df.to_csv(self.students_file, index=False)
            return True
        except Exception as e:
            print(f"Ошибка добавления студента: {e}")
            return False
    
    def update_student(self, username: str, updates: Dict) -> bool:
        """Обновить данные студента"""
        try:
            df = self.load_students()
            mask = df['username'] == username
            if mask.any():
                for key, value in updates.items():
                    df.loc[mask, key] = value
                df.to_csv(self.students_file, index=False)
                return True
            return False
        except Exception as e:
            print(f"Ошибка обновления студента: {e}")
            return False
    
    def record_violation(self, username: str, violation_type: str, details: str = "") -> bool:
        """Записать нарушение"""
        student = self.get_student_by_username(username)
        if not student:
            return False
        
        current_violations = student.get('violations', '')
        timestamp = pd.Timestamp.now().isoformat()
        new_violation = f"[{timestamp}] {violation_type}: {details}"
        
        if current_violations:
            updated_violations = f"{current_violations} | {new_violation}"
        else:
            updated_violations = new_violation
        
        return self.update_student(username, {
            'violations': updated_violations,
            'last_check': timestamp
        })
    
    def get_all_students(self) -> List[Dict]:
        """Получить список всех студентов"""
        df = self.load_students()
        return df.to_dict('records')
    
    def get_students_for_check(self) -> List[Dict]:
        """Получить студентов для проверки (все активные)"""
        df = self.load_students()
        active = df[df['status'] != 'inactive']
        return active.to_dict('records')
