import sys
import os


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db, Resource, Event, Allocation
from datetime import datetime, timedelta

def init_db():
    with app.app_context():
        # Create tables
        db.create_all()
        print("Database tables created.")

        # Check if data already exists
        if Resource.query.first():
            print("Data already exists. Skipping seed.")
            return

        # Create Resources
        r1 = Resource(name="Conference Room A", type="Room")
        r2 = Resource(name="Projector 1", type="Equipment")
        r3 = Resource(name="John Doe", type="Instructor")
        r4 = Resource(name="Lab 101", type="Room")

        db.session.add_all([r1, r2, r3, r4])
        db.session.commit()
        print("Resources added.")

        # Create Events
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        
        e1 = Event(
            title="Python Workshop",
            start_time=now + timedelta(days=1, hours=9),
            end_time=now + timedelta(days=1, hours=12),
            description="Intro to Python programming"
        )
        
        e2 = Event(
            title="Team Meeting",
            start_time=now + timedelta(days=1, hours=14),
            end_time=now + timedelta(days=1, hours=15),
            description="Weekly sync"
        )

        db.session.add_all([e1, e2])
        db.session.commit()
        print("Events added.")

        # Create Allocations
        # Allocate Room A and John Doe to Python Workshop
        a1 = Allocation(event_id=e1.id, resource_id=r1.id)
        a2 = Allocation(event_id=e1.id, resource_id=r3.id)
        
        # Allocate Room A to Team Meeting (This would be a conflict if times overlapped, but they don't)
        a3 = Allocation(event_id=e2.id, resource_id=r1.id)

        db.session.add_all([a1, a2, a3])
        db.session.commit()
        print("Allocations added.")
        print("Database initialized with sample data!")

if __name__ == "__main__":
    init_db()
