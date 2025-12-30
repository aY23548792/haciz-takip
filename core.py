#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HACİZ TAKİP SİSTEMİ - MVP Core
Satış hedefi: İcra avukatları için haciz süre takip ve risk uyarı sistemi
"""

import pandas as pd
import re
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum

class RiskSeviyesi(Enum):
    KRITIK = "🔴 KRİTİK"      # 0-30 gün
    YUKSEK = "🟠 YÜKSEK"      # 31-90 gün
    ORTA = "🟡 ORTA"          # 91-180 gün
    DUSUK = "🟢 DÜŞÜK"        # 181-365 gün
    GUVENLI = "⚪ GÜVENLİ"    # 365+ gün veya düşmüş

class MalTuru(Enum):
    TASINMAZ = "Taşınmaz"
    ARAC = "Araç"
    MENKUL = "Menkul"
    BANKA = "Banka Hesabı"
    DIGER = "Diğer"

@dataclass
class HacizKaydi:
    dosya_no: str
    borclu_adi: str
    tckn: Optional[str]
    mal_turu: MalTuru
    haciz_tarihi: datetime
    dusme_tarihi: datetime
    kalan_gun: int
    risk: RiskSeviyesi
    detay: str
    kaynak_sekme: str

@dataclass
class ParseSonucu:
    basarili: int
    basarisiz: int
    toplam: int
    kayitlar: List[HacizKaydi]
    hatalar: List[str]

class HacizTakipCore:
    """Ana iş mantığı sınıfı"""
    
    # 7343 sayılı Kanun (30.11.2021) öncesi/sonrası süre farkı
    KANUN_7343_TARIHI = datetime(2021, 11, 30)
    
    def __init__(self):
        self.bugun = datetime.now()
        
        # Her sekme için parse pattern'ları
        self.parse_patterns = {
            'derdest': {
                'borclu': r'BORÇLULAR?:\s*([^|]+)',
                'dosya_no': r'DOSYA NO:\s*([^|]+)',
                'tckn': r'(\d{11})\s*-\s*',
                'tarih_sutun': 'TAKİP TARİHİ'
            },
            'btidk': {
                'borclu': r'Müşteri Ad Soyad/Unvan',  # Sütun adı
                'dosya_no': r'İcra Dosya No',
                'tckn': None,
                'tarih_sutun': 'Takibe Geçiş Tarihi'
            },
            'ticari': {
                'borclu': r'BORÇLULAR?:\s*([^|]+)',
                'dosya_no': r'DOSYA NO:\s*([^|]+)',
                'tckn': r'(\d{11})\s*-\s*',
                'tarih_sutun': 'TAKİP TARİHİ'
            },
            'tasinmaz': {
                'borclu': 'BORÇLU İSMİ',
                'dosya_no': 'DOSYA NO',
                'tckn': 'TCKN',
                'tarih_sutun': 'HACİZ TARİHİ'
            },
            'arac': {
                'borclu': 'BORÇLU İSMİ',
                'dosya_no': 'DOSYA NO',
                'tckn': 'TCKN',
                'tarih_sutun': 'HACİZ TARİHİ'
            },
            'mahrumiyet': {
                'borclu': None,
                'dosya_no': 'ESAS_NO',
                'tckn': None,
                'tarih_sutun': 'EKLEME_TARIHI'
            }
        }
    
    def sekme_tipi_belirle(self, sekme_adi: str) -> str:
        """Sekme adından parse tipini belirle"""
        sekme_lower = sekme_adi.lower()
        
        if 'derdest' in sekme_lower:
            return 'derdest'
        elif 'btidk' in sekme_lower and 'infaz' not in sekme_lower:
            return 'btidk'
        elif 'ticari' in sekme_lower and 'sorgu' not in sekme_lower:
            return 'ticari'
        elif 'taşınmaz' in sekme_lower or 'tasinmaz' in sekme_lower:
            return 'tasinmaz'
        elif 'araç' in sekme_lower or 'arac' in sekme_lower:
            return 'arac'
        elif 'mahrumiyet' in sekme_lower:
            return 'mahrumiyet'
        elif '121' in sekme_lower:
            return 'tasinmaz'
        elif '103' in sekme_lower:
            return 'tasinmaz'
        elif 'kıymet' in sekme_lower or 'kiymet' in sekme_lower:
            return 'tasinmaz'
        else:
            return 'derdest'  # Default
    
    def mal_turu_belirle(self, sekme_adi: str, detay: str = "") -> MalTuru:
        """Sekme adı ve detaydan mal türünü belirle"""
        sekme_lower = sekme_adi.lower()
        detay_lower = detay.lower() if detay else ""
        
        if 'araç' in sekme_lower or 'arac' in sekme_lower or 'plaka' in detay_lower:
            return MalTuru.ARAC
        elif 'taşınmaz' in sekme_lower or 'tasinmaz' in sekme_lower or '121' in sekme_lower:
            return MalTuru.TASINMAZ
        elif 'menkul' in sekme_lower:
            return MalTuru.MENKUL
        elif '89' in sekme_lower or 'banka' in detay_lower:
            return MalTuru.BANKA
        else:
            return MalTuru.DIGER
    
    def haciz_suresi_hesapla(self, haciz_tarihi: datetime, mal_turu: MalTuru) -> int:
        """
        İİK 106/110'a göre haciz düşme süresi hesapla
        7343 s.K. (30.11.2021) öncesi: Menkul 6 ay, Taşınmaz 1 yıl
        7343 s.K. sonrası: Hepsi 1 yıl
        """
        if haciz_tarihi < self.KANUN_7343_TARIHI:
            # Eski rejim
            if mal_turu in [MalTuru.MENKUL, MalTuru.ARAC]:
                return 180  # 6 ay
            else:
                return 365  # 1 yıl
        else:
            # Yeni rejim - hepsi 1 yıl
            return 365
    
    def risk_hesapla(self, haciz_tarihi: datetime, mal_turu: MalTuru) -> Tuple[datetime, int, RiskSeviyesi]:
        """Düşme tarihi, kalan gün ve risk seviyesi hesapla"""
        sure = self.haciz_suresi_hesapla(haciz_tarihi, mal_turu)
        dusme_tarihi = haciz_tarihi + timedelta(days=sure)
        kalan_gun = (dusme_tarihi - self.bugun).days
        
        if kalan_gun < 0:
            risk = RiskSeviyesi.GUVENLI  # Zaten düşmüş
        elif kalan_gun <= 30:
            risk = RiskSeviyesi.KRITIK
        elif kalan_gun <= 90:
            risk = RiskSeviyesi.YUKSEK
        elif kalan_gun <= 180:
            risk = RiskSeviyesi.ORTA
        elif kalan_gun <= 365:
            risk = RiskSeviyesi.DUSUK
        else:
            risk = RiskSeviyesi.GUVENLI
        
        return dusme_tarihi, kalan_gun, risk
    
    def tarih_parse(self, deger) -> Optional[datetime]:
        """Çeşitli formatlardaki tarihleri parse et"""
        if pd.isna(deger):
            return None
        
        # Zaten datetime ise
        if isinstance(deger, datetime):
            return deger
        
        # Pandas Timestamp ise
        if hasattr(deger, 'to_pydatetime'):
            return deger.to_pydatetime()
        
        # String ise
        deger_str = str(deger).strip()
        
        if not deger_str or deger_str.lower() in ['nan', 'none', 'nat', '']:
            return None
        
        formatlar = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%d.%m.%Y',
            '%d/%m/%Y',
            '%d-%m-%Y',
            '%d.%m.%y',
        ]
        
        for fmt in formatlar:
            try:
                dt = datetime.strptime(deger_str[:19], fmt)
                if 1990 <= dt.year <= 2030:
                    return dt
            except:
                continue
        
        return None
    
    def satir_parse_detay(self, detay: str, pattern_dict: dict) -> dict:
        """Detay string'inden veri çıkar"""
        sonuc = {'borclu': None, 'dosya_no': None, 'tckn': None}
        
        if not detay:
            return sonuc
        
        # Borçlu
        if pattern_dict.get('borclu') and '|' in detay:
            match = re.search(pattern_dict['borclu'], detay)
            if match:
                sonuc['borclu'] = match.group(1).strip()
        
        # Dosya No
        if pattern_dict.get('dosya_no') and '|' in detay:
            match = re.search(r'DOSYA NO:\s*([^|]+)', detay)
            if match:
                sonuc['dosya_no'] = match.group(1).strip()
        
        # TCKN
        if pattern_dict.get('tckn'):
            match = re.search(pattern_dict['tckn'], detay)
            if match:
                sonuc['tckn'] = match.group(1)
        
        return sonuc
    
    def sekme_isle(self, df: pd.DataFrame, sekme_adi: str) -> List[HacizKaydi]:
        """Tek bir sekmeyi işle ve HacizKaydi listesi döndür"""
        kayitlar = []
        sekme_tipi = self.sekme_tipi_belirle(sekme_adi)
        patterns = self.parse_patterns.get(sekme_tipi, self.parse_patterns['derdest'])
        mal_turu = self.mal_turu_belirle(sekme_adi)
        
        # Sütun isimlerini normalize et
        df.columns = [str(c).strip() for c in df.columns]
        
        for idx, row in df.iterrows():
            try:
                # Tarih sütununu bul
                tarih = None
                tarih_sutunlari = [
                    patterns.get('tarih_sutun'),
                    'HACİZ TARİHİ', 'HACIZ TARİHİ', 'Haciz Tarihi',
                    'TAKİP TARİHİ', 'Takip Tarihi', 'EKLEME_TARIHI',
                    'Takibe Geçiş Tarihi'
                ]
                
                for ts in tarih_sutunlari:
                    if ts and ts in df.columns:
                        tarih = self.tarih_parse(row[ts])
                        if tarih:
                            break
                
                if not tarih:
                    continue  # Tarih yoksa atla
                
                # Borçlu bilgisi
                borclu = None
                dosya_no = None
                tckn = None
                
                # Önce direkt sütunlardan dene
                borclu_sutunlari = ['BORÇLU İSMİ', 'Borçlu', 'BORÇLULAR', 
                                   'Müşteri Ad Soyad/Unvan', 'ANA KREDİ BORÇLUSU']
                for bs in borclu_sutunlari:
                    if bs in df.columns and pd.notna(row[bs]):
                        borclu = str(row[bs]).strip()
                        # TCKN - isim formatını temizle
                        if ' - ' in borclu:
                            parts = borclu.split(' - ')
                            if len(parts) == 2 and parts[0].isdigit():
                                tckn = parts[0]
                                borclu = parts[1]
                        break
                
                dosya_sutunlari = ['DOSYA NO', 'Dosya No', 'İcra Dosya No', 
                                  'ESAS_NO', 'Esas No']
                for ds in dosya_sutunlari:
                    if ds in df.columns and pd.notna(row[ds]):
                        dosya_no = str(row[ds]).strip()
                        break
                
                tckn_sutunlari = ['TCKN', 'TC_NO', 'Borçlu TCKN/VKN']
                for ts in tckn_sutunlari:
                    if ts in df.columns and pd.notna(row[ts]):
                        tckn_val = str(row[ts]).strip()
                        if tckn_val.isdigit() and len(tckn_val) in [10, 11]:
                            tckn = tckn_val
                            break
                
                # Detay sütunundan parse dene (Sağlam Köprü formatı)
                detay = ""
                if 'detaylar' in df.columns:
                    detay = str(row['detaylar']) if pd.notna(row['detaylar']) else ""
                    parsed = self.satir_parse_detay(detay, patterns)
                    if not borclu and parsed['borclu']:
                        borclu = parsed['borclu']
                    if not dosya_no and parsed['dosya_no']:
                        dosya_no = parsed['dosya_no']
                    if not tckn and parsed['tckn']:
                        tckn = parsed['tckn']
                
                # Minimum veri kontrolü
                if not dosya_no:
                    dosya_no = f"{sekme_adi}_{idx}"
                
                if not borclu:
                    borclu = "Bilinmeyen"
                
                # Risk hesapla
                dusme_tarihi, kalan_gun, risk = self.risk_hesapla(tarih, mal_turu)
                
                kayit = HacizKaydi(
                    dosya_no=dosya_no,
                    borclu_adi=borclu,
                    tckn=tckn,
                    mal_turu=mal_turu,
                    haciz_tarihi=tarih,
                    dusme_tarihi=dusme_tarihi,
                    kalan_gun=kalan_gun,
                    risk=risk,
                    detay=detay[:500] if detay else "",
                    kaynak_sekme=sekme_adi
                )
                kayitlar.append(kayit)
                
            except Exception as e:
                continue  # Hatalı satırı atla
        
        return kayitlar
    
    def excel_isle(self, dosya_yolu: str, secili_sekmeler: List[str] = None) -> ParseSonucu:
        """Excel dosyasını işle"""
        tum_kayitlar = []
        hatalar = []
        basarili = 0
        basarisiz = 0
        
        try:
            xl = pd.ExcelFile(dosya_yolu)
            sekmeler = secili_sekmeler or xl.sheet_names
            
            # Atlanacak sekmeler
            atla = ['şablon', 'sablon', 'şube', 'arşiv', 'arsiv', 'gm avukat', 
                   'borçlu bilgi', 'devir', 'infaz', 'vknyok']
            
            for sekme in sekmeler:
                sekme_lower = sekme.lower()
                
                # Atlanacak sekmeleri kontrol et
                if any(a in sekme_lower for a in atla):
                    continue
                
                try:
                    df = pd.read_excel(xl, sheet_name=sekme)
                    
                    if len(df) == 0:
                        continue
                    
                    kayitlar = self.sekme_isle(df, sekme)
                    tum_kayitlar.extend(kayitlar)
                    basarili += len(kayitlar)
                    
                except Exception as e:
                    hatalar.append(f"{sekme}: {str(e)}")
                    basarisiz += 1
            
        except Exception as e:
            hatalar.append(f"Dosya okuma hatası: {str(e)}")
        
        return ParseSonucu(
            basarili=basarili,
            basarisiz=basarisiz,
            toplam=basarili + basarisiz,
            kayitlar=tum_kayitlar,
            hatalar=hatalar
        )
    
    def csv_isle(self, dosya_yolu: str) -> ParseSonucu:
        """Sağlam Köprü CSV çıktısını işle (Varliklar.csv veya Hukuki_Islemler.csv)"""
        tum_kayitlar = []
        hatalar = []
        
        try:
            df = pd.read_csv(dosya_yolu)
            
            # Hukuki_Islemler.csv formatı
            if 'islem_tarihi' in df.columns and 'risk_seviyesi' in df.columns:
                for idx, row in df.iterrows():
                    try:
                        tarih = self.tarih_parse(row['islem_tarihi'])
                        if not tarih:
                            continue
                        
                        # Risk mapping
                        risk_map = {
                            'kritik': RiskSeviyesi.KRITIK,
                            'yüksek': RiskSeviyesi.YUKSEK,
                            'orta': RiskSeviyesi.ORTA,
                            'düşük': RiskSeviyesi.DUSUK,
                            'güvenli': RiskSeviyesi.GUVENLI
                        }
                        risk = risk_map.get(row['risk_seviyesi'], RiskSeviyesi.GUVENLI)
                        
                        kalan_gun = int(row['kalan_gun']) if pd.notna(row['kalan_gun']) else 0
                        dusme = self.tarih_parse(row['dusme_tarihi'])
                        
                        kayit = HacizKaydi(
                            dosya_no=str(row.get('dosya_id', idx)),
                            borclu_adi="CSV Import",
                            tckn=None,
                            mal_turu=MalTuru.DIGER,
                            haciz_tarihi=tarih,
                            dusme_tarihi=dusme or (tarih + timedelta(days=365)),
                            kalan_gun=kalan_gun,
                            risk=risk,
                            detay=str(row.get('aciklama', '')),
                            kaynak_sekme=row.get('kaynak', 'CSV')
                        )
                        tum_kayitlar.append(kayit)
                    except:
                        continue
            
            # Varliklar.csv formatı
            elif 'detaylar' in df.columns:
                patterns = self.parse_patterns['derdest']
                
                for idx, row in df.iterrows():
                    try:
                        detay = str(row['detaylar']) if pd.notna(row['detaylar']) else ""
                        parsed = self.satir_parse_detay(detay, patterns)
                        
                        # Tarih bul (detaydan)
                        tarih_match = re.search(r'TAKİP TARİHİ:\s*(\d{4}-\d{2}-\d{2})', detay)
                        if tarih_match:
                            tarih = self.tarih_parse(tarih_match.group(1))
                        else:
                            continue
                        
                        if not tarih:
                            continue
                        
                        mal_turu = MalTuru(row['varlik_tipi']) if row.get('varlik_tipi') in [e.value for e in MalTuru] else MalTuru.DIGER
                        dusme, kalan, risk = self.risk_hesapla(tarih, mal_turu)
                        
                        kayit = HacizKaydi(
                            dosya_no=parsed['dosya_no'] or str(idx),
                            borclu_adi=parsed['borclu'] or "Bilinmeyen",
                            tckn=parsed['tckn'],
                            mal_turu=mal_turu,
                            haciz_tarihi=tarih,
                            dusme_tarihi=dusme,
                            kalan_gun=kalan,
                            risk=risk,
                            detay=detay[:500],
                            kaynak_sekme=row.get('kaynak', 'CSV')
                        )
                        tum_kayitlar.append(kayit)
                    except:
                        continue
        
        except Exception as e:
            hatalar.append(str(e))
        
        return ParseSonucu(
            basarili=len(tum_kayitlar),
            basarisiz=0,
            toplam=len(tum_kayitlar),
            kayitlar=tum_kayitlar,
            hatalar=hatalar
        )
    
    def risk_ozeti(self, kayitlar: List[HacizKaydi]) -> Dict:
        """Risk özeti oluştur"""
        ozet = {
            'toplam': len(kayitlar),
            'kritik': 0,
            'yuksek': 0,
            'orta': 0,
            'dusuk': 0,
            'guvenli': 0,
            'kritik_liste': [],
            'yuksek_liste': []
        }
        
        for k in kayitlar:
            if k.risk == RiskSeviyesi.KRITIK:
                ozet['kritik'] += 1
                ozet['kritik_liste'].append(k)
            elif k.risk == RiskSeviyesi.YUKSEK:
                ozet['yuksek'] += 1
                ozet['yuksek_liste'].append(k)
            elif k.risk == RiskSeviyesi.ORTA:
                ozet['orta'] += 1
            elif k.risk == RiskSeviyesi.DUSUK:
                ozet['dusuk'] += 1
            else:
                ozet['guvenli'] += 1
        
        # Kalan güne göre sırala
        ozet['kritik_liste'].sort(key=lambda x: x.kalan_gun)
        ozet['yuksek_liste'].sort(key=lambda x: x.kalan_gun)
        
        return ozet
    
    def excel_export(self, kayitlar: List[HacizKaydi], dosya_adi: str):
        """Sonuçları Excel'e aktar"""
        data = []
        for k in kayitlar:
            data.append({
                'Dosya No': k.dosya_no,
                'Borçlu': k.borclu_adi,
                'TCKN': k.tckn or '',
                'Mal Türü': k.mal_turu.value,
                'Haciz Tarihi': k.haciz_tarihi.strftime('%d.%m.%Y'),
                'Düşme Tarihi': k.dusme_tarihi.strftime('%d.%m.%Y'),
                'Kalan Gün': k.kalan_gun,
                'Risk': k.risk.value,
                'Kaynak': k.kaynak_sekme
            })
        
        df = pd.DataFrame(data)
        
        # Risk sırasına göre sırala
        risk_sirasi = {
            RiskSeviyesi.KRITIK.value: 0,
            RiskSeviyesi.YUKSEK.value: 1,
            RiskSeviyesi.ORTA.value: 2,
            RiskSeviyesi.DUSUK.value: 3,
            RiskSeviyesi.GUVENLI.value: 4
        }
        df['_sira'] = df['Risk'].map(risk_sirasi)
        df = df.sort_values(['_sira', 'Kalan Gün']).drop('_sira', axis=1)
        
        df.to_excel(dosya_adi, index=False)
        return dosya_adi


# Test
if __name__ == "__main__":
    core = HacizTakipCore()
    
    # Test: Tarih parse
    print("Tarih parse testi:")
    test_tarihler = ["2024-06-15", "15.06.2024", "2024-06-15 00:00:00"]
    for t in test_tarihler:
        parsed = core.tarih_parse(t)
        print(f"  {t} -> {parsed}")
    
    # Test: Risk hesaplama
    print("\nRisk hesaplama testi:")
    test_tarih = datetime(2024, 12, 1)
    dusme, kalan, risk = core.risk_hesapla(test_tarih, MalTuru.TASINMAZ)
    print(f"  Haciz: {test_tarih.date()}")
    print(f"  Düşme: {dusme.date()}")
    print(f"  Kalan: {kalan} gün")
    print(f"  Risk: {risk.value}")
