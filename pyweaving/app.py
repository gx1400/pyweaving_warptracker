import streamlit as st
import os
from pathlib import Path
from wif import WIFReader
from render import ImageRenderer
from PIL import Image, ImageDraw

# Create 'uploads' folder if it doesn't exist
UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)

st.title("WIF File Uploader")

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

# Initialize session state for draft and selected weft index
if "draft" not in st.session_state:
    st.session_state.draft = None
if "weft_index" not in st.session_state:
    st.session_state.weft_index = 0  # Default to 1

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
                st.session_state.draft = load_draft(str(file_path))
                st.success(f"File loaded successfully: {selected_file}")
                st.write(f"Number of shafts: {len(st.session_state.draft.shafts)}")
                st.write(f"Number of weft threads: {len(st.session_state.draft.weft)}")
                st.write(f"Number of treadles: {len(st.session_state.draft.treadles)}")
                st.write(f"Number of warp threads: {len(st.session_state.draft.warp)}")
            except Exception as e:
                st.error(f"Error loading file: {e}")

# Render the image in the main content area
if st.session_state.draft is not None:
    # Add a button to trigger rendering
    if st.sidebar.button("Display Entire Liftplan"):
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

    # Add numeric input for selecting a weft index
    st.sidebar.markdown("---")
    num_wefts = len(st.session_state.draft.weft)
    st.session_state.weft_index = st.sidebar.number_input(
        "Select Weft Index",
        min_value=0,
        max_value=num_wefts,
        value=st.session_state.weft_index,  # Use the global variable
        step=1,
        help=f"Enter a number between 0 and {num_wefts}."
    )

    # Validate the numeric input
    if st.session_state.weft_index < 0:
        st.session_state.weft_index = 0
        st.sidebar.warning("Index cannot be zero or negative. Reset to 0.")
    elif st.session_state.weft_index >= num_wefts:
        st.session_state.weft_index = num_wefts + 1
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

    # Main content buttons to adjust the weft index
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])  # Add a third column for "Current Weft"

    # Decrease index button
    with col1:
        if st.session_state.weft_index > 0:
            if st.button("Previous Weft", key="previous_weft"):
                st.session_state.weft_index -= 1
                st.rerun()  # Force rerun to immediately update visibility

    # Display the current weft number in the center column
    with col2:
        st.markdown(f"<div style='text-align: center; font-size: 18px;'>Current Weft: {st.session_state.weft_index}</div>", unsafe_allow_html=True)

    # Increase index button
    with col3:
        if st.session_state.weft_index < num_wefts - 1:
            if st.button("Next Weft", key="next_weft"):
                st.session_state.weft_index += 1
                st.rerun()  # Force rerun to immediately update visibility

    # Always display the lift plan for the current weft below the buttons
    st.markdown("---")
    try:
        liftplan = getLiftPlan(st.session_state.draft)
        selected_weft = liftplan[st.session_state.weft_index]  # Adjust for zero-based indexing
        st.write(f"Lift Plan for Weft {st.session_state.weft_index}: {selected_weft}")
    except IndexError:
        st.error("Invalid weft index selected.")
    except Exception as e:
        st.error(f"Error displaying weft: {e}")


