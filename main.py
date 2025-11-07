# -*- coding: utf-8 -*-
"""
==============================================================================
=== PARTE 2: INTERFAZ DE USUARIO (STREAMLIT) ===
==============================================================================

Este archivo contiene toda la interfaz de usuario (UI) de Streamlit.
Importa la lógica de cálculo desde 'logica_calculo.py'.

Para ejecutar esta aplicación:
1.  Guarde este archivo como 'app_streamlit.py'.
2.  Guarde 'logica_calculo.py' en la misma carpeta.
3.  Asegúrese de tener las librerías: pip install streamlit pandas python-dateutil
4.  Ejecute en su terminal: streamlit run app_streamlit.py
"""

# --- 0. IMPORTACIONES NECESARIAS ---
import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- IMPORTAR TODO EL MOTOR DE CÁLCULO ---
# Importa todas las funciones y constantes (ej. UIT_2025, RMV_2025)
# desde el archivo 'logica_calculo.py'
from logica_calculo import *

# ==============================================================================
# --- SECCIÓN DE HELPERS DE UI ---
# ==============================================================================

# (NUEVO) Lista de meses para el Selectbox
MESES_LISTA = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
               'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

def crear_editor_historial_semestral(key_prefix: str) -> Dict[str, List[float]]:
    """
    (NUEVO) Helper reutilizable para crear la tabla st.data_editor
    para el historial semestral (Regularidad).
    """
    st.write("Ingrese los montos de los 6 meses del semestre (Ene-Jun o Jul-Dic):")

    # 1. Crear un DataFrame de ejemplo
    data_historial = {
        'Horas Extras (S/)': [0.0] * 6,
        'Bono Nocturno (S/)': [0.0] * 6,
        'Otros Afectos (S/)': [0.0] * 6,
        'Días Falta': [0] * 6
    }
    meses_semestre = [f"Mes {i+1}" for i in range(6)]
    df_historial = pd.DataFrame(data_historial, index=meses_semestre)

    # 2. Usar st.data_editor para que el usuario edite la tabla
    df_historial_editado = st.data_editor(
        df_historial, 
        num_rows_dynamic=False, # Evita que el usuario agregue/elimine filas
        key=f"{key_prefix}_data_editor" # Clave única para esta tabla
    )

    # 3. Preparar el diccionario para la función de lógica
    historial_completo = {
        'ing_sobretiempo_total': df_historial_editado['Horas Extras (S/)'].tolist(),
        'ing_bonificacion_nocturna': df_historial_editado['Bono Nocturno (S/)'].tolist(),
        'otros_ingresos_afectos': df_historial_editado['Otros Afectos (S/)'].tolist(),
        'dias_falta': df_historial_editado['Días Falta'].tolist()
    }
    return historial_completo

def mostrar_boleta_streamlit(boleta: Dict[str, Any], mes_num: int):
    """Muestra los resultados de la boleta en la UI de Streamlit."""
    
    st.header(f"Resultados de la Boleta ({MESES_LISTA[mes_num-1]})")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Neto a Pagar", f"S/ {boleta['neto_a_pagar']:,.2f}")
    col2.metric("Total Ingresos", f"S/ {boleta['total_ingresos_brutos_mes']:,.2f}")
    col3.metric("Total Descuentos", f"S/ {boleta['total_descuentos']:,.2f}")
    
    st.subheader("Ratios de Eficiencia (Trabajador)")
    col1, col2 = st.columns(2)
    col1.metric("Neto vs. Sueldo Nominal", f"{boleta['ratio_neto_vs_sueldo_nominal']:.2%}", help="Cuánto recibe el trabajador por cada S/ 1.00 de sueldo básico.")
    col2.metric("Neto vs. Bruto Total", f"{boleta['ratio_neto_vs_bruto']:.2%}", help="Qué porcentaje del ingreso bruto total se convierte en dinero 'en el bolsillo'.")

    with st.expander("Ver Desglose de Ingresos"):
        st.markdown(f"**Sueldo Básico Nominal:** `S/ {boleta['sueldo_basico_nominal']:,.2f}`")
        if boleta['dias_falta'] > 0:
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Descuento Faltas ({boleta['dias_falta']} días): `S/ {boleta['desc_faltas']:,.2f}`")
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Sueldo Básico (Ajustado):** `S/ {boleta['ing_basico_ajustado']:,.2f}`")
        st.markdown(f"**Asignación Familiar:** `S/ {boleta['ing_asig_familiar']:,.2f}`")
        st.markdown(f"**Bonificación Nocturna:** `S/ {boleta['ing_bonificacion_nocturna']:,.2f}`")
        st.markdown(f"**Sobretiempo (Total):** `S/ {boleta['ing_sobretiempo_total']:,.2f}`")
        st.markdown(f"**Otros Afectos (Bonos):** `S/ {boleta['otros_ingresos_afectos']:,.2f}`")
        st.markdown(f"**No Remunerativos (Movilidad):** `S/ {boleta['ingresos_no_remunerativos']:,.2f}`")
        st.markdown(f"**Prestación Alimentaria:** `S/ {boleta['ingreso_lpa']:,.2f}`")
        st.markdown(f"**Utilidades:** `S/ {boleta['ingreso_utilidades']:,.2f}`")
        st.markdown(f"**Subsidio (DM):** `S/ {boleta['ingreso_subsidio']:,.2f}`")
        if boleta['ing_gratificacion'] > 0:
            st.success(f"**Gratificación:** `S/ {boleta['ing_gratificacion']:,.2f}`")
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;(Base Grati: S/ {boleta['rem_computable_grati']:.2f})")
            if boleta['dias_falta_semestre_grati'] > 0:
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;(Desc. Faltas {boleta['dias_falta_semestre_grati']} días * 1/180vo)")
            st.success(f"**Bonificación Ley:** `S/ {boleta['ing_boni_ley']:,.2f}`")
            
    with st.expander("Ver Desglose de Descuentos"):
        st.markdown(f"**Pensión ({boleta['sistema_pension']}):** `S/ {boleta['desc_pension']:,.2f}`")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;(Base Afecta: S/ {boleta['base_pension_salud_mes']:.2f})")
        if boleta['sistema_pension'] != 'ONP':
            st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;Prima AFP aplicada hasta TMA S/ {TOPE_MAXIMO_ASEGURABLE_AFP_2025:,.2f}")
        st.markdown(f"**Renta 5ta Cat. (Mes):** `S/ {boleta['desc_renta_quinta']:,.2f}`")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;(Proy. Anual R5 Afecta): `S/ {boleta['proyeccion_anual_r5']:,.2f}`")
        if boleta['tiene_eps']:
            st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;(Proy. Base Salud: S/ {boleta['proyeccion_base_salud_anual']:.2f})")
        st.markdown(f"**Desc. Prest. Aliment.:** `S/ {boleta['desc_lpa']:,.2f}`")
        st.markdown(f"**Otros Descuentos (Fijos):** `S/ {boleta['otros_descuentos_fijos']:,.2f}`")

    with st.expander("Ver Diccionario de Resultados (JSON)"):
        st.json(boleta)

def mostrar_liquidacion_streamlit(lqbs: Dict[str, Any]):
    """Toma el diccionario de LQBS y lo imprime en la UI de Streamlit."""
    
    st.header(f"Resultados de la Liquidación (LQBS)")
    
    st.metric("Total Liquidación a Pagar", f"S/ {lqbs['total_liquidacion']:,.2f}")
    
    st.info(f"**Cálculo para:** {lqbs['motivo_cese']} | **Ingreso:** {lqbs['fecha_ingreso']} | **Cese:** {lqbs['fecha_cese']}")

    if lqbs.get('info_part_time'):
        st.warning(f"**Régimen:** PART-TIME (< 4h/día). {lqbs['info_part_time']}")
        
    if lqbs.get('ha_perdido_record_vacacional'):
        st.warning(f"**INFO:** Trabajador PERDIÓ derecho a Vacaciones (Récord no cumplido).")

    with st.expander("Ver Desglose de Beneficios Truncos", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**RC (Grati / Vacaciones):** `S/ {lqbs['rc_grati_vacas']:,.2f}`")
            st.markdown(f"**RC (CTS - incl. 1/6 Grati):** `S/ {lqbs['rc_cts']:,.2f}`")
            st.caption(f"(Promedio Variables Regulares: S/ {lqbs['promedio_variables_regulares']:,.2f})")
            
        with col2:
            st.markdown(f"**1. CTS Trunca:** `S/ {lqbs['cts_trunca']:,.2f}`")
            st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;(Periodo: {lqbs['cts_meses']} meses, {lqbs['cts_dias']} días)")
            st.markdown(f"**2. Gratificación Trunca:** `S/ {lqbs['grati_trunca']:,.2f}`")
            st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;(Periodo: {lqbs['grati_meses']} meses completos)")
            if lqbs.get('dias_falta_en_semestre_trunco', 0) > 0:
                st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;(Desc. Faltas {lqbs['dias_falta_en_semestre_trunco']} días * 1/180vo = S/ {lqbs['grati_desc_faltas']:.2f})")
            st.markdown(f"**3. Vacaciones Truncas:** `S/ {lqbs['vacas_truncas']:,.2f}`")
            st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;(Periodo: {lqbs['vacas_meses']} meses, {lqbs['vacas_dias']} días)")
            
        st.subheader(f"Total Beneficios Truncos: S/ {lqbs['total_beneficios_truncos']:,.2f}")

    with st.expander("Ver Cálculo de Indemnización"):
        if lqbs['indemnizacion_despido'] > 0:
            st.markdown(f"**Indemnización Despido:** `S/ {lqbs['indemnizacion_despido']:,.2f}`")
            st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;(Tiempo: {lqbs['indemnizacion_anios']}a, {lqbs['indemnizacion_meses']}m, {lqbs['indemnizacion_dias']}d)")
            st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;(Base Legal: Art. 38 D.S. 003-97-TR)")
        else:
            st.markdown(f"**Indemnización Despido:** `S/ 0.00`")
            st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;(No aplica para '{lqbs['motivo_cese']}')")

    with st.expander("Ver Diccionario de Resultados (JSON)"):
        # Convertir fechas a str para que st.json funcione
        lqbs_json = lqbs.copy()
        lqbs_json['fecha_ingreso'] = lqbs_json['fecha_ingreso'].isoformat()
        lqbs_json['fecha_cese'] = lqbs_json['fecha_cese'].isoformat()
        st.json(lqbs_json)

def mostrar_boleta_ria_streamlit(boleta: Dict[str, Any], mes_num: int):
    """Imprime la boleta simplificada del régimen RIA."""
    
    st.header(f"Resultados de la Boleta RIA ({MESES_LISTA[mes_num-1]})")

    if 'error' in boleta:
        st.error(boleta['error'])
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Neto a Pagar", f"S/ {boleta['neto_a_pagar']:,.2f}")
    col2.metric("Ingreso Integral Mensual", f"S/ {boleta['ingreso_integral_mensual']:,.2f}")
    col3.metric("Total Descuentos", f"S/ {boleta['total_descuentos']:,.2f}")

    with st.expander("Ver Desglose de Descuentos"):
        st.markdown(f"**Pensión ({boleta['sistema_pension']}):** `S/ {boleta['desc_pension']:,.2f}`")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;(Base Afecta: S/ {boleta['base_pension_salud_mes']:.2f})")
        st.markdown(f"**Renta 5ta Cat. (Mes):** `S/ {boleta['desc_renta_quinta']:,.2f}`")

    with st.expander("Ver Diccionario de Resultados (JSON)"):
        st.json(boleta)

def mostrar_indemnizacion_vacaciones_streamlit(indemnizacion: Dict[str, Any]):
    """Imprime el reporte de la indemnización vacacional."""
    
    st.header(f"Resultados de la Indemnización Vacacional")
    st.caption(f"Base Legal: Art. 23, D.L. N° 713")
    
    if indemnizacion.get('info_adicional'):
        st.warning(f"**INFO:** {indemnizacion['info_adicional']}")

    st.metric("Total a Pagar", f"S/ {indemnizacion['total_a_pagar']:,.2f}")

    col1, col2 = st.columns(2)
    col1.metric("Pago por Vacación No Gozada", f"S/ {indemnizacion['pago_por_vacacion_no_gozada']:,.2f}")
    col2.metric("Pago por Indemnización", f"S/ {indemnizacion['pago_por_indemnizacion']:,.2f}")
    
    st.markdown(f"**Remuneración Computable:** `S/ {indemnizacion['rc_vacacional']:,.2f}`")
    st.markdown(f"**Períodos Vencidos:** `{indemnizacion['periodos_vencidos']}`")

    with st.expander("Ver Diccionario de Resultados (JSON)"):
        st.json(indemnizacion)

# ==============================================================================
# === INICIO DE LA APLICACIÓN STREAMLIT ===
# ==============================================================================

# --- Configuración de la Página ---
st.set_page_config(
    layout="wide",
    page_title="Calculadora de Planilla Perú 2025",
    page_icon="🇵🇪"
)

st.title("Calculadora de Planilla y BB.SS. Perú 2025")
st.info("Herramienta de cálculo basada en la legislación peruana. (Versión Refactorizada)")

# --- Definición de Pestañas ---
tab_boleta, tab_lqbs, tab_ria, tab_indemnizacion = st.tabs([
    "Calculadora de Boleta Mensual (Régimen 728)", 
    "Calculadora de Liquidación (LQBS)", 
    "Calculadora Régimen Integral (RIA)",
    "Calculadora Indemnización Vacaciones"
])


# --- PESTAÑA 1: BOLETA MENSUAL (RÉGIMEN 728) ---
with tab_boleta:
    st.header("Calculadora de Boleta Mensual (Régimen 728)")
    
    # --- MEJORA: Mover el data_editor FUERA del formulario ---
    # Usamos st.session_state para guardar sus datos
    
    with st.expander("Historial Semestral (Para Regularidad de Gratificación)"):
        st.warning("Importante: Estos datos solo se usan en Julio (Mes 7) y Diciembre (Mes 12) para el Principio de Regularidad (3 de 6).")
        st.write("Ingrese los montos de los 6 meses del semestre (Ene-Jun o Jul-Dic):")

        # 1. Crear un DataFrame de ejemplo
        data_historial_boleta = {
            'Horas Extras (S/)': [0.0] * 6,
            'Bono Nocturno (S/)': [0.0] * 6,
            'Otros Afectos (S/)': [0.0] * 6,
            'Días Falta': [0] * 6
        }
        meses_semestre_boleta = [f"Mes {i+1}" for i in range(6)]
        df_historial_boleta = pd.DataFrame(data_historial_boleta, index=meses_semestre_boleta)

        # 2. Usar st.data_editor y guardar su estado en su propia clave
        st.data_editor(
            df_historial_boleta, 
            num_rows_dynamic=False,
            key="historial_boleta_editor" # Clave única para esta tabla
        )
    # --- FIN DE LA MEJORA ---
    
    with st.form("boleta_form"):
        # --- Columnas de Inputs ---
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("Datos del Empleado")
            in_sueldo_basico = st.number_input("Sueldo Básico Nominal", min_value=0.0, value=5300.0, step=100.0)
            in_tiene_hijos = st.checkbox("¿Tiene Hijos? (Asig. Familiar)", value=False)
            in_sistema_pension = st.selectbox("Sistema de Pensión", 
                                              SISTEMAS_PENSION, # Usando la constante importada
                                              index=1,
                                              key="boleta_pension") # <- CLAVE AÑADIDA
            in_tiene_eps = st.checkbox("¿Tiene EPS?", value=True, key="boleta_eps") # <- CLAVE AÑADIDA

        with col2:
            st.subheader("Datos del Mes")
            
            # --- MEJORA: Selectbox para el mes ---
            in_mes_nombre = st.selectbox("Mes de Cálculo", options=MESES_LISTA, index=0, key="boleta_mes_nombre") # <- CLAVE AÑADIDA
            in_mes_actual = MESES_LISTA.index(in_mes_nombre) + 1 # Convertir a 1-12
            
            in_dias_falta = st.number_input("Días de Falta Injustificada", min_value=0, max_value=30, value=0, step=1)
            in_horas_nocturnas = st.number_input("Total Horas Nocturnas en el Mes", min_value=0.0, value=0.0, step=1.0)
            in_he_25 = st.number_input("Total Horas Extras al 25%", min_value=0.0, value=0.0, step=0.5)
            in_he_35 = st.number_input("Total Horas Extras al 35%", min_value=0.0, value=0.0, step=0.5)
            in_he_100 = st.number_input("Total Horas Extras al 100% (Feriados)", min_value=0.0, value=0.0, step=0.5)

        with col3:
            st.subheader("Otros Ingresos / Descuentos")
            in_otros_ingresos_afectos = st.number_input("Otros Bonos Afectos", min_value=0.0, value=0.0, step=50.0)
            in_movilidad = st.number_input("Ingreso No Remunerativo (Movilidad)", min_value=0.0, value=500.0, step=50.0)
            in_lpa = st.number_input("Prestación Alimentaria (LPA)", min_value=0.0, value=0.0, step=50.0)
            in_utilidades = st.number_input("Ingreso por Utilidades (Pago único)", min_value=0.0, value=0.0, step=100.0)
            in_subsidio = st.number_input("Ingreso por Subsidio (DM)", min_value=0.0, value=0.0, step=100.0)
            in_otros_descuentos = st.number_input("Otros Descuentos Fijos (Sindicato, etc.)", min_value=0.0, value=0.0, step=10.0)

        # --- CORRECCIÓN CRÍTICA: Mover inputs de Costo Empleador DENTRO del form ---
        st.subheader("Parámetros Costo Empleador")
        c1_costo, c2_costo, c3_costo = st.columns(3)
        with c1_costo:
            in_tasa_sctr = st.number_input("Tasa SCTR (%)", min_value=0.0, value=1.2, step=0.1, help="Ingrese 1.2 para 1.2%")
        with c2_costo:
            in_tasa_senati = st.number_input("Tasa SENATI (%)", min_value=0.0, value=0.0, step=0.75, help="Ingrese 0.75 para 0.75%")
        with c3_costo:
            in_prima_vida = st.number_input("Prima Seguro Vida Ley (Monto S/)", min_value=0.0, value=15.0, step=1.0)
        # --- FIN DE LA CORRECCIÓN ---

        # --- Expanders para datos complejos ---
        with st.expander("Gastos Deducibles (3 UIT Anuales)"):
            st.caption("Ingrese el total gastado en el año. El sistema calculará el % deducible.")
            in_gastos_restaurantes = st.number_input("Gastos en Restaurantes y Hoteles (15%)", min_value=0.0, value=6000.0, step=100.0, key="boleta_rest") # <- CLAVE AÑADIDA
            in_gastos_alquiler = st.number_input("Gastos en Arrendamiento (30%)", min_value=0.0, value=0.0, step=100.0, key="boleta_alq") # <- CLAVE AÑADIDA
            in_gastos_medicos = st.number_input("Gastos en Honorarios Médicos/Odont. (30%)", min_value=0.0, value=0.0, step=100.0, key="boleta_med") # <- CLAVE AÑADIDA
            in_gastos_profesionales = st.number_input("Gastos en Servicios Profesionales (30%)", min_value=0.0, value=0.0, step=100.0, key="boleta_prof") # <- CLAVE AÑADIDA
            in_gastos_essalud_hogar = st.number_input("Gastos en EsSalud Trabajador del Hogar (100%)", min_value=0.0, value=0.0, step=100.0, key="boleta_hogar") # <- CLAVE AÑADIDA

        # --- MEJORA DE UX: Usar st.data_editor para el Historial Semestral ---
        # (El expander fue movido AFUERA del formulario)
        # --- FIN DE LA MEJORA ---

        with st.expander("Acumuladores Anuales (Para Renta 5ta)"):
            st.info("Para un cálculo preciso, ingrese los montos acumulados de Enero hasta el mes *anterior* al que está calculando.")
            in_acum_r5 = st.number_input("Acumulado Bruto Renta 5ta (Sin Grati)", min_value=0.0, value=0.0, step=1000.0, key="boleta_acum_r5") # <- CLAVE AÑADIDA
            in_acum_salud = st.number_input("Acumulado Base Afecta a Salud", min_value=0.0, value=0.0, step=1000.0, key="boleta_acum_salud") # <- CLAVE AÑADIDA
            in_acum_retenciones = st.number_input("Acumulado Retenciones Renta 5ta Pagadas", min_value=0.0, value=0.0, step=100.0, key="boleta_acum_ret") # <- CLAVE AÑADIDA

        # --- Botón de Envío ---
        submitted_boleta = st.form_submit_button("Calcular Boleta Mensual", type="primary")

    # --- Área de Resultados (Boleta) ---
    if submitted_boleta:
        with st.spinner("Calculando boleta..."):
            
            # --- MEJORA: Recolectar datos del editor desde st.session_state ---
            historial_editado_boleta = st.session_state.historial_boleta_editor
            historial_semestral_completo = {
                'ing_sobretiempo_total': historial_editado_boleta['Horas Extras (S/)'].tolist(),
                'ing_bonificacion_nocturna': historial_editado_boleta['Bono Nocturno (S/)'].tolist(),
                'otros_ingresos_afectos': historial_editado_boleta['Otros Afectos (S/)'].tolist(),
                'dias_falta': historial_editado_boleta['Días Falta'].tolist()
            }
            # --- FIN DE LA MEJORA ---
            
            boleta_calculada = generar_boleta_mensual(
                sueldo_basico_nominal=in_sueldo_basico,
                tiene_hijos=in_tiene_hijos,
                sistema_pension=in_sistema_pension,
                tiene_eps=in_tiene_eps,
                mes_actual_num=in_mes_actual,
                dias_falta=in_dias_falta,
                horas_nocturnas_mes=in_horas_nocturnas,
                horas_25=in_he_25,
                horas_35=in_he_35,
                horas_100=in_he_100,
                otros_ingresos_afectos=in_otros_ingresos_afectos,
                ingresos_no_remunerativos=in_movilidad,
                ingreso_lpa=in_lpa,
                otros_descuentos_fijos=in_otros_descuentos,
                ingreso_utilidades=in_utilidades,
                ingreso_subsidio=in_subsidio,
                ingresos_brutos_acumulados_renta5=in_acum_r5,
                ingresos_afectos_salud_acumulados=in_acum_salud,
                retenciones_acumuladas_renta5=in_acum_retenciones,
                historial_semestral_ingresos_variables=historial_semestral_completo,
                gastos_deducibles_arrendamiento=in_gastos_alquiler,
                gastos_deducibles_honorarios_medicos=in_gastos_medicos,
                gastos_deducibles_servicios_profesionales=in_gastos_profesionales,
                gastos_deducibles_essalud_hogar=in_gastos_essalud_hogar,
                gastos_deducibles_hoteles_rest=in_gastos_restaurantes
            )
            
            # Mostrar resultados formateados
            mostrar_boleta_streamlit(boleta_calculada, in_mes_actual)
            
            # Calcular y mostrar costo laboral
            st.header(f"Costo Laboral del Empleador ({MESES_LISTA[in_mes_actual-1]})")
            
            # --- CORRECCIÓN: Los inputs ya no están aquí, solo el cálculo ---
            costo_empleador = calcular_costo_laboral_mensual(
                boleta=boleta_calculada,
                tasa_sctr=in_tasa_sctr / 100.0,
                tasa_senati=in_tasa_senati / 100.0,
                prima_vida_ley=in_prima_vida
            )
            
            col1, col2 = st.columns(2)
            col1.metric("Costo Laboral Total del Mes", f"S/ {costo_empleador['costo_laboral_total_mes']:,.2f}")
            col2.metric("Total Aportes Empleador", f"S/ {costo_empleador['total_aportes_empleador']:,.2f}")
            
            with st.expander("Ver Desglose de Aportes del Empleador"):
                st.markdown(f"**Aporte EsSalud (9%):** `S/ {costo_empleador['aporte_essalud_9_porc']:,.2f}`")
                st.markdown(f"**Aporte SCTR:** `S/ {costo_empleador['aporte_sctr']:,.2f}`")
                st.markdown(f"**Aporte SENATI:** `S/ {costo_empleador['aporte_senati']:,.2f}`")
                st.markdown(f"**Aporte Seguro Vida Ley:** `S/ {costo_empleador['aporte_vida_ley']:,.2f}`")

            st.subheader("Ratios de Costo (Empleador)")
            col1, col2 = st.columns(2)
            col1.metric("Costo Total vs. Sueldo Nominal", f"{costo_empleador['ratio_costo_vs_sueldo_nominal']:.2%}", help="Costo total por cada S/ 1.00 de sueldo básico.")
            col2.metric("Costo Total vs. Bruto Total", f"{costo_empleador['ratio_costo_vs_bruto']:.2%}", help="Sobrecosto real del empleador sobre el bruto pagado.")


# --- PESTAÑA 2: LIQUIDACIÓN (LQBS) ---
with tab_lqbs:
    st.header("Calculadora de Liquidación (LQBS)")

    # --- MEJORA: Mover el data_editor FUERA del formulario ---
    with st.expander("Historial de Variables (Últimos 6 Meses para Regularidad)"):
        st.write("Ingrese los montos de los 6 meses *anteriores* al cese (para Principio de Regularidad 3 de 6).")
        
        # 1. Crear un DataFrame de ejemplo
        data_historial_lqbs = {
            'Horas Extras (S/)': [0.0] * 6,
            'Bono Nocturno (S/)': [0.0] * 6,
            'Otros Afectos (S/)': [0.0] * 6,
            'Días Falta': [0] * 6 # Aunque no se usa aquí, mantenemos la estructura
        }
        meses_semestre_lqbs = [f"Mes {i+1}" for i in range(6)]
        df_historial_lqbs = pd.DataFrame(data_historial_lqbs, index=meses_semestre_lqbs)

        # 2. Usar st.data_editor y guardar su estado
        st.data_editor(
            df_historial_lqbs, 
            num_rows_dynamic=False,
            key="historial_lqbs_editor" # Clave única
        )
    # --- FIN DE LA MEJORA ---
    
    with st.form("lqbs_form"):
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Datos del Cese")
            today = datetime.now().date()
            in_lqbs_fecha_ingreso = st.date_input("Fecha de Ingreso", value=today - relativedelta(years=2, months=9, days=30))
            in_lqbs_fecha_cese = st.date_input("Fecha de Cese", value=today)
            in_lqbs_motivo = st.selectbox("Motivo de Cese", 
                                          ['RENUNCIA', 'DESPIDO_ARBITRARIO', 'FALTA_GRAVE', 'TERMINO_CONTRATO'], 
                                          index=1)
        
        with col2:
            st.subheader("Bases Computables")
            st.caption("Ingrese las bases de cálculo según el Art. 19 del D.S. 001-97-TR.")
            in_lqbs_rc_basica = st.number_input("RC Básica (Sueldo + Asig. Familiar)", min_value=0.0, value=5300.0, step=100.0)
            in_lqbs_sexto_grati = st.number_input("Último 1/6 de Gratificación (para CTS)", min_value=0.0, value=(5300/6), step=10.0, format="%.2f")

        st.subheader("Regímenes Especiales y Faltas")
        col1, col2, col3 = st.columns(3)
        in_lqbs_part_time = col1.checkbox("¿Es Part-Time (< 4h/día)?", value=False, help="Si marca esto, CTS y Vacaciones serán 0.", key="lqbs_part_time") # <- CLAVE AÑADIDA
        in_lqbs_pierde_record = col2.checkbox("¿Perdió Récord Vacacional?", value=False, help="Si marca esto, Vacaciones Truncas será 0.", key="lqbs_pierde_record") # <- CLAVE AÑADIDA
        in_lqbs_faltas_sem_trunco = col3.number_input("Faltas en Semestre Trunco", min_value=0, value=5, step=1, help="Días de falta para descuento en Grati Trunca (1/180vo).")

        # --- MEJORA DE UX: Usar st.data_editor para el Historial Semestral ---
        # (El expander fue movido AFUERA del formulario)
        # --- FIN DE LA MEJORA ---

        # --- Botón de Envío ---
        submitted_lqbs = st.form_submit_button("Calcular Liquidación (LQBS)", type="primary")

    # --- Área de Resultados (LQBS) ---
    if submitted_lqbs:
        with st.spinner("Calculando liquidación..."):
            
            # --- MEJORA: Recolectar datos del editor desde st.session_state ---
            historial_editado_lqbs = st.session_state.historial_lqbs_editor
            historial_lqbs_completo = {
                'ing_sobretiempo_total': historial_editado_lqbs['Horas Extras (S/)'].tolist(),
                'ing_bonificacion_nocturna': historial_editado_lqbs['Bono Nocturno (S/)'].tolist(),
                'otros_ingresos_afectos': historial_editado_lqbs['Otros Afectos (S/)'].tolist(),
                # 'dias_falta' no se usa en la lógica de LQBS, pero lo podríamos incluir
            }
            # --- FIN DE LA MEJORA ---
            
            lqbs_calculada = generar_liquidacion(
                fecha_ingreso=in_lqbs_fecha_ingreso,
                fecha_cese=in_lqbs_fecha_cese,
                motivo_cese=in_lqbs_motivo,
                es_part_time_lt_4h=in_lqbs_part_time,
                ha_perdido_record_vacacional=in_lqbs_pierde_record,
                dias_falta_en_semestre_trunco=in_lqbs_faltas_sem_trunco,
                rc_basica=in_lqbs_rc_basica,
                historial_ultimos_6_meses_variables=historial_lqbs_completo,
                ultimo_sexto_grati=in_lqbs_sexto_grati
            )
            
            # Mostrar resultados formateados
            mostrar_liquidacion_streamlit(lqbs_calculada)


# --- PESTAÑA 3: RÉGIMEN INTEGRAL (RIA) ---
with tab_ria:
    st.header("Calculadora de Boleta Mensual (Régimen RIA)")
    st.info(f"Régimen opcional para trabajadores con remuneración promedio superior a 2 UIT (S/ {LIMITE_MINIMO_RIA_MENSUAL:,.2f} mensual).")
    
    with st.form("ria_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Datos del Empleado")
            in_ria_paquete_anual = st.number_input("Remuneración Integral Anual (Paquete)", min_value=0.0, value=192000.0, step=1000.0)
            in_ria_sistema_pension = st.selectbox("Sistema de Pensión", 
                                                  SISTEMAS_PENSION, 
                                                  key="ria_pension", index=3)
            in_ria_tiene_eps = st.checkbox("¿Tiene EPS?", value=False, key="ria_eps")
        
        with col2:
            st.subheader("Datos del Mes")
            # --- MEJORA: Selectbox para el mes ---
            in_ria_mes_nombre = st.selectbox("Mes de Cálculo", options=MESES_LISTA, index=0, key="ria_mes_nombre")
            in_ria_mes_actual = MESES_LISTA.index(in_ria_mes_nombre) + 1 # Convertir a 1-12
            
            in_ria_acum_retenciones = st.number_input("Acumulado Retenciones Renta 5ta Pagadas", min_value=0.0, value=0.0, step=100.0, key="ria_acum")

        with st.expander("Gastos Deducibles (3 UIT Anuales)"):
            st.caption("Ingrese el total gastado en el año. El sistema calculará el % deducible.")
            in_ria_gastos_restaurantes = st.number_input("Gastos en Restaurantes y Hoteles (15%)", min_value=0.0, value=20000.0, step=100.0, key="ria_rest")
            in_ria_gastos_alquiler = st.number_input("Gastos en Arrendamiento (30%)", min_value=0.0, value=0.0, step=100.0, key="ria_alq")
            in_ria_gastos_medicos = st.number_input("Gastos en Honorarios Médicos/Odont. (30%)", min_value=0.0, value=0.0, step=100.0, key="ria_med")
            in_ria_gastos_profesionales = st.number_input("Gastos en Servicios Profesionales (30%)", min_value=0.0, value=0.0, step=100.0, key="ria_prof")
            in_ria_gastos_essalud_hogar = st.number_input("Gastos en EsSalud Trabajador del Hogar (100%)", min_value=0.0, value=0.0, step=100.0, key="ria_hogar")

        # --- Botón de Envío ---
        submitted_ria = st.form_submit_button("Calcular Boleta RIA", type="primary")

    # --- Área de Resultados (RIA) ---
    if submitted_ria:
        with st.spinner("Calculando boleta RIA..."):
            boleta_ria_calculada = generar_boleta_ria(
                remuneracion_integral_anual=in_ria_paquete_anual,
                sistema_pension=in_ria_sistema_pension,
                tiene_eps=in_ria_tiene_eps,
                mes_actual_num=in_ria_mes_actual,
                retenciones_acumuladas_renta5=in_ria_acum_retenciones,
                gastos_deducibles_arrendamiento=in_ria_gastos_alquiler,
                gastos_deducibles_honorarios_medicos=in_ria_gastos_medicos,
                gastos_deducibles_servicios_profesionales=in_ria_gastos_profesionales,
                gastos_deducibles_essalud_hogar=in_ria_gastos_essalud_hogar,
                gastos_deducibles_hoteles_rest=in_ria_gastos_restaurantes
            )
            
            # Mostrar resultados formateados
            mostrar_boleta_ria_streamlit(boleta_ria_calculada, in_ria_mes_actual)


# --- PESTAÑA 4: INDEMNIZACIÓN POR VACACIONES NO GOZADAS ---
with tab_indemnizacion:
    st.header("Calculadora de Indemnización por Vacaciones No Gozadas")
    st.warning("Este pago aplica cuando un trabajador no disfruta de su descanso físico dentro del año siguiente a aquél en el que generó el derecho (Art. 23, D.L. N° 713).")
    
    with st.form("indemn_vacas_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Datos del Cálculo")
            in_indv_rc = st.number_input("Remuneración Computable Vacacional (RC)", min_value=0.0, value=4500.0, step=100.0)
            in_indv_periodos = st.number_input("N° de Períodos Vencidos (No Gozados)", min_value=1, value=1, step=1)
            
        with col2:
            st.subheader("Regímenes y Excepciones")
            in_indv_part_time = st.checkbox("¿Es Part-Time (< 4h/día)?", value=False, help="Si marca esto, el pago será 0.", key="indv_part_time") # <- CLAVE AÑADIDA
            in_indv_pierde_record = st.checkbox("¿Perdió Récord Vacacional por Faltas?", value=False, help="Si marca esto, el pago será 0.", key="indv_pierde_record") # <- CLAVE AÑADIDA

        # --- Botón de Envío ---
        submitted_indv = st.form_submit_button("Calcular Indemnización", type="primary")

    # --- Área de Resultados (Indemnización Vacaciones) ---
    if submitted_indv:
        with st.spinner("Calculando indemnización..."):
            indemnizacion_calculada = calcular_indemnizacion_vacaciones_no_gozadas(
                rc_vacacional=in_indv_rc,
                periodos_vencidos=in_indv_periodos,
                es_part_time_lt_4h=in_indv_part_time,
                ha_perdido_record_vacacional=in_indv_pierde_record
            )
            
            # Mostrar resultados formateados
            mostrar_indemnizacion_vacaciones_streamlit(indemnizacion_calculada)
