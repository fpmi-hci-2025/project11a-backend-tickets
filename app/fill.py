from sqlalchemy.orm import Session
from main import SessionLocal, User, Train, Promotion, Passenger, SupportTicket, hash_password

def seed():
    db: Session = SessionLocal()
    try:
        # Admin user
        admin_email = "admin@example.com"
        admin = db.query(User).filter(User.email == admin_email).first()
        if not admin:
            admin_user = User(
                email=admin_email,
                hashed_password=hash_password("adminpass"),
                name="Admin",
                is_admin=True
            )
            db.add(admin_user)
            print("Created admin user:", admin_email)

        # Test regular users
        users_data = [
            ("alice@example.com", "alicepass", "Alice"),
            ("bob@example.com", "bobpass", "Bob"),
        ]
        for email, pw, name in users_data:
            if not db.query(User).filter(User.email == email).first():
                u = User(email=email, hashed_password=hash_password(pw), name=name)
                db.add(u)
                print("Created user:", email)

        # Trains
        trains = [
            ("Moscow", "Saint Petersburg", "2025-11-01T08:00:00", 35.50),
            ("Moscow", "Kazan", "2025-11-02T09:30:00", 50.00),
            ("Kazan", "Samara", "2025-11-03T12:00:00", 20.00),
        ]
        for f, t, time, price in trains:
            if not db.query(Train).filter(Train.from_city==f, Train.to_city==t, Train.time==time).first():
                tr = Train(from_city=f, to_city=t, time=time, price=price)
                db.add(tr)
                print("Added train:", f, "->", t, time)

        # Promotions
        promos = [
            ("Early bird", "10% off for bookings 30+ days in advance"),
            ("Weekend special", "Special fares for weekend trips"),
        ]
        for title, desc in promos:
            if not db.query(Promotion).filter(Promotion.title==title).first():
                db.add(Promotion(title=title, description=desc))
                print("Added promotion:", title)

        db.commit()

        # Add some passengers and tickets for one user
        alice = db.query(User).filter(User.email=="alice@example.com").first()
        if alice:
            if not db.query(Passenger).filter(Passenger.user_id==alice.id, Passenger.name=="Alice Jr.").first():
                p = Passenger(user_id=alice.id, name="Alice Jr.", age=5)
                db.add(p)
                print("Added passenger for Alice")

        # Example support ticket
        if alice and not db.query(SupportTicket).filter(SupportTicket.user_id==alice.id).first():
            t = SupportTicket(user_id=alice.id, message="Test ticket: payment issue")
            db.add(t)
            print("Created support ticket for Alice")

        db.commit()
        print("Seeding completed.")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
