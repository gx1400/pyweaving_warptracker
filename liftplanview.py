from nicegui import ui, observables, events
from pathlib import Path
from pyweaving.wif import WIFReader, Draft
import sqlite3
import hashlib
from PIL import Image, ImageDraw, ImageFont
import io
import base64
from pyweaving.render import ImageRenderer
from datetime import datetime


# Create 'uploads' folder if it doesn't exist
UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)  

# Initialize SQLite database
DB_PATH = Path("db")
DB_PATH.mkdir(exist_ok=True)
DB_FILE = DB_PATH / "index_store.db"


# File selection section
select : ui.select
file_list = observables.ObservableList()
draft : Draft
selected_file = None
working_file = None
weft_index = 1
curr_file_hash = None



# Add a container for the lift plan cards
lift_plan_container = ui.column().classes('w-full')


#========== Functions ===========
def get_file_list():
    """Get the list of .wif files in the upload folder."""
    global file_list
    file_list.clear()  # Clear the existing list
    for f in UPLOAD_FOLDER.iterdir():
        if f.suffix == ".wif":
            file_list.append(f.name)

def select_file(filename):
    """Select a file from the list."""
    global selected_file
    global curr_file_hash
    global working_file
    global weft_index
    selected_file = filename
    working_file = None
    weft_index = 0
    
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
        ui.notify(f'Invalid weft index: {index}', type='negative')
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
        elif key.key.arrow_up:
            previous_weft()
        elif key.key.arrow_down:   
            next_weft()
        elif key.key.page_up:
            previous_weft()
        elif key.key.page_down:
            next_weft()
        elif key.key.enter:
            next_weft()
        elif key.key.code == 'Space':
            previous_weft()
        #else:
        #    ui.notify(f'Key not supported: {key}')
        
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_indices (
            file_hash TEXT,
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
    """Retrieve the most recent index for the given file hash."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT weft_index, filename, date_created, last_modified
        FROM file_indices
        WHERE file_hash = ?
        ORDER BY last_modified DESC
        LIMIT 1
    """, (file_hash,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 1  # Default to 0 if no record is found

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
            ui.notify(f"Loaded Weft #{weft_index }")
            working_file = selected_file
            curr_file_hash = file_hash
            newCards()  # Generate the lift plan card
        except OSError as e:
            ui.notify(f'File system error: {e}', type='negative')
        except ValueError as e:
            ui.notify(f'Invalid file content: {e}', type='negative')
        except Exception as e:
            ui.notify(f'Unexpected error: {e}', type='negative')

def save_index(file_hash, filename, weft_index):
    """Save the current index for the given file hash."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Current timestamp
    cursor.execute("""
        INSERT INTO file_indices (file_hash, filename, weft_index, date_created, last_modified)
        VALUES (?, ?, ?, ?, ?)
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

def getColor(index):
    global draft
    colorobj = draft.weft[index -1].color
    colortuple = colorobj.rgb if hasattr(colorobj, 'rgb') else None
    if colortuple is None:
        return (0, 0, 0)  # Default to white if no color is specified
    elif isinstance(colortuple, tuple) and len(colortuple) == 3:
        return colortuple  # If it's an RGB tuple
    else:
        return (0, 0, 0)  # Fallback to white for any other case

def draw_weft_lift(index, textcolor="black", caption=None):
    liftplan = getLiftPlan()
    color = getColor(index)
    next_selected_weft = liftplan[index -1] if liftplan and index - 1 < len(liftplan) else []
    # Render squares for the next weft
    next_target_width = 800  # Half the size of the main rendering
                
    num_shafts = len(draft.shafts)
                
    spacing = 5  # Spacing between squares
    next_square_size = (next_target_width - (spacing * (num_shafts - 1))) // num_shafts
    next_width = next_square_size * num_shafts + spacing * (num_shafts - 1)
    next_height = next_square_size

    color_spacing = 5
    color_height = 20

    padding = 2

    boxheight = next_height + color_height + color_spacing + padding * 2
    boxwidth = next_width + padding * 2

    im = Image.new("RGB", (boxwidth, boxheight), (255, 255, 255))
    next_draw = ImageDraw.Draw(im)
                
    # Load a font for the text
    font_size = int(next_square_size * 0.7)  # Font size to fill most of the box
    try:
        font = ImageFont.truetype("arial12.ttf", font_size)  # Use a system font
    except IOError:
        font = ImageFont.load_default(size=font_size)  # Fallback to default font if "arial.ttf" is not available

    # Draw the color bar
    color_x0 = padding
    color_y0 = padding
    color_x1 = next_width
    color_y1 = padding + color_height
    next_draw.rectangle([color_x0, color_y0, color_x1, color_y1], fill=color, outline="black")


    for i in range(num_shafts):
        x0 = padding + (i * (next_square_size + spacing))
        y0 = padding + color_height + color_spacing   # Start below the color bar
        x1 = x0 + next_square_size
        y1 = y0 + next_square_size

        if i + 1 in next_selected_weft:
            fill_color = color
            text_color = "white"
        else:
            fill_color = "white"
            text_color = textcolor
        border_thickness = 4 if i + 1 in next_selected_weft else 1
        next_draw.rectangle([x0, y0, x1, y1], fill=fill_color, outline="black", width=border_thickness)

        if i + 1 in next_selected_weft:
            text = str(i + 1)
            text_bbox = font.getbbox(text)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            text_x = x0 + (next_square_size - text_width) // 2
            text_y = y0 - text_bbox[1] + (next_square_size - text_height) // 2
            next_draw.text((text_x, text_y), text, fill=text_color, font=font, stroke_width=2, stroke_fill="black")
    return im

def genLiftCard(index, textcolor="black", caption=''):
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
    #ui.notify("Lift plan cards cleared.")

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
        
        with ui.row().classes('w-full items-center justify-center'):
            genLiftCard(weft_index, "black", f"Current Weft: #{weft_index}").style('width: 60%;')  # Show the current weft
            
        
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

        # Display the third card in its own row
        with ui.row().classes('w-full items-center justify-center'):
            ui.button('Previous', color='red', icon='arrow_back', on_click=previous_weft).props('push glossy').bind_visibility_from(globals(), 'working_file')
            ui.button('Next', color='green', icon='arrow_forward', on_click=next_weft).props('push glossy text-color=black').bind_visibility_from(globals(), 'working_file')
    

def render_lift_plan():
    """Render the lift plan for the current weft."""
    global draft
    global working_file
    global weft_index

    if not draft or not working_file:
        ui.notify('No draft loaded. Please select a file and load it.', type='negative')
        return

    # Clear existing cards
    clear_cards()
    renderer = ImageRenderer(draft, scale=100)
    bufferspace = (len(str(len(draft.weft))) * 50)
    width = 60 + bufferspace + renderer.pixels_per_square * len(draft.shafts)
    height = 6 + renderer.pixels_per_square * len(draft.weft)
    im = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(im)
    renderer.paint_liftplan(draw)
    buffered = io.BytesIO()
    im.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    caption = f"Lift Plan for in {working_file}"
    newcard = ui.card().tight().style('width: 80%;')
    with lift_plan_container:
        with ui.row().classes('w-full justify-center items-center'):
            with ui.card().tight().style('width: 40%;'):
                ui.label(caption).classes('text-lg font-bold')
                ui.image(f'data:image/png;base64,{img_str}').style('width: 100%;')  # Adjust image width

def view_weft_history():
    """Display the history of the last 100 updates for the current working file."""
    clear_cards()  # Clear existing cards

    if not working_file:
        ui.notify('No file is currently loaded. Please load a file first.', type='negative')
        return

    # Query the database for the last 100 updates for the current working file, sorted by most recent
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT weft_index, last_modified
        FROM file_indices
        WHERE filename = ?
        ORDER BY last_modified DESC
        LIMIT 100
    """, (working_file,))
    history = cursor.fetchall()
    conn.close()

    # Prepare rows for the table
    rows = [{'Weft Index': str(row[0]), 'Last Modified': row[1]} for row in history]

    # Create a table to display the history
    with lift_plan_container:
        with ui.card().tight().style('width: 80%;'):
            ui.label(f'Recent Weft Updates for "{working_file}"').classes('text-lg font-bold')
            ui.table(rows=rows).classes('w-full')  # Pass rows to the table
    

def render_design():
    global draft
    global working_file
    global weft_index

    if not draft or not working_file:
        ui.notify('No draft loaded. Please select a file and load it.', type='negative')
        return

    # Clear existing cards
    clear_cards()
    renderer = ImageRenderer(draft)
    im = renderer.make_pil_image()
    draw = ImageDraw.Draw(im)
    buffered = io.BytesIO()
    im.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    caption = f"Rendered design for in {working_file}"
    with lift_plan_container:
        with ui.row().classes('w-full justify-center items-center'):
            with ui.card().tight().style('width: 80%;'):
                ui.label(caption).classes('text-lg font-bold')
                ui.image(f'data:image/png;base64,{img_str}').style('width: 100%;')
                

# Function to validate and navigate to the specified weft index
def validate_weft_input(value):
    try:
        index = int(value)
        if 1 <= index <= len(draft.weft):
            manualWeft(index)
            go_to_weft_dialog.close()
        else:
            ui.notify(f'Invalid weft index: {index}. Please enter a number between 1 and {len(draft.weft)}.', type='negative')
    except ValueError:
        ui.notify('Invalid input. Please enter a valid integer.', type='negative')


def handle_upload(e: events.UploadEventArguments):
    file = e.content.read()
    """Handle the file upload."""
    global selected_file
    global curr_file_hash
    global working_file
    global weft_index
    
    file_path = UPLOAD_FOLDER / e.name
    
    if file_path.suffix == '.wif':
        
        # Load the draft from the uploaded file
        try:
            with open(file_path, 'wb') as f:
                f.write(file)
            get_file_list()
            ui.notify(f'File uploaded and loaded successfully: {file_path.name}')
        except Exception as exc:
            ui.notify(f'Error loading uploaded file: {exc}', type='negative')
    else:
        ui.notify('Please upload a valid .wif file.', type='negative')
        
def home():
    """Navigate to the home screen."""
    global working_file
    global weft_index
    working_file = None
    weft_index = 1
    clear_cards()
    with lift_plan_container:
        with ui.row().classes('w-full justify-center items-center'):
            ui.label('Welcome to Megan\'s Lift Plan Viewer!').classes('text-lg font-bold')
        with ui.row().classes('w-full justify-center items-center'):
            ui.label('Begin by loading a file').classes('text-lg font-bold')
        with ui.row().classes('w-full justify-center items-center'):
            ui.button('Load File', color='green', icon='file_open', on_click=load_file_dialog.open).props('push glossy text-color=black')
            ui.button('Upload File', color='blue', icon='file_upload', on_click=upload_file_dialog.open).props('push glossy text-color=black')
    ui.notify('Home screen loaded. Please load a file to continue.')

#========== UI        ===========

fullscreen = ui.fullscreen()
keyboard = ui.keyboard(on_key=handle_key)

upload_file_dialog = ui.dialog()
with upload_file_dialog:
    with ui.card():
        ui.label('Upload a WIF File').classes('text-lg font-bold')
        file_input = ui.upload(multiple=False, on_upload=handle_upload).classes('w-full bg-white text-black').props('accept=.wif')
        ui.button('Close', color='red', on_click=lambda: [upload_file_dialog.close()]).props('push glossy text-color=black')

# Create a dialog for file selection and loading
load_file_dialog = ui.dialog()
with load_file_dialog:
    with ui.card():
        ui.label('Select and Load File').classes('text-lg font-bold')
        select = ui.select(
            file_list,
            label='Select File',
            on_change=lambda e: select_file(e.value),
            value=None
        ).classes('w-full bg-white text-black')
        ui.button('Load File', color='green', icon='file_open', on_click=lambda: [load_file(), load_file_dialog.close]).props('push glossy text-color=black').bind_visibility_from(globals(), 'selected_file')

# Create a dialog for "Go To Weft"
go_to_weft_dialog = ui.dialog()
with go_to_weft_dialog:
    with ui.card():
        ui.label('Enter Weft Index').classes('text-lg font-bold')
        weft_input = ui.input(label='Weft Index', value=str(weft_index)).props('type=number').classes('w-full')
        with ui.row().classes('w-full justify-center items-center'):
            ui.button('Cancel', color='red', on_click=go_to_weft_dialog.close).props('push glossy text-color=black')
            ui.button('Accept', color='green', on_click=lambda: validate_weft_input(weft_input.value)).props('push glossy text_color=black')

# Update the header
with ui.header().classes('flex items-center justify-between'):
    with ui.button(icon='menu', color='green').props('push glossy text-color=black'):
        with ui.menu() as menu:
            ui.menu_item('Load File', on_click=load_file_dialog.open)
            ui.menu_item('Render Design', on_click=render_design).bind_visibility_from(globals(), 'working_file')
            ui.menu_item('Render Lift Plan', on_click=render_lift_plan).bind_visibility_from(globals(), 'working_file')
            ui.menu_item('Weft History', on_click=view_weft_history).bind_visibility_from(globals(), 'working_file')
    ui.button(icon='home', color='blue', on_click=home).props('push glossy text_color=black').bind_visibility_from(globals(), 'working_file')
    ui.label('Megan\'s Lift Plan Viewer').classes('text-h5').bind_visibility_from(globals(), 'working_file')
    ui.label().bind_text_from(globals(), 'weft_index', lambda value: f'Current Weft: {value}').classes('text-h6').bind_visibility_from(globals(), 'working_file')
    
    ui.button('Go To Weft', color='yellow', on_click=go_to_weft_dialog.open).props('push glossy text_color=black').bind_visibility_from(globals(), 'working_file')
    ui.button('Toggle Fullscreen', color='green', on_click=fullscreen.toggle).props('push glossy text_color=black')
    
# Add the lift plan container
with lift_plan_container:
    pass

ui.run()


init_db()  # Initialize the database
file_list = observables.ObservableList(on_change=lambda e: select.set_options(file_list))
get_file_list()
home()


