import streamlit as st
import gspread
import holidays
import hashlib
import calendar as _calendar_mod
from datetime import datetime, timedelta, date
from babel.dates import format_date
from utils import *

load_functions_from("functions", globals())

ferie_sheet_id = None
try:
    ferie_sheet_id = st.secrets.get("FERIE_GSHEET_ID")
except Exception:
    ferie_sheet_id = None

# --- Calendario ferie: costanti e helper ---
_PALETTE_CALENDARIO = ["#4C6EF5", "#12B886", "#F59F00", "#E64980", "#7048E8",
                       "#15AABF", "#FA5252", "#82C91E", "#228BE6", "#F76707"]
_GIORNI_IT = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
_MESI_IT = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
MESI_IT_LUNGO = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
                  "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

def tema_colori():
    try:
        is_dark = st.context.theme.type == "dark"
    except Exception:
        is_dark = False

    if is_dark:
        return {
            "card_bg": "#262730",
            "card_border": "#3b3c46",
            "text_primary": "#e6e6e6",
            "text_secondary": "#a3a8b8",
            "oggi_bg": "#1f2b4d",
            "weekend_bg": "#1c1d24",
            "festivo_bg": "#3d2f14",
            "fuori_mese_bg": "#1c1d24",
            "fuori_mese_text": "#5a5b66",
            "bar_track": "#3b3c46",
            "divider": "#3b3c46",
            "accent_bg": "#16233d",
        }
    return {
        "card_bg": "#f9f9f9",
        "card_border": "#e6e9ef",
        "text_primary": "#31333F",
        "text_secondary": "#555555",
        "oggi_bg": "#EEF2FF",
        "weekend_bg": "#ECECEC",
        "festivo_bg": "#FFF3E0",
        "fuori_mese_bg": "#FAFAFA",
        "fuori_mese_text": "#c9c9c9",
        "bar_track": "#e6e9ef",
        "divider": "#e6e9ef",
        "accent_bg": "#f0f7ff",
    }

def _colore_per_nome(nome):
    h = int(hashlib.md5(nome.encode("utf-8")).hexdigest(), 16)
    return _PALETTE_CALENDARIO[h % len(_PALETTE_CALENDARIO)]

def _assenze_nel_periodo(df_storico, giorni):
    assenze = {g: [] for g in giorni}
    if not df_storico.empty:
        for _, riga in df_storico.iterrows():
            try:
                inizio_f = pd.to_datetime(riga['DATA INIZIO'], dayfirst=True, errors='raise').date()
                fine_f = pd.to_datetime(riga['DATA FINE'], dayfirst=True, errors='raise').date()
            except Exception:
                continue
            tipo = riga.get('TIPO', '') or ''
            giorni_val = pd.to_numeric(riga.get('GIORNI LAVORATIVI'), errors='coerce')
            dettaglio = str(riga.get('DETTAGLIO', '') or '').strip()
            for g in giorni:
                if inizio_f <= g <= fine_f:
                    assenze[g].append({
                        "nome": riga['NOME'], "tipo": tipo, "giorni": giorni_val,
                        "dettaglio": dettaglio, "inizio": inizio_f, "fine": fine_f,
                    })
    return assenze

def _mappa_ore_previste(df_dipendenti):
    mappa = {}
    if df_dipendenti is not None and not df_dipendenti.empty:
        for _, riga in df_dipendenti.iterrows():
            mappa[riga['NOME']] = ore_giornaliere_previste(get_orario_dipendente(riga))
    return mappa

def _chip_html(assenza, opacity="1", ore_previste_dipendente=8.0):
    nome = assenza["nome"]
    tipo = assenza.get("tipo") or ""
    giorni_val = assenza.get("giorni")
    dettaglio = assenza.get("dettaglio") or ""
    colore = _colore_per_nome(nome)
    primo_nome = str(nome).split()[0] if nome else "?"

    is_parziale = tipo == "Permesso Orario"

    if tipo and tipo not in ["Ferie", "Permesso Orario"]:
        descrizione = tipo
        icona = ""
    elif is_parziale and dettaglio:
        descrizione = dettaglio
        icona = "🕐 "
    elif is_parziale:
        ore_stimate = round(float(giorni_val) * ore_previste_dipendente * 2) / 2
        descrizione = f"Permesso orario (~{ore_stimate:g}h)"
        icona = "🕐 "
    else:
        descrizione = "Ferie"
        icona = ""

    tooltip = f"{descrizione}"

    inizio_a, fine_a = assenza.get("inizio"), assenza.get("fine")
    if inizio_a and fine_a and inizio_a != fine_a:
        if dettaglio.lower() == "rettifica":
            tooltip += f" — Rettifica"
        else:
            inizio_str = format_date(inizio_a, format="d MMMM", locale="it_IT")
            fine_str = format_date(fine_a, format="d MMMM", locale="it_IT")
            tooltip += f" — Dal {inizio_str} al {fine_str}"

    return (
        f'<div title="{tooltip}" style="background:{colore}22; color:{colore}; '
        f'border:1px solid {colore}55; border-radius:6px; padding:2px 6px; '
        f'font-size:11px; font-weight:600; margin-top:4px; white-space:nowrap; '
        f'overflow:hidden; text-overflow:ellipsis; opacity:{opacity};">{icona}{primo_nome}</div>'
    )

def build_calendario_ferie_html(df_storico, df_dipendenti=None):
    oggi = datetime.now().date()
    inizio_settimana = oggi - timedelta(days=oggi.weekday())
    giorni_totali = [inizio_settimana + timedelta(days=i) for i in range(14)]
    assenze_per_giorno = _assenze_nel_periodo(df_storico, giorni_totali)
    mappa_ore = _mappa_ore_previste(df_dipendenti)
    t = tema_colori()

    anni_griglia = {g.year for g in giorni_totali}
    festivi_it = holidays.Italy(years=list(anni_griglia))

    parts = ['<div style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;">']

    for settimana_idx in range(2):
        settimana_giorni_full = giorni_totali[settimana_idx * 7:(settimana_idx + 1) * 7]
        settimana_giorni = [g for g in settimana_giorni_full if g.weekday() < 5]
        label = "Questa settimana" if settimana_idx == 0 else "Prossima settimana"
        margine_top = "0" if settimana_idx == 0 else "20px"
        parts.append(
            f'<div style="font-size:12px; font-weight:700; color:{t["text_secondary"]}; '
            f'text-transform:uppercase; letter-spacing:0.6px; margin:{margine_top} 0 8px 2px;">{label}</div>'
        )
        parts.append('<div style="overflow-x:auto;">')
        parts.append('<div style="display:grid; grid-template-columns:repeat(5, 1fr); gap:8px; min-width:430px;">')

        for g in settimana_giorni:
            is_oggi = (g == oggi)
            e_festivo = g in festivi_it
            assenze_giorno = [] if e_festivo else assenze_per_giorno[g]

            if is_oggi:
                bg = t["oggi_bg"]
            elif e_festivo:
                bg = t["festivo_bg"]
            else:
                bg = t["card_bg"]
            border = f'2px solid #4C6EF5' if is_oggi else f'1px solid {t["card_border"]}'
            chips = "".join(
                _chip_html(a, ore_previste_dipendente=mappa_ore.get(a["nome"], 8.0))
                for a in assenze_giorno
                if (a.get("dettaglio") or "").lower() != "rettifica"
            )

            giorno_label = _GIORNI_IT[g.weekday()]
            mese_label = f" {_MESI_IT[g.month - 1]}" if (g.day == 1 or g == giorni_totali[0]) else ""

            parts.append(
                f'<div style="background:{bg}; border:{border}; border-radius:10px; padding:8px; min-height:76px;">'
                f'<div style="font-size:10px; color:{t["text_secondary"]}; font-weight:700; text-transform:uppercase;">{giorno_label}</div>'
                f'<div style="font-size:15px; font-weight:700; color:{t["text_primary"]};">{g.day}{mese_label}</div>'
                f'{chips}'
                f'</div>'
            )

        parts.append('</div></div>')

    parts.append('</div>')
    return "".join(parts)

def build_calendario_mensile_html(df_storico, anno, mese, df_dipendenti=None):
    oggi = datetime.now().date()
    primo_giorno = date(anno, mese, 1)
    ultimo_giorno_num = _calendar_mod.monthrange(anno, mese)[1]
    ultimo_giorno = date(anno, mese, ultimo_giorno_num)

    inizio_griglia = primo_giorno - timedelta(days=primo_giorno.weekday())
    fine_griglia = ultimo_giorno + timedelta(days=(6 - ultimo_giorno.weekday()))

    giorni_totali = []
    g = inizio_griglia
    while g <= fine_griglia:
        giorni_totali.append(g)
        g += timedelta(days=1)

    assenze_per_giorno = _assenze_nel_periodo(df_storico, giorni_totali)
    mappa_ore = _mappa_ore_previste(df_dipendenti)
    t = tema_colori()

    anni_griglia = {g.year for g in giorni_totali}
    festivi_it = holidays.Italy(years=list(anni_griglia))

    parts = ['<div style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;">']
    parts.append('<div style="overflow-x:auto;">')
    parts.append('<div style="display:grid; grid-template-columns:repeat(7, 1fr); gap:8px; min-width:600px;">')

    for g in giorni_totali:
        is_oggi = (g == oggi)
        e_weekend = g.weekday() >= 5
        e_festivo = g in festivi_it
        nascondi_nomi = e_weekend or e_festivo
        fuori_mese = (g.month != mese)
        assenze_giorno = [] if nascondi_nomi else assenze_per_giorno[g]

        if fuori_mese:
            bg = t["oggi_bg"] if is_oggi else t["fuori_mese_bg"]
            border = f'1px solid {t["card_border"]}'
            colore_numero = t["fuori_mese_text"]
            opacity_chip = "0.5"
        else:
            if is_oggi:
                bg = t["oggi_bg"]
            elif e_festivo:
                bg = t["festivo_bg"]
            elif e_weekend:
                bg = t["weekend_bg"]
            else:
                bg = t["card_bg"]
            border = f'2px solid #4C6EF5' if is_oggi else f'1px solid {t["card_border"]}'
            colore_numero = t["text_primary"]
            opacity_chip = "1"

        chips = "".join(
            _chip_html(a, ore_previste_dipendente=mappa_ore.get(a["nome"], 8.0))
            for a in assenze_giorno
            if (a.get("dettaglio") or "").lower() != "rettifica"
        )

        giorno_label = _GIORNI_IT[g.weekday()]

        parts.append(
            f'<div style="background:{bg}; border:{border}; border-radius:10px; padding:8px; min-height:76px;">'
            f'<div style="font-size:10px; color:{t["text_secondary"]}; font-weight:700; text-transform:uppercase;">{giorno_label}</div>'
            f'<div style="font-size:15px; font-weight:700; color:{colore_numero};">{g.day}</div>'
            f'{chips}'
            f'</div>'
        )

    parts.append('</div></div>')
    parts.append('</div>')
    return "".join(parts)

ORARIO_DEFAULT = {"mattina_inizio": "08:00", "mattina_fine": "12:00",
                   "pomeriggio_inizio": "14:00", "pomeriggio_fine": "18:00"}
_DATA_RIF_ORARIO = date(2000, 1, 1)

def time_slider(label, value, key):
    minuti_default = value.hour * 60 + value.minute
    minuti_default = round(minuti_default / 15) * 15
    minuti_default = min(max(minuti_default, 0), 23 * 60 + 45)
    minuti = st.select_slider(
        label,
        options=list(range(0, 24 * 60, 15)),
        value=minuti_default,
        format_func=lambda m: f"{m // 60:02d}:{m % 60:02d}",
        key=key,
    )
    from datetime import time as _time
    return _time(minuti // 60, minuti % 60)

def _parse_ora(valore, default_str):
    try:
        return datetime.strptime(str(valore).strip(), "%H:%M").time()
    except Exception:
        return datetime.strptime(default_str, "%H:%M").time()

def get_orario_dipendente(row_dipendente):
    getter = row_dipendente.get if hasattr(row_dipendente, "get") else (lambda k, d=None: getattr(row_dipendente, k, d))
    return {
        "mattina_inizio": _parse_ora(getter("MATTINA INIZIO", None), ORARIO_DEFAULT["mattina_inizio"]),
        "mattina_fine": _parse_ora(getter("MATTINA FINE", None), ORARIO_DEFAULT["mattina_fine"]),
        "pomeriggio_inizio": _parse_ora(getter("POMERIGGIO INIZIO", None), ORARIO_DEFAULT["pomeriggio_inizio"]),
        "pomeriggio_fine": _parse_ora(getter("POMERIGGIO FINE", None), ORARIO_DEFAULT["pomeriggio_fine"]),
    }

def ore_giornaliere_previste(orario):
    mattina = datetime.combine(_DATA_RIF_ORARIO, orario["mattina_fine"]) - datetime.combine(_DATA_RIF_ORARIO, orario["mattina_inizio"])
    pomeriggio = datetime.combine(_DATA_RIF_ORARIO, orario["pomeriggio_fine"]) - datetime.combine(_DATA_RIF_ORARIO, orario["pomeriggio_inizio"])
    return (mattina.total_seconds() + pomeriggio.total_seconds()) / 3600

def calcola_riepilogo_ferie_annuale(df_storico, nome, totale_annuo):
    oggi_anno = datetime.now().year
    totale_annuo = float(totale_annuo) if totale_annuo not in (None, "") else 0.0

    date_valide = []
    if not df_storico.empty and 'NOME' in df_storico.columns:
        dip_ferie = df_storico[(df_storico['NOME'] == nome) & (df_storico.get('TIPO').isin(['Ferie', 'Permesso Orario', 'Rettifica']))]
        for _, riga in dip_ferie.iterrows():
            try:
                inizio_f = pd.to_datetime(riga['DATA INIZIO'], dayfirst=True, errors='raise').date()
            except Exception:
                continue
            giorni_val = pd.to_numeric(riga.get('GIORNI LAVORATIVI', 0), errors='coerce')
            date_valide.append((inizio_f.year, float(giorni_val) if pd.notna(giorni_val) else 0.0))

    anni = {a for a, _ in date_valide}
    anni.add(oggi_anno)
    anno_min, anno_max = min(anni), max(anni)

    riepilogo = {}
    residuo_precedente = 0.0
    for anno in range(anno_min, anno_max + 1):
        usati_anno = sum(g for a, g in date_valide if a == anno)
        disponibili_anno = totale_annuo + residuo_precedente
        residuo_anno = disponibili_anno - usati_anno
        riepilogo[anno] = {"usati": usati_anno, "disponibili": disponibili_anno, "residuo": residuo_anno}
        residuo_precedente = residuo_anno

    return riepilogo

def formatta_data_lunga(d):
    return f"{d.day} {MESI_IT_LUNGO[d.month - 1]} {d.year}"

def formatta_giorni_ore(valore_giorni, ore_per_giorno=8.0):
    segno = "-" if valore_giorni < 0 else ""
    valore_assoluto = abs(valore_giorni)
    giorni_interi = int(valore_assoluto)
    resto = valore_assoluto - giorni_interi
    ore_residue = round(resto * ore_per_giorno)
    if ore_residue >= ore_per_giorno:
        giorni_interi += 1
        ore_residue = 0
    if ore_residue == 0:
        return f"{segno}{giorni_interi}g"
    return f"{segno}{giorni_interi}g {ore_residue}h"

@st.cache_data(ttl=30, show_spinner=False)
def get_dipendenti():
    if not ferie_sheet_id:
        from core.app_db import get_dipendenti_df
        return get_dipendenti_df()
    try:
        sheet = get_sheet(ferie_sheet_id, "DIPENDENTI")
        dipendenti = pd.DataFrame(sheet.get_all_records())
        dipendenti = dipendenti.sort_values(by='NOME', ascending=True)
        return dipendenti
    except Exception:
        from core.app_db import get_dipendenti_df
        return get_dipendenti_df()

@st.cache_data(ttl=30, show_spinner=False)
def get_ferie_storico():
    if not ferie_sheet_id:
        from core.app_db import get_ferie_storico_df
        return get_ferie_storico_df()
    try:
        sheet = get_sheet(ferie_sheet_id, "FERIE")
        data = sheet.get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception:
        from core.app_db import get_ferie_storico_df
        return get_ferie_storico_df()

def calcola_giorni_lavorativi_esatti(inizio, fine):
    it_holidays = holidays.Italy(years=[inizio.year, fine.year])
    giorni_lavorativi = 0
    giorno_corrente = inizio
    while giorno_corrente <= fine:
        if giorno_corrente.weekday() < 5 and giorno_corrente not in it_holidays:
            giorni_lavorativi += 1
        giorno_corrente += timedelta(days=1)
    return giorni_lavorativi

def check_overlaps(inizio_nuovo, fine_nuovo, escludi_nome=None):
    try:
        df = get_ferie_storico()
        if df.empty:
            return []

        overlaps = []
        for _, row in df.iterrows():
            nome = row.get('NOME')
            if escludi_nome and nome == escludi_nome:
                continue

            try:
                inizio_es = pd.to_datetime(row.get('DATA INIZIO'), dayfirst=True, errors='raise').date()
                fine_es = pd.to_datetime(row.get('DATA FINE'), dayfirst=True, errors='raise').date()

                if inizio_nuovo <= fine_es and inizio_es <= fine_nuovo:
                    overlaps.append(nome)
            except:
                continue

        return list(set(overlaps))
    except Exception as e:
        st.error(f"Errore controllo sovrapposizioni: {e}")
        return []
