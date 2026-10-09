import streamlit as st
import openai
import pandas as pd
import json
import sqlite3
from datetime import datetime
import pypdf
import docx2txt

# 1. KONFIGURASI HALAMAN & DATABASE
st.set_page_config(
    page_title="KBC Smart Search Engine, Evaluator & Database",
    page_icon="🔍",
    layout="wide"
)

# Inisialisasi Database SQLite Lokal
def init_db():
    conn = sqlite3.connect("kbc_evaluation.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS penilaian_kbc (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_siswa TEXT,
            tanggal TEXT,
            ringkasan TEXT,
            skor_allah REAL,
            skor_sesama REAL,
            skor_alam REAL,
            skor_tanahair REAL,
            skor_ilmu REAL,
            rata_rata REAL,
            rekomendasi TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# 2. PENGATURAN SIDEBAR
with st.sidebar:
    st.header("🔑 Pengaturan API & Input")
    api_key = st.text_input("Masukkan OpenAI API Key Anda:", type="password")
    
    st.markdown("---")
    st.header("👤 Identitas Siswa")
    nama_siswa = st.text_input("Nama Siswa:", placeholder="Contoh: Ahmad Fauzi")
    
    st.markdown("---")
    st.markdown("### 📖 Sistem KBC Kemenag")
    st.info("Aplikasi ini otomatis mengonversi esai menjadi indikator capaian karakter berskala 1 - 4 sesuai KMA 1503.")

# Validasi API Client
client = openai.OpenAI(api_key=api_key) if api_key else None

# Prompt Standar Evaluasi KBC
RUBRIK_KBC_SYSTEM_PROMPT = """
Anda adalah AI Asesor resmi Kurikulum Berbasis Cinta (KBC) Kementerian Agama.
Tugas Anda adalah menilai esai/laporan siswa dengan Skala 1 sampai 4:
4 = Sangat Baik, 3 = Baik, 2 = Cukup, 1 = Kurang.

Evaluasi wajib mencakup 5 aspek ini dalam format JSON murni:
{
  "ringkasan": "Ringkasan dokumen",
  "nilai": {
    "Cinta Allah & Rasul": {"skor": 3, "alasan": "alasan"},
    "Cinta Diri & Sesama": {"skor": 4, "alasan": "alasan"},
    "Cinta Alam & Lingkungan": {"skor": 2, "alasan": "alasan"},
    "Cinta Tanah Air": {"skor": 3, "alasan": "alasan"},
    "Cinta Ilmu": {"skor": 4, "alasan": "alasan"}
  },
  "rekomendasi": "Saran tindakan nyata"
}
"""

# 3. FUNGSI MEMBACA DOKUMEN (PDF & DOCX)
def extract_text_from_file(uploaded_file):
    file_type = uploaded_file.name.split('.')[-1].lower()
    if file_type == 'pdf':
        pdf_reader = pypdf.PdfReader(uploaded_file)
        text = "".join([page.extract_text() for page in pdf_reader.pages])
        return text
    elif file_type in ['docx', 'doc']:
        return docx2txt.process(uploaded_file)
    return ""

# 4. ANTARMUKA UTAMA (TABS)
tab1, tab2 = st.tabs(["📝 Input & Evaluasi Esai", "📊 Rekap Database Nilai"])

with tab1:
    st.title("🔍 KBC Smart Search Engine & Automatic Evaluator")
    st.markdown("---")
    
    # Pilihan Metode Input
    metode_input = st.radio("Pilih Metode Input Dokumen:", ["Ketik/Tempel Teks Manual", "Unggah File (PDF / Word)"])
    
    dokumen_teks = ""
    if metode_input == "Ketik/Tempel Teks Manual":
        dokumen_teks = st.text_area("Masukkan Esai atau Laporan Kegiatan Siswa:", height=200, placeholder="Tulis di sini...")
    else:
        uploaded_file = st.file_uploader("Unggah dokumen esai siswa (Format .pdf atau .docx)", type=["pdf", "docx"])
        if uploaded_file is not None:
            dokumen_teks = extract_text_from_file(uploaded_file)
            st.success(f"Berhasil mengekstrak teks dari file: {uploaded_file.name}")
            with st.expander("Lihat Isi Dokumen Ekstraksi"):
                st.write(dokumen_teks)

    btn_evaluasi = st.button("🚀 Analisis & Simpan Nilai", type="primary")

    if btn_evaluasi:
        if not api_key:
            st.error("Silakan masukkan OpenAI API Key di sidebar!")
        elif not nama_siswa.strip():
            st.warning("Mohon isi Nama Siswa di sidebar terlebih dahulu agar data bisa direkap.")
        elif not dokumen_teks.strip():
            st.warning("Konten dokumen kosong atau belum dimasukkan.")
        else:
            with st.spinner("AI sedang menganalisis rubrik KBC dan melakukan scoring..."):
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": RUBRIK_KBC_SYSTEM_PROMPT},
                            {"role": "user", "content": dokumen_teks}
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.2
                    )
                    
                    result = json.loads(response.choices.message.content)
                    data_nilai = result.get("nilai", {})
                    
                    # Hitung Rata-rata Skor
                    skor_list = [d.get("skor", 0) for d in data_nilai.values()]
                    rerata = sum(skor_list) / len(skor_list) if skor_list else 0
                    
                    # --- SIMPAN KE DOKUMEN DATABASE ---
                    conn = sqlite3.connect("kbc_evaluation.db")
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO penilaian_kbc (
                            nama_siswa, tanggal, ringkasan, 
                            skor_allah, skor_sesama, skor_alam, skor_tanahair, skor_ilmu, 
                            rata_rata, rekomendasi
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        nama_siswa, 
                        datetime.now().strftime("%Y-%m-%d %H:%M"),
                        result.get("ringkasan"),
                        data_nilai.get("Cinta Allah & Rasul", {}).get("skor", 0),
                        data_nilai.get("Cinta Diri & Sesama", {}).get("skor", 0),
                        data_nilai.get("Cinta Alam & Lingkungan", {}).get("skor", 0),
                        data_nilai.get("Cinta Tanah Air", {}).get("skor", 0),
                        data_nilai.get("Cinta Ilmu", {}).get("skor", 0),
                        rerata,
                        result.get("rekomendasi")
                    ))
                    conn.commit()
                    conn.close()
                    
                    # --- TAMPILKAN HASIL EVALUASI ---
                    st.success(f"Analisis Selesai! Data milik **{nama_siswa}** telah otomatis disimpan ke database.")
                    
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown("### 📊 Hasil Penilaian Rubrik")
                        rows = [{"Aspek KBC": k, "Skor (1-4)": v.get("skor"), "Keterangan": v.get("alasan")} for k, v in data_nilai.items()]
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    with col2:
                        st.markdown("### 🌟 Indeks KBC")
                        st.metric(label="Rata-rata Skor Karakter", value=f"{rerata:.2f} / 4.00")
                    
                    st.markdown("### 📋 Ringkasan Dokumen")
                    st.write(result.get("ringkasan"))
                    
                    st.markdown("### 💡 Rekomendasi Transformatif")
                    st.info(result.get("rekomendasi"))
                    
                except Exception as e:
                    st.error(f"Gagal memproses AI: {str(e)}")

# 5. TAB REKAP DATABASE LOKAL
with tab2:
    st.title("📊 Rekap Histori Nilai KBC Siswa")
    st.markdown("Seluruh nilai yang dianalisis oleh AI tersimpan secara permanen di database lokal komputer Anda (`kbc_evaluation.db`).")
    
    conn = sqlite3.connect("kbc_evaluation.db")
    df_db = pd.read_sql_query("SELECT * FROM penilaian_kbc ORDER BY id DESC", conn)
    conn.close()
    
    if not df_db.empty:
        # Mengubah nama kolom agar lebih mudah dibaca user
        df_db.columns = [
            "ID", "Nama Siswa", "Tanggal Evaluasi", "Ringkasan", 
            "Cinta Allah & Rasul", "Cinta Diri & Sesama", "Cinta Alam", 
            "Cinta Tanah Air", "Cinta Ilmu", "Rata-rata Indeks", "Rekomendasi"
        ]
        
        # Opsi Pencarian Siswa di Database (Search Engine Internal)
        search_query = st.text_input("🔍 Cari berdasarkan nama siswa di database:")
        if search_query:
            df_db = df_db[df_db["Nama Siswa"].str.contains(search_query, case=False, na=False)]
            
        st.dataframe(df_db, use_container_width=True, hide_index=True)
        
        # Fitur download laporan Excel/CSV
        csv = df_db.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Unduh Seluruh Data Rekap (CSV)",
            data=csv,
            file_name=f"rekap_nilai_kbc_{datetime.now().strftime('%Y%m%d')}.csv",
            mime='text/csv'
        )
    else:
        st.info("Database masih kosong. Silakan lakukan penilaian pertama di Tab 1.")
