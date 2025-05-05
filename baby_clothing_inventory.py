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

# --- Paths in /mnt/data so the UI and your browser inspect the very same files ---
DATA_DIR    = "/mnt/data"
DB_PATH     = os.path.join(DATA_DIR, "baby_clothes_inventory.db")
PHOTOS_DIR  = os.path.join(DATA_DIR, "baby_clothes_photos")
os.makedirs(PHOTOS_DIR, exist_ok=True)

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
    url     = f"{GITHUB_API_URL}/{filename}"
    content = base64.b64encode(image_bytes).decode("utf-8")
    # get SHA if exists
    get_resp = requests.get(url, headers=headers)
    sha      = get_resp.json().get("sha") if get_resp.status_code == 200 else None

    data = {"message": f"Upload {filename}", "content": content}
    if sha:
        data["sha"] = sha

    put_resp = requests.put(url, headers=headers, json=data)
    if put_resp.status_code in (200,201):
        return f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{GITHUB_PHOTO_FOLDER}/{filename}"
    else:
        st.error(f"GitHub upload failed: {put_resp.json()}")
        return None

# --- Page config & CSS ---
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

# --- Database setup (in /mnt/data) ---
conn   = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS baby_clothes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        category    TEXT,
        age_range   TEXT,
        photo_path  TEXT,
        description TEXT
    )
""")
conn.commit()

# --- Sidebar (no fixed index so it stays where you click) ---
menu = st.sidebar.radio(
    "Menu",
    ["Add Item", "View Inventory", "Search & Manage", "Visualize Data", "Gallery", "Export/Import"]
)

# --- Image display helper ---
def show_image(path: str, caption: str = ""):
    try:
        if path.startswith("http"):
            st.image(path, use_container_width=True, caption=caption)
        else:
            fn = os.path.basename(path.replace("\\","/"))
            p  = os.path.join(PHOTOS_DIR, fn)
            if os.path.exists(p):
                st.image(p, use_container_width=True, caption=caption)
            else:
                st.warning(f"Image file not found: {fn}")
    except Exception as e:
        st.warning(f"Could not load image: {e}")

show_image_bytes = show_image  # alias

# --- 1. Add Item ---
if menu == "Add Item":
    st.title("Add New Baby Clothing Item")

    # Force fresh widget keys after submit
    if "reset_add_item" not in st.session_state:
        st.session_state.reset_add_item = False
    flag     = st.session_state.reset_add_item
    cam_key  = f"cam_{flag}"
    upl_key  = f"upl_{flag}"
    form_key = f"form_{flag}"

    with st.form(key=form_key):
        camera_file   = st.camera_input("📷 Take a Photo", key=cam_key)
        uploaded_file = st.file_uploader("Or upload a Photo", type=["jpg","png"], key=upl_key)

        cols = st.columns(2)
        with cols[0]:
            category = st.selectbox(
                "Category",
                ["Bodysuits","Pants","Tops","Dresses","Jackets","Knitwear",
                 "Jumpers","Accessories","Shoes","Sleepwear","Sets",
                 "Home","Food Prep","Dungarees"],
                key="form_category"
            )
        with cols[1]:
            age_range = st.selectbox(
                "Age Range",
                ["0–3 months","3–6 months","6–9 months","9–12 months",
                 "12–18 months","18–24 months","24–36 months",
                 "3–4 years","4–5 years","5–6 years","No age"],
                key="form_age_range"
            )

        description = st.text_area("Description", key="form_description")
        submit      = st.form_submit_button("Add Item")

    if submit:
        if camera_file:
            photo_data = camera_file.getvalue()
            fn         = f"{int(time.time()*1000)}.jpg"
        elif uploaded_file:
            photo_data = uploaded_file.read()
            fn         = uploaded_file.name
        else:
            st.error("Please take or upload a photo.")
            st.stop()

        # 1) Save locally & INSERT
        local_p = os.path.join(PHOTOS_DIR, fn)
        with open(local_p, "wb") as f:
            f.write(photo_data)

        cursor.execute(
            "INSERT INTO baby_clothes (category, age_range, photo_path, description) VALUES (?,?,?,?)",
            (category, age_range, local_p, description)
        )
        conn.commit()
        new_id = cursor.lastrowid

        # 2) Try GitHub & UPDATE that row
        gh = upload_image_to_github(photo_data, fn)
        if gh:
            cursor.execute(
                "UPDATE baby_clothes SET photo_path = ? WHERE id = ?",
                (gh, new_id)
            )
            conn.commit()

        st.success("Item added!")
        time.sleep(1)

        # Clear form widget state so it really resets
        for k in (cam_key, upl_key, "form_category", "form_age_range", "form_description"):
            st.session_state.pop(k, None)
        st.session_state.reset_add_item = not flag

        st.rerun()

# --- 2. View Inventory ---
elif menu == "View Inventory":
    st.title("View Inventory")
    df = pd.read_sql("SELECT * FROM baby_clothes", conn)
    if df.empty:
        st.info("No items yet.")
    else:
        for cat in sorted(df["category"].unique()):
            with st.expander(cat):
                group = df[df["category"] == cat]
                cols  = st.columns(min(3, len(group)))
                for i,row in group.iterrows():
                    with cols[i % len(cols)]:
                        show_image(row["photo_path"], caption=row["description"])
                        st.write(f"**Age:** {row['age_range']}")

# --- 3. Search & Manage ---
elif menu == "Search & Manage":
    st.title("Search & Manage Inventory")
    df   = pd.read_sql("SELECT * FROM baby_clothes", conn)
    if df.empty:
        st.info("Nothing to manage.")
    else:
        cats = sorted(df["category"].unique())
        ages = sorted(df["age_range"].unique())

        sel_c = st.multiselect("Category", options=cats)
        sel_a = st.multiselect("Age Range", options=ages)
        txt   = st.text_input("Description search…")

        if not sel_c: sel_c = cats
        if not sel_a: sel_a = ages

        filt = df[df["category"].isin(sel_c) & df["age_range"].isin(sel_a)]
        if txt:
            filt = filt[filt["description"].str.contains(txt, case=False, na=False)]

        st.write(f"Showing {len(filt)} of {len(df)} items")
        if filt.empty:
            st.warning("No matches.")
        else:
            for _,row in filt.iterrows():
                with st.expander(f"{row['category']} ({row['age_range']})"):
                    show_image(row["photo_path"], caption=row["description"])
                    st.write(row["description"])

# --- 4. Visualize Data ---
elif menu == "Visualize Data":
    st.title("Visualize Inventory Data")
    df = pd.read_sql("SELECT * FROM baby_clothes", conn)
    if df.empty:
        st.info("Nothing to plot.")
    else:
        fig,ax = plt.subplots()
        df["category"].value_counts().plot(kind="bar", ax=ax)
        st.pyplot(fig)
        fig2,ax2 = plt.subplots()
        df["age_range"].value_counts().plot(kind="pie", ax=ax2, autopct="%1.1f%%")
        st.pyplot(fig2)

# --- 5. Gallery ---
elif menu == "Gallery":
    st.title("Photo Gallery")
    df = pd.read_sql("SELECT * FROM baby_clothes", conn)
    if df.empty:
        st.info("No photos yet.")
    else:
        cols = st.columns(3)
        for idx,row in df.iterrows():
            with cols[idx % len(cols)]:
                show_image(row["photo_path"], caption=f"{row['category']} ({row['age_range']})")
                st.write(row["description"])

# --- 6. Export/Import ---
elif menu == "Export/Import":
    st.title("Export / Import")
    if st.button("Export CSV"):
        df = pd.read_sql("SELECT * FROM baby_clothes", conn)
        st.download_button("Download", df.to_csv(index=False), "inventory.csv")
    imp = st.file_uploader("Import CSV", type="csv")
    if imp:
        pd.read_csv(imp).to_sql("baby_clothes", conn, if_exists="append", index=False)
        st.success("Imported!")
        time.sleep(1)
        st.rerun()

conn.close()
