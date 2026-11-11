from __future__ import annotations
import json
import os
from typing import List
from .classroom import Classroom


class Configuration:
    def __init__(self, name: str):
        self.name = name
        self.classrooms: List[Classroom] = []

    @property
    def total_seats(self) -> int:
        return sum(cr.total_seats for cr in self.classrooms)

    def add_classroom(self, classroom: Classroom) -> None:
        self.classrooms.append(classroom)

    def remove_classroom(self, index: int) -> None:
        if 0 <= index < len(self.classrooms):
            self.classrooms.pop(index)

    def copy_classroom(self, index: int) -> None:
        if 0 <= index < len(self.classrooms):
            original = self.classrooms[index]
            existing = {cr.name for cr in self.classrooms}
            base = f"{original.name} (копия)"
            counter = 1
            name = f"{base} {counter}"
            while name in existing:
                counter += 1
                name = f"{base} {counter}"
            data = original.to_dict()
            data['name'] = name
            self.classrooms.append(Classroom.from_dict(data))

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'classrooms': [cr.to_dict() for cr in self.classrooms],
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Configuration':
        cfg = cls(data['name'])
        cfg.classrooms = [Classroom.from_dict(cr) for cr in data.get('classrooms', [])]
        return cfg

    def save(self, directory: str) -> str:
        """Сохраняет конфигурацию в JSON, возвращает путь к файлу"""
        os.makedirs(directory, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in self.name)
        filepath = os.path.join(directory, f"{safe_name}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        return filepath

    @classmethod
    def load(cls, filepath: str) -> 'Configuration':
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def load_all(cls, directory: str) -> List['Configuration']:
        """Загружает все конфигурации из директории"""
        configs = []
        if not os.path.exists(directory):
            return configs
        for filename in os.listdir(directory):
            if filename.endswith('.json'):
                try:
                    cfg = cls.load(os.path.join(directory, filename))
                    configs.append(cfg)
                except Exception:
                    pass
        return configs
