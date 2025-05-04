import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import os
import time  # <-- Ensure we have time imported for delays
from PIL import Image

# Connect to SQLite database
db_path = "baby_clothes_inventory.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Ensure photos directory exists
photos_dir = "baby_clothes_photos"
if not os.path.exists(photos_dir):
    os.makedirs(photos_dir)

# Create database table if not exists
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

# CSS for Mobile Optimizations and Scrollable Dropdowns
st.markdown(
    """
    <style>
    button {
        font-size: 16px !important;
        padding: 10px !important;
    }
    .streamlit-expander {
        overflow-y: auto !important;
        max-height: 300px; /* Adjust dropdown max height */
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Sidebar menu
menu = st.sidebar.radio(
    "Menu",
    ["Add Item", "View Inventory", "Search & Edit", "Visualize Data", "Gallery", "Export/Import"],
    index=0,  # Default to Add Item page
)

if menu == "Add Item":
    st.title("Add New Baby Clothing Item")

    # Initialize session state for reset
    if "reset_add_item" not in st.session_state:
        st.session_state.reset_add_item = False

    with st.form(key="add_item_form"):
        category = st.radio(
            "Category",
            [
                "Bodysuits", "Pants", "Tops", "Dresses", "Jackets", "Knitwear",
                "Jumpers", "Accessories", "Shoes", "Sleepwear", "Sets", 
                "Home", "Food Prep", "Dungarees"
            ],
            key="form_category" if st.session_state.reset_add_item else "category",
        )
        age_range = st.radio(
            "Age Range",
            [
                "0–3 months", "3–6 months", "6–9 months", "9–12 months", "12–18 months", 
                "18–24 months", "24–36 months", "3–4 years", "4–5 years", "5–6 years", "No age"
            ],
            key="form_age_range" if st.session_state.reset_add_item else "age_range",
        )
        description = st.text_area("Description", key="form_description" if st.session_state.reset_add_item else "description")

        st.write("### Upload a Photo")
        uploaded_file = st.file_uploader("Upload Photo", type=["jpg", "png"], key="form_uploaded_file" if st.session_state.reset_add_item else "uploaded_file")

        submit_button = st.form_submit_button(label="Add Item")

    if submit_button:
        photo_path = None

        if uploaded_file:
            photo_path = os.path.join(photos_dir, uploaded_file.name)
            with open(photo_path, "wb") as f:
                f.write(uploaded_file.read())

        if photo_path:
            cursor.execute(
                """
                INSERT INTO baby_clothes (category, age_range, photo_path, description)
                VALUES (?, ?, ?, ?)
                """,
                (category, age_range, photo_path, description),
            )
            conn.commit()
            st.success("Baby clothing item added successfully!")

            # Add a delay to show the success message
            time.sleep(2)  # 2-second delay

            # Force refresh using session state
            st.session_state.reset_add_item = not st.session_state.reset_add_item
            st.rerun()  # Refresh the page after the delay
        else:
            st.error("Please upload a photo.")

elif menu == "View Inventory":
    st.title("View Inventory")
    df = pd.read_sql("SELECT * FROM baby_clothes", conn)

    if not df.empty:
        categories = df["category"].unique()
        for category in categories:
            with st.expander(category):
                category_items = df[df["category"] == category]

                if len(category_items) >= 3:
                    col1, col2, col3 = st.columns(3)
                elif len(category_items) == 2:
                    col1, col2 = st.columns(2)
                    col3 = None
                elif len(category_items) == 1:
                    col1 = st.container()
                    col2, col3 = None, None
                else:
                    st.write("No items in this category.")
                    continue

                for idx, row in category_items.iterrows():
                    if len(category_items) >= 3:
                        col = [col1, col2, col3][idx % 3]
                    elif len(category_items) == 2:
                        col = [col1, col2][idx % 2]
                    elif len(category_items) == 1:
                        col = col1

                    with col:
                        try:

                    filename = os.path.basename(row["photo_path"].strip())

                    github_image_url = f"https://raw.githubusercontent.com/mrjohnfox/baby_clothing_app/main/baby_clothes_photos/{filename}"

                    st.image(github_image_url, use_container_width=True, caption=row.get("description", ""))

                except Exception as e:

                    st.warning(f"Could not load image: {e}")

elif menu == "Search & Edit":
    st.title("Search & Edit Items")
    df = pd.read_sql("SELECT * FROM baby_clothes", conn)

    if not df.empty:
        for index, row in df.iterrows():
            with st.expander(f"{row['category']} ({row['age_range']}) - {row['description']}"):
                try:

                    filename = os.path.basename(row["photo_path"].strip())

                    github_image_url = f"https://raw.githubusercontent.com/mrjohnfox/baby_clothing_app/main/baby_clothes_photos/{filename}"

                    st.image(github_image_url, use_container_width=True, caption=row.get("description", ""))

                except Exception as e:

                    st.warning(f"Could not load image: {e}")

                st.write(f"**Category:** {row['category']}")
                st.write(f"**Age Range:** {row['age_range']}")
                st.write(f"**Description:** {row['description']}")

                # ------ EDIT FEATURE ------
                if st.button(f"Edit Item {row['id']}"):
                    st.session_state[f"editing_{row['id']}"] = True

                if st.session_state.get(f"editing_{row['id']}", False):
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
                            ].index(row["category"])
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
                            ].index(row["age_range"])
                        )
                        new_description = st.text_area("Description", row["description"])

                        edit_submit = st.form_submit_button("Submit Changes")

                        if edit_submit:
                            cursor.execute(
                                """
                                UPDATE baby_clothes
                                SET category = ?, age_range = ?, description = ?
                                WHERE id = ?
                                """,
                                (new_category, new_age_range, new_description, row["id"]),
                            )
                            conn.commit()
                            st.success(f"Item {row['id']} updated successfully!")
                            
                            # Delay, then refresh
                            time.sleep(2)
                            st.rerun()

                # ------ DELETE FEATURE ------
                if st.button(f"Delete Item {row['id']}"):
                    cursor.execute("DELETE FROM baby_clothes WHERE id = ?", (row["id"],))
                    conn.commit()
                    st.warning(f"Item {row['id']} deleted successfully!")

                    # Delay, then refresh
                    time.sleep(2)
                    st.rerun()
    else:
        st.info("No items found in inventory.")

elif menu == "Gallery":
    st.title("Photo Gallery")
    df = pd.read_sql("SELECT * FROM baby_clothes", conn)

    if not df.empty:
        col1, col2, col3 = st.columns(3)
        for idx, row in df.iterrows():
            col = [col1, col2, col3][idx % 3]
                    with col:
                try:

                    filename = os.path.basename(row["photo_path"].strip())

                    github_image_url = f"https://raw.githubusercontent.com/mrjohnfox/baby_clothing_app/main/baby_clothes_photos/{filename}"

                    st.image(github_image_url, use_container_width=True, caption=row.get("description", ""))

                except Exception as e:

                    st.warning(f"Could not load image: {e}")

elif menu == "Export/Import":
    st.title("Export and Import Data")

    st.subheader("Export Inventory")
    export_button = st.button("Export as CSV")
    if export_button:
        df = pd.read_sql("SELECT * FROM baby_clothes", conn)
        if not df.empty:
            csv_path = "baby_clothes_inventory.csv"
            df.to_csv(csv_path, index=False)
            with open(csv_path, "rb") as f:
                st.download_button(
                    label="Download CSV",
                    data=f,
                    file_name="baby_clothes_inventory.csv",
                    mime="text/csv",
                )
        else:
            st.warning("No data available to export.")

    st.subheader("Import Inventory")
    uploaded_csv = st.file_uploader("Upload a CSV file", type="csv")
    if uploaded_csv:
    try:
            imported_df = pd.read_csv(uploaded_csv)
            imported_df.to_sql("baby_clothes", conn, if_exists="append", index=False)
            st.success("Data imported successfully!")
                except Exception as e:
            st.error(f"An error occurred: {e}")

elif menu == "Visualize Data":
    st.title("Visualize Inventory Data")
    df = pd.read_sql("SELECT * FROM baby_clothes", conn)

    if not df.empty:
        st.subheader("Number of Items by Category")
        fig, ax = plt.subplots()
        df["category"].value_counts().plot(kind="bar", ax=ax)
        ax.set_title("Number of Items by Category")
        st.pyplot(fig)

        st.subheader("Age Range Distribution")
        fig, ax = plt.subplots()
        df["age_range"].value_counts().plot(kind="pie", ax=ax, autopct="%1.1f%%")
        ax.set_title("Age Range Distribution")
        st.pyplot(fig)
        else:
        st.info("No data to visualize.")

conn.close()