#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HACİZ TAKİP SİSTEMİ - Web Arayüzü
Demo ve satış için Streamlit uygulaması
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import os
import sys
import tempfile

# Core modülü import et
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import HacizTakipCore, RiskSeviyesi, MalTuru, HacizKaydi, ParseSonucu

# Sayfa ayarları
st.set_page_config(
    page_title="Haciz Takip Sistemi",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E3A5F;
        text-align: center;
        padding: 1rem;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .kritik-box {
        background-color: #ffebee;
        border-left: 5px solid #f44336;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0 5px 5px 0;
    }
    .yuksek-box {
        background-color: #fff3e0;
        border-left: 5px solid #ff9800;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0 5px 5px 0;
    }
    .footer {
        text-align: center;
        color: #666;
        padding: 2rem;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

def main():
    # Header
    st.markdown('<div class="main-header">⚖️ Haciz Takip Sistemi</div>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #666; margin-top: -1rem;">İİK 106/110 Uyarınca Haciz Süre Takibi ve Risk Analizi</p>', unsafe_allow_html=True)
    
    # Session state
    if 'kayitlar' not in st.session_state:
        st.session_state.kayitlar = []
    if 'parse_sonucu' not in st.session_state:
        st.session_state.parse_sonucu = None
    
    # Sidebar
    with st.sidebar:
        st.header("📁 Dosya Yükleme")
        
        uploaded_file = st.file_uploader(
            "Excel veya CSV dosyası yükleyin",
            type=['xlsx', 'xls', 'csv'],
            help="Ziraat Dosya Listesi, Araç/Taşınmaz Haciz Raporu veya Sağlam Köprü CSV çıktısı"
        )
        
        if uploaded_file:
            st.success(f"✅ {uploaded_file.name}")
            
            if st.button("🔄 Analiz Et", type="primary", width="stretch"):
                with st.spinner("Dosya analiz ediliyor..."):
                    core = HacizTakipCore()
                    
                    # Dosyayı geçici kaydet
                    temp_path = os.path.join(tempfile.gettempdir(), uploaded_file.name)
                    with open(temp_path, 'wb') as f:
                        f.write(uploaded_file.getvalue())
                    
                    # Parse et
                    if uploaded_file.name.endswith('.csv'):
                        sonuc = core.csv_isle(temp_path)
                    else:
                        sonuc = core.excel_isle(temp_path)
                    
                    st.session_state.kayitlar = sonuc.kayitlar
                    st.session_state.parse_sonucu = sonuc
                    
                    # Geçici dosyayı sil
                    try:
                        os.remove(temp_path)
                    except:
                        pass  # Silinmezse önemli değil
                
                st.rerun()
        
        st.divider()
        
        # Filtreler
        st.header("🔍 Filtreler")
        
        risk_filtre = st.multiselect(
            "Risk Seviyesi",
            options=["🔴 KRİTİK", "🟠 YÜKSEK", "🟡 ORTA", "🟢 DÜŞÜK", "⚪ GÜVENLİ"],
            default=["🔴 KRİTİK", "🟠 YÜKSEK"]
        )
        
        mal_turu_filtre = st.multiselect(
            "Mal Türü",
            options=["Taşınmaz", "Araç", "Menkul", "Banka Hesabı", "Diğer"],
            default=["Taşınmaz", "Araç", "Menkul", "Banka Hesabı", "Diğer"]
        )
        
        st.divider()
        
        # Bilgi kutusu
        st.info("""
        **İİK 106/110 Süreleri:**
        - 7343 s.K. öncesi (< 30.11.2021):
          - Menkul/Araç: 6 ay
          - Taşınmaz: 1 yıl
        - 7343 s.K. sonrası (≥ 30.11.2021):
          - Tümü: 1 yıl
        """)
    
    # Ana içerik
    if st.session_state.kayitlar:
        kayitlar = st.session_state.kayitlar
        sonuc = st.session_state.parse_sonucu
        core = HacizTakipCore()
        ozet = core.risk_ozeti(kayitlar)
        
        # Üst metrikler
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric(
                label="📊 Toplam Kayıt",
                value=ozet['toplam'],
                help="Analiz edilen toplam haciz kaydı"
            )
        
        with col2:
            st.metric(
                label="🔴 Kritik",
                value=ozet['kritik'],
                delta=f"{ozet['kritik']} acil aksiyon" if ozet['kritik'] > 0 else None,
                delta_color="inverse"
            )
        
        with col3:
            st.metric(
                label="🟠 Yüksek Risk",
                value=ozet['yuksek'],
                help="90 gün içinde düşecek hacizler"
            )
        
        with col4:
            st.metric(
                label="🟡 Orta Risk",
                value=ozet['orta'],
                help="90-180 gün arası"
            )
        
        with col5:
            st.metric(
                label="🟢 Güvenli",
                value=ozet['guvenli'] + ozet['dusuk'],
                help="180+ gün veya düşmüş"
            )
        
        st.divider()
        
        # Sekmeler
        tab1, tab2, tab3, tab4 = st.tabs(["🚨 Kritik Uyarılar", "📋 Tüm Kayıtlar", "📊 Grafikler", "📥 Dışa Aktar"])
        
        # Tab 1: Kritik Uyarılar
        with tab1:
            st.subheader("🔴 Kritik Riskli Hacizler (30 gün içinde düşecek)")
            
            if ozet['kritik_liste']:
                for k in ozet['kritik_liste'][:20]:  # İlk 20
                    with st.container():
                        st.markdown(f"""
                        <div class="kritik-box">
                            <strong>📁 {k.dosya_no}</strong> | <strong>{k.borclu_adi}</strong><br>
                            <small>
                                {k.mal_turu.value} | Haciz: {k.haciz_tarihi.strftime('%d.%m.%Y')} | 
                                Düşme: {k.dusme_tarihi.strftime('%d.%m.%Y')} | 
                                <span style="color: red; font-weight: bold;">⏰ {k.kalan_gun} gün kaldı!</span>
                            </small>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.success("✅ Kritik riskli haciz bulunmuyor!")
            
            st.subheader("🟠 Yüksek Riskli Hacizler (31-90 gün)")
            
            if ozet['yuksek_liste']:
                for k in ozet['yuksek_liste'][:20]:
                    with st.container():
                        st.markdown(f"""
                        <div class="yuksek-box">
                            <strong>📁 {k.dosya_no}</strong> | <strong>{k.borclu_adi}</strong><br>
                            <small>
                                {k.mal_turu.value} | Haciz: {k.haciz_tarihi.strftime('%d.%m.%Y')} | 
                                Düşme: {k.dusme_tarihi.strftime('%d.%m.%Y')} | 
                                <span style="color: orange; font-weight: bold;">⏰ {k.kalan_gun} gün kaldı</span>
                            </small>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("ℹ️ Yüksek riskli haciz bulunmuyor.")
        
        # Tab 2: Tüm Kayıtlar
        with tab2:
            st.subheader("📋 Tüm Haciz Kayıtları")
            
            # Filtreleme
            filtered = kayitlar
            
            if risk_filtre:
                filtered = [k for k in filtered if k.risk.value in risk_filtre]
            
            if mal_turu_filtre:
                filtered = [k for k in filtered if k.mal_turu.value in mal_turu_filtre]
            
            # DataFrame oluştur
            if filtered:
                df_data = []
                for k in filtered:
                    df_data.append({
                        'Risk': k.risk.value,
                        'Dosya No': k.dosya_no,
                        'Borçlu': k.borclu_adi,
                        'TCKN': k.tckn or '-',
                        'Mal Türü': k.mal_turu.value,
                        'Haciz Tarihi': k.haciz_tarihi.strftime('%d.%m.%Y'),
                        'Düşme Tarihi': k.dusme_tarihi.strftime('%d.%m.%Y'),
                        'Kalan Gün': k.kalan_gun,
                        'Kaynak': k.kaynak_sekme
                    })
                
                df_display = pd.DataFrame(df_data)
                
                # Sıralama
                risk_order = {"🔴 KRİTİK": 0, "🟠 YÜKSEK": 1, "🟡 ORTA": 2, "🟢 DÜŞÜK": 3, "⚪ GÜVENLİ": 4}
                df_display['_sort'] = df_display['Risk'].map(risk_order)
                df_display = df_display.sort_values(['_sort', 'Kalan Gün']).drop('_sort', axis=1)
                
                st.dataframe(
                    df_display,
                    width="stretch",
                    height=500,
                    column_config={
                        'Risk': st.column_config.TextColumn('Risk', width='small'),
                        'Kalan Gün': st.column_config.NumberColumn('Kalan Gün', format='%d gün')
                    }
                )
                
                st.caption(f"Toplam {len(filtered)} kayıt gösteriliyor (filtrelenmiş)")
            else:
                st.warning("Seçili filtrelere uygun kayıt bulunamadı.")
        
        # Tab 3: Grafikler
        with tab3:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Risk Dağılımı")
                
                risk_data = {
                    'Risk': ['Kritik', 'Yüksek', 'Orta', 'Düşük', 'Güvenli'],
                    'Adet': [ozet['kritik'], ozet['yuksek'], ozet['orta'], ozet['dusuk'], ozet['guvenli']],
                    'Renk': ['#f44336', '#ff9800', '#ffc107', '#4caf50', '#9e9e9e']
                }
                df_risk = pd.DataFrame(risk_data)
                
                fig_pie = px.pie(
                    df_risk, 
                    values='Adet', 
                    names='Risk',
                    color='Risk',
                    color_discrete_map={
                        'Kritik': '#f44336',
                        'Yüksek': '#ff9800', 
                        'Orta': '#ffc107',
                        'Düşük': '#4caf50',
                        'Güvenli': '#9e9e9e'
                    },
                    hole=0.4
                )
                fig_pie.update_layout(showlegend=True, height=350)
                st.plotly_chart(fig_pie, width="stretch")
            
            with col2:
                st.subheader("Mal Türü Dağılımı")
                
                mal_turu_sayim = {}
                for k in kayitlar:
                    mt = k.mal_turu.value
                    mal_turu_sayim[mt] = mal_turu_sayim.get(mt, 0) + 1
                
                df_mal = pd.DataFrame({
                    'Mal Türü': list(mal_turu_sayim.keys()),
                    'Adet': list(mal_turu_sayim.values())
                })
                
                fig_bar = px.bar(
                    df_mal,
                    x='Mal Türü',
                    y='Adet',
                    color='Mal Türü',
                    color_discrete_sequence=px.colors.qualitative.Set2
                )
                fig_bar.update_layout(showlegend=False, height=350)
                st.plotly_chart(fig_bar, width="stretch")
            
            # Zaman çizelgesi
            st.subheader("📅 Düşme Tarihi Takvimi (Önümüzdeki 90 Gün)")
            
            bugun = datetime.now()
            son_90_gun = bugun + timedelta(days=90)
            
            yaklasan = [k for k in kayitlar if bugun <= k.dusme_tarihi <= son_90_gun]
            yaklasan.sort(key=lambda x: x.dusme_tarihi)
            
            if yaklasan:
                timeline_data = []
                for k in yaklasan[:50]:  # İlk 50
                    timeline_data.append({
                        'Dosya': k.dosya_no,
                        'Tarih': k.dusme_tarihi,
                        'Kalan': k.kalan_gun,
                        'Risk': 'Kritik' if k.kalan_gun <= 30 else 'Yüksek'
                    })
                
                df_timeline = pd.DataFrame(timeline_data)
                
                fig_timeline = px.scatter(
                    df_timeline,
                    x='Tarih',
                    y='Dosya',
                    color='Risk',
                    size='Kalan',
                    color_discrete_map={'Kritik': '#f44336', 'Yüksek': '#ff9800'},
                    hover_data=['Kalan']
                )
                fig_timeline.update_layout(height=400, showlegend=True)
                # Bugün çizgisi (hata verirse atla)
                try:
                    fig_timeline.add_vline(x=datetime.now().timestamp() * 1000, line_dash="dash", line_color="blue")
                except:
                    pass  # Grafik çizgisiz de çalışır
                st.plotly_chart(fig_timeline, width="stretch")
            else:
                st.info("Önümüzdeki 90 gün içinde düşecek haciz bulunmuyor.")
        
        # Tab 4: Dışa Aktar
        with tab4:
            st.subheader("📥 Rapor İndir")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Excel Raporu")
                st.write("Tüm kayıtları risk sırasına göre Excel dosyası olarak indirin.")
                
                if st.button("📊 Excel Oluştur", type="primary"):
                    # DataFrame oluştur
                    export_data = []
                    for k in kayitlar:
                        export_data.append({
                            'Risk': k.risk.value,
                            'Dosya No': k.dosya_no,
                            'Borçlu': k.borclu_adi,
                            'TCKN': k.tckn or '',
                            'Mal Türü': k.mal_turu.value,
                            'Haciz Tarihi': k.haciz_tarihi.strftime('%d.%m.%Y'),
                            'Düşme Tarihi': k.dusme_tarihi.strftime('%d.%m.%Y'),
                            'Kalan Gün': k.kalan_gun,
                            'Kaynak': k.kaynak_sekme
                        })
                    
                    df_export = pd.DataFrame(export_data)
                    
                    # Risk sırasına göre sırala
                    risk_order = {"🔴 KRİTİK": 0, "🟠 YÜKSEK": 1, "🟡 ORTA": 2, "🟢 DÜŞÜK": 3, "⚪ GÜVENLİ": 4}
                    df_export['_sort'] = df_export['Risk'].map(risk_order)
                    df_export = df_export.sort_values(['_sort', 'Kalan Gün']).drop('_sort', axis=1)
                    
                    # Excel buffer
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df_export.to_excel(writer, index=False, sheet_name='Tüm Hacizler')
                        
                        # Kritik ve Yüksek için ayrı sekmeler
                        kritik_data = [d for d in export_data if '🔴' in d['Risk']]
                        yuksek_data = [d for d in export_data if '🟠' in d['Risk']]
                        
                        if kritik_data:
                            pd.DataFrame(kritik_data).to_excel(writer, index=False, sheet_name='Kritik Riskler')
                        if yuksek_data:
                            pd.DataFrame(yuksek_data).to_excel(writer, index=False, sheet_name='Yüksek Riskler')
                    
                    st.download_button(
                        label="⬇️ Excel İndir",
                        data=buffer.getvalue(),
                        file_name=f"haciz_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            
            with col2:
                st.markdown("### Özet Rapor")
                st.write("Kritik ve yüksek riskli dosyaların özetini indirin.")
                
                rapor_metni = f"""
HACIZ TAKİP SİSTEMİ - ÖZET RAPOR
================================
Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}

GENEL ÖZET
----------
Toplam Kayıt: {ozet['toplam']}
🔴 Kritik (0-30 gün): {ozet['kritik']}
🟠 Yüksek (31-90 gün): {ozet['yuksek']}
🟡 Orta (91-180 gün): {ozet['orta']}
🟢 Düşük/Güvenli: {ozet['dusuk'] + ozet['guvenli']}

KRİTİK RİSKLİ DOSYALAR
----------------------
"""
                for k in ozet['kritik_liste'][:10]:
                    rapor_metni += f"• {k.dosya_no} | {k.borclu_adi} | {k.kalan_gun} gün kaldı\n"
                
                rapor_metni += f"""

YÜKSEK RİSKLİ DOSYALAR
----------------------
"""
                for k in ozet['yuksek_liste'][:10]:
                    rapor_metni += f"• {k.dosya_no} | {k.borclu_adi} | {k.kalan_gun} gün kaldı\n"
                
                rapor_metni += """

---
Bu rapor Haciz Takip Sistemi tarafından otomatik oluşturulmuştur.
İİK 106/110 ve 7343 s.K. hükümlerine göre hesaplanmıştır.
"""
                
                st.download_button(
                    label="⬇️ Özet İndir (TXT)",
                    data=rapor_metni,
                    file_name=f"haciz_ozet_{datetime.now().strftime('%Y%m%d')}.txt",
                    mime="text/plain"
                )
    
    else:
        # Boş durum - hoş geldin ekranı
        st.markdown("""
        <div style="text-align: center; padding: 3rem;">
            <h2>📁 Başlamak için bir dosya yükleyin</h2>
            <p style="color: #666;">
                Sol menüden Excel veya CSV dosyanızı yükleyerek haciz analizi yapabilirsiniz.
            </p>
            <br>
            <h4>Desteklenen Formatlar:</h4>
            <ul style="list-style: none; padding: 0;">
                <li>✅ Ziraat Dosya Listesi (.xlsx)</li>
                <li>✅ Araç/Taşınmaz Haciz Raporu (.xlsx)</li>
                <li>✅ Sağlam Köprü CSV çıktıları</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        # Demo butonu
        st.divider()
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🎮 Demo Verisiyle Dene", width="stretch"):
                # Demo veri oluştur
                core = HacizTakipCore()
                demo_kayitlar = []
                
                demo_data = [
                    ("2024/12345", "Ali Yılmaz", "12345678901", MalTuru.TASINMAZ, -25),
                    ("2024/12346", "Mehmet Demir", "23456789012", MalTuru.ARAC, -15),
                    ("2024/12347", "Ayşe Kaya", "34567890123", MalTuru.TASINMAZ, -5),
                    ("2024/12348", "Fatma Öz", "45678901234", MalTuru.MENKUL, -60),
                    ("2024/12349", "Hasan Çelik", "56789012345", MalTuru.TASINMAZ, -75),
                    ("2024/12350", "Zeynep Ak", "67890123456", MalTuru.ARAC, -120),
                    ("2024/12351", "Mustafa Er", "78901234567", MalTuru.TASINMAZ, -200),
                    ("2024/12352", "Elif Su", "89012345678", MalTuru.BANKA, -300),
                ]
                
                for dosya, borclu, tckn, mal, gun_once in demo_data:
                    haciz_tarihi = datetime.now() + timedelta(days=gun_once) - timedelta(days=365)
                    dusme, kalan, risk = core.risk_hesapla(haciz_tarihi, mal)
                    
                    demo_kayitlar.append(HacizKaydi(
                        dosya_no=dosya,
                        borclu_adi=borclu,
                        tckn=tckn,
                        mal_turu=mal,
                        haciz_tarihi=haciz_tarihi,
                        dusme_tarihi=dusme,
                        kalan_gun=kalan,
                        risk=risk,
                        detay="Demo veri",
                        kaynak_sekme="Demo"
                    ))
                
                st.session_state.kayitlar = demo_kayitlar
                st.session_state.parse_sonucu = ParseSonucu(
                    basarili=len(demo_kayitlar),
                    basarisiz=0,
                    toplam=len(demo_kayitlar),
                    kayitlar=demo_kayitlar,
                    hatalar=[]
                )
                st.rerun()
    
    # Footer
    st.markdown("""
    <div class="footer">
        <hr>
        <p>
            ⚖️ <strong>Haciz Takip Sistemi</strong> v1.0 | 
            İİK 106/110 ve 7343 s.K. hükümlerine uygun | 
            © 2024 - Tüm hakları saklıdır
        </p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
