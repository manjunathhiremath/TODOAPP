import streamlit as st
import sqlite3
import os
import shutil
import json
from datetime import datetime
from groq import Groq
import base64
from io import BytesIO
from PIL import Image
from pathlib import Path

# Setup database
# Setup database
def init_db():
    conn = sqlite3.connect('todo.db')
    c = conn.cursor()
    
    # Check if the table exists
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
    table_exists = c.fetchone() is not None
    
    if not table_exists:
        # Create the table with all columns
        c.execute('''
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY,
            title TEXT,
            description TEXT,
            created_at TIMESTAMP,
            deadline TIMESTAMP,
            completed_at TIMESTAMP,
            status TEXT,
            verification_result TEXT
        )
        ''')
    else:
        # Check if deadline column exists
        c.execute("PRAGMA table_info(tasks)")
        columns = [column[1] for column in c.fetchall()]
        
        # Add the deadline column if it doesn't exist
        if 'deadline' not in columns:
            c.execute("ALTER TABLE tasks ADD COLUMN deadline TIMESTAMP")
    
    conn.commit()
    return conn

# Groq Llama API setup
def verify_task_completion(image_bytes, task_description):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    # Convert image bytes to base64 for API
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    # Create a message with the Groq Llama Vision API
    # Note: Llama 3.2 doesn't support system messages with image inputs
    chat_completion = client.chat.completions.create(
        model="llama-3.2-11b-vision-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text", 
                        "text": f"You are a task verification assistant. Your job is to verify if the uploaded image shows evidence that the described task has been completed. Be strict but fair in your assessment.\n\nDoes this image show evidence that the following task has been completed? Task: {task_description}\n\nPlease respond with either 'VERIFIED' if the image clearly shows the task has been completed, or 'NOT VERIFIED' if the evidence is insufficient or unclear. Then briefly explain your reasoning."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                        },
                    },
                ],
            }
        ]
    )
    
    return chat_completion.choices[0].message.content

# Setup PWA files
def setup_pwa():
    # Create directories for static files
    static_dir = Path("static")
    icons_dir = static_dir / "icons"
    
    # Create directories if they don't exist
    static_dir.mkdir(exist_ok=True)
    icons_dir.mkdir(exist_ok=True)
    
    # Copy manifest.json to static directory
    manifest_path = Path("manifest.json")
    if manifest_path.exists():
        shutil.copy(manifest_path, static_dir / "manifest.json")
    else:
        # Create manifest.json if it doesn't exist
        manifest = {
            "name": "Photo-Verified Todo App",
            "short_name": "Todo Verify",
            "description": "A Todo app that verifies task completion with photos",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#ffffff",
            "theme_color": "#4CAF50",
            "icons": [
                {
                    "src": "icons/icon-192x192.png",
                    "sizes": "192x192",
                    "type": "image/png"
                },
                {
                    "src": "icons/icon-512x512.png",
                    "sizes": "512x512",
                    "type": "image/png"
                }
            ]
        }
        with open(static_dir / "manifest.json", "w") as f:
            json.dump(manifest, f)
    
    # Copy service-worker.js to static directory
    sw_path = Path("service-worker.js")
    if sw_path.exists():
        shutil.copy(sw_path, static_dir / "service-worker.js")
    
    # Generate a sample icon if none exists
    icon_file = icons_dir / "icon-192x192.png"
    if not icon_file.exists():
        # Create a simple colored square as icon (in a real app, use proper icons)
        img = Image.new('RGB', (192, 192), color=(76, 175, 80))
        img.save(icon_file)
        
        # Create a larger icon as well
        img_large = Image.new('RGB', (512, 512), color=(76, 175, 80))
        img_large.save(icons_dir / "icon-512x512.png")

def main():
    # Setup PWA files
    setup_pwa()
    
    st.set_page_config(
        page_title="Photo-Verified Todo App",
        page_icon="✅",
        layout="wide"
    )
    
    # Add custom HTML for PWA
    with open("pwa_template.html", "r") as f:
        pwa_html = f.read()
        st.markdown(
            f"""
            <script>
                // This is injected into the Streamlit app to enable PWA features
                document.addEventListener('DOMContentLoaded', (event) => {{
                    const linkElement = document.createElement('link');
                    linkElement.rel = 'manifest';
                    linkElement.href = '/static/manifest.json';
                    document.head.appendChild(linkElement);
                    
                    // Register service worker
                    if ('serviceWorker' in navigator) {{
                        navigator.serviceWorker.register('/static/service-worker.js')
                            .then(reg => console.log('Service Worker registered', reg))
                            .catch(err => console.error('Service Worker registration failed', err));
                    }}
                }});
            </script>
            """,
            unsafe_allow_html=True
        )
    
    # Check for API key
    if not os.environ.get("GROQ_API_KEY"):
        st.error("Please set your GROQ_API_KEY environment variable to use this app.")
        st.stop()
    
    # Initialize database
    conn = init_db()
    
    st.title("📸 Photo-Verified Todo App")
    st.write("Complete tasks and provide photo evidence for verification!")
    
    # Navigation
    page = st.sidebar.radio("Navigation", ["Add Task", "View Tasks", "Complete Task"])
    
    # Initialize session state
    if "complete_task_id" not in st.session_state:
        st.session_state["complete_task_id"] = None
    
    if "page" in st.session_state:
        page = st.session_state["page"]
        st.session_state["page"] = None
    
    if page == "Add Task":
        st.header("Add a New Task")
        
        with st.form("add_task_form"):
            title = st.text_input("Task Title")
            description = st.text_area("Task Description (Be specific for better verification)")
            
            # Add deadline field
            st.write("Set a deadline for this task:")
            deadline_date = st.date_input("Deadline Date")
            deadline_time = st.time_input("Deadline Time")
            deadline = datetime.combine(deadline_date, deadline_time)
            
            # Calculate time remaining in hours (for display)
            time_remaining = (deadline - datetime.now()).total_seconds() / 3600
            
            if time_remaining > 0:
                st.info(f"Time to complete: {time_remaining:.1f} hours")
            else:
                st.error("Selected deadline is in the past!")
                
            submitted = st.form_submit_button("Add Task")
            if submitted and title:
                if time_remaining <= 0:
                    st.error("Cannot create task with a deadline in the past. Please choose a future deadline.")
                else:
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO tasks (title, description, created_at, deadline, status) VALUES (?, ?, ?, ?, ?)",
                        (title, description, datetime.now(), deadline, "pending")
                    )
                    conn.commit()
                    st.success(f"Task '{title}' added successfully!")
    
    elif page == "View Tasks":
        st.header("Your Tasks")
        
        # Create tabs for different task statuses
        tab1, tab2 = st.tabs(["Pending Tasks", "Completed Tasks"])
        
        with tab1:
            c = conn.cursor()
            c.execute("SELECT id, title, description, created_at, deadline FROM tasks WHERE status='pending' ORDER BY deadline ASC")
            pending_tasks = c.fetchall()
            
            if not pending_tasks:
                st.info("No pending tasks. Add some tasks to get started!")
            
            now = datetime.now()
            
            for task in pending_tasks:
                task_id, task_title, task_desc, created, deadline = task
                
                # Calculate time remaining
                now = datetime.now()
                
                # Handle NULL or missing deadline values
                if deadline is None:
                    # For tasks without deadlines, set a default
                    expander_label = f"📌 {task_title} (No deadline)"
                    time_str = "No deadline set"
                    time_color = "gray"
                else:
                    try:
                        if isinstance(deadline, str):
                            deadline_dt = datetime.fromisoformat(deadline)
                        else:
                            deadline_dt = deadline
                            
                        remaining = deadline_dt - now
                        hours_remaining = remaining.total_seconds() / 3600
                        
                        # Style based on time remaining
                        if hours_remaining < 0:
                            expander_label = f"🚨 OVERDUE: {task_title}"
                            time_str = f"**OVERDUE by {abs(hours_remaining):.1f} hours!**"
                            time_color = "red"
                        elif hours_remaining < 1:
                            expander_label = f"⚠️ URGENT: {task_title}"
                            time_str = f"**{hours_remaining*60:.0f} minutes remaining!**"
                            time_color = "orange"
                        elif hours_remaining < 24:
                            expander_label = f"⏰ {task_title}"
                            time_str = f"**{hours_remaining:.1f} hours remaining**"
                            time_color = "blue"
                        else:
                            expander_label = f"📌 {task_title}"
                            days = hours_remaining / 24
                            time_str = f"{days:.1f} days remaining"
                            time_color = "green"
                    except (ValueError, TypeError):
                        # Handle invalid datetime format
                        expander_label = f"📌 {task_title}"
                        time_str = "Invalid deadline format"
                        time_color = "gray"
                        hours_remaining = 999  # Just a large value for logic below
            
            with st.expander(expander_label):
                st.write(f"**Description:** {task_desc}")
                st.write(f"**Created:** {created}")
                st.write(f"**Deadline:** {deadline}")
                st.markdown(f"<span style='color:{time_color};'>{time_str}</span>", unsafe_allow_html=True)
                
                # Add hidden element for notifications to find
                if hours_remaining < 24 and hours_remaining > 0:
                    task_info = {
                        "id": task_id,
                        "title": task_title,
                        "deadline": str(deadline)
                    }
                    st.markdown(
                        f'<div id="urgent-task-{task_id}" data-task-info=\'{json.dumps(task_info)}\'></div>',
                        unsafe_allow_html=True
                    )
                
                st.write("Status: Pending verification")
                
                # Add quick complete button
                if st.button(f"Complete task now", key=f"quick_complete_{task_id}"):
                    st.session_state["complete_task_id"] = task_id
                    st.session_state["page"] = "Complete Task"
                    st.experimental_rerun()
        
        with tab2:
            c = conn.cursor()
            c.execute("SELECT id, title, description, deadline, completed_at, verification_result FROM tasks WHERE status='completed' ORDER BY completed_at DESC")
            completed_tasks = c.fetchall()
            
            if not completed_tasks:
                st.info("No completed tasks yet. Complete some tasks to see them here!")
            
            for task in completed_tasks:
                task_id, title, desc, deadline, completed, verification = task
                
                # Handle NULL or invalid deadline format
                if deadline is None:
                    deadline_met = True  # No deadline means always on time
                    deadline_str = "No deadline set"
                    deadline_label = "✅ "
                else:
                    try:
                        if isinstance(deadline, str):
                            deadline_dt = datetime.fromisoformat(deadline)
                        else:
                            deadline_dt = deadline
                            
                        if isinstance(completed, str):
                            completed_dt = datetime.fromisoformat(completed)
                        else:
                            completed_dt = completed
                            
                        deadline_met = completed_dt <= deadline_dt
                        deadline_str = str(deadline)
                        deadline_label = "✅ ON TIME: " if deadline_met else "⚠️ LATE: "
                    except (ValueError, TypeError):
                        deadline_met = True  # Invalid format means we can't tell
                        deadline_str = "Invalid deadline format"
                        deadline_label = "✅ "
                
                with st.expander(f"{deadline_label}{title}"):
                    st.write(f"**Description:** {desc}")
                    st.write(f"**Deadline:** {deadline_str}")
                    st.write(f"**Completed:** {completed}")
                    
                    # Calculate time diff if possible
                    if deadline is not None and completed is not None:
                        try:
                            if isinstance(deadline, str):
                                deadline_dt = datetime.fromisoformat(deadline)
                            else:
                                deadline_dt = deadline
                                
                            if isinstance(completed, str):
                                completed_dt = datetime.fromisoformat(completed)
                            else:
                                completed_dt = completed
                                
                            time_diff = (completed_dt - deadline_dt).total_seconds() / 3600
                            if time_diff <= 0:
                                st.write(f"**Completed {abs(time_diff):.1f} hours before deadline**")
                            else:
                                st.write(f"**Completed {time_diff:.1f} hours after deadline**")
                        except (ValueError, TypeError):
                            st.write("**Time difference calculation unavailable**")
                    
                    st.write(f"**Verification:** {verification}")
    
    elif page == "Complete Task":
        st.header("Complete a Task")
        
        # If we have a selected task from a button click
        preselected_task_id = st.session_state.get("complete_task_id")
        
        c = conn.cursor()
        c.execute("SELECT id, title FROM tasks WHERE status='pending'")
        pending_tasks = c.fetchall()
        
        if not pending_tasks:
            st.info("No pending tasks. Add some tasks first!")
            st.stop()
        
        task_options = {task[1]: task[0] for task in pending_tasks}
        
        # If we have a preselected task, get its title
        preselected_title = None
        if preselected_task_id:
            for title, task_id in task_options.items():
                if task_id == preselected_task_id:
                    preselected_title = title
                    break
        
        selected_task_title = st.selectbox(
            "Select a task to complete", 
            list(task_options.keys()),
            index=list(task_options.keys()).index(preselected_title) if preselected_title else 0
        )
        selected_task_id = task_options[selected_task_title]
        
        # Clear the session state
        st.session_state["complete_task_id"] = None
        
        # Get task details
        c.execute("SELECT description, deadline FROM tasks WHERE id=?", (selected_task_id,))
        task_data = c.fetchone()
        task_description = task_data[0]
        
        # Handle case where deadline might be NULL for existing tasks
        task_deadline = task_data[1] if task_data[1] else datetime.now().isoformat()
        
        # Calculate time remaining
        now = datetime.now()
        try:
            deadline_dt = datetime.fromisoformat(task_deadline)
            time_remaining = (deadline_dt - now).total_seconds() / 3600
        except (ValueError, TypeError):
            # Handle case where deadline might be in wrong format
            time_remaining = 0
        
        st.write(f"**Task Description:** {task_description}")
        
        # Show deadline information
        if time_remaining > 0:
            st.info(f"⏰ Time remaining: {time_remaining:.1f} hours (Deadline: {task_deadline})")
        else:
            st.error(f"🚨 Task is OVERDUE by {abs(time_remaining):.1f} hours! (Deadline: {task_deadline})")
        
        st.write("**Instructions:** Upload a photo showing clear evidence that you've completed this task.")
        
        uploaded_file = st.file_uploader("Upload photo evidence", type=["jpg", "jpeg", "png"])
        
        if uploaded_file is not None:
            # Display the uploaded image
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Evidence", use_column_width=True)
            
            if st.button("Submit for Verification"):
                with st.spinner("Analyzing your evidence with Llama 3.2..."):
                    # Reset file pointer
                    uploaded_file.seek(0)
                    image_bytes = uploaded_file.getvalue()
                    
                    # Verify using Claude
                    verification_result = verify_task_completion(image_bytes, task_description)
                    
                    # Get current deadline for comparison
                    c.execute("SELECT deadline FROM tasks WHERE id=?", (selected_task_id,))
                    deadline_data = c.fetchone()[0]
                    
                    now = datetime.now()
                    
                    # Handle cases where deadline might be NULL or invalid
                    if deadline_data is None:
                        deadline_met = True  # If no deadline, consider it met
                    else:
                        try:
                            if isinstance(deadline_data, str):
                                deadline = datetime.fromisoformat(deadline_data)
                            else:
                                deadline = deadline_data
                            deadline_met = now <= deadline
                        except (ValueError, TypeError):
                            deadline_met = True  # If deadline format is invalid, consider it met
                    
                    # Update the task status
                    c = conn.cursor()
                    c.execute(
                        "UPDATE tasks SET status=?, completed_at=?, verification_result=? WHERE id=?",
                        ("completed", now, verification_result, selected_task_id)
                    )
                    conn.commit()
                    
                    # Display results
                    if "VERIFIED" in verification_result:
                        st.success("🎉 Task verified as complete!")
                    else:
                        st.warning("Task marked as completed, but verification had some concerns.")
                    
                    # Show deadline status
                    if deadline_data is not None:
                        try:
                            if deadline_met:
                                time_diff = (deadline - now).total_seconds() / 3600
                                st.success(f"✅ Completed on time! ({abs(time_diff):.1f} hours before deadline)")
                            else:
                                time_diff = (now - deadline).total_seconds() / 3600
                                st.error(f"⚠️ Completed {time_diff:.1f} hours after deadline")
                        except (ValueError, TypeError, NameError):
                            st.info("Deadline information unavailable")
                    
                    st.write("**Verification Details:**")
                    st.write(verification_result)

if __name__ == "__main__":
    main()