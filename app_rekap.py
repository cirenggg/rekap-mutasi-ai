import streamlit as st
import pdfplumber
import pandas as pd
import io
import google.generativeai as genai
import json
import numpy as np

# --- PENGATURAN DEFAULT ADMIN ---
DEFAULT_API_KEY = "AQ.Ab8RN6IjnYsyy4U-W4l7ApxakVUnhgQZu3_lMUHzq0PNiUXk3w" # <--- Paste API Key Premium Anda
DEFAULT_MODEL = "models/gemini-3.1-flash-lite"
ADMIN_PASSWORD = "semarangpemuda" 

# --- PENGATURAN HALAMAN ---
st.set_page_config(page_title="Pampam Converter", page_icon="🤖", layout="wide")

import base64

# --- FUNGSI UNTUK BACKGROUND GAMBAR ---
def set_background(nama_file_gambar):
    try:
        with open(nama_file_gambar, "rb") as file:
            encoded_string = base64.b64encode(file.read()).decode()
        
        css = f"""
        <style>
        .stApp {{
            background-image: url(data:image/jpeg;base64,{encoded_string});
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}
        /* Lapisan gelap transparan agar tulisan Excel/Aplikasi tetap terbaca */
        .stApp::before {{
            content: "";
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background-color: rgba(14, 17, 23, 0.75); /* Angka 0.75 adalah tingkat kegelapan (0.0 sampai 1.0) */
            z-index: -1;
        }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)
    except Exception as e:
        st.warning("Gambar background tidak ditemukan. Pastikan nama file dan letaknya benar.")

# Panggil fungsinya di sini (Sesuaikan nama file-nya)
set_background("Background.jpeg")

# --- INISIALISASI MEMORI (SESSION STATE) ---
# Ini berfungsi agar hasil tidak hilang saat halaman refresh/download
if 'excel_data' not in st.session_state:
    st.session_state['excel_data'] = None
if 'summary_df' not in st.session_state:
    st.session_state['summary_df'] = None
if 'nama_file_terakhir' not in st.session_state:
    st.session_state['nama_file_terakhir'] = ""

# --- MENU SAMPING (ADMIN HIDDEN PANEL) ---
with st.sidebar:
    st.header("🏢 Internal Tool")
    st.write("Aplikasi Rekap Mutasi Otomatis")
    
    with st.expander("🛠️ Admin Panel (Restricted)"):
        pwd = st.text_input("Password Admin:", type="password")
        
        if pwd == ADMIN_PASSWORD:
            st.success("Akses Admin Terbuka")
            api_key = st.text_input("Ubah API Key:", value=DEFAULT_API_KEY, type="password")
            try:
                genai.configure(api_key=api_key)
                daftar_model = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                if daftar_model:
                    idx = daftar_model.index(DEFAULT_MODEL) if DEFAULT_MODEL in daftar_model else 0
                    model_pilihan = st.selectbox("Ubah Model Default:", daftar_model, index=idx)
                else:
                    model_pilihan = DEFAULT_MODEL
            except Exception:
                model_pilihan = DEFAULT_MODEL
                st.error("API Key Invalid")
        else:
            api_key = DEFAULT_API_KEY
            model_pilihan = DEFAULT_MODEL

st.title("🤖 Pampam Converter")
st.write("Mengubah e-statement PDF ke Excel dan otomatis menghitung mutasi bulanan serta Average CASA.")

file_pdf = st.file_uploader("Unggah file PDF Rekening Koran di sini", type=["pdf"])

if file_pdf is not None:
    if api_key == "ISI_API_KEY_ANDA_DI_SINI" or not api_key:
        st.warning("⚠️ API Key Default belum dimasukkan ke dalam kode aplikasi.")
    else:
        # Jika user mengunggah file baru, bersihkan memori lama
        if st.session_state['nama_file_terakhir'] != file_pdf.name:
            st.session_state['excel_data'] = None
            st.session_state['summary_df'] = None
            st.session_state['nama_file_terakhir'] = file_pdf.name
            
        st.success(f"File '{file_pdf.name}' siap diproses!")
        
        # Tombol Proses
        if st.button("Proses"):
            with st.spinner("Sistem sedang mengekstrak dan menganalisa data... (Ini butuh beberapa detik)"):
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel(model_pilihan)

                    teks_lengkap = ""
                    with pdfplumber.open(file_pdf) as pdf:
                        for hal in pdf.pages:
                            teks_lengkap += hal.extract_text() + "\n"
                    
                    prompt = f"""
                    Anda adalah analis data perbankan yang teliti. 
                    Berikut adalah teks mentah dari mutasi rekening koran:
                    
                    {teks_lengkap}
                    
                    Tugas Anda:
                    1. Temukan dan ekstrak semua baris transaksi mutasi keuangan.
                    2. Gabungkan teks keterangan (Narration) yang terpecah ke baris bawah menjadi satu kalimat utuh. Abaikan angka yang merupakan kode jam transaksi atau ID Teller.
                    3. Bersihkan angka mutasi menjadi format angka murni (buang titik pemisah ribuan, ganti koma desimal jadi titik). Jika tidak ada nilai, gunakan null.
                    
                    Kembalikan data HANYA dalam format JSON array yang valid tanpa tambahan teks apapun.
                    Gunakan persis nama kunci berikut:
                    - "Date" (String DD/MM/YYYY)
                    - "Narration" (String)
                    - "Debit" (Number atau null)
                    - "Credit" (Number atau null)
                    - "Balance" (Number atau null)
                    """
                    
                    response = model.generate_content(prompt)
                    jawaban_ai = response.text.strip()
                    
                    if jawaban_ai.startswith("```json"):
                        jawaban_ai = jawaban_ai[7:-3].strip()
                    elif jawaban_ai.startswith("```"):
                        jawaban_ai = jawaban_ai[3:-3].strip()
                        
                    data_transaksi = json.loads(jawaban_ai)
                    df = pd.DataFrame(data_transaksi)
                    
                    # --- KALKULASI SALDO BERJALAN ---
                    df['Debit'] = pd.to_numeric(df['Debit'], errors='coerce').fillna(0)
                    df['Credit'] = pd.to_numeric(df['Credit'], errors='coerce').fillna(0)
                    df['Balance'] = pd.to_numeric(df['Balance'], errors='coerce')

                    for i in range(1, len(df)):
                        if pd.isna(df.loc[i, 'Balance']):
                            df.loc[i, 'Balance'] = df.loc[i-1, 'Balance'] + df.loc[i, 'Credit'] - df.loc[i, 'Debit']
                    
                    df['Debit'] = df['Debit'].replace(0, np.nan)
                    df['Credit'] = df['Credit'].replace(0, np.nan)
                    
                    # --- PEMBUATAN RINGKASAN ANALISA ---
                    df['Date_Obj'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
                    df_valid = df.dropna(subset=['Date_Obj']).sort_values('Date_Obj').copy()
                    
                    bulan_indo = {1:'Januari', 2:'Februari', 3:'Maret', 4:'April', 5:'Mei', 6:'Juni',
                                  7:'Juli', 8:'Agustus', 9:'September', 10:'Oktober', 11:'November', 12:'Desember'}
                    df_valid['Bulan_Tahun'] = df_valid['Date_Obj'].dt.month.map(bulan_indo) + " " + df_valid['Date_Obj'].dt.year.astype(str)
                    df_valid['Bulan_Sort'] = df_valid['Date_Obj'].dt.to_period('M')

                    summary_mutasi = df_valid.groupby(['Bulan_Sort', 'Bulan_Tahun']).agg(
                        Mutasi_Kredit=('Credit', 'sum'),
                        Freq_Kredit=('Credit', 'count'),
                        Mutasi_Debit=('Debit', 'sum'),
                        Freq_Debit=('Debit', 'count'),
                        Saldo_Tertinggi=('Balance', 'max'),
                        Saldo_Terendah=('Balance', 'min')
                    ).reset_index()

                    df_eod = df_valid.drop_duplicates(subset=['Date_Obj'], keep='last').set_index('Date_Obj')
                    
                    if not df_eod.empty:
                        kalender_penuh = pd.date_range(start=df_eod.index.min(), end=df_eod.index.max())
                        df_daily = df_eod.reindex(kalender_penuh)
                        df_daily['Balance'] = df_daily['Balance'].ffill()
                        
                        df_daily['Bulan_Sort'] = df_daily.index.to_period('M')
                        avg_casa = df_daily.groupby('Bulan_Sort').agg(Rata_rata_CASA=('Balance', 'mean')).reset_index()
                    else:
                        avg_casa = pd.DataFrame(columns=['Bulan_Sort', 'Rata_rata_CASA'])

                    df_summary = pd.merge(summary_mutasi, avg_casa, on='Bulan_Sort', how='left')
                    
                    df_summary = df_summary[['Bulan_Tahun', 'Mutasi_Kredit', 'Freq_Kredit', 'Mutasi_Debit', 'Freq_Debit', 'Rata_rata_CASA', 'Saldo_Tertinggi', 'Saldo_Terendah']]
                    df_summary.rename(columns={
                        'Bulan_Tahun': 'Bulan',
                        'Mutasi_Kredit': 'Mutasi Kredit',
                        'Freq_Kredit': 'Freq Kredit',
                        'Mutasi_Debit': 'Mutasi Debit',
                        'Freq_Debit': 'Freq Debit',
                        'Rata_rata_CASA': 'Rata-rata CASA (Avg)',
                        'Saldo_Tertinggi': 'Saldo Tertinggi',
                        'Saldo_Terendah': 'Saldo Terendah'
                    }, inplace=True)

                    df.drop(columns=['Date_Obj'], inplace=True, errors='ignore')

                    df.rename(columns={
                        "Date": "Date - Text Format (DD/MM/YYYY)",
                        "Narration": "Narration ",
                        "Debit": "Debit - Number Format",
                        "Credit": "Credit - Number Format",
                        "Balance": "Balance - Number Format"
                    }, inplace=True)
                    
                    # --- PEMBUATAN EXCEL & SIMPAN KE MEMORI ---
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, sheet_name="Rekening Koran", index=False)
                        df_summary.to_excel(writer, sheet_name="Ringkasan", index=False)
                    
                    # Simpan hasil akhir ke brankas memori (session state)
                    st.session_state['excel_data'] = buffer.getvalue()
                    st.session_state['summary_df'] = df_summary
                    
                except Exception as e:
                    st.error(f"Terjadi kesalahan teknis: {e}")
        
        # --- MENAMPILKAN HASIL DARI MEMORI (Bebas dari efek Refresh) ---
        if st.session_state['excel_data'] is not None:
            st.success("✅ Dokumen berhasil disusun dan dianalisa!")
            
            st.write("### 📊 Preview Ringkasan Analisa")
            st.dataframe(st.session_state['summary_df'])
            
            st.download_button(
                label="⬇️ Download Full Excel (2 Sheet)",
                data=st.session_state['excel_data'],
                file_name=f"Rekap_&_Analisa_{file_pdf.name.replace('.pdf', '')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )