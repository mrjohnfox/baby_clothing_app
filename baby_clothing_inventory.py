from streamlit_back_camera_input import back_camera_input
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os
import time
import requests
import base64
from io import BytesIO
from PIL import Image as PILImage
from supabase import create_client, Client

# --- Supabase client setup ---
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["key"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- GitHub upload helper (unchanged) ---
GITHUB_TOKEN        = st.secrets["github"]["token"]
GITHUB_REPO         = "mrjohnfox/baby_clothing_app"
GITHUB_PHOTO_FOLDER = "baby_clothes_photos"
GITHUB_API_URL      = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PHOTO_FOLDER}"

def upload_image_to_github(image_bytes: bytes, filename: str) -> str | None:
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github+json",
    }
    url     = f"{GITHUB_API_URL}/{filename}"
    content = base64.b64encode(image_bytes).decode("utf-8")

    get_resp = requests.get(url, headers=headers)
    sha      = get_resp.json().get("sha") if get_resp.status_code == 200 else None

    data = {"message": f"Upload {filename}", "content": content}
    if sha:
        data["sha"] = sha

    put_resp = requests.put(url, headers=headers, json=data)
    if put_resp.status_code in (200, 201):
        return (
            f"https://raw.githubusercontent.com/"
            f"{GITHUB_REPO}/main/{GITHUB_PHOTO_FOLDER}/{filename}"
        )
    else:
        st.error(f"GitHub upload failed: {put_resp.json()}")
        return None

# --- Helper to always fetch fresh inventory from Supabase ---
@st.cache_data
def read_inventory() -> pd.DataFrame:
    resp = supabase.table("baby_clothes").select("*").execute()
    data = resp.data or []
    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values("category", ignore_index=True)
    return df

# --- Page config & CSS ---
st.set_page_config(
    page_title="Baby Clothing Inventory",
    layout="wide",
    initial_sidebar_state="auto",
)

# Base responsive CSS
st.markdown("""
    <style>
    @media (max-width: 768px) {
      [data-testid="column"] { width:100% !important; display:block !important; }
      button, .stButton>button { width:100% !important; margin:0.5rem 0!important;
                                 font-size:1rem!important; padding:0.75rem!important; }
      textarea, input, .stTextInput>div>input { font-size:1rem!important; }
      .stPlotlyChart, .stPyplotContainer { padding:0!important; }
    }
    button { font-size:16px!important; padding:10px!important; }
    .streamlit-expander { overflow-y:auto!important; max-height:300px; }
    </style>
""", unsafe_allow_html=True)

# Added css for gallery fix
st.markdown("""
<style>
.gallery {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  overflow-x: auto;
  padding: 1rem 0;
}
.gallery-item {
  flex: 0 0 auto;
  width: 200px;
}
.gallery-item img {
  width: 100%;
  height: auto;
  border-radius: 0.5rem;
}
.gallery-item p {
  text-align: center;
  margin-top: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

# Mobile-first gallery CSS
st.markdown("""
    <style>
    /* Full-width columns on very small screens */
    @media (max-width: 600px) {
      [data-testid="column"] {
        width: 100% !important;
        display: block !important;
      }
    }

    /* Swipeable Gallery Container */
    .gallery {
      display: flex;
      overflow-x: auto;
      gap: 1rem;
      padding: 1rem 0;
      -webkit-overflow-scrolling: touch;
    }
    .gallery-item {
      flex: 0 0 auto;
      width: 80%;
      max-width: 300px;
    }
    .gallery-item img {
      width: 100%;
      height: auto;
      object-fit: cover;
      border-radius: 8px;
    }
    .gallery-item p {
      text-align: center;
      margin: 0.5rem 0 0;
      font-size: 0.9rem;
    }

    /* Three-across on larger screens */
    @media (min-width: 768px) {
      .gallery-item {
        width: calc((100% - 2rem) / 3);
        max-width: none;
      }
    }
    </style>
""", unsafe_allow_html=True)

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
            st.warning("Invalid image path")
    except Exception as e:
        st.warning(f"Could not load image: {e}")

# --- 1. Add Item ---
if menu == "Add Item":
    st.title("Add New Baby Clothing Item")
    if "reset_add_item" not in st.session_state:
        st.session_state.reset_add_item = False
    reset = st.session_state.reset_add_item
    form_key = f"add_item_form_{reset}"

    with st.form(key=form_key):
        c1, c2 = st.columns(2)
        with c1:
            category = st.selectbox(
                "Category",
                ["Bodysuits","Pants","Tops","Dresses","Jackets","Knitwear",
                 "Jumpers","Accessories","Shoes","Sleepwear","Sets",
                 "Home","Food Prep","Dungarees"],
                key=f"cat_{reset}"
            )
        with c2:
            age_range = st.selectbox(
                "Age Range",
                ["0–3 months","3–6 months","6–9 months","9–12 months",
                 "12–18 months","18–24 months","24–36 months",
                 "3–4 years","4–5 years","5–6 years","No age"],
                key=f"age_{reset}"
            )

        description = st.text_area("Description", key=f"desc_{reset}")
        st.write("### Upload or Snap a Photo")
        cam = st.camera_input("📷 Take a Photo", key=f"cam_{reset}")
        upl = st.file_uploader("Upload Photo", type=["jpg","png"], key=f"upl_{reset}")
        submit = st.form_submit_button("Add Item")

    if submit:
        if cam:
            img_bytes = cam.getvalue()
            fn = f"{int(time.time()*1000)}.jpg"
        elif upl:
            img_bytes = upl.read()
            fn = upl.name
        else:
            st.error("Please provide a photo.")
            st.stop()

        gh_url = upload_image_to_github(img_bytes, fn)
        if not gh_url:
            st.stop()

        supabase.table("baby_clothes").insert({
            "category":    category,
            "age_range":   age_range,
            "photo_path":  gh_url,
            "description": description,
        }).execute()

        read_inventory.clear()
        st.success("Item added!")
        st.session_state.reset_add_item = not reset
        st.rerun()

# --- 2. View Inventory ---
elif menu == "View Inventory":
    st.title("View Inventory")
    df = read_inventory()
    if df.empty:
        st.info("No items in inventory.")
    else:
        for cat in df["category"].unique():
            with st.expander(cat):
                items = df[df["category"] == cat]
                cols = st.columns(min(3, len(items)))
                for i, row in items.reset_index().iterrows():
                    with cols[i % len(cols)]:
                        show_image(row["photo_path"], caption=row["description"])
                        st.write(f"**Age:** {row['age_range']}")

# --- 3. Search & Manage ---
elif menu == "Search & Manage":
    st.title("Search & Manage Inventory")
    df = read_inventory()
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
            for row in filt.itertuples():
                with st.expander(f"{row.category} – {row.description}"):
                    show_image(row.photo_path, caption=row.description)
                    st.write(f"**Age:** {row.age_range}")
                    # (edit/delete forms remain unchanged)

# --- 4. Visualize Data ---
elif menu == "Visualize Data":
    st.title("Visualize Inventory Data")
    df = read_inventory()
    if df.empty:
        st.info("No data to visualize.")
    else:
        st.subheader("Items by Category")
        fig, ax = plt.subplots()
        df["category"].value_counts().plot.bar(ax=ax)
        st.pyplot(fig)
        st.subheader("Age Range Distribution")
        fig2, ax2 = plt.subplots()
        df["age_range"].value_counts().plot.pie(ax=ax2, autopct="%1.1f%%")
        st.pyplot(fig2)

# --- 5. Gallery (HTML carousel) ---
elif menu == "Gallery":
    st.title("Photo Gallery")
    df = read_inventory()
    if df.empty:
        st.info("No photos available.")
    else:
        # build one big HTML block
        gallery_html = '<div class="gallery">'
        for row in df.itertuples():
            gallery_html += f'''
            <div class="gallery-item">
              <img src="{row.photo_path}" alt="{row.description}" />
              <p>{row.category} ({row.age_range})</p>
            </div>
            '''
        gallery_html += '</div>'

        # render it as HTML
        st.markdown(gallery_html, unsafe_allow_html=True)

# --- 6. Export/Import ---
elif menu == "Export/Import":
    st.title("Export / Import")
    if st.button("Export CSV"):
        df = read_inventory()
        st.download_button("Download CSV", df.to_csv(index=False), "inventory.csv")
    up = st.file_uploader("Upload CSV to import", type="csv")
    if up:
        df2 = pd.read_csv(up)
        supabase.table("baby_clothes").insert(df2.to_dict("records")).execute()
        st.success("Imported!")
        st.rerun()
