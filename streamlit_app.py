import streamlit as st
import pandas as pd
import os

# -------- LOGIN SECTION --------
st.set_page_config(page_title="Project Cost Estimator", layout="centered")

st.title("Secure Project Cost Estimator")

# Hardcoded login credentials
USERNAME = "wouterleenknegt"
PASSWORD = "wachtwoordvanpapa?"

# Session state to remember login
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    with st.form("login_form"):
        st.subheader("Login required")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login = st.form_submit_button("Login")

        if login:
            if username == USERNAME and password == PASSWORD:
                st.session_state.authenticated = True
                st.success("Login successful. Please press login again.")
                st.stop()
            else:
                st.error("Invalid credentials. Please try again.")
    st.stop()

# -------- MAIN APP (only visible after login) --------

# Load or initialize the CSV database
CSV_PATH = "database.csv"
if os.path.exists(CSV_PATH):
    df = pd.read_csv(CSV_PATH)
else:
    df = pd.DataFrame(columns=["name", "destination", "special_features", "surface", "finish", "price", "price_per_m2"])

# Page selection
page = st.sidebar.radio("Navigation", ["Forecast price", "Add new project", "View and modify projects"])

# =============================
# 1. FORECAST PRICE
# =============================
if page == "Forecast price":
    st.title("Forecast Project Price")

    st.markdown("""
    Based on similar past projects in our database, this tool estimates the average price per square meter  
    and calculates the estimated total cost by multiplying with the surface you provide.
    """)

    destination = st.selectbox("Project destination", ["SME", "hangar", "hangar with office", "shoppincenter"])
    special_features = st.checkbox("Are special techniques present (e.g. HVAC, solar panels, etc.)?")
    special_value = "yes" if special_features else "no"
    input_surface = st.number_input("Expected surface area (m²)", min_value=1)

    filtered = df[(df["destination"] == destination) & (df["special_features"] == special_value)]

    st.subheader("Forecast")
    if not filtered.empty:
        avg_price_per_m2 = filtered["price_per_m2"].mean()
        estimated_total = avg_price_per_m2 * input_surface
        count = filtered.shape[0]

        st.info(f"{count} similar projects found.")
        st.write(f"Average price per m²: **€{avg_price_per_m2:,.2f}**")
        st.success(f"Estimated total price: **€{estimated_total:,.2f}**")
    else:
        st.warning("No matching projects found in the database yet.")

# =============================
# 2. ADD NEW PROJECT
# =============================
elif page == "Add new project":
    st.title("Add New Project")

    st.markdown("""
    Help improve the estimator by adding your completed project.  
    The app will automatically calculate the price per m².
    """)

    with st.form("add_form"):
        name = st.text_input("Project name")
        dest = st.selectbox("Destination", ["SME", "hangar", "hangar with office", "shoppincenter"])
        spec = st.checkbox("Special techniques present?")
        spec_val = "yes" if spec else "no"
        surface = st.number_input("Surface area (m²)", min_value=1)
        price = st.number_input("Total sale price (€)", min_value=1)

        submit = st.form_submit_button("Submit project")

        if submit:
            if name and dest and finish:
                price_per_m2 = price / surface
                new_row = pd.DataFrame([{
                    "name": name,
                    "destination": dest,
                    "special_features": spec_val,
                    "surface": surface,
                    "price": price,
                    "price_per_m2": price_per_m2
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                df.to_csv(CSV_PATH, index=False)
                st.success("Project successfully added.")
            else:
                st.error("Please fill out all required fields.")

# =============================
# 3. VIEW & MODIFY PROJECTS
# =============================
elif page == "View and modify projects":
    st.title("Project Database")

    if df.empty:
        st.warning("No projects in the database.")
    else:
        st.markdown("Browse all stored projects below.")
        st.dataframe(df)

        st.subheader("Modify or delete a project")
        row_index = st.number_input("Select row index", min_value=0, max_value=len(df)-1, step=1)

        st.markdown(f"Selected project (row {row_index}):")
        st.write(df.iloc[row_index])

        new_price = st.number_input("New price (€)", min_value=1, value=int(df.iloc[row_index]["price"]))

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Update price"):
                df.at[row_index, "price"] = new_price
                df.at[row_index, "price_per_m2"] = new_price / df.at[row_index, "surface"]
                df.to_csv(CSV_PATH, index=False)
                st.success("Price updated successfully.")

        with col2:
            if st.button("Delete project"):
                df = df.drop(index=row_index).reset_index(drop=True)
                df.to_csv(CSV_PATH, index=False)
                st.success("Project deleted successfully.")
