import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

# sqlite secret key 
app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key'  
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///schedule.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# tables

class Resource(db.Model):
    resource_id = db.Column(db.Integer, primary_key=True)
    resource_name = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50), nullable=False)  
    allocations = db.relationship('EventResourceAllocation', backref='resource', lazy=True)

class Event(db.Model):
    event_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.Text, nullable=True)
    allocations = db.relationship('EventResourceAllocation', backref='event', lazy=True, cascade="all, delete-orphan")

class EventResourceAllocation(db.Model):
    allocation_id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.event_id'), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.resource_id'), nullable=False)

# conflict checking 

def check_conflict(resource_id, start_time, end_time, exclude_event_id=None):
    """
    Check if a resource is already booked during the requested time window.
    Overlap logic: (StartA < EndB) and (EndA > StartB)
    """
    # Get all eventid,stime,end times for this resource
    allocations = EventResourceAllocation.query.filter_by(resource_id=resource_id).all()
    
    for allocation in allocations:
        # Skip the same event
        if exclude_event_id and allocation.event_id == exclude_event_id:
            continue
            
        existing_event = Event.query.get(allocation.event_id)
        
       
        if start_time < existing_event.end_time and end_time > existing_event.start_time:
            return True, existing_event.title
            
    return False, None

# Rotutes section(events add,edit,delete and resources add,edit,delete and report generation)

@app.route('/')
def index():
    upcoming_events = Event.query.filter(Event.start_time > datetime.now()).order_by(Event.start_time).limit(5).all()
    total_events = Event.query.count()
    total_resources = Resource.query.count()
    return render_template('index.html', upcoming_events=upcoming_events, total_events=total_events, total_resources=total_resources)

#Resource section;
@app.route('/resources')
def resources():
    all_resources = Resource.query.all()
    return render_template('resources.html', resources=all_resources)

#Event section;

@app.route('/events')
def events():
    all_events = Event.query.order_by(Event.start_time.desc()).all()
    
    all_resources = Resource.query.all()
    return render_template('events.html', events=all_events, resources=all_resources, now=datetime.now())

@app.route('/allocations', methods=['GET', 'POST'])
def allocations():
    if request.method == 'POST':
        event_id = request.form.get('event_id')
        resource_ids = request.form.getlist('resource_ids')
        
        if not resource_ids:
            flash('Please select at least one resource to allocate.', 'warning')
            return redirect(url_for('allocations'))
        
        event = Event.query.get(event_id)
        
        if event.start_time.date() < datetime.now().date():
            flash('Cannot allocate resources to past events.', 'error')
            return redirect(url_for('allocations'))
        
        conflicts = []
        allocations_to_add = []
        
        for resource_id in resource_ids:
            # Check if already allocated
            existing = EventResourceAllocation.query.filter_by(event_id=event_id, resource_id=resource_id).first()
            if existing:
                resource = Resource.query.get(resource_id)
                flash(f'{resource.resource_name} is already allocated to this event.', 'warning')
                continue
            
            # conflict checking
            is_conflict, conflict_event = check_conflict(resource_id, event.start_time, event.end_time, exclude_event_id=event.event_id)
            
            if is_conflict:
                resource = Resource.query.get(resource_id)
                conflicts.append(f"{resource.resource_name} is busy with '{conflict_event}'")
            else:
                allocations_to_add.append(resource_id)
        
        if conflicts:
            flash(f"Conflicts detected: {', '.join(conflicts)}", 'error')
        
        if allocations_to_add:
            for resource_id in allocations_to_add:
                new_alloc = EventResourceAllocation(event_id=event_id, resource_id=resource_id)
                db.session.add(new_alloc)
            db.session.commit()
            flash(f'Successfully allocated {len(allocations_to_add)} resource(s)!', 'success')
        
        return redirect(url_for('allocations'))

    allocations_list = EventResourceAllocation.query.all()
    events = Event.query.order_by(Event.start_time.desc()).all()
    resources = Resource.query.all()
    return render_template('allocations.html', allocations=allocations_list, events=events, resources=resources)

# resource add function-------------------------------------------------------->

@app.route('/resource/add', methods=['POST'])
def add_resource():
    name = request.form.get('resource_name')
    r_type = request.form.get('resource_type')
    
    if name and r_type:
        new_resource = Resource(resource_name=name, resource_type=r_type)
        db.session.add(new_resource)
        db.session.commit()
        flash('Resource added successfully!', 'success')
    else:
        flash('Missing resource details.', 'error')
    return redirect(url_for('resources'))

#edit resource function-------------------------------------------------------->

@app.route('/resource/edit/<int:resource_id>', methods=['GET', 'POST'])
def edit_resource(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    if request.method == 'POST':
        resource.resource_name = request.form.get('resource_name')
        resource.resource_type = request.form.get('resource_type')
        db.session.commit()
        flash('Resource updated successfully!', 'success')
        return redirect(url_for('resources'))
    return render_template('edit_resource.html', resource=resource)

#resource delete function-------------------------------------------------------->

@app.route('/resource/delete/<int:resource_id>', methods=['POST'])
def delete_resource(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    try:
        db.session.delete(resource)
        db.session.commit()
        flash('Resource deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Cannot delete resource. It may be allocated to events.', 'error')
    return redirect(url_for('resources'))

#event section;

# Event add function-------------------------------------------------------->

@app.route('/event/add', methods=['POST'])
def add_event():
    title = request.form.get('title')
    start_str = request.form.get('start_time')
    end_str = request.form.get('end_time')
    description = request.form.get('description')
    resource_ids = request.form.getlist('resources') 

    try:
        start_time = datetime.strptime(start_str, '%Y-%m-%dT%H:%M')
        end_time = datetime.strptime(end_str, '%Y-%m-%dT%H:%M')

        if start_time.date() < datetime.now().date():
            flash('Cannot schedule events for past dates.', 'error')
            return redirect(url_for('events'))

        # 1. Validate Conflicts for ALL selected resources before saving anything
        conflicts = []
        for r_id in resource_ids:
            is_conflict, conflict_event = check_conflict(r_id, start_time, end_time)
            if is_conflict:
                r_name = Resource.query.get(r_id).resource_name
                conflicts.append(f"{r_name} is busy (Event: {conflict_event})")

        if conflicts:
            flash(f"Cannot schedule event. Conflicts detected: {', '.join(conflicts)}", 'error')
            return redirect(url_for('events'))

        # 2. Create Event
        new_event = Event(title=title, start_time=start_time, end_time=end_time, description=description)
        db.session.add(new_event)
        db.session.flush() # Flush to get the new_event.event_id

        # 3. Allocate Resources
        for r_id in resource_ids:
            allocation = EventResourceAllocation(event_id=new_event.event_id, resource_id=r_id)
            db.session.add(allocation)

        db.session.commit()
        flash('Event scheduled and resources allocated!', 'success')

    except ValueError:
        flash('Invalid date format.', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred: {str(e)}', 'error')

    return redirect(url_for('events'))

# Event edit function-------------------------------------------------------->
@app.route('/event/edit/<int:event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    event = Event.query.get_or_404(event_id)
    if request.method == 'POST':
        title = request.form.get('title')
        start_str = request.form.get('start_time')
        end_str = request.form.get('end_time')
        description = request.form.get('description')
        
        try:
            new_start = datetime.strptime(start_str, '%Y-%m-%dT%H:%M')
            new_end = datetime.strptime(end_str, '%Y-%m-%dT%H:%M')

            if new_start.date() < datetime.now().date():
                flash('Cannot move event to a past date.', 'error')
                return render_template('edit_event.html', event=event)

            # Check conflicts for ALL existing allocations with the NEW time
            conflicts = []
            for allocation in event.allocations:
                is_conflict, conflict_event = check_conflict(allocation.resource_id, new_start, new_end, exclude_event_id=event.event_id)
                if is_conflict:
                    conflicts.append(f"{allocation.resource.resource_name} is busy (Event: {conflict_event})")
            
            if conflicts:
                flash(f"Cannot update event time. Conflicts detected: {', '.join(conflicts)}", 'error')
                return render_template('edit_event.html', event=event)

            event.title = title
            event.start_time = new_start
            event.end_time = new_end
            event.description = description
            db.session.commit()
            flash('Event updated successfully!', 'success')
            return redirect(url_for('events'))
            
        except ValueError:
            flash('Invalid date format.', 'error')
            
    return render_template('edit_event.html', event=event)

# Event delete function-------------------------------------------------------->

@app.route('/event/delete/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    flash('Event deleted successfully!', 'success')
    return redirect(url_for('events'))

# Report Section-------------------------------------------------------->

@app.route('/report', methods=['GET', 'POST'])
def report():
    report_data = []
    start_date = None
    end_date = None

    if request.method == 'POST':
        s_str = request.form.get('start_date')
        e_str = request.form.get('end_date')
        
        if s_str and e_str:
            # Save to session
            session['report_start_date'] = s_str
            session['report_end_date'] = e_str
    
    if 'report_start_date' in session and 'report_end_date' in session:
        try:
            start_date = datetime.strptime(session['report_start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(session['report_end_date'], '%Y-%m-%d').replace(hour=23, minute=59)
            
            resources = Resource.query.all()
            
            for r in resources:
                total_seconds = 0
                upcoming_bookings = 0
                
                # Get all allocations for this resource
                allocs = EventResourceAllocation.query.filter_by(resource_id=r.resource_id).all()
                
                for alloc in allocs:
                    evt = Event.query.get(alloc.event_id)
                    
                    # Check if event overlaps with report window
                    # Overlap logic: max(start1, start2) < min(end1, end2)
                    overlap_start = max(evt.start_time, start_date)
                    overlap_end = min(evt.end_time, end_date)
                    
                    if overlap_start < overlap_end:
                        duration = (overlap_end - overlap_start).total_seconds()
                        total_seconds += duration
                    
                    if evt.start_time > datetime.now():
                        upcoming_bookings += 1

                hours = round(total_seconds / 3600, 2)
                report_data.append({
                    'resource': r.resource_name,
                    'type': r.resource_type,
                    'hours': hours,
                    'upcoming': upcoming_bookings
                })
                
        except ValueError:
            # Clear invalid session data
            session.pop('report_start_date', None)
            session.pop('report_end_date', None)

    return render_template('report.html', report_data=report_data, start_date=start_date, end_date=end_date)

@app.route('/clear_report')
def clear_report():
    session.pop('report_start_date', None)
    session.pop('report_end_date', None)
    return redirect(url_for('report'))

@app.route('/allocation/delete/<int:allocation_id>', methods=['POST'])
def delete_allocation(allocation_id):
    allocation = EventResourceAllocation.query.get_or_404(allocation_id)
    db.session.delete(allocation)
    db.session.commit()
    flash('Allocation removed successfully!', 'success')
    return redirect(url_for('allocations'))

# Initialize DB
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, port=5000)