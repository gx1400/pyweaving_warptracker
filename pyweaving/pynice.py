from liftplanview import ui
from pathlib import Path
from wif import WIFReader
import sqlite3
import hashlib
from PIL import Image
import io
import base64
from render import ImageRenderer

# Create 'uploads' folder if it doesn't exist
UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)

# Initialize SQLite database
DB_FILE = "index_store.db"

# File selection section
file_list = []
draft = None
selected_file = None
working_file = None

def get_file_list():
    """Get the list of .wif files in the upload folder."""
    return [f.name for f in UPLOAD_FOLDER.iterdir() if f.suffix == ".wif"]

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_indices (
            file_hash TEXT PRIMARY KEY,
            filename TEXT,
            weft_index INTEGER,
            date_created TEXT,
            last_modified TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_file_hash(file_path):
    """Generate SHA256 hash for the given file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

def get_saved_index(file_hash):
    """Retrieve the saved index for the given file hash."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT weft_index, filename, date_created, last_modified
        FROM file_indices
        WHERE file_hash = ?
    """, (file_hash,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0  # Default to 0 if not found

def load_draft(file_path):
    """Load the draft from the file."""
    return WIFReader(file_path).read()



# Create a dropdown menu for sidebar elements

# File upload dialog
upload_dialog = ui.dialog()
with upload_dialog:
    with ui.card():
        ui.label('Upload a .wif file').classes('text-lg font-bold')
        #ui.upload(on_upload=handle_upload, label='Upload')

# File selection dialog
select_file_dialog = ui.dialog()
with select_file_dialog:
    with ui.card():
        ui.label('Select a file to view').classes('text-lg font-bold')
        if file_list:
            ui.select(file_list, label='Files', value=selected_file, on_change=lambda e: on_file_select_change(e.value))

# File upload section
uploaded_file = None
def handle_upload(file):
    global uploaded_file
    uploaded_file = file
    save_path = UPLOAD_FOLDER / file.name
    with open(save_path, "wb") as f:
        f.write(file.read())
    ui.notify(f"File uploaded: {file.name}")



def on_file_select_change(selected):
    global selected_file
    selected_file = selected
    ui.notify(f"Selected file changed to: {selected_file}")

# Load button functionality
def load_file():
    ui.notify(f"Button clicked to load file: {selected_file}")
    global draft
    global working_file
    if selected_file:
        file_path = UPLOAD_FOLDER / selected_file
        try:
            # Load the draft
            draft = load_draft(str(file_path))

            # Generate file hash for persistence
            file_hash = get_file_hash(file_path)

            # Retrieve the saved index for the file
            weft_index = get_saved_index(file_hash)

            # Notify the user
            ui.notify(f"File loaded successfully: {selected_file}")
            ui.notify(f"Loaded Weft #{weft_index + 1}")
            working_file = selected_file
        except Exception as e:
            ui.notify(f"Error loading file: {e}", type='error')

# Function to render the design
def render_design():
    if selected_file:
        file_path = UPLOAD_FOLDER / selected_file
        try:
            # Load the draft
            global draft
            draft = load_draft(str(file_path))

            # Create an instance of the ImageRenderer
            renderer = ImageRenderer(draft)

            # Generate the rendered image
            im = renderer.make_pil_image()

            # Convert the image to a format that can be displayed in NiceGUI
            buffered = io.BytesIO()
            im.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()

            # Display the rendered image in the main content column
            
            with ui.card().tight().style('width: 100%;'):
                ui.label('Rendered Image').classes('text-lg font-bold')
                ui.image(f'data:image/png;base64,{img_str}').style('width: 100%;')  # Adjust image width
        except Exception as e:
            ui.notify(f"Error rendering image: {e}", type='error')
    else:
        ui.notify("No file selected. Please select a file first.", type='error')



# Initialize the database
init_db()

ui.label('WIF Lift Plan Viewer').classes('text-2xl font-bold')
    
with ui.dialog() as dialog, ui.card():
    file_list = get_file_list()  # Get the list of .wif files
    selected_file = file_list[0] if file_list else None  # Automatically select the first file if the list is not empty
    ui.label('Hello world!')
        
    ui.label('Select a file to view').classes('text-lg font-bold')
    if file_list:
        ui.select(file_list, label='Files', value=selected_file, on_change=lambda e: on_file_select_change(e.value))

    ui.button('Load', on_click=load_file)
    ui.button('Close', on_click=dialog.close)

ui.button('Menu', on_click=dialog.open)

ui.label(working_file if working_file else "No file selected")

ui.run()