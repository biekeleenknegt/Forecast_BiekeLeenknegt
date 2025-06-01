import streamlit as st
import pandas as pd
import os
from datetime import datetime
from scipy.stats import shapiro, norm

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Project Cost Estimator", layout="centered")
st.title("Project Cost Estimator")

USERNAME = "test"
PASSWORD = "test"

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

# ---------------- DATABASE ----------------
CSV_PATH = "database.csv"
if os.path.exists(CSV_PATH):
    df = pd.read_csv(CSV_PATH, sep=",", decimal=".")
    if "vaults" not in df.columns:
        df["vaults"] = 0
    if "loading_bay" not in df.columns:
        df["loading_bay"] = 0
    for col in [
        "surface","price","price_per_m2",
        "exterior_surface","exterior_price","exterior_price_per_m2","year"
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
else:
    df = pd.DataFrame(columns=[
        "name", "vaults", "loading_bay", "surface", "price", "price_per_m2",
        "exterior_surface", "exterior_price", "exterior_price_per_m2", "year"
    ])

# ---------------- NAVIGATION ----------------
page = st.sidebar.radio("Navigation", [
    "Forecast price", "Add new project", "View and modify projects", "About this tool"
])

# ---------------- 1. FORECAST ----------------
if page == "Forecast price":
    st.header("Forecast Project Price")
    st.markdown("""
    This tool estimates both building cost and exterior works separately, with adjustments for time-based inflation.
    Additionally, performs normality test and computes prediction intervals accordingly.
    """)

    vaults_req  = st.checkbox("Are vaults required?")
    loading_req = st.checkbox("Is a loading bay required?")
    vault_val   = 1 if vaults_req else 0
    load_val    = 1 if loading_req else 0

    input_surface    = st.number_input("Expected building surface (m²)", min_value=1)
    exterior_surface = st.number_input("Expected exterior surface (m²)", min_value=0)
    forecast_year    = st.number_input(
        "Planned project year", min_value=1900, max_value=2100,
        value=datetime.now().year
    )

    filtered = df[(df["vaults"] == vault_val) & (df["loading_bay"] == load_val)]

    if not filtered.empty:
        def correct(row):
            return 1.023 ** (forecast_year - row["year"])

        filtered["corr_ppm2"] = filtered["price_per_m2"] * filtered.apply(correct, axis=1)
        filtered["corr_ext_ppm2"] = filtered["exterior_price_per_m2"] * filtered.apply(correct, axis=1)

        est_build_ppm2 = filtered["corr_ppm2"].dropna()
        mean_ppm2 = est_build_ppm2.mean()
        est_build = mean_ppm2 * input_surface

        st.info(f"{filtered.shape[0]} matching projects found.")
        st.write(f"Corrected avg price per m²: **€{mean_ppm2:,.2f}**")
        st.success(f"Estimated building cost: **€{est_build:,.2f}**")

        st.subheader("Building price interval (normality test)")

        # ---------------- AANGEPASTE CONTROLE OP MINIMALE DATAPUNTEN ----------------
        if len(est_build_ppm2) < 3:
            st.info(
                "Op dit moment zijn er nog niet genoeg projecten beschikbaar om "
                "een betrouwbaar prijsinterval te berekenen (minimaal 3 waarden nodig). "
                "Kom later terug zodra er minstens 3 vergelijkbare projecten zijn ingevoerd."
            )
        else:
            try:
                stat, p = shapiro(est_build_ppm2)
                st.write(f"Shapiro–Wilk p-value: {p:.3f}")
                if p > 0.05:
                    # assume normal, z-interval
                    z = norm.ppf(0.975)
                    sd = est_build_ppm2.std(ddof=1)
                    se = sd / (len(est_build_ppm2) ** 0.5)
                    low = mean_ppm2 - z * se
                    high = mean_ppm2 + z * se
                    st.write(f"95% prediction interval (±1.96 SE): €/m² [{low:,.2f} – {high:,.2f}] (normal)")
                else:
                    # quantile interval
                    q_low, q_high = est_build_ppm2.quantile([0.025, 0.975])
                    st.write(f"95% prediction interval (quantiles): €/m² [{q_low:,.2f} – {q_high:,.2f}] (non-normal)")
            except ValueError:
                st.error(
                    "Er is een onverwacht probleem opgetreden bij het berekenen van het interval. "
                    "Controleer of de gegevens correct zijn ingevoerd."
                )

        st.subheader("Exterior works estimate")
        ex = filtered["corr_ext_ppm2"].dropna()
        ex = ex[ex > 0]
        if not ex.empty and exterior_surface > 0:
            mn, mx = ex.min(), ex.max()
            st.write(
                f"Estimated exterior cost range: **€{mn * exterior_surface:,.2f} – €{mx * exterior_surface:,.2f}**"
            )
            st.write(f"Based on corrected €/m² from **€{mn:,.2f}** to **€{mx:,.2f}**")

            # totaal
            total_min = est_build + mn * exterior_surface
            total_max = est_build + mx * exterior_surface
            st.subheader("Total project cost estimate")
            st.write(
                f"Estimated total cost range: **€{total_min:,.2f} – €{total_max:,.2f}**"
            )
        elif exterior_surface > 0:
            st.warning("No positive exterior pricing data available.")
        else:
            st.info("Enter an exterior surface to see a cost range.")
    else:
        st.warning("No matching projects found in the database yet.")

# ---------------- 2. ADD PROJECT ----------------
elif page == "Add new project":
    st.header("Add New Project")
    with st.form("add_form"):
        name        = st.text_input("Project name")
        vaults_pres = 1 if st.checkbox("Are vaults present?") else 0
        load_pres   = 1 if st.checkbox("Is a loading bay present?") else 0
        surface     = st.number_input("Building surface (m²)", min_value=1)
        price       = st.number_input("Total sale price (€)", min_value=1)
        ext_surf    = st.number_input("Exterior surface (m²)", min_value=0)
        ext_price   = st.number_input("Total exterior price (€)", min_value=0)
        year        = st.number_input(
            "Year of construction",
            min_value=2000, max_value=datetime.now().year,
            value=datetime.now().year
        )

        submit = st.form_submit_button("Submit project")
        if submit:
            if name:
                ppm2 = price / surface
                ext_ppm2 = ext_price / ext_surf if ext_surf > 0 else None
                new = pd.DataFrame([{
                    "name": name,
                    "vaults": vaults_pres,
                    "loading_bay": load_pres,
                    "surface": surface,
                    "price": price,
                    "price_per_m2": ppm2,
                    "exterior_surface": ext_surf,
                    "exterior_price": ext_price,
                    "exterior_price_per_m2": ext_ppm2,
                    "year": year
                }])
                df = pd.concat([df, new], ignore_index=True)
                df.to_csv(CSV_PATH, index=False)
                st.success("Project successfully added.")
            else:
                st.error("Please fill out all required fields.")

# ---------------- 3. VIEW / MODIFY ----------------
elif page == "View and modify projects":
    st.header("Project Database")
    if df.empty:
        st.warning("No projects in the database.")
    else:
        st.dataframe(df)
        st.subheader("Modify or delete a project")
        idx = st.number_input("Select row index", min_value=0, max_value=len(df)-1)
        st.write(df.iloc[idx])

        new_price     = st.number_input(
            "New building price (€)",
            min_value=1,
            value=int(df.at[idx, "price"])
        )
        new_ext_price = st.number_input(
            "New exterior price (€)",
            min_value=0,
            value=int(df.at[idx, "exterior_price"] or 0)
        )

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Update price"):
                df.at[idx, "price"] = new_price
                df.at[idx, "price_per_m2"] = new_price / df.at[idx, "surface"]
                df.at[idx, "exterior_price"] = new_ext_price
                if df.at[idx, "exterior_surface"] > 0:
                    df.at[idx, "exterior_price_per_m2"] = (
                        new_ext_price / df.at[idx, "exterior_surface"]
                    )
                df.to_csv(CSV_PATH, index=False)
                st.success("Price updated.")
        with c2:
            if st.button("Delete project"):
                df = df.drop(index=idx).reset_index(drop=True)
                df.to_csv(CSV_PATH, index=False)
                st.success("Project deleted.")

# ---------------- 4. ABOUT TOOL ----------------
elif page == "About this tool":
    st.header("About this Tool")

    st.markdown("""
    **Welcome to the presentation about this tool.**

    First of all, I am Bieke Leenknegt.  
    I have added my Masterproef (Master’s thesis) for more background and details, but tijdens mijn thesis en bij het ontwikkelen van deze tool heb ik mij vooral gericht op twee kernvariabelen: **AirBase (vaults)** en **LoadingBay (loading bay)**. 

    **Wat doet deze tool precies?**  
    Dit is een interactieve webapplicatie (gebouwd met Streamlit) waarmee je in een paar klikken een betrouwbare kostenraming kunt genereren voor jouw nieuwbouwproject. 
    - Je kiest aan de hand van checkboxen of er een vault (kelder/onderbouw) en/of een loading bay (laadperron) nodig is.  
    - Je vult de geschatte bouw- en exterieuroppervlakte (in m²) in.  
    - Je selecteert het planningsjaar (bijvoorbeeld 2025).  

    De methode erachter:
    1. **Referentieklassen (Reference Class Forecasting)**  
       Op basis van historische projecten (met dezelfde kenmerken: vaults = ja/nee, loading bay = ja/nee) bepaalt de tool de gemiddelde prijs per m² (geïnflateerd naar het gewenste jaar).  
       - Als er voldoende vergelijkbare projecten zijn (> 3), berekent hij ook een betrouwbaarheidsinterval (z-score of kwantiel-methode, afhankelijk van normaliteit).  
       - Exterieure werken (buitenaanleg) berekent hij apart als een min–max-range per m².  
       - Daarna loopt hij vaults en loading bay apart door volgens exact dezelfde logica. 

    2. **Tijdsaanpassing (2,3 % inflatie per jaar)**  
       Historische prijzen worden automatisch gecorrigeerd met 2,3 % per jaar zodat je in 2025 meteen de juiste marktwaarde ziet.  

    3. **Onder de motorkap: CSV-database**  
       Je kunt zelf nieuwe projecten toevoegen (met jaar, oppervlakte, prijs, vaults-/loading-bay-indicators), of bestaande records wijzigen of verwijderen. Elke nieuwe invoer wordt automatisch omgezet naar €/m² en opgeslagen in een CSV-bestand, zodat de database continu groeit en je ramingen na verloop van tijd steeds nauwkeuriger worden.

    **Functionaliteiten per tab:**
    - **Forecast price**: Kies vaults/loading bay, vul oppervlaktes en jaar in → krijg een schatting van de bouwkost + exterieurkost (met betrouwbaarheidsintervallen). 
    - **Add new project**: Vul één nieuw project in (naam, vaults?, loading bay?, oppervlaktes, prijzen, bouwjaar) → het wordt automatisch geconverteerd naar €/m² en opgeslagen. 
    - **View and modify projects**: Bekijk de tabel met alle opgeslagen projecten en pas prijzen aan of verwijder records. 
    - **About this tool**: De uitleg die je nu leest, inclusief mijn naam (Bieke Leenknegt) en vermelding van de Masterproef.

    **Waarom deze tool?**  
    - Hij vervangt handmatige spreadsheets of papieren berekeningen en levert in enkele seconden een kostprijsraming die gebaseerd is op realistische, empirisch gevalideerde data (Reference Class Forecasting).  
    - Hij is modulair en uitbreidbaar: elke keer dat je een nieuw project toevoegt, verbetert de database zichzelf.  
    - Omdat de inflatie automatisch wordt meegerekend, kun je al in de ontwerpfase meteen nagaan of je kostencalculatie up-to-date is.  
    - RCF corrigeert voor systematische onderschattingen die in traditionele lineaire regressiemodellen vaak optreden.  
    - Splitst bouw- en exterieurkosten apart, wat handiger is bij bijvoorbeeld aanpassing van alleen de buitenaanleg.  

    Deze webapplicatie is gebouwd met **Streamlit** en maakt gebruik van een eenvoudige **CSV-backend**.  
    Het is de praktijkgerichte implementatie van mijn Masterproef “From regression to reference class: A data-driven approach to forecast project pricing with real-time updates” (Bieke Leenknegt, 2024-2025), waarin ik heb aangetoond dat Reference Class Forecasting (met een minimale representativiteitsgarantie via (M)CR) betrouwbaarder is dan klassieke OLS-modellen voor industriële bouwprojecten.  
    """)

