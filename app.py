import streamlit as st
import sqlite3
import pandas as pd
import datetime
import plotly.express as px
import hashlib

# ==========================================
# 1. SETĂRI ȘI BAZĂ DE DATE (SQLite)
# ==========================================
DB_FILE = 'buget_familie.db'

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        # Tabel Utilizatori
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)''')
        # Tabel Tranzactii
        c.execute('''CREATE TABLE IF NOT EXISTS transactions
                     (id INTEGER PRIMARY KEY, user_id INTEGER, type TEXT, 
                      category TEXT, amount REAL, date TEXT, description TEXT)''')
        # Tabel Bugete
        c.execute('''CREATE TABLE IF NOT EXISTS budgets
                     (id INTEGER PRIMARY KEY, user_id INTEGER, category TEXT UNIQUE, limit_amount REAL)''')
        conn.commit()

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# ==========================================
# 2. FUNCȚII DE AUTENTIFICARE
# ==========================================
def register_user(username, password):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hash_password(password)))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False # User exista deja

def authenticate_user(username, password):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username=? AND password=?", (username, hash_password(password)))
        result = c.fetchone()
        return result[0] if result else None

# ==========================================
# 3. INTERFAȚA DE AUTENTIFICARE
# ==========================================
def login_screen():
    st.title("💰 Creează-ți propriul buget!")
    
    menu = ["Autentificare", "Înregistrare"]
    choice = st.sidebar.selectbox("Meniu", menu)
    
    if choice == "Autentificare":
        st.subheader("Intră în cont")
        username = st.text_input("Nume utilizator")
        password = st.text_input("Parolă", type='password')
        if st.button("Login"):
            user_id = authenticate_user(username, password)
            if user_id:
                st.session_state['user_id'] = user_id
                st.session_state['username'] = username
                st.success(f"Bun venit, {username}!")
                st.rerun()
            else:
                st.error("Utilizator sau parolă incorecte!")
                
    elif choice == "Înregistrare":
        st.subheader("Creează un cont nou")
        new_user = st.text_input("Nume utilizator")
        new_password = st.text_input("Parolă", type='password')
        if st.button("Înregistrare"):
            if register_user(new_user, new_password):
                st.success("Cont creat cu succes! Te poți autentifica.")
            else:
                st.warning("Numele de utilizator există deja.")

# ==========================================
# 4. FUNCȚII PRINCIPALE (CRUD & DASHBOARD)
# ==========================================
def add_transaction(user_id, t_type, category, amount, date, desc):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO transactions (user_id, type, category, amount, date, description) VALUES (?, ?, ?, ?, ?, ?)",
                  (user_id, t_type, category, amount, date, desc))
        conn.commit()

def set_budget(user_id, category, limit):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO budgets (id, user_id, category, limit_amount) VALUES ((SELECT id FROM budgets WHERE user_id=? AND category=?), ?, ?, ?)", 
                  (user_id, category, user_id, category, limit))
        conn.commit()

def load_data(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        df_trans = pd.read_sql_query(f"SELECT * FROM transactions WHERE user_id={user_id}", conn)
        df_budgets = pd.read_sql_query(f"SELECT * FROM budgets WHERE user_id={user_id}", conn)
    return df_trans, df_budgets

def main_dashboard():
    st.sidebar.title(f"Salut, {st.session_state['username']}")
    if st.sidebar.button("Deconectare"):
        st.session_state.clear()
        st.rerun()
        
    menu = ["Dashboard (Statistici)", "Adaugă Tranzacție", "Setare Bugete", "Export Date"]
    choice = st.sidebar.radio("Navigare", menu)
    
    user_id = st.session_state['user_id']
    df_trans, df_budgets = load_data(user_id)
    
    # Conversie dată pentru procesare
    if not df_trans.empty:
        df_trans['date'] = pd.to_datetime(df_trans['date'])
        df_trans['Lună'] = df_trans['date'].dt.to_period('M')

    if choice == "Adaugă Tranzacție":
        st.header("➕ Adaugă Venit sau Cheltuială")
        t_type = st.selectbox("Tip", ["Cheltuială", "Venit"])
        category = st.selectbox("Categorie", ["Mâncare", "Utilități", "Transport", "Educație", "Divertisment", "Salariu", "Altele"])
        amount = st.number_input("Sumă (RON)", min_value=0.01, format="%.2f")
        date = st.date_input("Data", datetime.date.today())
        desc = st.text_input("Descriere scurtă")
        
        if st.button("Salvează Tranzacția"):
            add_transaction(user_id, t_type, category, amount, date.strftime('%Y-%m-%d'), desc)
            st.success("Salvat cu succes!")
            
    elif choice == "Setare Bugete":
        st.header("🎯 Bugete Lunare")
        category = st.selectbox("Alege Categoria", ["Mâncare", "Utilități", "Transport", "Educație", "Divertisment", "Altele"])
        limit = st.number_input("Limită lunară (RON)", min_value=1.0, format="%.2f")
        if st.button("Setează Buget"):
            set_budget(user_id, category, limit)
            st.success(f"Buget pentru {category} setat la {limit} RON.")
            
        st.subheader("Bugetele tale actuale")
        if not df_budgets.empty:
            st.dataframe(df_budgets[['category', 'limit_amount']].rename(columns={'category': 'Categorie', 'limit_amount': 'Limită (RON)'}))

    elif choice == "Dashboard (Statistici)":
        st.header("📊 Dashboard Financiar")
        
        if df_trans.empty:
            st.info("Nu ai nicio tranzacție adăugată. Mergi la 'Adaugă Tranzacție'.")
            return
            
        # Filtru Luna
        luni_disponibile = df_trans['Lună'].astype(str).unique()
        luna_selectata = st.selectbox("Selectează Luna", sorted(luni_disponibile, reverse=True))
        
        df_luna = df_trans[df_trans['Lună'].astype(str) == luna_selectata]
        
        # Agregări
        venituri = df_luna[df_luna['type'] == 'Venit']['amount'].sum()
        cheltuieli = df_luna[df_luna['type'] == 'Cheltuială']['amount'].sum()
        sold = venituri - cheltuieli
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Venituri", f"{venituri:.2f} RON")
        col2.metric("Cheltuieli", f"{cheltuieli:.2f} RON")
        col3.metric("Sold Rămas", f"{sold:.2f} RON", delta=sold)
        
        st.divider()
        
        # Alerte de Buget
        st.subheader("⚠️ Status Bugete")
        cheltuieli_luna = df_luna[df_luna['type'] == 'Cheltuială'].groupby('category')['amount'].sum().reset_index()
        
        if not df_budgets.empty and not cheltuieli_luna.empty:
            merged = pd.merge(cheltuieli_luna, df_budgets, on='category', how='inner')
            for index, row in merged.iterrows():
                if row['amount'] > row['limit_amount']:
                    st.error(f"**Avertisment!** Ai depășit bugetul la **{row['category']}**: Cheltuit {row['amount']} / Limită {row['limit_amount']} RON")
                elif row['amount'] > 0.8 * row['limit_amount']:
                    st.warning(f"Atenție! Te apropii de limita la **{row['category']}**: Cheltuit {row['amount']} / Limită {row['limit_amount']} RON")
                else:
                    st.success(f"În grafic la **{row['category']}**: Cheltuit {row['amount']} / Limită {row['limit_amount']} RON")
        else:
            st.write("Nu ai bugete setate sau nu ai cheltuieli în această lună.")
            
        st.divider()
        
        # Vizualizări (Plotly)
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.write("**Distribuția Cheltuielilor**")
            if not cheltuieli_luna.empty:
                fig1 = px.pie(cheltuieli_luna, values='amount', names='category', hole=0.4)
                st.plotly_chart(fig1, use_container_width=True)
            else:
                st.write("Nicio cheltuială în această lună.")
                
        with col_chart2:
            st.write("**Evoluția zilnică (Luna curentă)**")
            zilnic = df_luna.groupby(['date', 'type'])['amount'].sum().reset_index()
            if not zilnic.empty:
                fig2 = px.bar(zilnic, x='date', y='amount', color='type', barmode='group')
                st.plotly_chart(fig2, use_container_width=True)

    elif choice == "Export Date":
        st.header("📥 Exportă Rapoarte")
        st.write("Aici poți descărca istoricul tău financiar în format CSV.")
        
        if not df_trans.empty:
            csv = df_trans.drop(columns=['user_id', 'Lună']).to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Descarcă Istoric (CSV)",
                data=csv,
                file_name=f'istoric_tranzactii_{datetime.date.today()}.csv',
                mime='text/csv',
            )
        else:
            st.warning("Nu există date de exportat.")

# ==========================================
# 5. EXECUȚIA APLICAȚIEI
# ==========================================
if __name__ == '__main__':
    st.set_page_config(page_title="Spendometer", page_icon="💰", layout="wide")
    init_db()
    
    if 'user_id' not in st.session_state:
        login_screen()
    else:
        main_dashboard()
