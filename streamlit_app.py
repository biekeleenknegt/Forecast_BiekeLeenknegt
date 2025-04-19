import streamlit as st
import pandas as pd
import os
from datetime import datetime

st.set_page_config(page_title="Project Cost Estimator", layout="centered")
st.title("Project Cost Estimator")

USERNAME = "tom"
PASSWORD = "wachtwoordvoortom!"

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

# -------- Load database --------
CSV_PATH = "database.csv"
if os.path.exists(CSV_PATH):
    df = pd.read_csv(CSV_PATH)
else:
    df = pd.DataFrame(columns=[
        "name", "destination", "special_features", "surface", "price", "price_per_m2",
        "exterior_surface", "exterior_price", "exterior_price_per_m2", "year"
    ])

# -------- Navigation --------
page = st.sidebar.radio("Navigation", ["Forecast price", "Add new project", "View and modify projects", "About this tool"])

# -------- 1. FORECAST --------
if page == "Forecast price":
    st.title("Forecast Project Price")
    st.markdown("This tool estimates both building cost and exterior works separately.")

    current_year = datetime.now().year

    destination = st.selectbox("Project destination", ["SME", "hangar", "hangar with office", "shoppincenter"])
    special_features = st.checkbox("Is a cellar present?")
    special_value = "yes" if special_features else "no"
    input_surface = st.number_input("Expected building surface (m²)", min_value=1)
    exterior_surface = st.number_input("Expected exterior surface (m²)", min_value=0)

    filtered = df[(df["destination"] == destination) & (df["special_features"] == special_value)]

    if not filtered.empty:
        # Inflatiecorrectie van 2,3% per jaar
        filtered = filtered.copy()
        filtered["corrected_price_per_m2"] = filtered.apply(
            lambda row: row["price_per_m2"] * (1.023 ** (current_year - int(row["year"]))), axis=1
        )

        st.subheader("Building price estimate")
        avg_price_per_m2 = filtered["corrected_price_per_m2"].mean()
        estimated_total = avg_price_per_m2 * input_surface
        st.info(f"{filtered.shape[0]} matching projects found.")
        st.write(f"Avg corrected price per m²: **€{avg_price_per_m2:,.2f}**")
        st.success(f"Estimated building cost: **€{estimated_total:,.2f}**")

        st.subheader("Exterior works estimate")
        ext_prices = filtered["exterior_price_per_m2"].dropna()
        if not ext_prices.empty:
            min_ext = ext_prices.min()
            max_ext = ext_prices.max()
            if exterior_surface > 0:
                min_total = min_ext * exterior_surface
                max_total = max_ext * exterior_surface
                st.write(f"Estimated exterior cost range: **€{min_total:,.2f} – €{max_total:,.2f}**")
                st.write(f"Based on price/m² ranging from **€{min_ext:.2f}** to **€{max_ext:.2f}**")
            else:
                st.info("Enter an exterior surface to see a cost range.")
        else:
            st.warning("No exterior pricing data available yet.")
    else:
        st.warning("No matching projects found in the database yet.")

# -------- 2. ADD PROJECT --------
elif page == "Add new project":
    st.title("Add New Project")

    with st.form("add_form"):
        name = st.text_input("Project name")
        dest = st.selectbox("Destination", ["SME", "hangar", "hangar with office", "shoppincenter"])
        spec = st.checkbox("Is a cellar present?")
        spec_val = "yes" if spec else "no"
        surface = st.number_input("Building surface (m²)", min_value=1)
        price = st.number_input("Total sale price (€)", min_value=1)
        year = st.number_input("Construction year", min_value=2000, max_value=datetime.now().year, value=datetime.now().year)

        exterior_surface = st.number_input("Exterior surface (m²)", min_value=0)
        exterior_price = st.number_input("Exterior price (€)", min_value=0)

        submit = st.form_submit_button("Submit project")

        if submit:
            if name and dest:
                price_per_m2 = price / surface
                ext_price_per_m2 = (exterior_price / exterior_surface) if exterior_surface > 0 else None
                new_row = pd.DataFrame([{
                    "name": name,
                    "destination": dest,
                    "special_features": spec_val,
                    "surface": surface,
                    "price": price,
                    "price_per_m2": price_per_m2,
                    "exterior_surface": exterior_surface,
                    "exterior_price": exterior_price,
                    "exterior_price_per_m2": ext_price_per_m2,
                    "year": year
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                df.to_csv(CSV_PATH, index=False)
                st.success("Project successfully added.")
            else:
                st.error("Please fill out all required fields.")

# -------- 3. VIEW / MODIFY --------
elif page == "View and modify projects":
    st.title("Project Database")

    if df.empty:
        st.warning("No projects in the database.")
    else:
        st.dataframe(df)

        st.subheader("Modify or delete a project")
        row_index = st.number_input("Select row index", min_value=0, max_value=len(df)-1)

        st.write("Selected project:")
        st.write(df.iloc[row_index])

        new_price = st.number_input("New building price (€)", min_value=1, value=int(df.iloc[row_index]["price"]))
        new_ext_price = st.number_input("New exterior price (€)", min_value=0, value=int(df.iloc[row_index]["exterior_price"] or 0))

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Update price"):
                df.at[row_index, "price"] = new_price
                df.at[row_index, "price_per_m2"] = new_price / df.at[row_index, "surface"]
                df.at[row_index, "exterior_price"] = new_ext_price
                if df.at[row_index, "exterior_surface"] > 0:
                    df.at[row_index, "exterior_price_per_m2"] = new_ext_price / df.at[row_index, "exterior_surface"]
                df.to_csv(CSV_PATH, index=False)
                st.success("New price is registrated, press update price again to confirm.")

        with col2:
            if st.button("Delete project"):
                df = df.drop(index=row_index).reset_index(drop=True)
                df.to_csv(CSV_PATH, index=False)
                st.success("Project will be deleted. Press delete project again to confirm.")

# -------- 4. ABOUT PAGE --------
elif page == "About this tool":
    st.title("About this Tool")
    st.markdown("""
    ### What does this estimator do?
    This tool is built to help estimate construction costs for industrial buildings like SMEs, hangars and shopping centers.

    **Key features:**
    - Predicts **total price** based on your building surface and presence of cellar.
    - Treats **exterior works** separately and gives a price **range** based on historical data.
    - Corrects prices for **inflation over time** with a 2.3% annual price increase.
    - Works with a custom internal database that you can extend by adding real projects.

    ### What is RCF (Reference Class Forecasting)?
    RCF is a method that predicts the likely outcome of a project by comparing it with a group (class) of similar past projects.
    This is more robust than relying only on one estimation model — and helps reduce optimism bias and underestimation.

    ### How does inflation correction work?
    If a project in the database is from 2022 and you're estimating for 2025, we adjust it:
    - `2022 → 2025 = 3 years → x (1.023)^3 ≈ +7.03%`
    - This makes price forecasts more realistic in a changing market.
    """)
