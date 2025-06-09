from nicegui import ui
from pathlib import Path
from wif import WIFReader
import sqlite3
import hashlib
from PIL import Image, ImageDraw, ImageFont
import io
import base64
from render import ImageRenderer
from datetime import datetime


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
weft_index = 1
curr_file_hash = None

# Add a container for the lift plan cards
lift_plan_container = ui.column().classes('w-full')


#========== Functions ===========
def get_file_list():
    """Get the list of .wif files in the upload folder."""
    return [f.name for f in UPLOAD_FOLDER.iterdir() if f.suffix == ".wif"]

def select_file(filename):
    """Select a file from the list."""
    global selected_file
    global curr_file_hash
    global working_file
    global weft_index
    selected_file = filename
    working_file = None
    weft_index = None
    
    #ui.notify(f'Selected file: {selected_file}')
    
def next_weft():
    """Go to the next weft."""
    global weft_index
    global selected_file
    global curr_file_hash
    global draft
    if weft_index < len(draft.weft):
        weft_index += 1
        save_index(curr_file_hash, selected_file, weft_index)
        #ui.notify(f'Current Weft: {weft_index}')
    else:
        ui.notify('Already at the last weft.')
    
    newCards()
    
def previous_weft():
    """Go to the previous weft."""
    global weft_index
    global selected_file
    global curr_file_hash
    if weft_index > 1:
        weft_index -= 1
        save_index(curr_file_hash, selected_file, weft_index)
        #ui.notify(f'Current Weft: {weft_index}')
        newCards()
    else:
        ui.notify('Already at the first weft.')
        

def manualWeft(index):
    if index < 1 or index > len(draft.weft):
        ui.notify(f'Invalid weft index: {index}', type='error')
        return
    global weft_index
    weft_index = index
    newCards()

def handle_key(key):
    """Handle keyboard events."""
    if key.action.keydown:
        if key.key.arrow_right:
            next_weft()
        elif key.key.arrow_left:
            previous_weft()
        #else:
        #    ui.notify(f'Key pressed: {key}')
        
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

# Load button functionality
def load_file():
    #ui.notify(f"Button clicked to load file: {selected_file}")
    global draft
    global working_file
    global weft_index
    global curr_file_hash
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
            curr_file_hash = file_hash
            newCards()  # Generate the lift plan card
        except Exception as e:
            ui.notify(f"Error loading file: {e}", type='error')

def save_index(file_hash, filename, weft_index):
    """Save the current index for the given file hash."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Current timestamp
    cursor.execute("""
        INSERT INTO file_indices (file_hash, filename, weft_index, date_created, last_modified)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(file_hash) DO UPDATE SET
            weft_index = excluded.weft_index,
            last_modified = excluded.last_modified
    """, (file_hash, filename, weft_index, now, now))
    conn.commit()
    conn.close()
    
def getLiftPlan():
    global draft
    num_threads = len(draft.weft)
    liftplan = []
    for ii, thread in enumerate(draft.weft):
        shafts = []
        for jj, shaft in enumerate(draft.shafts):
                if shaft in thread.connected_shafts:
                    shafts.append(jj+1)
        liftplan.append(shafts)
    return liftplan

def draw_weft_lift(index, textcolor="black", caption=None):
    liftplan = getLiftPlan()
    next_selected_weft = liftplan[index -1] if liftplan and index - 1 < len(liftplan) else []
    # Render squares for the next weft
    next_target_width = 800  # Half the size of the main rendering
                
    num_shafts = len(draft.shafts)
                
    spacing = 5  # Spacing between squares
    next_square_size = (next_target_width - (spacing * (num_shafts - 1))) // num_shafts
    next_width = next_square_size * num_shafts + spacing * (num_shafts - 1)
    next_height = next_square_size
    im = Image.new("RGB", (next_width, next_height), (255, 255, 255))
    next_draw = ImageDraw.Draw(im)
                
    # Load a font for the text
    font_size = int(next_square_size * 0.6)  # Font size to fill most of the box
    try:
        font = ImageFont.truetype("arial.ttf", font_size)  # Use a system font
    except IOError:
        font = ImageFont.load_default()  # Fallback to default font if "arial.ttf" is not available

    for i in range(num_shafts):
        x0 = i * (next_square_size + spacing)
        y0 = 0
        x1 = x0 + next_square_size
        y1 = y0 + next_square_size

        if i + 1 in next_selected_weft:
            fill_color = textcolor
            text_color = "white"
        else:
            fill_color = "white"
            text_color = textcolor
        border_thickness = 2 if i + 1 in next_selected_weft else 1
        next_draw.rectangle([x0, y0, x1, y1], fill=fill_color, outline="black", width=border_thickness)

        if i + 1 in next_selected_weft:
            text = str(i + 1)
            text_bbox = font.getbbox(text)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            text_x = x0 + (next_square_size - text_width) // 2
            text_y = y0 + (next_square_size - text_height) // 2
            next_draw.text((text_x, text_y), text, fill=text_color, font=font)
    return im

def genLiftCard(index, textcolor="black", caption=None):
    """Generate the lift plan card."""
    global draft
    global working_file

    if not draft or not working_file:
        return ui.label('No draft loaded. Please select a file and load it.')

    # Draw the lift plan for the current weft
    im = draw_weft_lift(index, textcolor=textcolor, caption=caption)
    #im.show()

    # Convert the image to a format that can be displayed in NiceGUI
    buffered = io.BytesIO()
    im.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    newcard = ui.card().tight().style('width: 80%;')
    with newcard:
        ui.label(caption).classes('text-lg font-bold')
        ui.image(f'data:image/png;base64,{img_str}').style('width: 100%;')  # Adjust image width
    return newcard




# Function to clear existing cards
def clear_cards():
    lift_plan_container.clear()
    ui.notify("Lift plan cards cleared.")

def newCards():
    global weft_index
    global draft
    lift_plan_container.clear()  # Clear existing cards

    with lift_plan_container:
        # Display the first two cards in a single row
        with ui.row().classes('w-full items-center justify-between'):
            if weft_index > 1:
                genLiftCard(weft_index - 1, "lightgrey", f"Prev Weft: #{weft_index - 1}").style('width: 48%;')  # Show the previous weft
            else:
                with ui.card():
                    ui.label('No previous weft').classes('text-lg font-bold')
            
            if weft_index >= len(draft.weft):
                with ui.card():
                    ui.label('No more wefts').classes('text-lg font-bold')
            else:
                genLiftCard(weft_index + 1, "lightgrey", f"Next Weft: #{weft_index + 1}").style('width: 48%;')  # Show the next weft

        # Display the third card in its own row
        with ui.row().classes('w-full items-center justify-center'):
            ui.button('Previous', color='red', icon='arrow_back', on_click=previous_weft).props('push glossy').bind_visibility_from(globals(), 'working_file')
            genLiftCard(weft_index, "black", f"Current Weft: #{weft_index}").style('width: 60%;')  # Show the current weft
            ui.button('Next', color='green', icon='arrow_forward', on_click=next_weft).props('push glossy text-color=black').bind_visibility_from(globals(), 'working_file')
    
        with ui.row().classes('w-full items-center justify-center'):
            with ui.card():
                ui.label(f"Total Warps: {len(draft.warp)}").classes('text-lg font-bold')
            with ui.card():
                ui.label(f"Total Wefts: {len(draft.weft)}").classes('text-lg font-bold')
            with ui.card():
                ui.label(f"Total Shafts: {len(draft.shafts)}").classes('text-lg font-bold')
            with ui.card():
                perc = (weft_index / len(draft.weft)) * 100
                ui.label(f"Percent Complete: {(perc):.1f}%").classes('text-lg font-bold')
                
#========== UI        ===========
init_db()  # Initialize the database
file_list = get_file_list()
#ui.notify(file_list)

fullscreen = ui.fullscreen()
keyboard = ui.keyboard(on_key=handle_key)

with ui.header():
    ui.label('Lift Plan Viewer').classes('text-h5')
    ui.button('Toggle Fullscreen', color='lightyellow', on_click=fullscreen.toggle).props('push glossy text-color=black')
    ui.select(
        file_list,
        label='Select File',
        on_change=lambda e: select_file(e.value),
        value=None
    ).classes('w-1/4 bg-white text-black')
    ui.button('Load File', color='blue', icon='file_download', on_click=lambda: load_file()).props('push glossy text-color=black').bind_visibility_from(globals(), 'selected_file')
    #ui.button('Previous', color='red', icon='arrow_back', on_click=previous_weft).props('push glossy').bind_visibility_from(globals(), 'working_file')
    #ui.button('Next', color='green', icon='arrow_forward', on_click=next_weft).props('push glossy text-color=black').bind_visibility_from(globals(), 'working_file')
    ui.label('Current Weft:').classes('text-h6').bind_visibility_from(globals(), 'working_file')
    #ui.label().bind_text_from(globals(), 'weft_index').classes('text-h6').bind_visibility_from(globals(), 'working_file')
    ui.number(
        value=weft_index,
        format='%d',
        on_change=lambda e: manualWeft(int(e.value)) if e.value else None
    ).bind_visibility_from(globals(), 'working_file').bind_value_from(globals(), 'weft_index').props('min=1 max=1000 step=1').classes('w-1/4 bg-white text-black text-xl font-bold')

# Add the lift plan container
with lift_plan_container:
    pass  # This will hold the dynamically generated cards

ui.run()
