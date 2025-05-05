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
GITHUB_TOKEN        = st.secrets["github"]["token"]
GITHUB_REPO         = "mrjohnfox/baby_clothing_app"
GITHUB_PHOTO_FOLDER = "baby_clothes_photos"
GITHUB_API_URL      = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PHOTO_FOLDER}"

def upload_image_to_github(image_bytes, filename):
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github+json",
    }
    url = f"{GITHUB_API_URL}/{filename}"
    content = base64.b64encode(image_bytes).decode("utf-8")
    # Fetch existing SHA if present
    get_resp = requests.get(url, headers=headers)
    sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None
    data = {"message": f"Upload {filename}", "content": content}
    if sha:
        data["sha"] = sha
    put_resp = requests.put(url, headers=headers, json=data)
    if put_resp.status_code in (200, 201):
        return f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{GITHUB_PHOTO_FOLDER}/{filename}"
    else:
        st.error(f"GitHub upload failed: {put_resp.json()}")
        return None

# --- Page config & responsive CSS ---
st.set_page_config(
    page_title="Baby Clothing Inventory",
    layout="wide",
    initial_sidebar_state="auto",
)
st.markdown("""
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
""", unsafe_allow_html=True)

# --- Database setup ---
db_path = "baby_clothes_inventory.db"
conn    = sqlite3.connect(db_path, check_same_thread=False)
cursor  = conn.cursor()

photos_dir = "baby_clothes_photos"
os.makedirs(photos_dir, exist_ok=True)

cursor.execute("""
    CREATE TABLE IF NOT EXISTS baby_clothes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        age_range TEXT,
        photo_path TEXT,
        description TEXT
    )
""")
conn.commit()

# --- Sidebar menu ---
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
            fn         = os.path.basename(path.replace("\\","/"))
            local_file = os.path.join(photos_dir, fn)
            if os.path.exists(local_file):
                st.image(local_file, use_container_width=True, caption=caption)
            else:
                st.warning(f"Image file not found: {fn}")
    except Exception as e:
        st.warning(f"Could not load image: {e}")

show_image_bytes = show_image  # alias

# --- 1. Add Item ---
if menu == "Add Item":
    st.title("Add New Baby Clothing Item")

    # reset flag toggles the form keys so they clear
    if "reset_add_item" not in st.session_state:
        st.session_state.reset_add_item = False
    reset_flag  = st.session_state.reset_add_item
    form_key     = f"add_item_form_{reset_flag}"
    camera_key   = f"form_camera_{reset_flag}"
    upload_key   = f"form_upload_{reset_flag}"

    with st.form(key=form_key):
        # 1) camera first
        camera_file = st.camera_input("📷 Take a Photo", key=camera_key)
        # 2) then upload
        uploaded_file = st.file_uploader("Or upload a Photo", type=["jpg","png"], key=upload_key)

        # 3) metadata
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
        submit      = st.form_submit_button("Add Item")

    # Handle the submission _after_ closing the with‐block
    if submit:
        if camera_file:
            photo_data = camera_file.getvalue()
            filename   = f"{int(time.time()*1000)}.jpg"
        elif uploaded_file:
            photo_data = uploaded_file.read()
            filename   = uploaded_file.name
        else:
            st.error("Please either take a photo or upload one.")
            st.stop()

        # Save locally & INSERT
        local_path = os.path.join(photos_dir, filename)
        with open(local_path, "wb") as f:
            f.write(photo_data)

        cursor.execute(
            "INSERT INTO baby_clothes (category, age_range, photo_path, description) VALUES (?, ?, ?, ?)",
            (category, age_range, local_path, description)
        )
        conn.commit()
        new_id = cursor.lastrowid

        # Try GitHub upload & UPDATE
        gh_url = upload_image_to_github(photo_data, filename)
        if gh_url:
            cursor.execute(
                "UPDATE baby_clothes SET photo_path = ? WHERE id = ?",
                (gh_url, new_id)
            )
            conn.commit()

        st.success("Item added successfully!")
        time.sleep(1)

        # Clear the old form keys
        for k in (camera_key, upload_key, "form_category", "form_age_range", "form_description"):
            if k in st.session_state:
                del st.session_state[k]
        # Toggle our reset flag to force new keys next render
        st.session_state.reset_add_item = not reset_flag

        st.rerun()

# --- 2. View Inventory ---
elif menu == "View Inventory":
    st.title("View Inventory")
    df = pd.read_sql("SELECT * FROM baby_clothes", conn)
    if df.empty:
        st.info("No items in inventory.")
    else:
        for cat in sorted(df["category"].unique()):
            with st.expander(cat):
                items = df[df["category"] == cat]
                cols  = st.columns(min(3, len(items)))
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
        cats = sorted(df["category"].unique())
        ages = sorted(df["age_range"].unique())

        sel_cats = st.multiselect("Category", options=cats, default=[])
        sel_ages = st.multiselect("Age Range", options=ages, default=[])
        txt      = st.text_input("Search Description…")

        if not sel_cats:
            sel_cats = cats
        if not sel_ages:
            sel_ages = ages

        filt = df[df["category"].isin(sel_cats) & df["age_range"].isin(sel_ages)]
        if txt:
            filt = filt[filt["description"].str.contains(txt, case=False, na=False)]

        st.write(f"Showing {len(filt)} of {len(df)} items")
        if filt.empty:
            st.warning("No items match.")
        else:
            for _, row in filt.iterrows():
                with st.expander(f"{row['category']} ({row['age_range']})"):
                    show_image(row["photo_path"], caption=row["description"])
                    st.write(f"**Description:** {row['description']}")

# --- 4. Visualize Data ---
elif menu == "Visualize Data":
    st.title("Visualize Inventory Data")
    df = pd.read_sql("SELECT * FROM baby_clothes", conn)
    if df.empty:
        st.info("No data to visualize.")
    else:
        fig, ax = plt.subplots()
        df["category"].value_counts().plot(kind="bar", ax=ax)
        st.pyplot(fig)
        fig2, ax2 = plt.subplots()
        df["age_range"].value_counts().plot(kind="pie", ax=ax2, autopct="%1.1f%%")
        st.pyplot(fig2)

# --- 5. Gallery ---
elif menu == "Gallery":
    st.title("Photo Gallery")
    df = pd.read_sql("SELECT * FROM baby_clothes", conn)
    if df.empty:
        st.info("No photos available.")
    else:
        cols = st.columns(3)
        for idx, row in df.iterrows():
            with cols[idx % 3]:
                show_image(row["photo_path"], caption=f"{row['category']} ({row['age_range']})")
                st.write(row["description"])

# --- 6. Export/Import ---
elif menu == "Export/Import":
    st.title("Export and Import Data")
    if st.button("Export as CSV"):
        df = pd.read_sql("SELECT * FROM baby_clothes", conn)
        st.download_button("Download Inventory", df.to_csv(index=False), "inventory.csv")
    up_csv = st.file_uploader("Upload CSV to import", type="csv")
    if up_csv:
        df_in = pd.read_csv(up_csv)
        df_in.to_sql("baby_clothes", conn, if_exists="append", index=False)
        st.success("Data imported!")
        time.sleep(1)
        st.rerun()

conn.close()
