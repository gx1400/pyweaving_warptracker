import streamlit as st
import os
from pathlib import Path
from wif import WIFReader
from render import ImageRenderer
from PIL import Image, ImageDraw, ImageFont  # Ensure ImageFont is imported
import sqlite3
import hashlib
from datetime import datetime

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
    """Retrieve the saved index and metadata for the given file hash."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT weft_index, filename, date_created, last_modified
        FROM file_indices
        WHERE file_hash = ?
    """, (file_hash,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {
            "weft_index": result[0],
            "filename": result[1],
            "date_created": result[2],
            "last_modified": result[3]
        }
    return {"weft_index": 0, "filename": None, "date_created": None, "last_modified": None}

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

def getLiftPlan(draft):
    num_threads = len(draft.weft)
    liftplan = []
    for ii, thread in enumerate(draft.weft):
        shafts = []
        for jj, shaft in enumerate(draft.shafts):
                if shaft in thread.connected_shafts:
                    shafts.append(jj+1)
        liftplan.append(shafts)
    return liftplan

# Function to load a draft
def load_draft(infile):
    if infile.endswith('.wif'):
        return WIFReader(infile).read()
    else:
        raise ValueError(
            "filename %r unrecognized: .wif and .json are supported" %
            infile
        )

# Initialize session state for draft, selected weft index, and file hash
if "draft" not in st.session_state:
    st.session_state.draft = None
if "weft_index" not in st.session_state:
    st.session_state.weft_index = 0  # Default to 0
if "file_hash" not in st.session_state:
    st.session_state.file_hash = None  # Initialize file_hash
if "loaded_file" not in st.session_state:
    st.session_state.loaded_file = None  # Initialize loaded_file

# --- Sidebar for file upload and selection ---
with st.sidebar:
    st.header("File Options")
    
    # File upload
    uploaded_file = st.file_uploader("Upload a .wif file", type=["wif"])
    
    if uploaded_file is not None:
        # Save uploaded file
        save_path = UPLOAD_FOLDER / uploaded_file.name
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Saved file: {uploaded_file.name}")
    
    # List files in uploads folder
    file_list = [f.name for f in UPLOAD_FOLDER.iterdir() if f.suffix == ".wif"]
    
    if file_list:
        selected_file = st.selectbox("Select a file to view", file_list)
        st.info(f"You selected: {selected_file}")

        # Add delete button
        if st.button("Delete Selected File"):
            # Initialize confirmation state
            st.session_state.confirm_delete = True

        # Show confirmation dialog if delete button was clicked
        if st.session_state.get("confirm_delete", False):
            st.warning(f"Are you sure you want to delete the file: {selected_file}?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Confirm Delete"):
                    file_to_delete = UPLOAD_FOLDER / selected_file
                    if file_to_delete.exists():
                        try:
                            file_to_delete.unlink()
                            st.success(f"Deleted file: {selected_file}")
                            st.session_state.confirm_delete = False
                            # Force app to rerun to refresh file list
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error deleting file: {e}")
                    else:
                        st.error(f"File not found: {file_to_delete}")
                        st.session_state.confirm_delete = False
            with col2:
                if st.button("Cancel"):
                    st.session_state.confirm_delete = False

        # Add a button to load the selected file
        st.sidebar.markdown("---")
        if st.button("Load"):
            file_path = UPLOAD_FOLDER / selected_file
            try:
                # Load the draft
                st.session_state.draft = load_draft(str(file_path))
                st.session_state.loaded_file = selected_file  # Store the loaded file name

                # Generate file hash for persistence
                file_hash = get_file_hash(file_path)

                # Retrieve the saved index for the file
                saved_data = get_saved_index(file_hash)
                st.session_state.weft_index = saved_data["weft_index"]  # Load the saved index
                st.session_state.file_hash = file_hash  # Store the file hash in session state

                st.success(f"File loaded successfully: {selected_file}")
                st.success(f"Loaded Weft #{st.session_state.weft_index + 1}")  # Display the loaded weft index
            except Exception as e:
                st.error(f"Error loading file: {e}")
                
# Render the image in the main content area
if st.session_state.draft is not None:
    # Add a button to trigger rendering
    if st.sidebar.button("Render Design"):
        try:
            renderer = ImageRenderer(st.session_state.draft)
            im = renderer.make_pil_image()
            st.image(im, caption="Rendered Image", use_container_width=True)
        except Exception as e:
            st.error(f"Error rendering image: {e}")

# Render the image in the main content area
if st.session_state.draft is not None:
    # Add a button to trigger rendering
    if st.sidebar.button("Render Liftplan"):
        try:
            renderer = ImageRenderer(st.session_state.draft)
            width = 34 + renderer.pixels_per_square * len(st.session_state.draft.shafts)
            height = 6 + renderer.pixels_per_square * len(st.session_state.draft.weft)
            im = Image.new("RGB", (width, height), (255, 255, 255))
            draw = ImageDraw.Draw(im)
            renderer.paint_liftplan(draw)
            st.image(im, caption="Rendered Image", use_container_width=True)
        except Exception as e:
            st.error(f"Error rendering image: {e}")

    # Adjust numeric input for selecting a weft index
    st.sidebar.markdown("---")
    num_wefts = len(st.session_state.draft.weft)
    st.session_state.weft_index = st.sidebar.number_input(
        "Select Weft Index",
        min_value=1,  # Start at 1 instead of 0
        max_value=num_wefts,
        value=st.session_state.weft_index + 1,  # Convert zero-indexed to one-indexed for display
        step=1,
        help=f"Enter a number between 1 and {num_wefts}."
    ) - 1  # Convert back to zero-indexed for internal logic

    # Validate the numeric input
    if st.session_state.weft_index < 0:
        st.session_state.weft_index = 0
        st.sidebar.warning("Index cannot be less than 1. Reset to 1.")
    elif st.session_state.weft_index >= num_wefts:
        st.session_state.weft_index = num_wefts - 1
        st.sidebar.warning(f"Index cannot exceed {num_wefts}. Reset to {num_wefts}.")

    # Add a button to display the selected weft's lift plan
    if st.sidebar.button("Display Weft"):
        try:
            liftplan = getLiftPlan(st.session_state.draft)
            selected_weft = liftplan[st.session_state.weft_index]  # Adjust for zero-based indexing
            #st.write(f"Lift Plan for Weft {st.session_state.weft_index}: {selected_weft}")
        except IndexError:
            st.error("Invalid weft index selected.")
        except Exception as e:
            st.error(f"Error displaying weft: {e}")
            
# --- Main content area ---
    # Display the loaded file name in the center of the app
    if "loaded_file" in st.session_state:
        st.markdown(
            f"""
            <div style='text-align: center; font-size: 18px; font-weight: bold;'>
                {st.session_state.loaded_file}
            </div>
            """,
            unsafe_allow_html=True,
        )


    
    try:
        liftplan = getLiftPlan(st.session_state.draft)
        selected_weft = liftplan[st.session_state.weft_index]  # Adjust for zero-based indexing
        
    except IndexError:
        st.error("Invalid weft index selected.")
    except Exception as e:
        st.error(f"Error displaying weft: {e}")

    prevweft, nextweft = st.columns([1, 1])  # Add columns for "Previous Weft" and "Next Weft"

    # Define spacing for squares
    spacing = 5  # Fixed spacing between squares
    border_thickness = 2 # Thickness of the square border
    

    with prevweft:
        if st.session_state.weft_index > 0:
            st.markdown(
                f"""
                <div style='text-align: left; font-size: 16px; font-weight: bold;'>
                    Next Weft: {st.session_state.weft_index}
                </div>
                """,
                unsafe_allow_html=True,
            )
            try:
                prev_selected_weft = liftplan[st.session_state.weft_index - 1]
                # Render squares for the previous weft
                prev_target_width = 400  # Half the size of the main rendering
                num_shafts = len(st.session_state.draft.shafts)
                prev_square_size = (prev_target_width - (spacing * (num_shafts - 1))) // num_shafts
                prev_width = prev_square_size * num_shafts + spacing * (num_shafts - 1)
                prev_height = prev_square_size
                prev_im = Image.new("RGB", (prev_width, prev_height), (255, 255, 255))
                prev_draw = ImageDraw.Draw(prev_im)
                
                
                # Load a font for the text
                font_size = int(prev_square_size * 0.6)  # Font size to fill most of the box
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)  # Use a system font
                except IOError:
                    font = ImageFont.load_default()  # Fallback to default font if "arial.ttf" is not available

                for i in range(num_shafts):
                    x0 = i * (prev_square_size + spacing)
                    y0 = 0
                    x1 = x0 + prev_square_size
                    y1 = y0 + prev_square_size

                    if i + 1 in prev_selected_weft:
                        fill_color = "darkgrey"
                        text_color = "white"
                    else:
                        fill_color = "white"
                        text_color = "darkgrey"

                    prev_draw.rectangle([x0, y0, x1, y1], fill=fill_color, outline="black", width=border_thickness)

                    if i + 1 in prev_selected_weft:
                        text = str(i + 1)
                        text_bbox = font.getbbox(text)
                        text_width = text_bbox[2] - text_bbox[0]
                        text_height = text_bbox[3] - text_bbox[1]
                        text_x = x0 + (prev_square_size - text_width) // 2
                        text_y = y0 + (prev_square_size - text_height) // 2
                        prev_draw.text((text_x, text_y), text, fill=text_color, font=font)

                st.image(prev_im, use_container_width=True)
            except IndexError:
                st.write("No previous weft available.")
        else:
            st.write("No previous weft available.")

    with nextweft:
        if st.session_state.weft_index < num_wefts - 1:
            st.markdown(
                f"""
                <div style='text-align: right; font-size: 16px; font-weight: bold;'>
                    Next Weft: {st.session_state.weft_index + 2}
                </div>
                """,
                unsafe_allow_html=True,
            )
            try:
                next_selected_weft = liftplan[st.session_state.weft_index + 1]
                # Render squares for the next weft
                next_target_width = 400  # Half the size of the main rendering
                
                num_shafts = len(st.session_state.draft.shafts)
                
                next_square_size = (next_target_width - (spacing * (num_shafts - 1))) // num_shafts
                next_width = next_square_size * num_shafts + spacing * (num_shafts - 1)
                next_height = next_square_size
                next_im = Image.new("RGB", (next_width, next_height), (255, 255, 255))
                next_draw = ImageDraw.Draw(next_im)
                
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
                        fill_color = "darkgrey"
                        text_color = "white"
                    else:
                        fill_color = "white"
                        text_color = "darkgrey"

                    next_draw.rectangle([x0, y0, x1, y1], fill=fill_color, outline="black", width=border_thickness)

                    if i + 1 in next_selected_weft:
                        text = str(i + 1)
                        text_bbox = font.getbbox(text)
                        text_width = text_bbox[2] - text_bbox[0]
                        text_height = text_bbox[3] - text_bbox[1]
                        text_x = x0 + (next_square_size - text_width) // 2
                        text_y = y0 + (next_square_size - text_height) // 2
                        next_draw.text((text_x, text_y), text, fill=text_color, font=font)

                st.image(next_im, use_container_width=True)
            except IndexError:
                st.write("No next weft available.")
        else:
            st.write("No next weft available.")
            
    st.markdown("---")
        
     # Draw squares for each shaft
    if st.session_state.draft is not None:
        try:
            st.markdown(
                f"""
                <div style='text-align: center; font-size: 24px; font-weight: bold;'>
                    Current Weft: {st.session_state.weft_index + 1}  <!-- Display as one-indexed -->
                </div>
                """,
                unsafe_allow_html=True,
                )
            liftplan = getLiftPlan(st.session_state.draft)
            selected_weft = liftplan[st.session_state.weft_index]  # Adjust for zero-based indexing

            # Use a fixed target width for the content area (e.g., 800px)
            target_width = 800  # Fixed width for the content area
            num_shafts = len(st.session_state.draft.shafts)

            # Calculate square size and spacing dynamically
            spacing = 5  # Fixed spacing between squares
            square_size = (target_width - (spacing * (num_shafts - 1))) // num_shafts
            border_thickness = 3  # Thickness of the square border

            # Create an image to draw the squares
            width = square_size * num_shafts + spacing * (num_shafts - 1)
            height = square_size  # No extra height needed since text is inside the box
            im = Image.new("RGB", (width, height), (255, 255, 255))
            draw = ImageDraw.Draw(im)

            # Load a font for the text
            font_size = int(square_size * 0.6)  # Font size to fill most of the box
            try:
                font = ImageFont.truetype("arial.ttf", font_size)  # Use a system font
            except IOError:
                font = ImageFont.load_default()  # Fallback to default font if "arial.ttf" is not available

            # Draw each square and annotate with shaft number
            for i in range(num_shafts):
                x0 = i * (square_size + spacing)
                y0 = 0
                x1 = x0 + square_size
                y1 = y0 + square_size

                # Determine if the square should be filled or not
                if i + 1 in selected_weft:  # Check if the shaft index is in the lift plan
                    fill_color = "black"
                    text_color = "white"
                else:
                    fill_color = "white"
                    text_color = "black"

                # Draw the square
                draw.rectangle([x0, y0, x1, y1], fill=fill_color, outline="black", width=border_thickness)

                if i + 1 in selected_weft:
                    # Annotate the square with the shaft number
                    text = str(i + 1)
                    text_bbox = font.getbbox(text)  # Use font.getbbox to calculate text dimensions
                    text_width = text_bbox[2] - text_bbox[0]
                    text_height = text_bbox[3] - text_bbox[1]
                    text_x = x0 + (square_size - text_width) // 2
                    text_y = y0 + (square_size - text_height) // 2
                    draw.text((text_x, text_y), text, fill=text_color, font=font)

            # Display the image in the column
            st.image(im, caption="Shafts Visualization", use_container_width=True)
        except Exception as e:
            st.error(f"Error drawing shafts: {e}")
    
    st.markdown("---")        
    
    col1, col3 = st.columns([1, 1])  # Add a third column for "Current Weft"

    # Decrease index button
    with col1:
        if st.session_state.weft_index > 0:
            if st.button("Previous Weft", key="previous_weft2"):
                st.session_state.weft_index -= 1
                save_index(st.session_state.file_hash, st.session_state.loaded_file, st.session_state.weft_index)
                st.rerun()  # Force rerun to immediately update visibility

    # Increase index button
    with col3:
        if st.session_state.weft_index < num_wefts - 1:
            if st.button("Next Weft", key="next_weft2"):
                st.session_state.weft_index += 1
                save_index(st.session_state.file_hash, st.session_state.loaded_file, st.session_state.weft_index)
                st.rerun()  # Force rerun to immediately update visibility
    
    
    st.markdown("---")
    stat1, stat2 = st.columns(2)  # Add two columns for statistics
    with stat1:
        st.write(f"Number of shafts: {len(st.session_state.draft.shafts)}")
        st.write(f"Number of weft threads: {len(st.session_state.draft.weft)}")
    with stat2:
        st.write(f"Number of treadles: {len(st.session_state.draft.treadles)}")
        st.write(f"Number of warp threads: {len(st.session_state.draft.warp)}")
    
    

# Initialize the database
init_db()

# --- Main Application Logic ---
if st.session_state.draft is not None:
    # Generate file hash for the loaded file
    file_path = UPLOAD_FOLDER / st.session_state.loaded_file
    file_hash = get_file_hash(file_path)

    # Retrieve the saved index and metadata for the file
    if "weft_index" not in st.session_state or st.session_state.file_hash != file_hash:
        saved_data = get_saved_index(file_hash)
        st.session_state.weft_index = saved_data["weft_index"]
        st.session_state.file_hash = file_hash
        st.session_state.filename = saved_data["filename"]
        st.session_state.date_created = saved_data["date_created"]
        st.session_state.last_modified = saved_data["last_modified"]




