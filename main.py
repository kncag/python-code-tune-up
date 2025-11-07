# -*- coding: utf-8 -*-
"""
CALCULADORA DE PLANILLA Y BB.SS. PERÚ 2025 (App Streamlit)

Este archivo contiene dos partes:
1.  El motor de cálculo completo (todo lo de 'planilla_tool.py').
2.  La interfaz de usuario (UI) de Streamlit que usa ese motor.

Para ejecutar esta aplicación:
1.  Guarde este archivo como 'app_streamlit.py'.
2.  Asegúrese de tener las librerías: pip install streamlit python-dateutil pandas
3.  Ejecute en su terminal: streamlit run app_streamlit.py
"""

# --- 0. IMPORTACIONES NECESARIAS ---
import streamlit as st
import pandas as pd # (NUEVO) Necesario para el data_editor
import math
from typing import Dict, Any, Tuple, List
from datetime import datetime
from dateutil.relativedelta import relativedelta

# ==============================================================================
# === PARTE 1: MOTOR DE CÁLCULO (PLANILLA_TOOL.PY) ===
# (Todo el código que desarrollamos, pegado aquí para ser un archivo único)
# ==============================================================================

# --- 1. CONSTANTES GLOBALES (Valores oficiales 2025) ---

# D.S. N° 260-2024-EF
UIT_2025 = 5350
# D.S. N° 006-2024-TR
RMV_2025 = 1130
# Ley N° 25129
PORC_ASIG_FAMILIAR = 0.10
# Ley N° 26790
PORC_ESSALUD = 0.09
# D.L. N° 19990
PORC_ONP = 0.13

# Art. 53, D.S. N° 179-2004-EF (TUO Ley Impuesto a la Renta)
TRAMOS_IR = [
    (5 * UIT_2025, 0.08),  # Hasta 26,750
    (20 * UIT_2025, 0.14), # Hasta 107,000
    (35 * UIT_2025, 0.17), # Hasta 187,250
    (45 * UIT_2025, 0.20), # Hasta 240,750
    (float('inf'), 0.30)   # Más de 240,750
]

# Ley N° 30334 (Desafecta gratificaciones de aportes)
BONI_LEY_ESSALUD = 0.09
BONI_LEY_EPS = 0.0675
# Art. 33, Ley N° 26790 y Art. 43, D.S. N° 009-97-SA
CREDITO_POR_EPS = 0.09 * 0.25 # 2.25%

# Art. 9, D.S. N° 007-2002-TR (TUO Jornada de Trabajo)
TASA_SOBRETIEMPO_25 = 0.25
TASA_SOBRETIEMPO_35 = 0.35
TASA_SOBRETIEMPO_100 = 1.0 # Para Feriados (D.L. 713) y DSO

# Art. 8, D.S. N° 007-2002-TR (TUO Jornada de Trabajo)
TASA_BONIFICACION_NOCTURNA = 0.35 # 35% sobre el valor-hora

# (REFINADO) Tasas AFP separadas para el cálculo del Tope Máximo Asegurable
# Base Legal: SBS, vigentes a Noviembre 2025
TASA_APORTE_AFP = 0.10 # Aporte obligatorio al fondo
TASA_PRIMA_SEGURO_AFP = 0.0174 # Tasa promedio (varía por AFP/licitación)

# (REFINADO) Tope Máximo Asegurable (TMA) - Se actualiza trimestralmente por SBS
# (Valor referencial para Q4 2025)
TOPE_MAXIMO_ASEGURABLE_AFP_2025 = 12234.34 

# Limite 3 UIT (Art. 46, LIR)
LIMITE_3_UIT = 3 * UIT_2025 # 3 * 5350 = 16,050

# Base Legal: Art. 8, D.S. N° 003-97-TR
LIMITE_MINIMO_RIA_UIT = 2.0
LIMITE_MINIMO_RIA_MENSUAL = LIMITE_MINIMO_RIA_UIT * UIT_2025 # 10,700

# --- 2. FUNCIONES DE CÁLCULO DE INGRESOS ---

def calcular_valor_hora(sueldo_basico: float) -> float:
    """
    Calcula el valor de una hora ordinaria.
    Base Legal: Se asume jornada de 8h/día, 30 días/mes
    (Jornada de 240h, Art. 5, D.S. N° 007-2002-TR)
    """
    if sueldo_basico <= 0:
        return 0
    return (sueldo_basico / 30) / 8

def calcular_sobretiempo(valor_hora: float, horas_25: float, horas_35: float, horas_100: float = 0.0) -> Tuple[float, float, float, float]:
    """
    Calcula el monto total de horas extras (sobretiempo).
    Base Legal: Art. 9, D.S. N° 007-2002-TR.
    Devuelve: (Total, Monto 25, Monto 35, Monto 100)
    """
    monto_25 = horas_25 * valor_hora * (1 + TASA_SOBRETIEMPO_25)
    monto_35 = horas_35 * valor_hora * (1 + TASA_SOBRETIEMPO_35)
    monto_100 = horas_100 * valor_hora * (1 + TASA_SOBRETIEMPO_100) 
    
    return (monto_25 + monto_35 + monto_100), monto_25, monto_35, monto_100

def calcular_asignacion_familiar(tiene_hijos: bool) -> float:
    """
    Calcula la asignación familiar.
    Base Legal: Ley N° 25129. Es el 10% de la RMV.
    No se ve afectada por faltas (como en "Asignación Familiar.csv").
    """
    return RMV_2025 * PORC_ASIG_FAMILIAR if tiene_hijos else 0

def calcular_bonificacion_nocturna(valor_hora: float, horas_nocturnas_mes: float) -> float:
    """
    Calcula la bonificación nocturna (BN) basada en las horas
    laboradas en jornada nocturna (10pm a 6am).
    Base Legal: Art. 8, D.S. N° 007-2002-TR. (35% sobretasa).
    """
    if horas_nocturnas_mes <= 0 or valor_hora <= 0:
        return 0
    
    sobretasa_nocturna_por_hora = valor_hora * TASA_BONIFICACION_NOCTURNA
    return sobretasa_nocturna_por_hora * horas_nocturnas_mes

# --- 3. FUNCIONES DE CÁLCULO DE DESCUENTOS ---

def calcular_descuento_pension(sueldo_bruto_afecto: float, sistema_pension: str) -> float:
    """
    Calcula el descuento de AFP u ONP sobre la base afecta.
    (REFINADO) Incluye el Tope Máximo Asegurable (TMA) para la Prima de AFP.
    Base Legal: D.L. 19990 (ONP), D.L. 25897 (AFP), Resoluciones SBS (TMA).
    """
    sistema_pension = sistema_pension.upper()
    
    if sistema_pension == 'ONP':
        return sueldo_bruto_afecto * PORC_ONP
    elif sistema_pension in ('INTEGRA', 'PRIMA', 'HABITAT', 'PROFUTURO'):
        # --- Lógica de AFP Refinada con TMA (Tope Máximo Asegurable) ---
        
        # 1. Aporte Obligatorio (10%): Se aplica sobre el total (sin tope).
        aporte_obligatorio = sueldo_bruto_afecto * TASA_APORTE_AFP
        
        # 2. Prima de Seguro (~1.74%): Se aplica solo hasta el TMA.
        base_prima_seguro = min(sueldo_bruto_afecto, TOPE_MAXIMO_ASEGURABLE_AFP_2025)
        prima_seguro = base_prima_seguro * TASA_PRIMA_SEGURO_AFP
        
        # 3. Comisión sobre Flujo (0% para Comisión Mixta)
        # No se añade, ya que la mayoría está en comisión mixta.
        
        return aporte_obligatorio + prima_seguro
    else:
        return 0

def _calcular_impuesto_anual_por_tramos(
    renta_neta_imponible_anual: float, 
    proyeccion_base_salud_anual: float, 
    tiene_eps: bool = False
) -> float:
    """
    Función interna: Calcula el impuesto anual basado en los tramos
    y aplica el crédito EPS si corresponde.
    Base Legal: Art. 53, TUO LIR (Tramos) y Ley 26790 (Crédito EPS).
    """
    
    # 1. Calcular impuesto por tramos 2025 (Art. 53, LIR)
    impuesto_anual = 0
    renta_acumulada_para_tramos = 0
    
    for limite, tasa in TRAMOS_IR:
        monto_en_tramo = min(renta_neta_imponible_anual - renta_acumulada_para_tramos, limite - renta_acumulada_para_tramos)
        if monto_en_tramo <= 0:
            break
        impuesto_anual += monto_en_tramo * tasa
        renta_acumulada_para_tramos += monto_en_tramo
        
    # 2. Crédito por EPS (Ley N° 26790)
    if tiene_eps:
        # El crédito es el 25% del aporte a EsSalud (9%) que se paga a la EPS.
        credito_eps = proyeccion_base_salud_anual * CREDITO_POR_EPS # 2.25%
        impuesto_anual = max(0, impuesto_anual - credito_eps)
        
    return impuesto_anual

def calcular_retencion_renta_quinta(
    ingresos_proyectados_anuales: float, # Renta Bruta (Base para 7 UIT)
    proyeccion_base_salud_anual: float, # Renta Afecta a Salud (Base para Crédito EPS)
    tiene_eps: bool = False, 
    mes_actual_num: int = 1, 
    retenciones_acumuladas: float = 0.0,
    # Gastos Deducibles 3 UIT (Art. 46, LIR)
    gastos_deducibles_arrendamiento: float = 0.0,
    gastos_deducibles_honorarios_medicos: float = 0.0,
    gastos_deducibles_servicios_profesionales: float = 0.0,
    gastos_deducibles_essalud_hogar: float = 0.0,
    gastos_deducibles_hoteles_rest: float = 0.0
) -> float:
    """
    Calcula la retención de 5ta categoría para el mes actual.
    (REFINADO) Sigue la lógica de recálculo por periodos fijos de SUNAT.
    Base Legal: Art. 40, D.S. N° 003-2007-EF (Reglamento LIR).
    """
    
    # 1. Base Imponible: Renta Bruta Anual
    renta_bruta = ingresos_proyectados_anuales
    
    # 2. Deducción de 7 UIT (Art. 46, TUO LIR)
    deduccion_7_uit = 7 * UIT_2025
    
    # 3. Deducción de 3 UIT adicionales (Art. 46, TUO LIR)
    
    # Arrendamiento: 30% del gasto
    deduccion_arrendamiento = gastos_deducibles_arrendamiento * 0.30
    # Honorarios Médicos y Odontólogos: 30% del gasto
    deduccion_honorarios_medicos = gastos_deducibles_honorarios_medicos * 0.30
    # Otros Servicios Profesionales (4ta Cat): 30% del gasto
    deduccion_servicios_profesionales = gastos_deducibles_servicios_profesionales * 0.30
    # EsSalud Trabajador del Hogar: 100% del gasto
    deduccion_essalud_hogar = gastos_deducibles_essalud_hogar * 1.00
    # Hoteles y Restaurantes: 15% del gasto
    deduccion_hoteles_rest = gastos_deducibles_hoteles_rest * 0.15
    
    total_deduccion_adicional_calculada = (
        deduccion_arrendamiento +
        deduccion_honorarios_medicos +
        deduccion_servicios_profesionales +
        deduccion_essalud_hogar +
        deduccion_hoteles_rest
    )
    
    # Aplicamos el límite de 3 UIT (S/ 16,050)
    total_deduccion_adicional_aplicable = min(total_deduccion_adicional_calculada, LIMITE_3_UIT)

    # Renta Neta Imponible = Renta Bruta - 7 UIT - 3 UIT
    renta_neta_imponible_anual = max(0, renta_bruta - deduccion_7_uit - total_deduccion_adicional_aplicable)
    
    # 4. Calcular impuesto anual total proyectado
    impuesto_anual_proyectado = _calcular_impuesto_anual_por_tramos(
        renta_neta_imponible_anual, 
        proyeccion_base_salud_anual, 
        tiene_eps
    )
    
    # 5. Lógica de Recálculo (REFINADO: Periodos Fijos SUNAT)
    # Base Legal: Art. 40, D.S. N° 003-2007-EF (Reglamento LIR)
    
    impuesto_restante_por_pagar = impuesto_anual_proyectado - retenciones_acumuladas
    
    # Determinar el divisor legal según el mes
    if mes_actual_num <= 3: # Enero a Marzo
        # La retención es (Proyección Anual / 12)
        retencion_mensual = impuesto_anual_proyectado / 12
    elif mes_actual_num == 4: # Abril
        # Ajuste de Ene-Mar. (Proy Anual - Acumulado Ene-Mar) / 9
        retencion_mensual = impuesto_restante_por_pagar / 9
    elif 5 <= mes_actual_num <= 7: # Mayo a Julio
        # (Proy Anual - Acumulado Ene-Abr) / 8
        retencion_mensual = impuesto_restante_por_pagar / 8
    elif 8 <= mes_actual_num <= 11: # Agosto a Noviembre
        # (Proy Anual - Acumulado Ene-Jul) / 5
        retencion_mensual = impuesto_restante_por_pagar / 5
    else: # Diciembre
        # (Proy Anual - Acumulado Ene-Nov) / 1
        retencion_mensual = impuesto_restante_por_pagar / 1
    
    if retencion_mensual < 0:
        return 0 # Indica un saldo a favor / devolución

    return retencion_mensual


# --- 4. FUNCIONES DE BENEFICIOS SOCIALES ---

def _calcular_promedio_regularidad(historial_semestral: Dict[str, list]) -> float:
    """
    Aplica el Principio de Regularidad (Art. 19, D.S. 001-97-TR).
    Suma el promedio (Total / 6) de ingresos variables si se
    recibieron al menos 3 meses en el semestre.
    """
    promedio_total = 0.0
    
    if not historial_semestral:
        return 0.0

    # Lista de claves de ingresos variables que deben estar en el historial
    claves_variables = ['ing_sobretiempo_total', 'ing_bonificacion_nocturna', 'otros_ingresos_afectos']

    for clave in claves_variables:
        valores = historial_semestral.get(clave, [])
        if not valores:
            continue
        
        # Contar meses que se recibió
        meses_con_percepcion = sum(1 for v in valores if v > 0)
        
        # Si cumple la regularidad (3 de 6)
        if meses_con_percepcion >= 3:
            # El promedio es el total del semestre / 6
            promedio_del_concepto = sum(valores) / 6
            promedio_total += promedio_del_concepto
    
    return promedio_total

def calcular_gratificacion(
    sueldo_computable: float, 
    meses_completos: int, 
    tiene_eps: bool = False,
    dias_falta_semestre: int = 0 # (NUEVO)
) -> Tuple[float, float]:
    """
    Calcula una gratificación semestral (Julio o Diciembre).
    Base Legal: Ley 27735 (Grati), Ley 30334 (Boni), D.S. 005-2002-TR (Desc. Faltas 1/180vo).
    """
    if meses_completos <= 0:
        return 0, 0
    
    # 1. Se paga 1/6 de la R. Computable por mes completo
    grati_bruta = (sueldo_computable / 6) * meses_completos
    
    # 2. (NUEVO) Descuento por faltas
    # Lógica de 1/180vo por día de falta (1/30 de 1/6)
    descuento_por_faltas = (sueldo_computable / 180) * dias_falta_semestre
    
    grati_neta_a_pagar = max(0, grati_bruta - descuento_por_faltas)
    
    # 3. Bonificación Extraordinaria (9% EsSalud o 6.75% EPS)
    tasa_bonificacion = BONI_LEY_EPS if tiene_eps else BONI_LEY_ESSALUD
    bonificacion = grati_neta_a_pagar * tasa_bonificacion
    
    return grati_neta_a_pagar, bonificacion

def calcular_cts_semestral(remuneracion_computable_cts: float, meses_completos: int) -> float:
    """
    Calcula el depósito de CTS semestral (Mayo u Octubre).
    Base Legal: D.S. N° 001-97-TR (TUO Ley de CTS).
    R. Computable (Art. 19) = RB + AF + (1/6 Grati)
    Cálculo (Art. 20) = (R.C. / 12) * meses_completos
    """
    if meses_completos <= 0:
        return 0
        
    cts_semestral = (remuneracion_computable_cts / 12) * meses_completos
    
    return cts_semestral

# --- 5. FUNCIONES PRINCIPALES Y DE ORQUESTACIÓN ---

def _calcular_proyecciones_renta_quinta(
    # --- Datos del empleado ---
    sueldo_basico_nominal: float,
    tiene_hijos: bool,
    tiene_eps: bool,
    # --- Datos del mes ---
    mes_actual_num: int,
    dias_falta: int,
    horas_nocturnas_mes: float,
    otros_ingresos_afectos: float,
    ingresos_no_remunerativos: float,
    ingreso_lpa: float,
    # --- Bases calculadas del mes ---
    base_renta_quinta_mes: float,
    base_pension_salud_mes: float,
    # --- Acumuladores ---
    ingresos_brutos_acumulados_renta5: float,
    ingresos_afectos_salud_acumulados: float
) -> Tuple[float, float]:
    """
    (NUEVO) Función interna para modularizar la lógica de proyección anual.
    Calcula y devuelve las dos proyecciones clave para Renta 5ta.
    Devuelve: (proyeccion_anual_r5, proyeccion_base_salud_anual)
    """
    
    # --- Proyecciones Anuales (FUTURO) ---
    
    # 1. Calcular la base fija para los meses futuros
    valor_hora_nominal = calcular_valor_hora(sueldo_basico_nominal)
    # Proyecta bono nocturno basado en el promedio de este mes
    bn_proyectado_fijo = 0
    dias_laborados_mes = 30 - dias_falta
    if dias_laborados_mes > 0 and horas_nocturnas_mes > 0:
        # Proyecta las horas nocturnas del mes a un mes completo de 30 días
        horas_nocturnas_proyectadas_mes = (horas_nocturnas_mes / dias_laborados_mes) * 30
        bn_proyectado_fijo = calcular_bonificacion_nocturna(valor_hora_nominal, horas_nocturnas_proyectadas_mes)

    # Base de Proyección para Renta 5ta (Sin Grati/Boni)
    base_proy_nominal_rem_R5 = (
        sueldo_basico_nominal + 
        calcular_asignacion_familiar(tiene_hijos) + 
        otros_ingresos_afectos +
        bn_proyectado_fijo 
    )
    base_proy_nominal_no_rem_R5 = ingresos_no_remunerativos + ingreso_lpa
    base_proyeccion_mes_normal_R5 = base_proy_nominal_rem_R5 + base_proy_nominal_no_rem_R5
    
    # 2. Calcular Ingresos Futuros Proyectados (Renta 5ta)
    
    # Suma los ingresos reales de Renta 5ta (sin grati/boni)
    ingresos_reales_acumulados_R5 = ingresos_brutos_acumulados_renta5 + base_renta_quinta_mes
    
    meses_futuros = 12 - mes_actual_num
    
    # Proyecta solo los meses futuros normales (sin grati/boni)
    ingresos_futuros_proyectados_R5 = base_proyeccion_mes_normal_R5 * meses_futuros
    
    ingresos_proyectados_anuales_r5 = ingresos_reales_acumulados_R5 + ingresos_futuros_proyectados_R5
    
    # 3. Calcular Proyección de Base Salud (para Crédito EPS)
    base_salud_real_acumulada = ingresos_afectos_salud_acumulados + base_pension_salud_mes
    base_fija_salud_futura = base_proy_nominal_rem_R5 
    proyeccion_base_salud_futura = base_fija_salud_futura * meses_futuros
    proyeccion_base_salud_anual = base_salud_real_acumulada + proyeccion_base_salud_futura

    return ingresos_proyectados_anuales_r5, proyeccion_base_salud_anual


def generar_boleta_mensual(
    # --- Datos del empleado ---
    sueldo_basico_nominal: float, 
    tiene_hijos: bool = False,
    sistema_pension: str = 'ONP', 
    tiene_eps: bool = False,
    
    # --- Datos del mes ---
    mes_actual_num: int = 1, 
    dias_falta: int = 0,
    horas_nocturnas_mes: float = 0.0, 
    horas_25: float = 0.0,
    horas_35: float = 0.0,
    horas_100: float = 0.0, 
    otros_ingresos_afectos: float = 0.0, 
    ingresos_no_remunerativos: float = 0.0, # Ej. Movilidad
    ingreso_lpa: float = 0.0, # Prestación Alimentaria
    otros_descuentos_fijos: float = 0.0, 
    
    # --- Conceptos No Computables ---
    ingreso_utilidades: float = 0.0,
    ingreso_subsidio: float = 0.0,
    
    # --- Datos del año (para Renta 5ta) ---
    ingresos_brutos_acumulados_renta5: float = 0.0, 
    ingresos_afectos_salud_acumulados: float = 0.0, 
    retenciones_acumuladas_renta5: float = 0.0,
    
    # --- Historial para Regularidad ---
    historial_semestral_ingresos_variables: Dict[str, List[float]] = None,
    
    # --- Gastos Deducibles 3 UIT (Anuales) ---
    gastos_deducibles_arrendamiento: float = 0.0,
    gastos_deducibles_honorarios_medicos: float = 0.0,
    gastos_deducibles_servicios_profesionales: float = 0.0,
    gastos_deducibles_essalud_hogar: float = 0.0,
    gastos_deducibles_hoteles_rest: float = 0.0
) -> Dict[str, Any]:
    """
    Genera un cálculo detallado de una boleta de pago mensual.
    Devuelve un diccionario con todos los resultados.
    """
    
    boleta: Dict[str, Any] = {} # Inicializa el diccionario de resultados
    boleta['mes'] = mes_actual_num # (NUEVO) Guardar el mes

    # --- 1. CÁLCULO DE INGRESOS MENSUALES ---
    
    # 1.1. Cálculo de Faltas
    valor_dia = sueldo_basico_nominal / 30
    desc_faltas = valor_dia * dias_falta
    ing_basico_ajustado = sueldo_basico_nominal - desc_faltas
    valor_hora_calculado = calcular_valor_hora(ing_basico_ajustado)
    
    boleta['sueldo_basico_nominal'] = sueldo_basico_nominal
    boleta['dias_falta'] = dias_falta
    boleta['desc_faltas'] = desc_faltas
    boleta['ing_basico_ajustado'] = ing_basico_ajustado
    boleta['valor_hora_calculado'] = valor_hora_calculado
    
    # 1.2. Ingresos Remunerativos
    ing_asig_familiar = calcular_asignacion_familiar(tiene_hijos)
    ing_bonificacion_nocturna = calcular_bonificacion_nocturna(valor_hora_calculado, horas_nocturnas_mes)
    ing_sobretiempo_total, m25, m35, m100 = calcular_sobretiempo(valor_hora_calculado, horas_25, horas_35, horas_100)
    
    boleta['ing_asig_familiar'] = ing_asig_familiar
    boleta['ing_bonificacion_nocturna'] = ing_bonificacion_nocturna
    boleta['ing_sobretiempo_total'] = ing_sobretiempo_total
    boleta['otros_ingresos_afectos'] = otros_ingresos_afectos
    
    # 1.3. Ingresos No Remunerativos (para boleta)
    boleta['ingresos_no_remunerativos'] = ingresos_no_remunerativos
    boleta['ingreso_lpa'] = ingreso_lpa
    boleta['ingreso_utilidades'] = ingreso_utilidades
    boleta['ingreso_subsidio'] = ingreso_subsidio
    
    # 1.4. Gratificación (si corresponde)
    ing_gratificacion = 0.0
    ing_boni_ley = 0.0
    es_mes_grati = (mes_actual_num == 7 or mes_actual_num == 12)
    dias_faltas_totales_semestre = 0
    rem_computable_grati = 0.0
    
    if es_mes_grati and historial_semestral_ingresos_variables:
        # Aplicar Principio de Regularidad (Art. 19, D.S. 001-97-TR)
        promedio_variables_regulares = _calcular_promedio_regularidad(historial_semestral_ingresos_variables)
        
        # RC = Básico (ajustado) + AF + Promedio Variables
        rem_computable_grati = (
            ing_basico_ajustado + 
            ing_asig_familiar + 
            promedio_variables_regulares
        )
        
        # Sumar faltas del semestre para descuento
        dias_faltas_totales_semestre = sum(historial_semestral_ingresos_variables.get('dias_falta', []))
        
        ing_gratificacion, ing_boni_ley = calcular_gratificacion(
            rem_computable_grati, 
            6, 
            tiene_eps,
            dias_falta_semestre=dias_faltas_totales_semestre
        )
    
    boleta['rem_computable_grati'] = rem_computable_grati
    boleta['ing_gratificacion'] = ing_gratificacion
    boleta['ing_boni_ley'] = ing_boni_ley
    boleta['dias_falta_semestre_grati'] = dias_faltas_totales_semestre
    
    # --- 2. CÁLCULO DE BASES AFECTAS (Este Mes) ---
    
    # Base Afecta a Pensión y Salud (Sin Grati/Boni/CNR/LPA/Util/Subsidio)
    base_pension_salud_mes = (
        ing_basico_ajustado + 
        ing_asig_familiar + 
        ing_bonificacion_nocturna + 
        ing_sobretiempo_total +     
        otros_ingresos_afectos
    )
    
    # Base Afecta a Renta 5ta (Sin Grati/Boni PERO CON CNR/LPA/Util/Subsidio)
    base_renta_quinta_mes = (
        base_pension_salud_mes +      
        ingresos_no_remunerativos +   
        ingreso_lpa +                 
        ingreso_utilidades +          
        ingreso_subsidio              
    )
    
    # Total Ingresos (Visual de Boleta) = Suma de todo
    total_ingresos_boleta = (
        base_renta_quinta_mes +
        ing_gratificacion +           
        ing_boni_ley                  
    )

    boleta['total_ingresos_brutos_mes'] = total_ingresos_boleta
    boleta['base_pension_salud_mes'] = base_pension_salud_mes
    boleta['base_renta_quinta_mes'] = base_renta_quinta_mes

    # --- 3. PROYECCIÓN ANUAL (RENTA 5TA) ---
    
    proyeccion_anual_r5, proyeccion_base_salud_anual = _calcular_proyecciones_renta_quinta(
        sueldo_basico_nominal=sueldo_basico_nominal,
        tiene_hijos=tiene_hijos,
        tiene_eps=tiene_eps,
        mes_actual_num=mes_actual_num,
        dias_falta=dias_falta,
        horas_nocturnas_mes=horas_nocturnas_mes,
        otros_ingresos_afectos=otros_ingresos_afectos,
        ingresos_no_remunerativos=ingresos_no_remunerativos,
        ingreso_lpa=ingreso_lpa,
        base_renta_quinta_mes=base_renta_quinta_mes,
        base_pension_salud_mes=base_pension_salud_mes,
        ingresos_brutos_acumulados_renta5=ingresos_brutos_acumulados_renta5,
        ingresos_afectos_salud_acumulados=ingresos_afectos_salud_acumulados
    )
    
    boleta['proyeccion_anual_r5'] = proyeccion_anual_r5
    boleta['proyeccion_base_salud_anual'] = proyeccion_base_salud_anual
    
    # --- 4. CÁLCULO DE DESCUENTOS ---
    
    # 4.1. Descuento de Pensión
    desc_pension = calcular_descuento_pension(base_pension_salud_mes, sistema_pension)
    boleta['desc_pension'] = desc_pension
    
    # 4.2. Descuento LPA (Neto Cero) - Ley N° 28051
    desc_lpa = ingreso_lpa
    boleta['desc_lpa'] = desc_lpa
    
    # 4.3. Descuento Renta 5ta
    desc_renta_quinta = calcular_retencion_renta_quinta(
        ingresos_proyectados_anuales=proyeccion_anual_r5,
        proyeccion_base_salud_anual=proyeccion_base_salud_anual,
        tiene_eps=tiene_eps,
        mes_actual_num=mes_actual_num,
        retenciones_acumuladas=retenciones_acumuladas_renta5,
        gastos_deducibles_arrendamiento=gastos_deducibles_arrendamiento,
        gastos_deducibles_honorarios_medicos=gastos_deducibles_honorarios_medicos,
        gastos_deducibles_servicios_profesionales=gastos_deducibles_servicios_profesionales,
        gastos_deducibles_essalud_hogar=gastos_deducibles_essalud_hogar,
        gastos_deducibles_hoteles_rest=gastos_deducibles_hoteles_rest
    )
    boleta['desc_renta_quinta'] = desc_renta_quinta
    
    # 4.4. Otros Descuentos Fijos
    boleta['otros_descuentos_fijos'] = otros_descuentos_fijos
    
    # --- 5. TOTALES ---
    
    total_descuentos = (
        desc_pension + 
        desc_renta_quinta + 
        desc_lpa +
        otros_descuentos_fijos 
    )
    neto_a_pagar = total_ingresos_boleta - total_descuentos
    
    boleta['total_descuentos'] = total_descuentos
    boleta['neto_a_pagar'] = neto_a_pagar
    boleta['sistema_pension'] = sistema_pension
    boleta['tiene_eps'] = tiene_eps

    # --- 6. RATIOS DE EFICIENCIA (TRABAJADOR) ---
    
    if total_ingresos_boleta > 0:
        boleta['ratio_neto_vs_bruto'] = neto_a_pagar / total_ingresos_boleta
    else:
        boleta['ratio_neto_vs_bruto'] = 0.0

    if sueldo_basico_nominal > 0:
        boleta['ratio_neto_vs_sueldo_nominal'] = neto_a_pagar / sueldo_basico_nominal
    else:
        boleta['ratio_neto_vs_sueldo_nominal'] = 0.0

    return boleta


# --- 6. FUNCIÓN DE IMPRESIÓN (Para pruebas y Streamlit) ---
def mostrar_boleta_streamlit(boleta: Dict[str, Any], mes: int):
    """Muestra los resultados de la boleta en la UI de Streamlit."""
    
    st.header(f"Resultados de la Boleta (Mes {mes})")
    
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
        
def mostrar_costo_laboral_streamlit(costo: Dict[str, Any]):
    """Muestra los resultados del costo laboral en la UI de Streamlit."""
    
    st.header(f"Costo Laboral del Empleador (Mes {costo['mes']})")
    
    col1, col2 = st.columns(2)
    col1.metric("Costo Laboral Total del Mes", f"S/ {costo['costo_laboral_total_mes']:,.2f}")
    col2.metric("Total Aportes Empleador", f"S/ {costo['total_aportes_empleador']:,.2f}")
    
    with st.expander("Ver Desglose de Aportes del Empleador"):
        st.markdown(f"**Aporte EsSalud (9%):** `S/ {costo['aporte_essalud_9_porc']:,.2f}`")
        st.markdown(f"**Aporte SCTR:** `S/ {costo['aporte_sctr']:,.2f}`")
        st.markdown(f"**Aporte SENATI:** `S/ {costo['aporte_senati']:,.2f}`")
        st.markdown(f"**Aporte Seguro Vida Ley:** `S/ {costo['aporte_vida_ley']:,.2f}`")

    st.subheader("Ratios de Costo (Empleador)")
    col1, col2 = st.columns(2)
    col1.metric("Costo Total vs. Sueldo Nominal", f"{costo['ratio_costo_vs_sueldo_nominal']:.2%}", help="Costo total por cada S/ 1.00 de sueldo básico.")
    col2.metric("Costo Total vs. Bruto Total", f"{costo['ratio_costo_vs_bruto']:.2%}", help="Sobrecosto real del empleador sobre el bruto pagado.")

    with st.expander("Ver Diccionario de Resultados (JSON)"):
        st.json(costo)


# --- 7. FUNCIONES DE LIQUIDACIÓN DE BENEFICIOS SOCIALES (LQBS) ---

def _calcular_tiempo_servicio(fecha_inicio: datetime.date, fecha_fin: datetime.date) -> relativedelta:
    """Helper: Calcula el tiempo total de servicio usando relativedelta."""
    try:
        # fecha_fin es el último día laborado. Se suma 1 para cálculo.
        fin = fecha_fin + relativedelta(days=1)
        return relativedelta(fin, fecha_inicio)
    except Exception as e:
        st.error(f"Error al calcular tiempo de servicio: {e}. Asegúrese que las fechas sean válidas.")
        return relativedelta()

def _calcular_truncos_cts(rc_cts: float, fecha_ingreso: datetime.date, fecha_cese: datetime.date) -> Tuple[float, int, int]:
    """
    Calcula la CTS Trunca.
    Base Legal: D.S. N° 001-97-TR (TUO Ley de CTS).
    Se calcula por meses y días desde el ÚLTIMO depósito (1-May o 1-Nov).
    """
    
    # Determinar el inicio del último período de CTS
    if 5 <= fecha_cese.month <= 10: # Cese entre Mayo y Octubre
        inicio_periodo_cts = datetime(fecha_cese.year, 5, 1).date() # Último depósito fue en Mayo
    else: # Cese entre Nov y Abr
        inicio_periodo_cts = datetime(fecha_cese.year, 11, 1).date()
        if fecha_cese.month < 5: # Si cesó en Ene-Abr, el período inició el año pasado
            inicio_periodo_cts = datetime(fecha_cese.year - 1, 11, 1).date()
            
    if inicio_periodo_cts < fecha_ingreso:
        inicio_periodo_cts = fecha_ingreso # Para trabajadores nuevos

    # Calcular meses y días truncos
    delta = _calcular_tiempo_servicio(inicio_periodo_cts, fecha_cese)
    meses_truncos = delta.months + (delta.years * 12)
    dias_truncos = delta.days

    # Cálculo: (RC / 12 * Meses) + (RC / 12 / 30 * Días)
    cts_trunca = (rc_cts / 12 * meses_truncos) + (rc_cts / 12 / 30 * dias_truncos)
    return cts_trunca, meses_truncos, dias_truncos

def _calcular_truncos_grati(
    rc_grati: float, 
    fecha_cese: datetime.date,
    dias_falta_en_semestre_trunco: int = 0 # (NUEVO)
) -> Tuple[float, int, float]:
    """
    Calcula la Gratificación Trunca.
    Base Legal: D.S. N° 005-2002-TR (Reglamento Grati).
    Se calcula por meses completos desde el inicio del semestre (1-Ene o 1-Jul).
    (REFINADO) Se descuenta 1/180vo por falta.
    """

    # Determinar el inicio del semestre
    if 1 <= fecha_cese.month <= 6: # Cese en Semestre Ene-Jun (Grati de Julio)
        inicio_semestre = datetime(fecha_cese.year, 1, 1).date()
    else: # Cese en Semestre Jul-Dic (Grati de Diciembre)
        inicio_semestre = datetime(fecha_cese.year, 7, 1).date()

    delta = _calcular_tiempo_servicio(inicio_semestre, fecha_cese)
    meses_completos = delta.months + (delta.years * 12)

    # Cálculo: (1/6 de RC por mes completo)
    grati_trunca_bruta = (rc_grati / 6) * meses_completos
    
    # (NUEVO) Descuento por faltas 1/180vo
    descuento_por_faltas = (rc_grati / 180) * dias_falta_en_semestre_trunco
    
    grati_trunca_neta = max(0, grati_trunca_bruta - descuento_por_faltas)
    
    return grati_trunca_neta, meses_completos, descuento_por_faltas

def _calcular_truncos_vacaciones(
    rc_vacas: float, 
    fecha_ingreso: datetime.date, 
    fecha_cese: datetime.date,
    ha_perdido_record_vacacional: bool = False # (NUEVO)
) -> Tuple[float, int, int]:
    """
    Calcula las Vacaciones Truncas.
    Base Legal: D.L. N° 713.
    Se calcula por meses y días desde el ÚLTIMO ANIVERSARIO de ingreso.
    (NUEVO) Pierde el derecho si no cumple Récord Vacacional (Art. 10, D.L. 713)
    """
    
    if ha_perdido_record_vacacional:
        return 0.0, 0, 0
    
    # Encontrar el último aniversario
    ultimo_aniversario = datetime(fecha_cese.year, fecha_ingreso.month, fecha_ingreso.day).date()
    if fecha_cese < ultimo_aniversario:
        ultimo_aniversario = datetime(fecha_cese.year - 1, fecha_ingreso.month, fecha_ingreso.day).date()

    if ultimo_aniversario < fecha_ingreso:
        ultimo_aniversario = fecha_ingreso # Para trabajadores nuevos

    delta = _calcular_tiempo_servicio(ultimo_aniversario, fecha_cese)
    meses_truncos = delta.months + (delta.years * 12)
    dias_truncos = delta.days

    # Cálculo: (RC / 12 * Meses) + (RC / 12 / 30 * Días)
    vacas_truncas = (rc_vacas / 12 * meses_truncos) + (rc_vacas / 12 / 30 * dias_truncos)
    return vacas_truncas, meses_truncos, dias_truncos

def _calcular_indemnizacion_despido(rc_indemnizacion: float, fecha_ingreso: datetime.date, fecha_cese: datetime.date) -> Tuple[float, int, int, int]:
    """
    Calcula la indemnización por despido arbitrario.
    Base Legal: Art. 34 y 38, D.S. N° 003-97-TR (LPCL).
    1.5 Remuneraciones por año completo (Tope 12 Remuneraciones).
    Fracciones (meses/días) se pagan por dozavos y treintavos.
    """
    delta_total = _calcular_tiempo_servicio(fecha_ingreso, fecha_cese)
    anios_completos = delta_total.years
    meses_completos = delta_total.months
    dias = delta_total.days
    
    # Cálculo por años completos (con tope)
    remuneracion_por_anio = rc_indemnizacion * 1.5
    indemnizacion_anios = min(remuneracion_por_anio * anios_completos, rc_indemnizacion * 12)
    
    # Cálculo por fracciones (meses y días) - SIN TOPE
    indemnizacion_meses = (remuneracion_por_anio / 12) * meses_completos
    indemnizacion_dias = (remuneracion_por_anio / 12 / 30) * dias
    
    total_indemnizacion = indemnizacion_anios + indemnizacion_meses + indemnizacion_dias
    
    return total_indemnizacion, anios_completos, meses_completos, dias

def generar_liquidacion(
    # --- Datos Requeridos ---
    rc_basica: float, # Sueldo + AF
    historial_ultimos_6_meses_variables: Dict[str, List[float]],
    ultimo_sexto_grati: float, # 1/6 de la última grati percibida
    fecha_ingreso: datetime.date, 
    fecha_cese: datetime.date, 
    motivo_cese: str,
    
    # --- Opcionales ---
    es_part_time_lt_4h: bool = False,
    ha_perdido_record_vacacional: bool = False,
    dias_falta_en_semestre_trunco: int = 0
) -> Dict[str, Any]:
    """
    Genera el cálculo completo de una Liquidación de Beneficios Sociales (LQBS).
    """
    
    lqbs = {
        'fecha_ingreso': fecha_ingreso,
        'fecha_cese': fecha_cese,
        'motivo_cese': motivo_cese,
        'es_part_time_lt_4h': es_part_time_lt_4h,
        'ha_perdido_record_vacacional': ha_perdido_record_vacacional,
        'dias_falta_en_semestre_trunco': dias_falta_en_semestre_trunco
    }

    # 1. Definir Remuneraciones Computables (RC)
    
    promedio_regularidad_lqbs = _calcular_promedio_regularidad(historial_ultimos_6_meses_variables)
    lqbs['promedio_variables_regulares'] = promedio_regularidad_lqbs
    
    # RC para Grati y Vacaciones (D.L. 713 y Ley 27735)
    rc_grati_vacas = rc_basica + promedio_regularidad_lqbs
    lqbs['rc_grati_vacas'] = rc_grati_vacas
    
    # RC para CTS (Art. 19, D.S. 001-97-TR)
    rc_cts = rc_grati_vacas + ultimo_sexto_grati
    lqbs['rc_cts'] = rc_cts
    
    # 2. Calcular Beneficios Truncos
    lqbs['cts_trunca'], lqbs['cts_meses'], lqbs['cts_dias'] = _calcular_truncos_cts(rc_cts, fecha_ingreso, fecha_cese)
    lqbs['grati_trunca'], lqbs['grati_meses'], lqbs['grati_desc_faltas'] = _calcular_truncos_grati(
        rc_grati_vacas, 
        fecha_cese,
        dias_falta_en_semestre_trunco
    )
    lqbs['vacas_truncas'], lqbs['vacas_meses'], lqbs['vacas_dias'] = _calcular_truncos_vacaciones(
        rc_grati_vacas, 
        fecha_ingreso, 
        fecha_cese,
        ha_perdido_record_vacacional
    )
    
    # (NUEVO) Validación Régimen Part-Time (< 4h/día)
    if es_part_time_lt_4h:
        lqbs['cts_trunca'] = 0.0
        lqbs['vacas_truncas'] = 0.0
        lqbs['info_part_time'] = "No se pagan CTS ni Vacaciones (Régimen Part-Time < 4h)."
    else:
        lqbs['info_part_time'] = None

    total_beneficios_truncos = lqbs['cts_trunca'] + lqbs['grati_trunca'] + lqbs['vacas_truncas']
    lqbs['total_beneficios_truncos'] = total_beneficios_truncos
    
    # 3. Calcular Indemnización (si aplica)
    indemnizacion = 0.0
    if motivo_cese.upper() == 'DESPIDO_ARBITRARIO':
        indemnizacion, anios, meses, dias = _calcular_indemnizacion_despido(rc_grati_vacas, fecha_ingreso, fecha_cese)
        lqbs['indemnizacion_anios'] = anios
        lqbs['indemnizacion_meses'] = meses
        lqbs['indemnizacion_dias'] = dias
        
    lqbs['indemnizacion_despido'] = indemnizacion
    
    # 4. Total a Pagar
    lqbs['total_liquidacion'] = total_beneficios_truncos + indemnizacion
    
    return lqbs

# --- 8. FUNCIÓN DE IMPRESIÓN (LQBS) ---

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
        lqbs_json = lqbs.copy()
        lqbs_json['fecha_ingreso'] = lqbs_json['fecha_ingreso'].isoformat()
        lqbs_json['fecha_cese'] = lqbs_json['fecha_cese'].isoformat()
        st.json(lqbs_json)


# --- 9. FUNCIONES DE COSTO LABORAL (EMPLEADOR) ---
def calcular_costo_laboral_mensual(
    boleta: Dict[str, Any],
    tasa_sctr: float = 0.0, # %
    tasa_senati: float = 0.0, # %
    prima_vida_ley: float = 0.0 # Monto S/
) -> Dict[str, Any]:
    """
    Calcula los aportes mensuales del empleador (Costo Laboral).
    Toma el diccionario de boleta_mes como input.
    """
    
    costos = {}
    costos['mes'] = boleta.get('mes', 0) # (NUEVO) Para el reporte anual
    
    base_afecta_salud = boleta['base_pension_salud_mes']
    
    # 1. Aporte EsSalud (Ley N° 26790)
    aporte_essalud = base_afecta_salud * PORC_ESSALUD
    costos['aporte_essalud_9_porc'] = aporte_essalud
    
    # 2. SCTR (D.S. N° 003-98-SA)
    aporte_sctr = base_afecta_salud * tasa_sctr
    costos['aporte_sctr'] = aporte_sctr
    
    # 3. SENATI (Ley N° 26272)
    aporte_senati = base_afecta_salud * tasa_senati
    costos['aporte_senati'] = aporte_senati
    
    # 4. Seguro Vida Ley (D.L. N° 688 y Ley N° 29549)
    aporte_vida_ley = prima_vida_ley
    costos['aporte_vida_ley'] = aporte_vida_ley
    
    total_aportes_empleador = (
        aporte_essalud +
        aporte_sctr +
        aporte_senati +
        aporte_vida_ley
    )
    costos['total_aportes_empleador'] = total_aportes_empleador
    
    costo_laboral_total_mes = boleta['total_ingresos_brutos_mes'] + total_aportes_empleador
    costos['costo_laboral_total_mes'] = costo_laboral_total_mes
    
    # --- 5. RATIOS DE COSTO (EMPLEADOR) ---
    base_nominal = boleta.get('sueldo_basico_nominal', 0.0)
    base_bruta = boleta.get('total_ingresos_brutos_mes', 0.0)
    
    if base_nominal > 0:
        costos['ratio_costo_vs_sueldo_nominal'] = costo_laboral_total_mes / base_nominal
    else:
        costos['ratio_costo_vs_sueldo_nominal'] = 0.0
        
    if base_bruta > 0:
        costos['ratio_costo_vs_bruto'] = costo_laboral_total_mes / base_bruta
    else:
        costos['ratio_costo_vs_bruto'] = 0.0
    
    return costos


# --- 10. FUNCIONES DE REMUNERACIÓN INTEGRAL ANUAL (RIA) ---

def generar_boleta_ria(
    remuneracion_integral_anual: float,
    sistema_pension: str = 'ONP',
    tiene_eps: bool = False,
    # --- Datos del mes/año ---
    mes_actual_num: int = 1,
    retenciones_acumuladas_renta5: float = 0.0,
    # --- Gastos Deducibles 3 UIT (Anuales) ---
    gastos_deducibles_arrendamiento: float = 0.0,
    gastos_deducibles_honorarios_medicos: float = 0.0,
    gastos_deducibles_servicios_profesionales: float = 0.0,
    gastos_deducibles_essalud_hogar: float = 0.0,
    gastos_deducibles_hoteles_rest: float = 0.0
) -> Dict[str, Any]:
    """
    Genera un cálculo de boleta para el régimen de Remuneración Integral Anual.
    Base Legal: Art. 8, D.S. N° 003-97-TR (LPCL).
    
    **NOTA:** Este régimen es opcional y requiere un pacto por escrito.
    """
    
    boleta_ria = {}
    pago_mensual_integral = remuneracion_integral_anual / 12
    
    # 1. Validación Legal
    if pago_mensual_integral < LIMITE_MINIMO_RIA_MENSUAL:
        boleta_ria['error'] = f"Error: El pago mensual (S/ {pago_mensual_integral:,.2f}) no supera las 2 UIT (S/ {LIMITE_MINIMO_RIA_MENSUAL:,.2f}). No califica para RIA."
        return boleta_ria

    boleta_ria['ingreso_integral_mensual'] = pago_mensual_integral
    
    # 2. Bases Afectas
    base_pension_salud_mes = pago_mensual_integral
    base_renta_quinta_mes = pago_mensual_integral
    
    boleta_ria['base_pension_salud_mes'] = base_pension_salud_mes
    boleta_ria['base_renta_quinta_mes'] = base_renta_quinta_mes
    
    # 3. Descuentos
    desc_pension = calcular_descuento_pension(base_pension_salud_mes, sistema_pension)
    
    proyeccion_anual_r5 = remuneracion_integral_anual
    proyeccion_base_salud_anual = remuneracion_integral_anual
    
    desc_renta_quinta = calcular_retencion_renta_quinta(
        ingresos_proyectados_anuales=proyeccion_anual_r5,
        proyeccion_base_salud_anual=proyeccion_base_salud_anual,
        tiene_eps=tiene_eps,
        mes_actual_num=mes_actual_num,
        retenciones_acumuladas=retenciones_acumuladas_renta5,
        gastos_deducibles_arrendamiento=gastos_deducibles_arrendamiento,
        gastos_deducibles_honorarios_medicos=gastos_deducibles_honorarios_medicos,
        gastos_deducibles_servicios_profesionales=gastos_deducibles_servicios_profesionales,
        gastos_deducibles_essalud_hogar=gastos_deducibles_essalud_hogar,
        gastos_deducibles_hoteles_rest=gastos_deducibles_hoteles_rest
    )
    
    boleta_ria['desc_pension'] = desc_pension
    boleta_ria['desc_renta_quinta'] = desc_renta_quinta
    boleta_ria['sistema_pension'] = sistema_pension
    
    # 4. Totales
    total_descuentos = desc_pension + desc_renta_quinta
    neto_a_pagar = pago_mensual_integral - total_descuentos
    
    boleta_ria['total_descuentos'] = total_descuentos
    boleta_ria['neto_a_pagar'] = neto_a_pagar
    
    return boleta_ria

def mostrar_boleta_ria_streamlit(boleta: Dict[str, Any], mes: int):
    """Imprime la boleta simplificada del régimen RIA."""
    
    st.header(f"Resultados de la Boleta RIA (Mes {mes})")

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


# --- 11. FUNCIONES DE CASOS ESPECIALES (INDEMNIZACIONES) ---

def calcular_indemnizacion_vacaciones_no_gozadas(
    rc_vacacional: float,
    periodos_vencidos: int = 1,
    es_part_time_lt_4h: bool = False, 
    ha_perdido_record_vacacional: bool = False
) -> Dict[str, Any]:
    """
    Calcula la indemnización por vacaciones no gozadas (la "triple" vacación).
    Base Legal: Art. 23, D.L. N° 713.
    """
    
    info_adicional = None
    
    if es_part_time_lt_4h:
        info_adicional = "No aplica indemnización vacacional (Régimen Part-Time < 4h)."
    
    if ha_perdido_record_vacacional:
        info_adicional = "No aplica indemnización vacacional (Récord no cumplido por faltas)."

    if info_adicional:
        return {
            "rc_vacacional": rc_vacacional,
            "periodos_vencidos": periodos_vencidos,
            "pago_por_vacacion_no_gozada": 0.0,
            "pago_por_indemnizacion": 0.0,
            "total_a_pagar": 0.0,
            "info_adicional": info_adicional
        }

    pago_por_vacacion_no_gozada = rc_vacacional * periodos_vencidos
    pago_por_indemnizacion = rc_vacacional * periodos_vencidos
    
    total_indemnizacion_vacas = pago_por_vacacion_no_gozada + pago_por_indemnizacion
    
    return {
        "rc_vacacional": rc_vacacional,
        "periodos_vencidos": periodos_vencidos,
        "pago_por_vacacion_no_gozada": pago_por_vacacion_no_gozada,
        "pago_por_indemnizacion": pago_por_indemnizacion,
        "total_a_pagar": total_indemnizacion_vacas,
        "info_adicional": None
    }

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
# === PARTE 2: INTERFAZ DE USUARIO (STREAMLIT) ===
# ==============================================================================

# --- Configuración de la Página ---
st.set_page_config(
    layout="wide",
    page_title="Calculadora de Planilla Perú 2025",
    page_icon="🇵🇪"
)

# (NUEVO) CSS Global para ocultar los botones +/- en st.number_input
st.markdown("""
    <style>
        /* Ocultar los botones de incremento/decremento en st.number_input */
        div[data-testid="stNumberInput"] button[data-testid="stNumberInputUpButton"],
        div[data-testid="stNumberInput"] button[data-testid="stNumberInputDownButton"] {
            display: none;
        }
        /* Forzar que el texto del input ocupe todo el espacio */
        div[data-testid="stNumberInput"] div[data-baseweb="input"] > div:first-of-type {
            width: 100% !important;
        }
    </style>
""", unsafe_allow_html=True)


st.title("Calculadora de Planilla y BB.SS. Perú 2025")
st.info("Herramienta de cálculo basada en la legislación peruana, desarrollada a partir del motor 'planilla_tool.py'.")

# --- Definición de Pestañas ---
tab_boleta, tab_lqbs, tab_ria, tab_indemnizacion = st.tabs([
    "Calculadora de Boleta Mensual (Régimen 728)", 
    "Calculadora de Liquidación (LQBS)", 
    "Calculadora Régimen Integral (RIA)",
    "Calculadora Indemnización Vacaciones"
])


# --- PESTAÑA 1: BOLETA MENSUAL (RÉGIMEN 728) - (MEJORADA) ---
with tab_boleta:
    st.header("Calculadora de Boleta Mensual (Régimen 728)")
    
    # (NUEVO) Checkbox para Simulación Anual
    in_simulacion_anual = st.checkbox("Modo de Simulación Anual", value=False,
                                      help="Si se activa, la app calculará los 12 meses del año, acumulando Renta 5ta automáticamente.")
    
    with st.form("boleta_form"):
        
        # --- Columnas de Inputs ---
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("Datos del Empleado")
            in_sueldo_basico = st.number_input("Sueldo Básico Nominal", min_value=0.0, value=5300.0, step=100.0)
            in_tiene_hijos = st.checkbox("¿Tiene Hijos? (Asig. Familiar)", value=False)
            in_sistema_pension = st.selectbox("Sistema de Pensión", 
                                              ['ONP', 'INTEGRA', 'PRIMA', 'HABITAT', 'PROFUTURO'], 
                                              index=1)
            in_tiene_eps = st.checkbox("¿Tiene EPS?", value=True)

        with col2:
            st.subheader("Datos del Mes")
            # (NUEVO) Slider deshabilitado si la simulación anual está activa
            in_mes_actual = st.slider("Mes de Cálculo", 1, 12, 1, disabled=in_simulacion_anual)
            in_dias_falta = st.number_input("Días de Falta Injustificada", min_value=0, max_value=30, value=0, step=1,
                                            help="Para simulación anual: ingrese faltas del Mes 1 (Ene). Para faltas en otros meses, use el editor de historial.")
            in_horas_nocturnas = st.number_input("Total Horas Nocturnas en el Mes", min_value=0.0, value=0.0, step=1.0)
            in_he_25 = st.number_input("Total Horas Extras al 25%", min_value=0.0, value=0.0, step=0.5)
            in_he_35 = st.number_input("Total Horas Extras al 35%", min_value=0.0, value=0.0, step=0.5)
            in_he_100 = st.number_input("Total Horas Extras al 100% (Feriados)", min_value=0.0, value=0.0, step=0.5)

        with col3:
            st.subheader("Otros Ingresos / Descuentos")
            in_otros_ingresos_afectos = st.number_input("Otros Bonos Afectos", min_value=0.0, value=0.0, step=50.0)
            in_movilidad = st.number_input("Ingreso No Remunerativo (Movilidad)", min_value=0.0, value=500.0, step=50.0)
            in_lpa = st.number_input("Prestación Alimentaria (LPA)", min_value=0.0, value=0.0, step=50.0)
            in_utilidades = st.number_input("Ingreso por Utilidades (Pago único)", min_value=0.0, value=0.0, step=100.0,
                                             help="Para simulación anual: este monto se aplicará solo en Marzo.")
            in_subsidio = st.number_input("Ingreso por Subsidio (DM)", min_value=0.0, value=0.0, step=100.0)
            in_otros_descuentos = st.number_input("Otros Descuentos Fijos (Sindicato, etc.)", min_value=0.0, value=0.0, step=10.0)

        # --- (NUEVO) Expanders Reorganizados ---
        
        # 1. Configuración de Renta 5ta
        with st.expander("Configuración Avanzada de Renta 5ta"):
            tab_gastos, tab_acumuladores = st.tabs(["Gastos Deducibles (3 UIT Anuales)", "Acumuladores (Modo Mes Único)"])
            
            with tab_gastos:
                st.caption("Ingrese el total gastado en el año. El sistema calculará el % deducible.")
                gcol1, gcol2 = st.columns(2)
                in_gastos_restaurantes = gcol1.number_input("Gastos en Restaurantes y Hoteles (15%)", min_value=0.0, value=6000.0, step=100.0)
                in_gastos_alquiler = gcol1.number_input("Gastos en Arrendamiento (30%)", min_value=0.0, value=0.0, step=100.0)
                in_gastos_medicos = gcol2.number_input("Gastos en Honorarios Médicos/Odont. (30%)", min_value=0.0, value=0.0, step=100.0)
                in_gastos_profesionales = gcol2.number_input("Gastos en Servicios Profesionales (30%)", min_value=0.0, value=0.0, step=100.0)
                in_gastos_essalud_hogar = gcol1.number_input("Gastos en EsSalud Trabajador del Hogar (100%)", min_value=0.0, value=0.0, step=100.0)
            
            with tab_acumuladores:
                st.info("Para un cálculo preciso, ingrese los montos acumulados de Enero hasta el mes *anterior* al que está calculando.")
                # (NUEVO) Deshabilitado si la simulación anual está activa
                in_acum_r5 = st.number_input("Acumulado Bruto Renta 5ta (Sin Grati)", min_value=0.0, value=0.0, step=1000.0, disabled=in_simulacion_anual)
                in_acum_salud = st.number_input("Acumulado Base Afecta a Salud", min_value=0.0, value=0.0, step=1000.0, disabled=in_simulacion_anual)
                in_acum_retenciones = st.number_input("Acumulado Retenciones Renta 5ta Pagadas", min_value=0.0, value=0.0, step=100.0, disabled=in_simulacion_anual)

        # 2. Historial Semestral (NUEVO: st.data_editor)
        with st.expander("Historial Semestral (Para Regularidad de Gratificación y Faltas)"):
            st.warning("Importante: Estos datos se usan para el Principio de Regularidad (3 de 6).")
            st.info("En **Modo Simulación Anual**, esta tabla se aplicará a *ambos* semestres (Ene-Jun y Jul-Dic).")
            
            # Crear DataFrame para el editor
            hist_data = {
                'Mes': ['Mes 1 (Ene/Jul)', 'Mes 2 (Feb/Ago)', 'Mes 3 (Mar/Sep)', 'Mes 4 (Abr/Oct)', 'Mes 5 (May/Nov)', 'Mes 6 (Jun/Dic)'],
                'Horas Extras (S/)': [0.0] * 6,
                'Bon. Nocturna (S/)': [0.0] * 6,
                'Otros Bonos (S/)': [0.0] * 6,
                'Faltas (días)': [0] * 6
            }
            hist_df_in = pd.DataFrame(hist_data)
            
            # Usar st.data_editor para una UI tipo Excel
            in_historial_df = st.data_editor(hist_df_in, num_rows_to_display=6, hide_index=True,
                                             column_config={
                                                 "Mes": st.column_config.TextColumn(disabled=True)
                                             })
        
        # 3. Costo Laboral (NUEVO: Movido dentro del form)
        with st.expander("Aportes del Empleador (Costo Laboral)"):
            in_tasa_sctr = st.number_input("Tasa SCTR (%)", min_value=0.0, value=1.2, step=0.1, help="Ingrese 1.2 para 1.2%")
            in_tasa_senati = st.number_input("Tasa SENATI (%)", min_value=0.0, value=0.0, step=0.75, help="Ingrese 0.75 para 0.75%")
            in_prima_vida = st.number_input("Prima Seguro Vida Ley (Monto S/)", min_value=0.0, value=15.0, step=1.0)

        # --- Botón de Envío ---
        submitted_boleta = st.form_submit_button("Calcular", type="primary")

    # --- Área de Resultados (Boleta) ---
    if submitted_boleta:
        with st.spinner("Calculando..."):
            
            # (NUEVO) Parsear el DataFrame del historial
            historial_semestral_completo = {
                'ing_sobretiempo_total': in_historial_df['Horas Extras (S/)'].tolist(),
                'ing_bonificacion_nocturna': in_historial_df['Bon. Nocturna (S/)'].tolist(),
                'otros_ingresos_afectos': in_historial_df['Otros Bonos (S/)'].tolist(),
                'dias_falta': in_historial_df['Faltas (días)'].tolist()
            }
            
            # --- (NUEVA LÓGICA) SIMULACIÓN ANUAL ---
            if in_simulacion_anual:
                st.header("Resultados de la Simulación Anual")
                
                resultados_boletas = []
                resultados_costos = []
                
                # Inicializar acumuladores
                acum_r5_anual = 0.0
                acum_salud_anual = 0.0
                acum_ret_anual = 0.0
                
                # Inputs que varían por mes
                # (Usamos el editor de historial para variables, y los inputs fijos para pagos únicos)
                hist_he = historial_semestral_completo['ing_sobretiempo_total']
                hist_bn = historial_semestral_completo['ing_bonificacion_nocturna']
                hist_otros = historial_semestral_completo['otros_ingresos_afectos']
                hist_faltas = historial_semestral_completo['dias_falta']
                
                for mes in range(1, 13):
                    # Determinar el índice semestral (0-5)
                    idx_semestral = (mes - 1) % 6
                    
                    # Asignar ingresos variables del historial
                    mes_he = hist_he[idx_semestral]
                    mes_bn = hist_bn[idx_semestral]
                    mes_otros = hist_otros[idx_semestral]
                    mes_faltas = hist_faltas[idx_semestral]
                    
                    # Asignar ingresos únicos (Utilidades en Marzo)
                    mes_utilidades = in_utilidades if mes == 3 else 0.0
                    mes_subsidio = in_subsidio if mes == 5 else 0.0 # Ejemplo en Mayo
                    
                    # Si es el primer mes, usamos las faltas del input principal
                    if mes == 1:
                        mes_faltas = in_dias_falta 
                    
                    # Llamar al motor de cálculo
                    boleta_calculada = generar_boleta_mensual(
                        sueldo_basico_nominal=in_sueldo_basico,
                        tiene_hijos=in_tiene_hijos,
                        sistema_pension=in_sistema_pension,
                        tiene_eps=in_tiene_eps,
                        mes_actual_num=mes,
                        dias_falta=mes_faltas,
                        horas_nocturnas_mes=mes_bn, # Asumimos que el S/ es de horas
                        horas_25=mes_he, # Asumimos que el S/ es de horas
                        horas_35=0.0, # Simplificación
                        horas_100=0.0,
                        otros_ingresos_afectos=mes_otros,
                        ingresos_no_remunerativos=in_movilidad,
                        ingreso_lpa=in_lpa,
                        otros_descuentos_fijos=in_otros_descuentos,
                        ingreso_utilidades=mes_utilidades,
                        ingreso_subsidio=mes_subsidio,
                        ingresos_brutos_acumulados_renta5=acum_r5_anual,
                        ingresos_afectos_salud_acumulados=acum_salud_anual,
                        retenciones_acumuladas_renta5=acum_ret_anual,
                        historial_semestral_ingresos_variables=historial_semestral_completo,
                        gastos_deducibles_arrendamiento=in_gastos_alquiler,
                        gastos_deducibles_honorarios_medicos=in_gastos_medicos,
                        gastos_deducibles_servicios_profesionales=in_gastos_profesionales,
                        gastos_deducibles_essalud_hogar=in_gastos_essalud_hogar,
                        gastos_deducibles_hoteles_rest=in_gastos_restaurantes
                    )
                    
                    costo_empleador = calcular_costo_laboral_mensual(
                        boleta=boleta_calculada,
                        tasa_sctr=in_tasa_sctr / 100.0,
                        tasa_senati=in_tasa_senati / 100.0,
                        prima_vida_ley=in_prima_vida
                    )
                    
                    # Guardar resultados
                    resultados_boletas.append(boleta_calculada)
                    resultados_costos.append(costo_empleador)
                    
                    # Actualizar acumuladores para el próximo mes
                    acum_r5_anual += boleta_calculada['base_renta_quinta_mes']
                    acum_salud_anual += boleta_calculada['base_pension_salud_mes']
                    acum_ret_anual += boleta_calculada['desc_renta_quinta']

                # --- Mostrar Resultados Anuales ---
                
                # Convertir a DataFrame para visualización
                df_boletas = pd.DataFrame(resultados_boletas)
                df_costos = pd.DataFrame(resultados_costos)
                
                # Totales Anuales
                total_neto = df_boletas['neto_a_pagar'].sum()
                total_costo_laboral = df_costos['costo_laboral_total_mes'].sum()
                total_bruto = df_boletas['total_ingresos_brutos_mes'].sum()
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Neto Anual Pagado al Trabajador", f"S/ {total_neto:,.2f}")
                col2.metric("Costo Anual Total para Empleador", f"S/ {total_costo_laboral:,.2f}")
                col3.metric("Bruto Anual Pagado", f"S/ {total_bruto:,.2f}")
                
                # Gráfico
                st.subheader("Evolución Anual (Neto, Bruto y Costo)")
                chart_data = pd.DataFrame({
                    'Mes': range(1, 13),
                    'Neto a Pagar': df_boletas['neto_a_pagar'],
                    'Ingreso Bruto': df_boletas['total_ingresos_brutos_mes'],
                    'Costo Empleador': df_costos['costo_laboral_total_mes']
                }).set_index('Mes')
                st.line_chart(chart_data)
                
                # Tabla de Resumen
                st.subheader("Resumen Anual Mes a Mes")
                df_resumen = chart_data.copy()
                df_resumen['Pensión'] = df_boletas['desc_pension']
                df_resumen['Renta 5ta'] = df_boletas['desc_renta_quinta']
                df_resumen['EsSalud (9%)'] = df_costos['aporte_essalud_9_porc']
                st.dataframe(df_resumen.style.format("S/ {:,.2f}"))

            # --- LÓGICA ANTERIOR (MES ÚNICO) ---
            else:
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
                
                costo_empleador = calcular_costo_laboral_mensual(
                    boleta=boleta_calculada,
                    tasa_sctr=in_tasa_sctr / 100.0,
                    tasa_senati=in_tasa_senati / 100.0,
                    prima_vida_ley=in_prima_vida
                )
                
                # Mostrar resultados de costo
                mostrar_costo_laboral_streamlit(costo_empleador)


# --- PESTAÑA 2: LIQUIDACIÓN (LQBS) ---
with tab_lqbs:
    st.header("Calculadora de Liquidación (LQBS)")
    
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
        in_lqbs_part_time = col1.checkbox("¿Es Part-Time (< 4h/día)?", value=False, help="Si marca esto, CTS y Vacaciones serán 0.")
        in_lqbs_pierde_record = col2.checkbox("¿Perdió Récord Vacacional?", value=False, help="Si marca esto, Vacaciones Truncas será 0.")
        in_lqbs_faltas_sem_trunco = col3.number_input("Faltas en Semestre Trunco", min_value=0, value=5, step=1, help="Días de falta para descuento en Grati Trunca (1/180vo).")

        with st.expander("Historial de Variables (Últimos 6 Meses para Regularidad)"):
            st.write("Ingrese los montos de los 6 meses *anteriores* al cese (para Principio de Regularidad 3 de 6).")
            
            # (NUEVO) st.data_editor para LQBS
            hist_data_lqbs = {
                'Mes': ['Mes -6', 'Mes -5', 'Mes -4', 'Mes -3', 'Mes -2', 'Mes -1'],
                'Horas Extras (S/)': [0.0] * 6,
                'Bon. Nocturna (S/)': [0.0] * 6,
                'Otros Bonos (S/)': [0.0] * 6
            }
            hist_df_in_lqbs = pd.DataFrame(hist_data_lqbs)
            in_historial_df_lqbs = st.data_editor(hist_df_in_lqbs, num_rows_to_display=6, hide_index=True,
                                                  column_config={
                                                      "Mes": st.column_config.TextColumn(disabled=True)
                                                  })

        # --- Botón de Envío ---
        submitted_lqbs = st.form_submit_button("Calcular Liquidación (LQBS)", type="primary")

    # --- Área de Resultados (LQBS) ---
    if submitted_lqbs:
        with st.spinner("Calculando liquidación..."):
            
            # (NUEVO) Parsear el DataFrame del historial de LQBS
            historial_lqbs_completo = {
                'ing_sobretiempo_total': in_historial_df_lqbs['Horas Extras (S/)'].tolist(),
                'ing_bonificacion_nocturna': in_historial_df_lqbs['Bon. Nocturna (S/)'].tolist(),
                'otros_ingresos_afectos': in_historial_df_lqbs['Otros Bonos (S/)'].tolist()
            }
            
            lqbs_calculada = generar_liquidacion(
                rc_basica=in_lqbs_rc_basica,
                historial_ultimos_6_meses_variables=historial_lqbs_completo,
                ultimo_sexto_grati=in_lqbs_sexto_grati,
                fecha_ingreso=in_lqbs_fecha_ingreso,
                fecha_cese=in_lqbs_fecha_cese,
                motivo_cese=in_lqbs_motivo,
                es_part_time_lt_4h=in_lqbs_part_time,
                ha_perdido_record_vacacional=in_lqbs_pierde_record,
                dias_falta_en_semestre_trunco=in_lqbs_faltas_sem_trunco
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
                                                  ['ONP', 'INTEGRA', 'PRIMA', 'HABITAT', 'PROFUTURO'], 
                                                  key="ria_pension", index=3)
            in_ria_tiene_eps = st.checkbox("¿Tiene EPS?", value=False, key="ria_eps")
        
        with col2:
            st.subheader("Datos del Mes")
            in_ria_mes_actual = st.slider("Mes de Cálculo", 1, 12, 1, key="ria_mes")
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
            in_indv_part_time = st.checkbox("¿Es Part-Time (< 4h/día)?", value=False, help="Si marca esto, el pago será 0.")
            in_indv_pierde_record = st.checkbox("¿Perdió Récord Vacacional por Faltas?", value=False, help="Si marca esto, el pago será 0.")

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
