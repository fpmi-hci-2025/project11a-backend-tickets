# main.py
from fastapi import FastAPI, HTTPException, Depends, Header, Query
from pydantic import BaseModel
from typing import Optional, List, Dict
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Float, Text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session
from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta

# CONFIG
DATABASE_URL = "sqlite:///./train_booking.db"
JWT_SECRET = "e3f6eab1d1015fed53eb829"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

# DB setup
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="Train Booking API")

# --- Models ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    city = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)

class Train(Base):
    __tablename__ = "trains"
    id = Column(Integer, primary_key=True, index=True)
    from_city = Column(String, nullable=False)
    to_city = Column(String, nullable=False)
    time = Column(String, nullable=False)   # could be ISO string
    price = Column(Float, nullable=False)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    train_id = Column(Integer, ForeignKey("trains.id"))
    passenger_name = Column(String)
    passenger_age = Column(Integer)
    paid = Column(Boolean, default=False)
    user = relationship("User")
    train = relationship("Train")

class Passenger(Base):
    __tablename__ = "passengers"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=False)

class Promotion(Base):
    __tablename__ = "promotions"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

class SupportTicket(Base):
    __tablename__ = "support_tickets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    message = Column(Text, nullable=False)
    resolved = Column(Boolean, default=False)

# --- Pydantic Schemas ---
class RegisterSchema(BaseModel):
    email: str
    password: str

class LoginSchema(BaseModel):
    email: str
    password: str

class TrainSchema(BaseModel):
    id: Optional[int]
    from_city: str
    to_city: str
    time: str
    price: float

    class Config:
        orm_mode = True

class PassengerSchema(BaseModel):
    name: str
    age: int

class OrderCreateSchema(BaseModel):
    trainId: int
    passenger: PassengerSchema

class ProfileSchema(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None

# --- Utilities ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def get_current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> User:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user

# --- Auth Endpoints ---
@app.post("/auth/register")
def register(data: RegisterSchema, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail={"error": "Такой пользователь уже существует"})
    user = User(email=data.email, hashed_password=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "Регистрация прошла успешно", "user_id": user.id}

@app.post("/auth/login")
def login(data: LoginSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail={"error": "Пользователь не найден"})
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail={"error": "Неправильный логин или пароль"})
    token = create_access_token({"user_id": user.id})
    return {"token": token, "user_id": user.id}

# --- Trains ---
@app.get("/api/trains/search")
def search_trains(from_: Optional[str] = Query(None, alias="from"), to: Optional[str] = Query(None, alias="to"), db: Session = Depends(get_db)):
    q = db.query(Train)
    if from_:
        q = q.filter(Train.from_city.ilike(f"%{from_}%"))
    if to:
        q = q.filter(Train.to_city.ilike(f"%{to}%"))
    results = q.all()
    return [{"id": t.id, "from": t.from_city, "to": t.to_city, "time": t.time, "price": t.price} for t in results]

@app.get("/api/trains/{train_id}")
def get_train(train_id: int, db: Session = Depends(get_db)):
    t = db.query(Train).filter(Train.id == train_id).first()
    if not t:
        raise HTTPException(status_code=404, detail={"error": "Train not found"})
    return {"id": t.id, "from": t.from_city, "to": t.to_city, "time": t.time, "price": t.price}

# --- Orders ---
@app.post("/api/orders")
def create_order(payload: OrderCreateSchema, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not payload.trainId or not payload.passenger:
        raise HTTPException(status_code=400, detail={"error": "trainId and passenger are required"})
    train = db.query(Train).filter(Train.id == payload.trainId).first()
    if not train:
        raise HTTPException(status_code=404, detail={"error": "Train not found"})
    order = Order(user_id=user.id, train_id=train.id, passenger_name=payload.passenger.name, passenger_age=payload.passenger.age)
    db.add(order)
    db.commit()
    db.refresh(order)
    return {"message": "Ticket booked", "order": {"id": order.id, "trainId": order.train_id, "paid": order.paid}}

@app.get("/api/orders")
def get_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    orders = db.query(Order).filter(Order.user_id == user.id).all()
    return [{"id": o.id, "trainId": o.train_id, "paid": o.paid, "passenger_name": o.passenger_name, "passenger_age": o.passenger_age} for o in orders]

@app.post("/api/orders/{order_id}/pay")
def pay_order(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail={"error": "Order not found"})
    if order.paid:
        return {"message": "Order already paid"}
    order.paid = True
    db.commit()
    return {"message": "Payment successful", "order_id": order.id}

# --- Profile ---
@app.get("/api/profile")
def get_profile(user: User = Depends(get_current_user)):
    return {"name": user.name, "phone": user.phone, "city": user.city, "email": user.email}

@app.put("/api/profile")
def update_profile(profile: ProfileSchema, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if profile.name is None and profile.phone is None and profile.city is None:
        raise HTTPException(status_code=400, detail={"error": "Invalid input data"})
    user.name = profile.name or user.name
    user.phone = profile.phone or user.phone
    user.city = profile.city or user.city
    db.commit()
    return {"message": "Profile updated"}

# --- Promotions ---
@app.get("/api/promotions")
def list_promotions(db: Session = Depends(get_db)):
    promos = db.query(Promotion).all()
    return [{"id": p.id, "title": p.title, "description": p.description} for p in promos]

# --- Passengers ---
@app.get("/api/passengers")
def list_passengers(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ps = db.query(Passenger).filter((Passenger.user_id == user.id) | (Passenger.user_id == None)).all()
    return [{"id": p.id, "name": p.name, "age": p.age, "user_id": p.user_id} for p in ps]

@app.post("/api/passengers")
def add_passenger(p: PassengerSchema, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not p.name or p.age is None:
        raise HTTPException(status_code=400, detail={"error": "Invalid passenger data"})
    passenger = Passenger(user_id=user.id, name=p.name, age=p.age)
    db.add(passenger)
    db.commit()
    db.refresh(passenger)
    return {"message": "Passenger added", "passenger_id": passenger.id}

# --- Support ---
@app.get("/api/support/tickets")
def list_tickets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tickets = db.query(SupportTicket).filter(SupportTicket.user_id == user.id).all()
    return [{"id": t.id, "message": t.message, "resolved": t.resolved} for t in tickets]

@app.post("/api/support/tickets")
def create_ticket(payload: Dict[str, str], user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    message = payload.get("message")
    if not message:
        raise HTTPException(status_code=400, detail={"error": "Message is required"})
    ticket = SupportTicket(user_id=user.id, message=message)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return {"message": "Ticket created", "ticket_id": ticket.id}

# --- Admin endpoints ---
@app.get("/api/admin/flights")
def admin_list_flights(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    flights = db.query(Train).all()
    return [{"id": f.id, "from": f.from_city, "to": f.to_city, "time": f.time, "price": f.price} for f in flights]

@app.post("/api/admin/flights")
def admin_add_flight(payload: TrainSchema, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not payload.from_city or not payload.to_city or not payload.time or payload.price is None:
        raise HTTPException(status_code=400, detail={"error": "Invalid train data"})
    t = Train(from_city=payload.from_city, to_city=payload.to_city, time=payload.time, price=payload.price)
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"message": "Train added", "train_id": t.id}

@app.put("/api/admin/flights/{flight_id}")
def admin_update_flight(flight_id: int, payload: Dict[str, object], admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    t = db.query(Train).filter(Train.id == flight_id).first()
    if not t:
        raise HTTPException(status_code=404, detail={"error": "Train not found"})
    if "price" in payload:
        try:
            t.price = float(payload["price"])
        except Exception:
            raise HTTPException(status_code=400, detail={"error": "Invalid price"})
    if "time" in payload:
        t.time = str(payload["time"])
    if "from_city" in payload:
        t.from_city = str(payload["from_city"])
    if "to_city" in payload:
        t.to_city = str(payload["to_city"])
    db.commit()
    return {"message": "Train updated", "train_id": t.id}

@app.delete("/api/admin/flights/{flight_id}")
def admin_delete_flight(flight_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    t = db.query(Train).filter(Train.id == flight_id).first()
    if not t:
        raise HTTPException(status_code=404, detail={"error": "Train not found"})
    db.delete(t)
    db.commit()
    return {"message": "Train deleted", "train_id": flight_id}

# Optional: admin list users / tickets
@app.get("/api/admin/users")
def admin_list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [{"id": u.id, "email": u.email, "is_admin": u.is_admin, "name": u.name} for u in users]

@app.get("/")
def root():
    return {"message": "Train Booking API. See docs at /docs"}

__all__ = ["Base", "engine", "SessionLocal", "User", "Train", "create_access_token"]
if __name__ == "__main__":
    import uvicorn
    # Экспортируем объекты, чтобы pytest и другие модули могли импортировать ихнапрямую


    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
