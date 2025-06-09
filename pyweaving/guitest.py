from liftplanview import ui
from pathlib import Path
from wif import WIFReader
import sqlite3
import hashlib

# Create 'uploads' folder if it doesn't exist
UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)

# Initialize SQLite database
DB_FILE = "index_store.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_indices (
            file_hash TEXT PRIMARY KEY,
            weft_index INTEGER
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
    cursor.execute("SELECT weft_index FROM file_indices WHERE file_hash = ?", (file_hash,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0  # Default to 0 if not found

def load_draft(file_path):
    """Load the draft from the file."""
    return WIFReader(file_path).read()

# Initialize the database
init_db()

# Create a header
ui.label('Welcome to NiceGUI!').classes('text-2xl font-bold')

# File upload section
uploaded_file = None
def handle_upload(file):
    global uploaded_file
    uploaded_file = file
    save_path = UPLOAD_FOLDER / file.name
    with open(save_path, "wb") as f:
        f.write(file.read())
    ui.notify(f"File uploaded: {file.name}")

ui.upload(on_upload=handle_upload, label='Upload a .wif file')

# File selection section
file_list = [f.name for f in UPLOAD_FOLDER.iterdir() if f.suffix == ".wif"]
selected_file = None

def on_file_select_change(selected):
    global selected_file
    selected_file = selected
    ui.notify(f"Selected file changed to: {selected_file}")

if file_list:
    ui.select(file_list, label='Select a file to view', on_change=lambda e: on_file_select_change(e.value))

# Load button
def load_file():
    ui.notify(f"Button clicked to load file: {selected_file}")
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
        except Exception as e:
            ui.notify(f"Error loading file: {e}", type='error')

ui.button('Load File', on_click=load_file)

# Run the NiceGUI app
ui.run()