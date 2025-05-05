from streamlit_back_camera_input import back_camera_input
import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import os
import time
import requests
import base64
import tempfile
import shutil
from io import BytesIO
from PIL import Image as PILImage

# --- Paths & migration from repo into tempdir ---
PROJECT_ROOT = os.getcwd()
ORIG_DB = os.path.join(PROJECT_ROOT, "baby_clothes_inventory.db")
ORIG_PHOTOS = os.path.join(PROJECT_ROOT, "baby_clothes_photos")

BASE_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(BASE_DIR, "baby_clothes_inventory.db")
PHOTOS_DIR = os.path.join(BASE_DIR, "baby_clothes_photos")

# Copy DB if not already in temp
if os.path.exists(ORIG_DB) and not os.path.exists(DB_PATH):
    shutil.copyfile(ORIG_DB, DB_PATH)

# Ensure photo directory in temp
os.makedirs(PHOTOS_DIR, exist_ok=True)
# Copy original photos
if os.path.exists(ORIG_PHOTOS):
    for fname in os.listdir(ORIG_PHOTOS):
        src = os.path.join(ORIG_PHOTOS, fname)
        dst = os.path.join(PHOTOS_DIR, fname)
        if os.path.isfile(src) and not os.path.exists(dst):
            shutil.copyfile(src, dst)

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

# --- Database setup ---
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
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

# --- Streamlit page config & CSS ---
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

# --- Sidebar ---
menu = st.sidebar.radio(
    "Menu",
    ["Add Item", "View Inventory", "Search & Manage", "Visualize Data", "Gallery", "Export/Import"],
    index=0,
)

# --- Image display helper ---
def show_image(path: str, caption: str = ""):
    try:
        if path.startswith("http"):
            st.image(path, use_container_width=True, caption=caption)
        else:
            fn = os.path.basename(path)
            local = os.path.join(PHOTOS_DIR, fn)
            if os.path.exists(local):
                st.image(local, use_container_width=True, caption=caption)
            else:
                st.warning(f"Image not found: {fn}")
    except Exception as e:
        st.warning(f"Could not load image: {e}")

# --- 1. Add Item ---
if menu == "Add Item":
    st.title("Add New Baby Clothing Item")
    if "reset_add_item" not in st.session_state:
        st.session_state.reset_add_item = False
    fk = f"form_{st.session_state.reset_add_item}"
    with st.form(key=fk):
        c1, c2 = st.columns(2)
        with c1:
            category = st.selectbox(
                "Category",
                ["Bodysuits","Pants","Tops","Dresses","Jackets","Knitwear",
                 "Jumpers","Accessories","Shoes","Sleepwear","Sets",
                 "Home","Food Prep","Dungarees"],
                key="form_category"
            )
        with c2:
            age_range = st.selectbox(
                "Age Range",
                ["0–3 months","3–6 months","6–9 months","9–12 months",
                 "12–18 months","18–24 months","24–36 months",
                 "3–4 years","4–5 years","5–6 years","No age"],
                key="form_age_range"
            )
        description = st.text_area("Description", key="form_description")
        st.write("### Upload a Photo or Take a Photo")
        cam = st.camera_input("📷 Take a Photo", key="form_cam")
        upl = st.file_uploader("Upload Photo", type=["jpg","png"], key="form_upl")
        submit = st.form_submit_button("Add Item")

        if submit:
            if cam:
                data = cam.getvalue()
                fn = f"{int(time.time()*1000)}.jpg"
            elif upl:
                data = upl.read()
                fn = upl.name
            else:
                st.error("Please upload or take a photo.")
                st.stop()

            # write locally
            local_path = os.path.join(PHOTOS_DIR, fn)
            with open(local_path, "wb") as f:
                f.write(data)

            # insert into temp DB
            cursor.execute(
                "INSERT INTO baby_clothes(category, age_range, photo_path, description) VALUES (?, ?, ?, ?)",
                (category, age_range, local_path, description),
            )
            conn.commit()
            rid = cursor.lastrowid

            # push to GitHub and update row
            gh = upload_image_to_github(data, fn)
            if gh:
                cursor.execute(
                    "UPDATE baby_clothes SET photo_path=? WHERE id=?",
                    (gh, rid),
                )
                conn.commit()

            st.success("Item added!")
            time.sleep(1)
            st.session_state.reset_add_item = not st.session_state.reset_add_item
            st.experimental_rerun()

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
                for i, row in items.iterrows():
                    with cols[i % len(cols)]:
                        show_image(row["photo_path"], row["description"])
                        st.write(f"**Age:** {row['age_range']}")

# --- 3. Search & Manage ---
elif menu == "Search & Manage":
    st.title("Search & Manage Inventory")
    df = pd.read_sql("SELECT * FROM baby_clothes", conn)
    if df.empty:
        st.info("No items to manage.")
    else:
        cats = sorted(df["category"].unique())
        ages = sorted(df["age_range"].unique())
        sel_c = st.multiselect("Category", options=cats, default=[])
        sel_a = st.multiselect("Age Range", options=ages, default=[])
        tq    = st.text_input("Search Description…")
        if not sel_c: sel_c = cats
        if not sel_a: sel_a = ages
        filt = df[df["category"].isin(sel_c) & df["age_range"].isin(sel_a)]
        if tq:
            filt = filt[filt["description"].str.contains(tq, case=False, na=False)]
        st.write(f"Showing {len(filt)} of {len(df)} items")
        if filt.empty:
            st.warning("No matches")
        else:
            for _, row in filt.iterrows():
                with st.expander(f"{row['category']} – {row['description']}"):
                    show_image(row["photo_path"], row["description"])

# --- 4. Visualize Data ---
elif menu == "Visualize Data":
    st.title("Visualize Inventory Data")
    df = pd.read_sql("SELECT * FROM baby_clothes", conn)
    if df.empty:
        st.info("No data to visualize.")
    else:
        st.subheader("Items by Category")
        fig, ax = plt.subplots(); df['category'].value_counts().plot.bar(ax=ax); st.pyplot(fig)
        st.subheader("Age Range Distribution")
        fig2, ax2 = plt.subplots(); df['age_range'].value_counts().plot.pie(ax=ax2,autopct='%1.1f%%'); st.pyplot(fig2)

# --- 5. Gallery ---
elif menu == "Gallery":
    st.title("Photo Gallery")
    df = pd.read_sql("SELECT * FROM baby_clothes", conn)
    if df.empty:
        st.info("No photos.")
    else:
        cols = st.columns(3)
        for i, row in df.iterrows():
            with cols[i % 3]:
                show_image(row['photo_path'], f"{row['category']} ({row['age_range']})")

# --- 6. Export/Import ---
elif menu == "Export/Import":
    st.title("Export / Import")
    if st.button("Export CSV"):
        df = pd.read_sql("SELECT * FROM baby_clothes", conn)
        st.download_button("Download", df.to_csv(index=False), "inventory.csv")
    up = st.file_uploader("Upload CSV to import", type="csv")
    if up:
        df2 = pd.read_csv(up)
        df2.to_sql("baby_clothes", conn, if_exists="append", index=False)
        st.success("Imported!")
        st.experimental_rerun()

conn.close()
