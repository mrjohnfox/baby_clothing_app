import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import os
import time
from PIL import Image

st.set_page_config(
    page_title="Baby Clothing Inventory",
    layout="wide",
    initial_sidebar_state="auto",
)

# Responsive CSS
st.markdown(
    """
    <style>
    /* Stack all columns on screens narrower than 768px */
    @media (max-width: 768px) {
      /* Streamlit columns have this attribute */
      [data-testid="column"] {
        width: 100% !important;
        display: block !important;
      }
      /* Make buttons full-width for easier tapping */
      button, .stButton > button {
        width: 100% !important;
        margin: 0.5rem 0 !important;
        font-size: 1rem !important;
        padding: 0.75rem !important;
      }
      /* Increase textarea/input size */
      textarea, input, .stTextInput > div > input {
        font-size: 1rem !important;
      }
      /* Reduce chart padding */
      .stPlotlyChart, .stPyplotContainer {
        padding: 0 !important;
      }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Connect to SQLite database
db_path = "baby_clothes_inventory.db"
conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()

# Ensure photos directory exists
photos_dir = "baby_clothes_photos"
PHOTOS_DIR = photos_dir
os.makedirs(photos_dir, exist_ok=True)

# Create database table if not exists
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS baby_clothes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        age_range TEXT,
        photo_path TEXT,
        description TEXT
    )
    """
)
conn.commit()

# CSS for Mobile Optimizations and Scrollable Dropdowns
st.markdown(
    """
    <style>
    button { font-size:16px !important; padding:10px !important; }
    .streamlit-expander { overflow-y:auto !important; max-height:300px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Sidebar menu
menu = st.sidebar.radio(
    "Menu",
    [
        "Add Item",
        "View Inventory",
        "Search & Manage",
        "Visualize Data",
        "Gallery",
        "Export/Import",
    ],
    index=0,
)

# Helper to display images via GitHub raw URLs
from io import BytesIO
from PIL import Image as PILImage

@st.cache_data
def load_and_prepare_image(path: str) -> bytes:
    filename = os.path.basename(path.replace('\\', '/').strip())
    full_path = os.path.join(photos_dir, filename)
    img = PILImage.open(full_path)
    max_w = 400
    if img.width > max_w:
        ratio = max_w / img.width
        img = img.resize((max_w, int(img.height * ratio)), PILImage.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()

def show_image_bytes(path: str, caption: str = ""):
    try:
        img_bytes = load_and_prepare_image(path)
        st.image(img_bytes, use_container_width=True, caption=caption)
    except Exception as e:
        st.warning(f"Could not load image: {e}")

# 1. Add Item Add Item
if menu == "Add Item":
    st.title("Add New Baby Clothing Item")

    # Toggle to force form reset after submit
    if "reset_add_item" not in st.session_state:
        st.session_state.reset_add_item = False
    form_key = f"add_item_form_{st.session_state.reset_add_item}"

    with st.expander("➕ Add New Item", expanded=True):
        with st.form(key=form_key):
            # Side-by-side on tablet/desktop, stacked on mobile
            cols = st.columns(2)
            with cols[0]:
                category = st.selectbox(
                    "Category",
                    [
                        "Bodysuits", "Pants", "Tops", "Dresses", "Jackets", "Knitwear",
                        "Jumpers", "Accessories", "Shoes", "Sleepwear", "Sets",
                        "Home", "Food Prep", "Dungarees"
                    ],
                    key="form_category",
                )
            with cols[1]:
                age_range = st.selectbox(
                    "Age Range",
                    [
                        "0–3 months", "3–6 months", "6–9 months", "9–12 months",
                        "12–18 months", "18–24 months", "24–36 months",
                        "3–4 years", "4–5 years", "5–6 years", "No age"
                    ],
                    key="form_age_range",
                )

            description = st.text_area("Description", key="form_description")
            st.write("### Upload a Photo")
            uploaded_file = st.file_uploader(
                "Upload Photo", type=["jpg", "png"], key="form_uploaded_file"
            )

            submit = st.form_submit_button("Add Item")

        if submit:
            if not uploaded_file:
                st.error("Please upload a photo.")
            else:
                local_path = os.path.join(photos_dir, uploaded_file.name)
                with open(local_path, "wb") as f:
                    f.write(uploaded_file.read())

                cursor.execute(
                    "INSERT INTO baby_clothes (category, age_range, photo_path, description) VALUES (?, ?, ?, ?)",
                    (category, age_range, local_path, description),
                )
                conn.commit()
                st.success("Baby clothing item added successfully!")
                time.sleep(2)

                # reset the form on rerun
                st.session_state.reset_add_item = not st.session_state.reset_add_item
                st.rerun()

# ← Now you’re back at the top level for `elif menu == …`
elif menu == "View Inventory":
    st.title("View Inventory")
    df = pd.read_sql("SELECT * FROM baby_clothes", conn)
    if df.empty:
        st.info("No items in inventory.")
    else:
        for cat in df["category"].unique():
            with st.expander(cat):
                items = df[df["category"] == cat]
                cols = st.columns(min(3, len(items)))
                for idx, row in items.iterrows():
                    with cols[idx % len(cols)]:
                        show_image_bytes(row["photo_path"], caption=row["description"])
                        st.write(f"**Age:** {row['age_range']}")
                        st.write(f"**Description:** {row['description']}")

# 3. Search & Manage
if menu == "Search & Manage":
    st.title("Search & Manage Inventory")
    df = pd.read_sql("SELECT * FROM baby_clothes", conn)
    if df.empty:
        st.info("No items to manage.")
    else:
        cat_sel = st.multiselect(
            "Category",
            options=sorted(df["category"].unique()),
            default=sorted(df["category"].unique()),
        )
        age_sel = st.multiselect(
            "Age Range",
            options=sorted(df["age_range"].unique()),
            default=sorted(df["age_range"].unique()),
        )
        text_query = st.text_input("Search Description…")

        filtered = df[df["category"].isin(cat_sel) & df["age_range"].isin(age_sel)]
        if text_query:
            filtered = filtered[
                filtered["description"].str.contains(text_query, case=False, na=False)
            ]

        st.write(f"Showing {len(filtered)} of {len(df)} items")

        if filtered.empty:
            st.warning("No items match those filters.")
        else:
            for _, row in filtered.iterrows():
                with st.expander(f"{row['category']} ({row['age_range']}) - {row['description']}"):
                    show_image_bytes(row["photo_path"], row["description"])
                    st.write(f"**Category:** {row['category']}")
                    st.write(f"**Age Range:** {row['age_range']}")
                    st.write(f"**Description:** {row['description']}")

                    edit_key = f"edit_{row['id']}"
                    if st.button(f"Edit Item {row['id']}", key=edit_key):
                        st.session_state[edit_key] = True
                    if st.session_state.get(edit_key, False):
                        with st.form(key=f"edit_form_{row['id']}"):
                            new_category = st.selectbox(
                                "Category",
                                [
                                    "Bodysuits", "Pants", "Tops", "Dresses", "Jackets", "Knitwear",
                                    "Jumpers", "Accessories", "Shoes", "Sleepwear", "Sets", 
                                    "Home", "Food Prep", "Dungarees"
                                ],
                                index=[
                                    "Bodysuits", "Pants", "Tops", "Dresses", "Jackets", "Knitwear",
                                    "Jumpers", "Accessories", "Shoes", "Sleepwear", "Sets", 
                                    "Home", "Food Prep", "Dungarees"
                                ].index(row["category"]),
                            )
                            new_age_range = st.selectbox(
                                "Age Range",
                                [
                                    "0–3 months", "3–6 months", "6–9 months", "9–12 months", 
                                    "12–18 months", "18–24 months", "24–36 months", "3–4 years", 
                                    "4–5 years", "5–6 years", "No age"
                                ],
                                index=[
                                    "0–3 months", "3–6 months", "6–9 months", "9–12 months", 
                                    "12–18 months", "18–24 months", "24–36 months", "3–4 years", 
                                    "4–5 years", "5–6 years", "No age"
                                ].index(row["age_range"]),
                            )
                            new_description = st.text_area("Description", row["description"])
                            if st.form_submit_button("Save Changes"):
                                cursor.execute(
                                    """
                                    UPDATE baby_clothes
                                    SET category = ?, age_range = ?, description = ?
                                    WHERE id = ?
                                    """,
                                    (new_category, new_age_range, new_description, row["id"]),
                                )
                                conn.commit()
                                st.success("Item updated successfully!")
                                time.sleep(2)
                                st.rerun()

                    delete_key = f"delete_{row['id']}"
                    if st.button(f"Delete Item {row['id']}", key=delete_key):
                        cursor.execute("DELETE FROM baby_clothes WHERE id = ?", (row["id"],))
                        conn.commit()
                        st.warning("Item deleted successfully!")
                        time.sleep(2)
                        st.rerun()

# 4. Visualize Data
elif menu == "Visualize Data":
    st.title("Visualize Inventory Data")
    df = pd.read_sql("SELECT * FROM baby_clothes", conn)
    if df.empty:
        st.info("No data to visualize.")
    else:
        st.subheader("Number of Items by Category")
        fig, ax = plt.subplots()
        df['category'].value_counts().plot(kind='bar', ax=ax)
        st.pyplot(fig)
        st.subheader("Age Range Distribution")
        fig2, ax2 = plt.subplots()
        df['age_range'].value_counts().plot(kind='pie', ax=ax2, autopct='%1.1f%%')
        st.pyplot(fig2)

# 5. Gallery
elif menu == "Gallery":
    st.title("Photo Gallery")
    df = pd.read_sql("SELECT * FROM baby_clothes", conn)
    if df.empty:
        st.info("No photos available.")
    else:
        cols = st.columns(3)
        for idx, row in df.iterrows():
            with cols[idx % 3]:
                show_image_bytes(row['photo_path'], caption=f"{row['category']} ({row['age_range']})")
                st.write(row['description'])

# 6. Export/Import
elif menu == "Export/Import":
    st.title("Export and Import Data")
    st.subheader("Export Inventory")
    if st.button("Export as CSV"):
        df = pd.read_sql("SELECT * FROM baby_clothes", conn)
        st.download_button("Download Inventory", df.to_csv(index=False), "inventory.csv")
    st.subheader("Import Inventory")
    uploaded_csv = st.file_uploader("Upload CSV to import", type="csv")
    if uploaded_csv:
        try:
            imported = pd.read_csv(uploaded_csv)
            imported.to_sql("baby_clothes", conn, if_exists="append", index=False)
            st.success("Data imported successfully!")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"An error occurred: {e}")

# Close connection
conn.close()
