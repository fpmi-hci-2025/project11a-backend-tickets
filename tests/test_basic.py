import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) 
from app.main import app, Base, engine, SessionLocal, User, Train, create_access_token
from fastapi.testclient import TestClient
client = TestClient(app)

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Создает чистую тестовую БД перед всеми тестами"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Добавим тестовые данные
        u = User(email="test@example.com", hashed_password="$2b$12$fakehash")
        t = Train(from_city="Moscow", to_city="Kazan", time="2025-11-01T08:00:00", price=100.0)
        db.add_all([u, t])
        db.commit()
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=engine)


def test_db_connection():
    """Проверяем, что подключение к БД работает"""
    db = SessionLocal()
    users = db.query(User).all()
    trains = db.query(Train).all()
    db.close()
    assert len(users) >= 1
    assert len(trains) >= 1


def test_register_and_login():
    """Регистрация и логин нового пользователя"""
    reg = client.post("/auth/register", json={"email": "user@example.com", "password": "123456"})
    assert reg.status_code in (200, 400)
    login = client.post("/auth/login", json={"email": "user@example.com", "password": "123456"})
    assert login.status_code == 200
    data = login.json()
    assert "token" in data


def test_trains_search():
    """Поиск поездов"""
    response = client.get("/api/trains/search?from=Moscow")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["from"] == "Moscow"


def test_profile_update():
    """Обновление профиля"""
    # создаем токен вручную, так как пароль фиктивный
    token = create_access_token({"user_id": 1})
    headers = {"Authorization": f"Bearer {token}"}
    response = client.put("/api/profile", json={"name": "Tester", "city": "Moscow"}, headers=headers)
    assert response.status_code in (200, 400)
