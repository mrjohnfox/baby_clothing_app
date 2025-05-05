from streamlit_back_camera_input import back_camera_input
import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import os
import time
import requests
import base64
from io import BytesIO
from PIL import Image as PILImage

# --- GitHub upload helper ---
GITHUB_TOKEN = st.secrets["github"]["token"]
GITHUB_REPO = "mrjohnfox/baby_clothing_app"
GITHUB_PHOTO_FOLDER = "baby_clothes_photos"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PHOTO_FOLDER}"

def upload_image_to_github(image_bytes, filename):
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    url = f"{GITHUB_API_URL}/{filename}"
    content = base64.b64encode(image_bytes).decode("utf-8")

    # get SHA if exists
    get_resp = requests.get(url, headers=headers)
    sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None

    data = {"message": f"Upload {filename}", "content": content}
    if sha:
        data["sha"] = sha

    put_resp = requests.put(url, headers=headers, json=data)
    if put_resp.status_code in (200, 201):
        return (
            f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/"
            f"{GITHUB_PHOTO_FOLDER}/{filename}"
        )
    else:
        st.error(f"GitHub upload failed: {put_resp.json()}")
        return None

# --- Page config & responsive CSS ---
st.set_page_config(
    page_title="Baby Clothing Inventory",
    layout="wide",
    initial_sidebar_state="auto",
)
st.markdown(
    """
    <style>
    @media (max-width: 768px) {
      [data-testid="column"] { width:100% !important; display:block !important; }
      button, .stButton>button { width:100% !important; margin:0.5rem 0!important; font-size:1rem!important; padding:0.75rem!important; }
      textarea, input, .stTextInput>div>input { font-size:1rem!important; }
      .stPlotlyChart, .stPyplotContainer { padding:0!important; }
    }
    button { font-size:16px!important; padding:10px!important; }
    .streamlit-expander { overflow-y:auto!important; max-height:300px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Database setup ---
db_path = "baby_clothes_inventory.db"
conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()

# Debug: show which file and tables
st.write("Using database file:", os.path.abspath(db_path))
tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
st.write("Tables in database:", tables)

photos_dir = "baby_clothes_photos"
os.makedirs(photos_dir, exist_ok=True)

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

# --- Sidebar menu ---
menu = st.sidebar.radio(
    "Menu",
    ["Add Item", "View Inventory", "Search & Manage", "Visualize Data", "Gallery", "Export/Import"],
    index=0,
)

# --- Image helper ---
def show_image(path: str, caption: str = ""):
    try:
        if path.startswith("http"):
            st.image(path, use_container_width=True, caption=caption)
        else:
            filename = os.path.basename(path.replace("\\", "/"))
            local_file = os.path.join(photos_dir, filename)
            if os.path.exists(local_file):
                st.image(local_file, use_container_width=True, caption=caption)
            else:
                st.warning(f"Image file not found: {filename}")
    except Exception as e:
        st.warning(f"Could not load image: {e}")

show_image_bytes = show_image  # alias

# --- 1. Add Item ---
if menu == "Add Item":
    st.title("Add New Baby Clothing Item")
    if "reset_add_item" not in st.session_state:
        st.session_state.reset_add_item = False
    form_key = f"add_item_form_{st.session_state.reset_add_item}"

    with st.form(key=form_key):
        cols = st.columns(2)
        with cols[0]:
            category = st.selectbox(
                "Category",
                [
                    "Bodysuits","Pants","Tops","Dresses","Jackets","Knitwear",
                    "Jumpers","Accessories","Shoes","Sleepwear","Sets",
                    "Home","Food Prep","Dungarees"
                ],
                key="form_category",
            )
        with cols[1]:
            age_range = st.selectbox(
                "Age Range",
                [
                    "0–3 months","3–6 months","6–9 months","9–12 months",
                    "12–18 months","18–24 months","24–36 months",
                    "3–4 years","4–5 years","5–6 years","No age"
                ],
                key="form_age_range",
            )

        description = st.text_area("Description", key="form_description")

        st.write("### Upload a Photo or Take a Photo")
        camera_file   = st.camera_input("Take a Photo", key="form_camera_file")
        uploaded_file = st.file_uploader("Upload Photo", type=["jpg", "png"], key="form_uploaded_file")

        submit = st.form_submit_button("Add Item")

        if submit:
            # 1) grab bytes + filename
            if camera_file is not None:
                photo_data = camera_file.getvalue()
                filename   = f"{int(time.time()*1000)}.jpg"
            elif uploaded_file is not None:
                photo_data = uploaded_file.read()
                filename   = uploaded_file.name
            else:
                st.error("Please upload or take a photo.")
                st.stop()

            # 2) write locally & insert
            local_path = os.path.join(photos_dir, filename)
            with open(local_path, "wb") as f:
                f.write(photo_data)

            cursor.execute(
                "INSERT INTO baby_clothes (category, age_range, photo_path, description) "
                "VALUES (?, ?, ?, ?)",
                (category, age_range, local_path, description),
            )
            conn.commit()
            row_id = cursor.lastrowid

            # Debug: fetch the last 5 rows
            df_debug = pd.read_sql("SELECT * FROM baby_clothes ORDER BY id DESC LIMIT 5", conn)
            st.write("🔍 just-inserted rows:", df_debug)

            # 3) try GitHub upload & update
            github_url = upload_image_to_github(photo_data, filename)
            if github_url:
                cursor.execute(
                    "UPDATE baby_clothes SET photo_path = ? WHERE id = ?",
                    (github_url, row_id),
                )
                conn.commit()

            st.success("Baby clothing item added!")
            time.sleep(1)
            st.session_state.reset_add_item = not st.session_state.reset_add_item
            st.rerun()

# --- 2. View Inventory ---
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
                        show_image(row["photo_path"], caption=row["description"])
                        st.write(f"**Age:** {row['age_range']}")
                        st.write(f"**Description:** {row['description']}")

# --- 3. Search & Manage ---
elif menu == "Search & Manage":
    st.title("Search & Manage Inventory")
    df = pd.read_sql("SELECT * FROM baby_clothes", conn)
    if df.empty:
        st.info("No items to manage.")
    else:
        cat_options = sorted(df["category"].unique())
        age_options = sorted(df["age_range"].unique())

        cat_sel = st.multiselect("Category", options=cat_options, default=[])
        age_sel = st.multiselect("Age Range", options=age_options, default=[])
        text_query = st.text_input("Search Description…")

        if not cat_sel:
            cat_sel = cat_options
        if not age_sel:
            age_sel = age_options

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
                    show_image(row["photo_path"], caption=row["description"])
                    st.write(f"**Category:** {row['category']}")
                    st.write(f"**Age Range:** {row['age_range']}")
                    st.write(f"**Description:** {row['description']}")

                    # edit/delete logic unchanged…

# (Visualize, Gallery, Export/Import follow exactly as before)

conn.close()
