import streamlit as st
import os
from pathlib import Path
from wif import WIFReader
from render import ImageRenderer
from PIL import Image, ImageDraw, ImageFont  # Ensure ImageFont is imported

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
        st.markdown(
        f"""
        <div style='text-align: center; font-size: 24px; font-weight: bold;'>
            {st.session_state.weft_index}
        </div>
        """,
        unsafe_allow_html=True,
    )

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
            st.write("Previous Weft:")
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
            st.write("Next Weft:")
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
                    Current Weft: {st.session_state.weft_index}
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


