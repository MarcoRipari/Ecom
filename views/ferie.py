import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from functions.ferie_db import (
    get_dipendenti,
    get_ferie_storico,
    build_calendario_ferie_html,
    build_calendario_mensile_html,
    calcola_riepilogo_ferie_annuale,
    tema_colori,
    formatta_giorni_ore,
    formatta_data_lunga,
    sync_ferie_changes,
    add_ferie,
    check_overlaps,
    get_orario_dipendente,
    ore_giornaliere_previste,
    time_slider,
    update_dipendente_budget,
    update_orario_dipendente,
    MESI_IT_LUNGO
)

def calendario_ferie_mensile():
    st.subheader("🗓️ Calendario Ferie")

    oggi = datetime.now().date()
    if "cal_ferie_anno" not in st.session_state:
        st.session_state.cal_ferie_anno = oggi.year
        st.session_state.cal_ferie_mese = oggi.month

    col_prev, col_titolo, col_oggi, col_next = st.columns([1, 4, 1, 1])
    with col_prev:
        if st.button("◀", use_container_width=True, key="cal_ferie_prev"):
            m = st.session_state.cal_ferie_mese - 1
            a = st.session_state.cal_ferie_anno
            if m < 1:
                m = 12
                a -= 1
            st.session_state.cal_ferie_mese = m
            st.session_state.cal_ferie_anno = a
            st.rerun()
    with col_titolo:
        titolo = f"{MESI_IT_LUNGO[st.session_state.cal_ferie_mese - 1]} {st.session_state.cal_ferie_anno}"
        st.markdown(f"<h3 style='text-align:center; margin:4px 0;'>{titolo}</h3>", unsafe_allow_html=True)
    with col_oggi:
        if st.button("Oggi", use_container_width=True, key="cal_ferie_oggi"):
            st.session_state.cal_ferie_anno = oggi.year
            st.session_state.cal_ferie_mese = oggi.month
            st.rerun()
    with col_next:
        if st.button("▶", use_container_width=True, key="cal_ferie_next"):
            m = st.session_state.cal_ferie_mese + 1
            a = st.session_state.cal_ferie_anno
            if m > 12:
                m = 1
                a += 1
            st.session_state.cal_ferie_mese = m
            st.session_state.cal_ferie_anno = a
            st.rerun()

    df_storico = get_ferie_storico()
    df_dipendenti = get_dipendenti()
    html = build_calendario_mensile_html(df_storico, st.session_state.cal_ferie_anno, st.session_state.cal_ferie_mese, df_dipendenti)
    st.markdown(html, unsafe_allow_html=True)

def ferie():
    df_dipendenti = get_dipendenti()
    df_storico = get_ferie_storico()

    st.subheader("📅 Chi è in ferie")
    st.markdown(build_calendario_ferie_html(df_storico, df_dipendenti), unsafe_allow_html=True)

    st.divider()

    st.subheader("📊 Riepilogo Disponibilità")
    st.caption(f"Anno {datetime.now().year} — include il riporto del residuo dell'anno precedente")
    cols = st.columns(3)

    anno_corrente = datetime.now().year
    for i, dip in enumerate(df_dipendenti.itertuples(index=False)):
        riepilogo = calcola_riepilogo_ferie_annuale(df_storico, dip.NOME, dip.TOTALE)
        dati_anno = riepilogo[anno_corrente]
        usati = dati_anno["usati"]
        disponibili = dati_anno["disponibili"]
        residuo = dati_anno["residuo"]

        percentuale = min(usati / disponibili, 1.0) if disponibili > 0 else 1.0
        percentuale = max(percentuale, 0.0)
        t = tema_colori()
        colore_residuo = "#d32f2f" if residuo < 5 else t["text_primary"]
        colore_barra = "#d32f2f" if residuo < 0 else "#1E88E5"

        with cols[i % 3]:
            st.markdown(f"""
                <div style="border: 1px solid {t['card_border']}; padding: 20px; border-radius: 10px; background-color: {t['card_bg']}; height: 150px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);">
                    <h3 style="margin-top:0; color:#1E88E5; font-size: 18px;">{dip.NOME}</h3>
                    <p style="margin-bottom:5px; font-size:14px; color: {t['text_secondary']};">Godute: <b>{formatta_giorni_ore(usati)}</b> / {formatta_giorni_ore(disponibili)} disponibili</p>
                    <p style="color:{colore_residuo}; margin-bottom:8px; font-size:16px;">Residuo: <b>{formatta_giorni_ore(residuo)}</b></p>
                    <div style="background:{t['bar_track']}; border-radius:6px; height:10px; width:100%; overflow:hidden;">
                        <div style="background:{colore_barra}; height:100%; width:{percentuale*100}%; border-radius:6px;"></div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

    st.divider()
    opzioni = ["-- Seleziona un dipendente --"] + df_dipendenti['NOME'].tolist()
    dipendente_scelto = st.selectbox("Visualizza il dettaglio storico per:", options=opzioni)

    if dipendente_scelto != "-- Seleziona un dipendente --" and not df_storico.empty:
        dettaglio_utente = df_storico[df_storico['NOME'] == dipendente_scelto].copy()
        st.subheader(f"Dettaglio assenze: {dipendente_scelto}")

        dettaglio_utente['DATA INIZIO'] = pd.to_datetime(dettaglio_utente['DATA INIZIO'], dayfirst=True, errors='coerce')
        dettaglio_utente['DATA FINE'] = pd.to_datetime(dettaglio_utente['DATA FINE'], dayfirst=True, errors='coerce')

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            anni = ["Tutti"] + sorted(dettaglio_utente['DATA INIZIO'].dt.year.dropna().unique().astype(int).tolist(), reverse=True)
            anno_scelto = st.selectbox("Filtra per anno:", anni)
        with col_f2:
            tipi_validi = dettaglio_utente['TIPO'].dropna()
            tipi = ["Tutti"] + sorted(tipi_validi.unique().tolist())
            tipo_scelto = st.selectbox("Filtra per tipo:", tipi)

        dettaglio_completo = dettaglio_utente.sort_values(by='DATA INIZIO', ascending=False)

        if anno_scelto != "Tutti":
            dettaglio_utente = dettaglio_utente[dettaglio_utente['DATA INIZIO'].dt.year == anno_scelto]
        if tipo_scelto != "Tutti":
            dettaglio_utente = dettaglio_utente[dettaglio_utente['TIPO'] == tipo_scelto]

        dettaglio_utente = dettaglio_utente.sort_values(by='DATA INIZIO', ascending=False)

        colonne_editor = ['NOME', 'DATA INIZIO', 'DATA FINE', 'TIPO', 'GIORNI LAVORATIVI']
        ha_colonna_dettaglio = 'DETTAGLIO' in dettaglio_utente.columns
        if ha_colonna_dettaglio:
            colonne_editor.append('DETTAGLIO')
        df_editor = dettaglio_utente[colonne_editor].copy()
        df_editor['DATA INIZIO'] = df_editor['DATA INIZIO'].dt.date
        df_editor['DATA FINE'] = df_editor['DATA FINE'].dt.date

        column_config_editor = {
            "NOME": st.column_config.TextColumn("DIPENDENTE", disabled=True),
            "DATA INIZIO": st.column_config.DateColumn("INIZIO", format="DD/MM/YYYY", required=True),
            "DATA FINE": st.column_config.DateColumn("FINE", format="DD/MM/YYYY", required=True),
            "TIPO": st.column_config.SelectboxColumn("TIPO", options=["Ferie", "Permesso Orario", "Rettifica", "Altro"], required=True),
            "GIORNI LAVORATIVI": st.column_config.NumberColumn("GG", disabled=True),
        }
        if ha_colonna_dettaglio:
            column_config_editor["DETTAGLIO"] = st.column_config.TextColumn("Dettaglio permesso", disabled=True)

        edited_df = st.data_editor(
            df_editor,
            column_config=column_config_editor,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            key=f"editor_{dipendente_scelto}"
        )

        col_s1, col_s2 = st.columns([1, 1])
        with col_s1:
            if st.button("Salva modifiche storiche", use_container_width=True):
                with st.spinner("Salvataggio DB..."):
                    if anno_scelto != "Tutti" or tipo_scelto != "Tutti":
                        mask = (dettaglio_completo['DATA INIZIO'].dt.year == anno_scelto) if anno_scelto != "Tutti" else True
                        if tipo_scelto != "Tutti":
                            mask &= (dettaglio_completo['TIPO'] == tipo_scelto)
                        df_non_visibili = dettaglio_completo[~mask].copy()
                        df_final_sync = pd.concat([df_non_visibili, edited_df], ignore_index=True)
                    else:
                        df_final_sync = edited_df

                    if sync_ferie_changes(dipendente_scelto, df_final_sync):
                        st.success("Modifiche salvate nel DB!")
                        st.rerun()
        with col_s2:
            csv_data = edited_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Esporta report (CSV)",
                data=csv_data,
                file_name=f"report_ferie_{dipendente_scelto}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv',
                use_container_width=True
            )

def aggiungi_ferie():
    st.header("Aggiungi ferie")

    dipendenti = get_dipendenti()
    nomi_dipendenti = dipendenti['NOME'].tolist()

    nome = st.selectbox("Nome Dipendente", options=nomi_dipendenti)
    col1, col2 = st.columns(2)
    with col1:
        data_inizio = st.date_input("Data inizio", format="DD/MM/YYYY")
    with col2:
        data_fine = st.date_input("Data fine", format="DD/MM/YYYY")

    if data_inizio <= data_fine:
        sovrapposizioni = check_overlaps(data_inizio, data_fine, escludi_nome=nome)
        if sovrapposizioni:
            st.warning(f"⚠️ **Attenzione:** Nelle date selezionate sono già in ferie: {', '.join(sovrapposizioni)}")

    tipo = st.selectbox("Tipo di assenza", ["Ferie", "Rettifica", "Altro"])

    if st.button("Inserisci ferie"):
        if not nome:
            st.error("Il campo 'Nome' è obbligatorio.")
        elif data_fine < data_inizio:
            st.error("Errore: la data di fine non può essere precedente alla data di inizio.")
        else:
            nuova_riga = [nome, data_inizio.strftime('%d-%m-%Y'), data_fine.strftime('%d-%m-%Y'), tipo]
            upload = add_ferie(nuova_riga)
            if upload is True:
                st.success("Ferie inserite con successo!")
                st.rerun()
            else:
                st.error(f"{upload}")

@st.dialog("Modifica Dipendente")
def modifica_ferie_totali_modal(nome, ferie_attuale, orario_attuale):
    st.write(f"Stai modificando i dati per: **{nome}**")
    nuovo_budget = st.number_input("Giorni totali annui", value=int(ferie_attuale), min_value=0)

    col1, col2 = st.columns(2)
    with col1:
        mattina_inizio = time_slider("Mattina - inizio", orario_attuale["mattina_inizio"], key="mod_mattina_inizio")
        pomeriggio_inizio = time_slider("Pomeriggio - inizio", orario_attuale["pomeriggio_inizio"], key="mod_pomeriggio_inizio")
    with col2:
        mattina_fine = time_slider("Mattina - fine", orario_attuale["mattina_fine"], key="mod_mattina_fine")
        pomeriggio_fine = time_slider("Pomeriggio - fine", orario_attuale["pomeriggio_fine"], key="mod_pomeriggio_fine")

    if st.button("Salva Modifiche"):
        ok_budget = update_dipendente_budget(nome, nuovo_budget)
        ok_orario = update_orario_dipendente(nome, {
            "mattina_inizio": mattina_inizio.strftime("%H:%M"),
            "mattina_fine": mattina_fine.strftime("%H:%M"),
            "pomeriggio_inizio": pomeriggio_inizio.strftime("%H:%M"),
            "pomeriggio_fine": pomeriggio_fine.strftime("%H:%M"),
        })
        if ok_budget or ok_orario:
            st.success(f"Dati aggiornati per {nome}!")
            st.rerun()

def gestione_dipendenti():
    st.header("Gestione dipendenti")
    dipendenti = get_dipendenti()

    cols = st.columns(3)
    for i, dipendente in enumerate(dipendenti.itertuples(index=False)):
        with cols[i % 3]:
            orario_dip = get_orario_dipendente(dipendenti[dipendenti['NOME'] == dipendente.NOME].iloc[0])
            orario_label = (
                f"{orario_dip['mattina_inizio'].strftime('%H:%M')}–{orario_dip['mattina_fine'].strftime('%H:%M')} / "
                f"{orario_dip['pomeriggio_inizio'].strftime('%H:%M')}–{orario_dip['pomeriggio_fine'].strftime('%H:%M')}"
            )
            t = tema_colori()
            st.markdown(f"""
                <div style="border: 1px solid {t['card_border']}; padding: 20px; border-radius: 10px; background-color: {t['card_bg']}; margin-bottom: 5px; height: 140px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);">
                    <h3 style="margin-top:0; color:#1E88E5; font-size: 18px;">{dipendente.NOME}</h3>
                    <p style="margin-bottom:3px; font-size:14px; color: {t['text_secondary']};">Totale annuo: <b>{dipendente.TOTALE} gg</b></p>
                    <p style="margin-bottom:0; font-size:12px; color: {t['text_secondary']};">{orario_label}</p>
                </div>
            """, unsafe_allow_html=True)

            if st.button(f"Modifica {dipendente.NOME}", key=f"edit_{dipendente.NOME}", use_container_width=True):
                modifica_ferie_totali_modal(dipendente.NOME, dipendente.TOTALE, orario_dip)

def dashboard_dipendente():
    user = st.session_state.get("user", {}) or {}
    nome_utente = f"{(user.get('nome') or '').strip()} {(user.get('cognome') or '').strip()}".strip()

    st.header("Le mie ferie")
    if not nome_utente:
        st.error("Non riesco a determinare il tuo nome dal profilo utente.")
        return

    df_dipendenti = get_dipendenti()
    df_storico = get_ferie_storico()

    riga_dip = df_dipendenti[df_dipendenti['NOME'] == nome_utente]
    if riga_dip.empty:
        st.warning(
            f"Non trovo un'anagrafica ferie per **{nome_utente}**. "
            "Il nome e cognome del tuo account devono corrispondere a un dipendente."
        )
        return

    info_dip = riga_dip.iloc[0]
    anno_corrente = datetime.now().year
    riepilogo = calcola_riepilogo_ferie_annuale(df_storico, nome_utente, info_dip.TOTALE)
    dati_anno = riepilogo[anno_corrente]
    t_dip = tema_colori()

    colore_residuo = "#d32f2f" if dati_anno["residuo"] < 5 else t_dip["text_primary"]
    colore_barra = "#d32f2f" if dati_anno["residuo"] < 0 else "#1E88E5"
    percentuale = min(dati_anno["usati"] / dati_anno["disponibili"], 1.0) if dati_anno["disponibili"] > 0 else 1.0
    percentuale = max(percentuale, 0.0)

    st.subheader("📊 Le mie ferie residue")
    st.caption(f"Anno {anno_corrente}")
    st.markdown(f"""
        <div style="border: 1px solid {t_dip['card_border']}; padding: 20px; border-radius: 10px; background-color: {t_dip['card_bg']}; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);">
            <p style="margin-bottom:5px; font-size:14px; color: {t_dip['text_secondary']};">Godute: <b>{formatta_giorni_ore(dati_anno['usati'])}</b></p>
            <p style="color:{colore_residuo}; margin-bottom:8px; font-size:18px;">Residuo: <b>{formatta_giorni_ore(dati_anno['residuo'])}</b></p>
            <div style="background:{t_dip['bar_track']}; border-radius:6px; height:10px; width:100%; overflow:hidden;">
                <div style="background:{colore_barra}; height:100%; width:{percentuale*100}%; border-radius:6px;"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.divider()
    calendario_ferie_mensile()
