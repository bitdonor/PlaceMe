from dataclasses import dataclass, field


@dataclass
class Student:
    name: str            # ФИО
    school: str          # Образовательная организация
    grade: int           # Номер класса (7-11)
    letter: str          # Буква класса (А, Б, В...)
    municipality: str = ""  # Муниципальное образование (из столбца Район)
    city: str = ""          # Город (из столбца Город)
    acquaintance: str = ""  # Критерий знакомства (произвольная метка)

    def class_label(self) -> str:
        """Краткое обозначение класса, например '10А'"""
        return f"{self.grade}{self.letter}"

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if not isinstance(other, Student):
            return False
        return self.name == other.name
