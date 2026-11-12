from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class User:
    name: str
    email: str
    age: int
    is_active: bool = True

if __name__ == '__main__':
    u1 = User(name="Mohak", email="test@gmail.com", age=20, is_active=True)
    print(u1.__slots__)