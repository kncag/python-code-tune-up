# -*- coding: utf-8 -*-
"""
Calculadora de Planilla y Beneficios Sociales Perú 2025 (App Streamlit)

Archivo único que combina la lógica de cálculo (Motor) y la 
interfaz de usuario (Streamlit).
"""

# --- 0. IMPORTACIONES NECESARIAS ---
import streamlit as st
import pandas as pd
import math
from typing import Dict, Any, Tuple, List
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass, field

# ==============================================================================
# === PARTE 1: MOTOR DE CÁLCULO (LÓGICA) ===
# ==============================================================================

# --- 1. CONSTANTES GLOBALES (Valores oficiales 2025) ---
UIT_2025 = 5350 # D.S. N° 260-2024-EF
RMV_2025 = 1130 # D.S. N° 006-2024-TR
PORC_ASIG_FAMILIAR = 0.10 # Ley N° 25129
PORC_ESSALUD = 0.09 # Ley N° 26790
PORC_ONP = 0.13 # D.L. N° 19990

SISTEMAS_PENSION = ['ONP', 'INTEGRA', 'PRIMA', 'HABITAT', 'PROFUTURO']

# Art. 53, D.S. N° 179-2004-EF (TUO Ley Impuesto a la Renta)
TRAMOS_IR = [
    (5 * UIT_2025, 0.08),  # Hasta 26,750
    (20 * UIT_2025, 0.14), # Hasta 107,000
    (35 * UIT_2025, 0.17), # Hasta 187,250
    (45 * UIT_2025, 0.20), # Hasta 240,750
    (float('inf'), 0.30)   # Más de 240,750
]

BONI_LEY_ESSALUD = 0.09 # Ley N° 30334
BONI_LEY_EPS = 0.0675
CREDITO_POR_EPS = 0.09 * 0.25 # 2.25% (Art. 33, Ley N° 26790)

TASA_SOBRETIEMPO_25 = 0.25 # Art. 9, D.S. N° 007-2002-TR
TASA_SOBRETIEMPO_35 = 0.35
TASA_SOBRETIEMPO_100 = 1.0

TASA_BONIFICACION_NOCTURNA = 0.35 # Art. 8, D.S. N° 007-2002-TR

TASA_APORTE_AFP = 0.10
TASA_PRIMA_SEGURO_AFP = 0.0174 # Tasa promedio, varía por AFP
TOPE_MAXIMO_ASEGURABLE_AFP_2025 = 12234.34 # Se actualiza trimestralmente por SBS

LIMITE_3_UIT = 3 * UIT_2025 # 16,050 (Art. 46, LIR)

LIMITE_MINIMO_RIA_UIT = 2.0 # Art. 8, D.S. N° 003-97-TR
LIMITE_MINIMO_RIA_MENSUAL = LIMITE_MINIMO_RIA_UIT * UIT_2025 # 10,700


# ==============================================================================
# --- 2. CLASES DE DATOS (DATACLASSES) ---
# ==============================================================================
# Agrupamos los parámetros de entrada en Dataclasses para un código más limpio.

@dataclass
class EntradasEmpleado:
    """Datos fijos del empleado."""
    sueldo_basico_nominal: float
    tiene_hijos: bool = False
    sistema_pension: str = 'ONP'
    tiene_eps: bool = False

@dataclass
class EntradasMes:
    """Datos variables que cambian cada mes."""
    mes_actual_num: int
    dias_falta: int = 0
    horas_nocturnas_mes: float = 0.0
    horas_25: float = 0.0
    horas_35: float = 0.0
    horas_100: float = 0.0
    otros_ingresos_afectos: float = 0.0
    ingresos_no_remunerativos: float = 0.0
    ingreso_lpa: float = 0.0
    ingreso_utilidades: float = 0.0
    ingreso_subsidio: float = 0.0
    otros_descuentos_fijos: float = 0.0

@dataclass
class EntradasAcumuladas:
    """Acumuladores anuales para Renta 5ta."""
    ingresos_brutos_acumulados_renta5: float = 0.0
    ingresos_afectos_salud_acumulados: float = 0.0
    retenciones_acumuladas_renta5: float = 0.0

@dataclass
class EntradasGastosDeducibles:
    """Gastos anuales deducibles de Renta 5ta (3 UIT)."""
    arrendamiento: float = 0.0
    honorarios_medicos: float = 0.0
    servicios_profesionales: float = 0.0
    essalud_hogar: float = 0.0
    hoteles_rest: float = 0.0

@dataclass
class EntradasHistorialSemestral:
    """Historial de 6 meses para cálculo de regularidad (Grati/LQBS)."""
    ing_sobretiempo_total: List[float] = field(default_factory=lambda: [0.0]*6)
    ing_bonificacion_nocturna: List[float] = field(default_factory=lambda: [0.0]*6)
    otros_ingresos_afectos: List[float] = field(default_factory=lambda: [0.0]*6)
    dias_falta: List[int] = field(default_factory=lambda: [0]*6)

@dataclass
class EntradasLiquidacion:
    """Datos principales para una LQBS."""
    fecha_ingreso: datetime.date
    fecha_cese: datetime.date
    motivo_cese: str
    rc_basica: float
    ultimo_sexto_grati: float
    
@dataclass
class OpcionesLiquidacion:
    """Flags y opciones especiales para una LQBS."""
    es_part_time_lt_4h: bool = False
    ha_perdido_record_vacacional: bool = False
    dias_falta_en_semestre_trunco: int = 0

@dataclass
class EntradasRIA:
    """Datos para el régimen de Remuneración Integral Anual."""
    remuneracion_integral_anual: float
    sistema_pension: str = 'ONP'
    tiene_eps: bool = False
    mes_actual_num: int = 1
    retenciones_acumuladas_renta5: float = 0.0

# ==============================================================================
# --- 3. FUNCIONES DE CÁLCULO DE INGRESOS ---
# ==============================================================================

def calcular_valor_hora(sueldo_basico: float) -> float:
    """Calcula el valor de una hora ordinaria (Base: 240h/mes)."""
    if sueldo_basico <= 0:
        return 0
    return (sueldo_basico / 30) / 8

def calcular_sobretiempo(valor_hora: float, horas_25: float, horas_35: float, horas_100: float = 0.0) -> Tuple[float, float, float, float]:
    """Calcula el monto total de horas extras (sobretiempo)."""
    monto_25 = horas_25 * valor_hora * (1 + TASA_SOBRETIEMPO_25)
    monto_35 = horas_35 * valor_hora * (1 + TASA_SOBRETIEMPO_35)
    monto_100 = horas_100 * valor_hora * (1 + TASA_SOBRETIEMPO_100) 
    return (monto_25 + monto_35 + monto_100), monto_25, monto_35, monto_100

def calcular_asignacion_familiar(tiene_hijos: bool) -> float:
    """Calcula la asignación familiar (10% de la RMV)."""
    return RMV_2025 * PORC_ASIG_FAMILIAR if tiene_hijos else 0

def calcular_bonificacion_nocturna(valor_hora: float, horas_nocturnas_mes: float) -> float:
    """Calcula la bonificación nocturna (35% sobretasa)."""
    if horas_nocturnas_mes <= 0 or valor_hora <= 0:
        return 0
    sobretasa_nocturna_por_hora = valor_hora * TASA_BONIFICACION_NOCTURNA
    return sobretasa_nocturna_por_hora * horas_nocturnas_mes

# ==============================================================================
# --- 4. FUNCIONES DE CÁLCULO DE DESCUENTOS ---
# ==============================================================================

def calcular_descuento_pension(sueldo_bruto_afecto: float, sistema_pension: str) -> float:
    """Calcula el descuento de AFP (con TMA) u ONP."""
    sistema_pension = sistema_pension.upper()
    if sistema_pension == 'ONP':
        return sueldo_bruto_afecto * PORC_ONP
    elif sistema_pension in SISTEMAS_PENSION:
        aporte_obligatorio = sueldo_bruto_afecto * TASA_APORTE_AFP
        base_prima_seguro = min(sueldo_bruto_afecto, TOPE_MAXIMO_ASEGURABLE_AFP_2025)
        prima_seguro = base_prima_seguro * TASA_PRIMA_SEGURO_AFP
        return aporte_obligatorio + prima_seguro
    else:
        return 0

def _calcular_impuesto_anual_por_tramos(
    renta_neta_imponible_anual: float, 
    proyeccion_base_salud_anual: float, 
    tiene_eps: bool = False
) -> float:
    """Función interna: Calcula el impuesto anual por tramos y aplica crédito EPS."""
    impuesto_anual = 0
    renta_acumulada_para_tramos = 0
    for limite, tasa in TRAMOS_IR:
        monto_en_tramo = min(renta_neta_imponible_anual - renta_acumulada_para_tramos, limite - renta_acumulada_para_tramos)
        if monto_en_tramo <= 0:
            break
        impuesto_anual += monto_en_tramo * tasa
        renta_acumulada_para_tramos += monto_en_tramo
    if tiene_eps:
        credito_eps = proyeccion_base_salud_anual * CREDITO_POR_EPS
        impuesto_anual = max(0, impuesto_anual - credito_eps)
    return impuesto_anual

def calcular_retencion_renta_quinta(
    ingresos_proyectados_anuales: float,
    proyeccion_base_salud_anual: float,
    gastos: EntradasGastosDeducibles,
    tiene_eps: bool = False, 
    mes_actual_num: int = 1, 
    retenciones_acumuladas: float = 0.0
) -> float:
    """Calcula la retención de 5ta categoría para el mes actual."""
    
    renta_bruta = ingresos_proyectados_anuales
    deduccion_7_uit = 7 * UIT_2025
    
    # Deducción de 3 UIT adicionales (Art. 46, TUO LIR)
    deduccion_arrendamiento = gastos.arrendamiento * 0.30
    deduccion_honorarios_medicos = gastos.honorarios_medicos * 0.30
    deduccion_servicios_profesionales = gastos.servicios_profesionales * 0.30
    deduccion_essalud_hogar = gastos.essalud_hogar * 1.00
    deduccion_hoteles_rest = gastos.hoteles_rest * 0.15
    
    total_deduccion_adicional_calculada = (
        deduccion_arrendamiento + deduccion_honorarios_medicos + 
        deduccion_servicios_profesionales + deduccion_essalud_hogar + 
        deduccion_hoteles_rest
    )
    total_deduccion_adicional_aplicable = min(total_deduccion_adicional_calculada, LIMITE_3_UIT)

    renta_neta_imponible_anual = max(0, renta_bruta - deduccion_7_uit - total_deduccion_adicional_aplicable)
    
    impuesto_anual_proyectado = _calcular_impuesto_anual_por_tramos(
        renta_neta_imponible_anual, 
        proyeccion_base_salud_anual, 
        tiene_eps
    )
    
    # Lógica de Recálculo (Periodos Fijos SUNAT - Art. 40, D.S. N° 003-2007-EF)
    impuesto_restante_por_pagar = impuesto_anual_proyectado - retenciones_acumuladas
    
    if mes_actual_num <= 3:
        retencion_mensual = impuesto_anual_proyectado / 12
    elif mes_actual_num == 4:
        retencion_mensual = impuesto_restante_por_pagar / 9
    elif 5 <= mes_actual_num <= 7:
        retencion_mensual = impuesto_restante_por_pagar / 8
    elif 8 <= mes_actual_num <= 11:
        retencion_mensual = impuesto_restante_por_pagar / 5
    else: # Diciembre
        retencion_mensual = impuesto_restante_por_pagar / 1
    
    return max(0, retencion_mensual)

# ==============================================================================
# --- 5. FUNCIONES DE BENEFICIOS SOCIALES ---
# ==============================================================================

def _calcular_promedio_regularidad(historial: EntradasHistorialSemestral) -> float:
    """Aplica el Principio de Regularidad (3 de 6 meses) para Grati/CTS."""
    promedio_total = 0.0
    historial_dict = {
        'ing_sobretiempo_total': historial.ing_sobretiempo_total,
        'ing_bonificacion_nocturna': historial.ing_bonificacion_nocturna,
        'otros_ingresos_afectos': historial.otros_ingresos_afectos
    }
    for clave, valores in historial_dict.items():
        if not valores:
            continue
        meses_con_percepcion = sum(1 for v in valores if v > 0)
        if meses_con_percepcion >= 3:
            promedio_del_concepto = sum(valores) / 6
            promedio_total += promedio_del_concepto
    return promedio_total

def calcular_gratificacion(
    sueldo_computable: float, 
    meses_completos: int, 
    tiene_eps: bool = False,
    dias_falta_semestre: int = 0
) -> Tuple[float, float]:
    """Calcula una gratificación semestral con descuento por faltas (1/180vo)."""
    if meses_completos <= 0:
        return 0, 0
    grati_bruta = (sueldo_computable / 6) * meses_completos
    descuento_por_faltas = (sueldo_computable / 180) * dias_falta_semestre
    grati_neta_a_pagar = max(0, grati_bruta - descuento_por_faltas)
    tasa_bonificacion = BONI_LEY_EPS if tiene_eps else BONI_LEY_ESSALUD
    bonificacion = grati_neta_a_pagar * tasa_bonificacion
    return grati_neta_a_pagar, bonificacion

def calcular_cts_semestral(remuneracion_computable_cts: float, meses_completos: int) -> float:
    """Calcula el depósito de CTS semestral (Base Legal: D.S. N° 001-97-TR)."""
    if meses_completos <= 0:
        return 0
    return (remuneracion_computable_cts / 12) * meses_completos

# ==============================================================================
# --- 6. FUNCIONES PRINCIPALES Y DE ORQUESTACIÓN ---
# ==============================================================================

def _calcular_proyecciones_renta_quinta(
    empleado: EntradasEmpleado,
    mes: EntradasMes,
    acumulados: EntradasAcumuladas,
    base_renta_quinta_mes: float,
    base_pension_salud_mes: float
) -> Tuple[float, float]:
    """Función interna para modularizar la lógica de proyección anual."""
    
    valor_hora_nominal = calcular_valor_hora(empleado.sueldo_basico_nominal)
    bn_proyectado_fijo = 0
    dias_laborados_mes = 30 - mes.dias_falta
    if dias_laborados_mes > 0 and mes.horas_nocturnas_mes > 0:
        horas_nocturnas_proyectadas_mes = (mes.horas_nocturnas_mes / dias_laborados_mes) * 30
        bn_proyectado_fijo = calcular_bonificacion_nocturna(valor_hora_nominal, horas_nocturnas_proyectadas_mes)
        
    base_proy_nominal_rem_R5 = (
        empleado.sueldo_basico_nominal + 
        calcular_asignacion_familiar(empleado.tiene_hijos) + 
        mes.otros_ingresos_afectos + # Se asume que este bono se repite
        bn_proyectado_fijo 
    )
    base_proy_nominal_no_rem_R5 = mes.ingresos_no_remunerativos + mes.ingreso_lpa
    base_proyeccion_mes_normal_R5 = base_proy_nominal_rem_R5 + base_proy_nominal_no_rem_R5
    
    ingresos_reales_acumulados_R5 = acumulados.ingresos_brutos_acumulados_renta5 + base_renta_quinta_mes
    meses_futuros = 12 - mes.mes_actual_num
    ingresos_futuros_proyectados_R5 = base_proyeccion_mes_normal_R5 * meses_futuros
    ingresos_proyectados_anuales_r5 = ingresos_reales_acumulados_R5 + ingresos_futuros_proyectados_R5
    
    base_salud_real_acumulada = acumulados.ingresos_afectos_salud_acumulados + base_pension_salud_mes
    base_fija_salud_futura = base_proy_nominal_rem_R5 
    proyeccion_base_salud_futura = base_fija_salud_futura * meses_futuros
    proyeccion_base_salud_anual = base_salud_real_acumulada + proyeccion_base_salud_futura

    return ingresos_proyectados_anuales_r5, proyeccion_base_salud_anual

def generar_boleta_mensual(
    empleado: EntradasEmpleado,
    mes: EntradasMes,
    acumulados: EntradasAcumuladas,
    gastos: EntradasGastosDeducibles,
    historial: EntradasHistorialSemestral
) -> Dict[str, Any]:
    """Genera un cálculo detallado de una boleta de pago mensual."""
    
    boleta: Dict[str, Any] = {} 

    # --- 1. CÁLCULO DE INGRESOS MENSUALES ---
    valor_dia = empleado.sueldo_basico_nominal / 30
    desc_faltas = valor_dia * mes.dias_falta
    ing_basico_ajustado = empleado.sueldo_basico_nominal - desc_faltas
    valor_hora_calculado = calcular_valor_hora(ing_basico_ajustado)
    
    boleta['sueldo_basico_nominal'] = empleado.sueldo_basico_nominal
    boleta['dias_falta'] = mes.dias_falta
    boleta['desc_faltas'] = desc_faltas
    boleta['ing_basico_ajustado'] = ing_basico_ajustado
    boleta['valor_hora_calculado'] = valor_hora_calculado
    
    ing_asig_familiar = calcular_asignacion_familiar(empleado.tiene_hijos)
    ing_bonificacion_nocturna = calcular_bonificacion_nocturna(valor_hora_calculado, mes.horas_nocturnas_mes)
    ing_sobretiempo_total, m25, m35, m100 = calcular_sobretiempo(valor_hora_calculado, mes.horas_25, mes.horas_35, mes.horas_100)
    
    boleta['ing_asig_familiar'] = ing_asig_familiar
    boleta['ing_bonificacion_nocturna'] = ing_bonificacion_nocturna
    boleta['ing_sobretiempo_total'] = ing_sobretiempo_total
    boleta['ing_sobretiempo_25'] = m25
    boleta['ing_sobretiempo_35'] = m35
    boleta['ing_sobretiempo_100'] = m100
    boleta['otros_ingresos_afectos'] = mes.otros_ingresos_afectos
    
    boleta['ingresos_no_remunerativos'] = mes.ingresos_no_remunerativos
    boleta['ingreso_lpa'] = mes.ingreso_lpa
    boleta['ingreso_utilidades'] = mes.ingreso_utilidades
    boleta['ingreso_subsidio'] = mes.ingreso_subsidio
    
    # Gratificación (si corresponde)
    ing_gratificacion = 0.0
    ing_boni_ley = 0.0
    es_mes_grati = (mes.mes_actual_num == 7 or mes.mes_actual_num == 12)
    dias_faltas_totales_semestre = 0
    
    if es_mes_grati:
        promedio_variables_regulares = _calcular_promedio_regularidad(historial)
        rem_computable_grati = (ing_basico_ajustado + ing_asig_familiar + promedio_variables_regulares)
        boleta['rem_computable_grati'] = rem_computable_grati
        dias_faltas_totales_semestre = sum(historial.dias_falta)
        ing_gratificacion, ing_boni_ley = calcular_gratificacion(
            rem_computable_grati, 6, empleado.tiene_eps,
            dias_falta_semestre=dias_faltas_totales_semestre
        )
    else:
         boleta['rem_computable_grati'] = 0.0

    boleta['ing_gratificacion'] = ing_gratificacion
    boleta['ing_boni_ley'] = ing_boni_ley
    boleta['dias_falta_semestre_grati'] = dias_faltas_totales_semestre
    
    # --- 2. CÁLCULO DE BASES AFECTAS (Este Mes) ---
    base_pension_salud_mes = (
        ing_basico_ajustado + ing_asig_familiar + ing_bonificacion_nocturna + 
        ing_sobretiempo_total + mes.otros_ingresos_afectos
    )
    base_renta_quinta_mes = (
        base_pension_salud_mes + mes.ingresos_no_remunerativos + mes.ingreso_lpa + 
        mes.ingreso_utilidades + mes.ingreso_subsidio
    )
    total_ingresos_boleta = (
        base_renta_quinta_mes + ing_gratificacion + ing_boni_ley
    )

    boleta['total_ingresos_brutos_mes'] = total_ingresos_boleta
    boleta['base_pension_salud_mes'] = base_pension_salud_mes
    boleta['base_renta_quinta_mes'] = base_renta_quinta_mes

    # --- 3. PROYECCIÓN ANUAL (RENTA 5TA) ---
    proyeccion_anual_r5, proyeccion_base_salud_anual = _calcular_proyecciones_renta_quinta(
        empleado, mes, acumulados,
        base_renta_quinta_mes=base_renta_quinta_mes,
        base_pension_salud_mes=base_pension_salud_mes
    )
    boleta['proyeccion_anual_r5'] = proyeccion_anual_r5
    boleta['proyeccion_base_salud_anual'] = proyeccion_base_salud_anual
    
    # --- 4. CÁLCULO DE DESCUENTOS ---
    desc_pension = calcular_descuento_pension(base_pension_salud_mes, empleado.sistema_pension)
    boleta['desc_pension'] = desc_pension
    
    desc_lpa = mes.ingreso_lpa # Descuento neto cero
    boleta['desc_lpa'] = desc_lpa
    
    desc_renta_quinta = calcular_retencion_renta_quinta(
        ingresos_proyectados_anuales=proyeccion_anual_r5,
        proyeccion_base_salud_anual=proyeccion_base_salud_anual,
        gastos=gastos,
        tiene_eps=empleado.tiene_eps,
        mes_actual_num=mes.mes_actual_num,
        retenciones_acumuladas=acumulados.retenciones_acumuladas_renta5
    )
    boleta['desc_renta_quinta'] = desc_renta_quinta
    boleta['otros_descuentos_fijos'] = mes.otros_descuentos_fijos
    
    # --- 5. TOTALES ---
    total_descuentos = (
        desc_pension + desc_renta_quinta + desc_lpa + mes.otros_descuentos_fijos 
    )
    neto_a_pagar = total_ingresos_boleta - total_descuentos
    
    boleta['total_descuentos'] = total_descuentos
    boleta['neto_a_pagar'] = neto_a_pagar
    boleta['sistema_pension'] = empleado.sistema_pension
    boleta['tiene_eps'] = empleado.tiene_eps

    # --- 6. RATIOS ---
    boleta['ratio_neto_vs_bruto'] = (neto_a_pagar / total_ingresos_boleta) if total_ingresos_boleta > 0 else 0.0
    boleta['ratio_neto_vs_sueldo_nominal'] = (neto_a_pagar / empleado.sueldo_basico_nominal) if empleado.sueldo_basico_nominal > 0 else 0.0

    return boleta

# ==============================================================================
# --- 7. FUNCIONES DE LIQUIDACIÓN DE BENEFICIOS SOCIALES (LQBS) ---
# ==============================================================================

def _calcular_tiempo_servicio(fecha_inicio: datetime.date, fecha_fin: datetime.date) -> relativedelta:
    """Helper: Calcula el tiempo total de servicio usando relativedelta."""
    try:
        inicio = fecha_inicio
        fin = fecha_fin + relativedelta(days=1) # El cese es inclusivo
        return relativedelta(fin, inicio)
    except Exception as e:
        print(f"Error al calcular tiempo de servicio: {e}.")
        return relativedelta()

def _calcular_truncos_cts(rc_cts: float, fecha_ingreso: datetime.date, fecha_cese: datetime.date) -> Tuple[float, int, int]:
    """Calcula la CTS Trunca (desde el último depósito 1-May o 1-Nov)."""
    if 5 <= fecha_cese.month <= 10:
        inicio_periodo_cts = datetime(fecha_cese.year, 5, 1).date()
    else:
        inicio_periodo_cts = datetime(fecha_cese.year, 11, 1).date()
        if fecha_cese.month < 5:
            inicio_periodo_cts = datetime(fecha_cese.year - 1, 11, 1).date()
    if inicio_periodo_cts < fecha_ingreso:
        inicio_periodo_cts = fecha_ingreso
    delta = _calcular_tiempo_servicio(inicio_periodo_cts, fecha_cese)
    meses_truncos = delta.months + (delta.years * 12)
    dias_truncos = delta.days
    cts_trunca = (rc_cts / 12 * meses_truncos) + (rc_cts / 12 / 30 * dias_truncos)
    return cts_trunca, meses_truncos, dias_truncos

def _calcular_truncos_grati(
    rc_grati: float, 
    fecha_cese: datetime.date,
    dias_falta_en_semestre_trunco: int = 0
) -> Tuple[float, int, float]:
    """Calcula la Gratificación Trunca (desde el inicio del semestre 1-Ene o 1-Jul)."""
    if 1 <= fecha_cese.month <= 6:
        inicio_semestre = datetime(fecha_cese.year, 1, 1).date()
    else:
        inicio_semestre = datetime(fecha_cese.year, 7, 1).date()
    delta = _calcular_tiempo_servicio(inicio_semestre, fecha_cese)
    meses_completos = delta.months + (delta.years * 12)
    grati_trunca_bruta = (rc_grati / 6) * meses_completos
    descuento_por_faltas = (rc_grati / 180) * dias_falta_en_semestre_trunco
    grati_trunca_neta = max(0, grati_trunca_bruta - descuento_por_faltas)
    return grati_trunca_neta, meses_completos, descuento_por_faltas

def _calcular_truncos_vacaciones(
    rc_vacas: float, 
    fecha_ingreso: datetime.date, 
    fecha_cese: datetime.date,
    ha_perdido_record_vacacional: bool = False
) -> Tuple[float, int, int]:
    """Calcula las Vacaciones Truncas (desde el último aniversario)."""
    if ha_perdido_record_vacacional:
        return 0.0, 0, 0
    ultimo_aniversario = datetime(fecha_cese.year, fecha_ingreso.month, fecha_ingreso.day).date()
    if fecha_cese < ultimo_aniversario:
        ultimo_aniversario = datetime(fecha_cese.year - 1, fecha_ingreso.month, fecha_ingreso.day).date()
    delta = _calcular_tiempo_servicio(ultimo_aniversario, fecha_cese)
    meses_truncos = delta.months + (delta.years * 12)
    dias_truncos = delta.days
    vacas_truncas = (rc_vacas / 12 * meses_truncos) + (rc_vacas / 12 / 30 * dias_truncos)
    return vacas_truncas, meses_truncos, dias_truncos

def _calcular_indemnizacion_despido(
    rc_indemnizacion: float, 
    fecha_ingreso: datetime.date, 
    fecha_cese: datetime.date
) -> Tuple[float, int, int, int]:
    """Calcula la indemnización por despido arbitrario (Tope 12 sueldos)."""
    delta = relativedelta(fecha_cese + relativedelta(days=1), fecha_ingreso)
    anios_completos = delta.years
    meses_completos = delta.months
    dias = delta.days

    remuneracion_por_anio_y_medio = rc_indemnizacion * 1.5
    
    indemnizacion_anios = remuneracion_por_anio_y_medio * anios_completos
    indemnizacion_meses = (remuneracion_por_anio_y_medio / 12) * meses_completos
    indemnizacion_dias = (remuneracion_por_anio_y_medio / 12 / 30) * dias
    
    total_indemnizacion_calculada = indemnizacion_anios + indemnizacion_meses + indemnizacion_dias
    
    tope_legal = rc_indemnizacion * 12
    total_indemnizacion_final = min(total_indemnizacion_calculada, tope_legal)
    
    return total_indemnizacion_final, anios_completos, meses_completos, dias

def generar_liquidacion(
    datos: EntradasLiquidacion,
    opciones: OpcionesLiquidacion,
    historial: EntradasHistorialSemestral
) -> Dict[str, Any]:
    """Genera el cálculo completo de una Liquidación de Beneficios Sociales (LQBS)."""
    
    lqbs = {
        'fecha_ingreso': datos.fecha_ingreso,
        'fecha_cese': datos.fecha_cese,
        'motivo_cese': datos.motivo_cese,
        'es_part_time_lt_4h': opciones.es_part_time_lt_4h,
        'ha_perdido_record_vacacional': opciones.ha_perdido_record_vacacional,
        'dias_falta_en_semestre_trunco': opciones.dias_falta_en_semestre_trunco
    }

    # 1. Definir Remuneraciones Computables (RC)
    promedio_regularidad_lqbs = _calcular_promedio_regularidad(historial)
    lqbs['promedio_variables_regulares'] = promedio_regularidad_lqbs
    
    rc_grati_vacas = datos.rc_basica + promedio_regularidad_lqbs
    lqbs['rc_grati_vacas'] = rc_grati_vacas
    
    rc_cts = rc_grati_vacas + datos.ultimo_sexto_grati
    lqbs['rc_cts'] = rc_cts
    
    # 2. Calcular Beneficios Truncos
    lqbs['cts_trunca'], lqbs['cts_meses'], lqbs['cts_dias'] = _calcular_truncos_cts(rc_cts, datos.fecha_ingreso, datos.fecha_cese)
    
    lqbs['grati_trunca'], lqbs['grati_meses'], lqbs['grati_desc_faltas'] = _calcular_truncos_grati(
        rc_grati_vacas, datos.fecha_cese, opciones.dias_falta_en_semestre_trunco
    )
    lqbs['vacas_truncas'], lqbs['vacas_meses'], lqbs['vacas_dias'] = _calcular_truncos_vacaciones(
        rc_grati_vacas, datos.fecha_ingreso, datos.fecha_cese,
        opciones.ha_perdido_record_vacacional
    )
    
    # Aplicar validación de régimen Part-Time
    if opciones.es_part_time_lt_4h:
        lqbs['cts_trunca'] = 0.0
        lqbs['vacas_truncas'] = 0.0
        lqbs['info_part_time'] = "No se pagan CTS ni Vacaciones (Régimen Part-Time < 4h)."
    else:
        lqbs['info_part_time'] = None

    total_beneficios_truncos = lqbs['cts_trunca'] + lqbs['grati_trunca'] + lqbs['vacas_truncas']
    lqbs['total_beneficios_truncos'] = total_beneficios_truncos
    
    # 3. Calcular Indemnización (si aplica)
    indemnizacion = 0.0
    if datos.motivo_cese.upper() == 'DESPIDO_ARBITRARIO':
        indemnizacion, anios, meses, dias = _calcular_indemnizacion_despido(
            rc_grati_vacas, datos.fecha_ingreso, datos.fecha_cese
        )
        lqbs['indemnizacion_anios'] = anios
        lqbs['indemnizacion_meses'] = meses
        lqbs['indemnizacion_dias'] = dias
    lqbs['indemnizacion_despido'] = indemnizacion
    
    # 4. Total a Pagar
    lqbs['total_liquidacion'] = total_beneficios_truncos + indemnizacion
    return lqbs

# ==============================================================================
# --- 8. FUNCIONES DE COSTO LABORAL (EMPLEADOR) ---
# ==============================================================================
def calcular_costo_laboral_mensual(
    boleta: Dict[str, Any],
    tasa_sctr: float = 0.0,
    tasa_senati: float = 0.0,
    prima_vida_ley: float = 0.0
) -> Dict[str, Any]:
    """Calcula los aportes mensuales del empleador (Costo Laboral)."""
    
    costos = {}
    base_afecta_salud = boleta['base_pension_salud_mes']
    
    aporte_essalud = base_afecta_salud * PORC_ESSALUD
    costos['aporte_essalud_9_porc'] = aporte_essalud
    
    aporte_sctr = base_afecta_salud * tasa_sctr
    costos['aporte_sctr'] = aporte_sctr
    
    aporte_senati = base_afecta_salud * tasa_senati
    costos['aporte_senati'] = aporte_senati
    
    aporte_vida_ley = prima_vida_ley
    costos['aporte_vida_ley'] = aporte_vida_ley
    
    total_aportes_empleador = (
        aporte_essalud + aporte_sctr + aporte_senati + aporte_vida_ley
    )
    costos['total_aportes_empleador'] = total_aportes_empleador
    
    costo_laboral_total_mes = boleta['total_ingresos_brutos_mes'] + total_aportes_empleador
    costos['costo_laboral_total_mes'] = costo_laboral_total_mes
    
    base_nominal = boleta.get('sueldo_basico_nominal', 0.0)
    base_bruta = boleta.get('total_ingresos_brutos_mes', 0.0)
    
    costos['ratio_costo_vs_sueldo_nominal'] = (costo_laboral_total_mes / base_nominal) if base_nominal > 0 else 0.0
    costos['ratio_costo_vs_bruto'] = (costo_laboral_total_mes / base_bruta) if base_bruta > 0 else 0.0
    
    return costos

# ==============================================================================
# --- 9. FUNCIONES DE REMUNERACIÓN INTEGRAL ANUAL (RIA) ---
# ==============================================================================

def generar_boleta_ria(
    datos: EntradasRIA,
    gastos: EntradasGastosDeducibles
) -> Dict[str, Any]:
    """Genera un cálculo de boleta para el régimen RIA."""
    
    boleta_ria = {}
    pago_mensual_integral = datos.remuneracion_integral_anual / 12
    
    if pago_mensual_integral < LIMITE_MINIMO_RIA_MENSUAL:
        boleta_ria['error'] = f"Error: El pago mensual (S/ {pago_mensual_integral:.2f}) no supera las 2 UIT (S/ {LIMITE_MINIMO_RIA_MENSUAL:.2f}). No califica para RIA."
        return boleta_ria

    boleta_ria['ingreso_integral_mensual'] = pago_mensual_integral
    
    base_pension_salud_mes = pago_mensual_integral
    base_renta_quinta_mes = pago_mensual_integral
    boleta_ria['base_pension_salud_mes'] = base_pension_salud_mes
    boleta_ria['base_renta_quinta_mes'] = base_renta_quinta_mes
    
    desc_pension = calcular_descuento_pension(base_pension_salud_mes, datos.sistema_pension)
    
    desc_renta_quinta = calcular_retencion_renta_quinta(
        ingresos_proyectados_anuales=datos.remuneracion_integral_anual,
        proyeccion_base_salud_anual=datos.remuneracion_integral_anual,
        gastos=gastos,
        tiene_eps=datos.tiene_eps,
        mes_actual_num=datos.mes_actual_num,
        retenciones_acumuladas=datos.retenciones_acumuladas_renta5
    )
    
    boleta_ria['desc_pension'] = desc_pension
    boleta_ria['desc_renta_quinta'] = desc_renta_quinta
    boleta_ria['sistema_pension'] = datos.sistema_pension
    
    total_descuentos = desc_pension + desc_renta_quinta
    neto_a_pagar = pago_mensual_integral - total_descuentos
    
    boleta_ria['total_descuentos'] = total_descuentos
    boleta_ria['neto_a_pagar'] = neto_a_pagar
    
    return boleta_ria

# ==============================================================================
# --- 10. FUNCIONES DE CASOS ESPECIALES (INDEMNIZACIONES) ---
# ==============================================================================

def calcular_indemnizacion_vacaciones_no_gozadas(
    rc_vacacional: float,
    periodos_vencidos: int = 1,
    es_part_time_lt_4h: bool = False,
    ha_perdido_record_vacacional: bool = False
) -> Dict[str, Any]:
    """Calcula la indemnización por vacaciones no gozadas (la "triple" vacación)."""
    
    info_adicional = None
    if es_part_time_lt_4h:
        info_adicional = "No aplica indemnización vacacional (Régimen Part-Time < 4h)."
    if ha_perdido_record_vacacional:
        info_adicional = "No aplica indemnización vacacional (Récord no cumplido por faltas)."

    if info_adicional:
        return {
            "rc_vacacional": rc_vacacional, "periodos_vencidos": periodos_vencidos,
            "pago_por_vacacion_no_gozada": 0.0, "pago_por_indemnizacion": 0.0,
            "total_a_pagar": 0.0, "info_adicional": info_adicional
        }

    pago_por_vacacion_no_gozada = rc_vacacional * periodos_vencidos
    pago_por_indemnizacion = rc_vacacional * periodos_vencidos
    total_indemnizacion_vacas = pago_por_vacacion_no_gozada + pago_por_indemnizacion
    
    return {
        "rc_vacacional": rc_vacacional, "periodos_vencidos": periodos_vencidos,
        "pago_por_vacacion_no_gozada": pago_por_vacacion_no_gozada,
        "pago_por_indemnizacion": pago_por_indemnizacion,
        "total_a_pagar": total_indemnizacion_vacas, "info_adicional": None
    }

# ==============================================================================
# ==============================================================================
# === PARTE 2: INTERFAZ DE USUARIO (STREAMLIT) ===
# ==============================================================================
# ==============================================================================


# ==============================================================================
# --- SECCIÓN DE HELPERS DE UI (FUNCIONES 'MOSTRAR_...') ---
# ==============================================================================

MESES_LISTA = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
               'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

def _renderizar_gastos_deducibles(key_prefix: str) -> EntradasGastosDeducibles:
    """Helper reutilizable para mostrar el expander de Gastos Deducibles en columnas."""
    with st.expander("Gastos Deducibles (3 UIT Anuales) - Art. 46, LIR"):
        st.caption("Ingrese el total gastado en el año. El sistema calculará el % deducible.")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            in_gastos_restaurantes = st.number_input(
                "Restaurantes y Hoteles (15%)", 
                min_value=0.0, value=6000.0, step=100.0, key=f"{key_prefix}_rest",
                help="Base Legal: D.S. 399-2016-EF. Se deduce el 15% del gasto total."
            )
        with col2:
            in_gastos_alquiler = st.number_input(
                "Arrendamiento (30%)", 
                min_value=0.0, value=0.0, step=100.0, key=f"{key_prefix}_alq",
                help="Base Legal: Art. 46, LIR. Se deduce el 30% del gasto total por alquiler de vivienda."
            )
        with col3:
            in_gastos_medicos = st.number_input(
                "Honorarios Médicos (30%)", 
                min_value=0.0, value=0.0, step=100.0, key=f"{key_prefix}_med",
                help="Base Legal: Art. 46, LIR. Se deduce el 30% de honorarios a médicos y odontólogos."
            )

        col4, col5 = st.columns([2, 1])
        with col4:
            in_gastos_profesionales = st.number_input(
                "Servicios Profesionales (30%)", 
                min_value=0.0, value=0.0, step=100.0, key=f"{key_prefix}_prof",
                help="Base Legal: Art. 46, LIR. Se deduce el 30% de servicios profesionales (4ta Cat) excepto médicos/odont."
            )
        with col5:
            in_gastos_essalud_hogar = st.number_input(
                "EsSalud Hogar (100%)", 
                min_value=0.0, value=0.0, step=100.0, key=f"{key_prefix}_hogar",
                help="Base Legal: Art. 46, LIR. Se deduce el 100% del aporte a EsSalud por trabajador del hogar."
            )
        
        return EntradasGastosDeducibles(
            arrendamiento=in_gastos_alquiler,
            honorarios_medicos=in_gastos_medicos,
            servicios_profesionales=in_gastos_profesionales,
            essalud_hogar=in_gastos_essalud_hogar,
            hoteles_rest=in_gastos_restaurantes
        )

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

    # Desglose de ingresos en columnas
    with st.expander("Ver Desglose de Ingresos"):
        col1_ing, col2_ing = st.columns(2)
        with col1_ing:
            st.markdown(f"**Sueldo Básico Nominal:** `S/ {boleta['sueldo_basico_nominal']:,.2f}`")
            if boleta['dias_falta'] > 0:
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Descuento Faltas ({boleta['dias_falta']} días): `S/ {boleta['desc_faltas']:,.2f}`")
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Sueldo Básico (Ajustado):** `S/ {boleta['ing_basico_ajustado']:,.2f}`")
            st.markdown(f"**Asignación Familiar:** `S/ {boleta['ing_asig_familiar']:,.2f}`")
            st.markdown(f"**Bonificación Nocturna:** `S/ {boleta['ing_bonificacion_nocturna']:,.2f}`")
            st.markdown(f"**Sobretiempo (Total):** `S/ {boleta['ing_sobretiempo_total']:,.2f}`")
        
        with col2_ing:
            st.markdown(f"**Otros Afectos (Bonos):** `S/ {boleta['otros_ingresos_afectos']:,.2f}`")
            st.markdown(f"**No Remunerativos (Movilidad):** `S/ {boleta['ingresos_no_remunerativos']:,.2f}`")
            st.markdown(f"**Prestación Alimentaria:** `S/ {boleta['ingreso_lpa']:,.2f}`")
            st.markdown(f"**Utilidades:** `S/ {boleta['ingreso_utilidades']:,.2f}`")
            st.markdown(f"**Subsidio (DM):** `S/ {boleta['ingreso_subsidio']:,.2f}`")
        
        if boleta['ing_gratificacion'] > 0:
            st.divider()
            st.success(f"**Gratificación:** `S/ {boleta['ing_gratificacion']:,.2f}`")
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;(Base Grati: S/ {boleta['rem_computable_grati']:.2f})")
            if boleta['dias_falta_semestre_grati'] > 0:
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;(Desc. Faltas {boleta['dias_falta_semestre_grati']} días * 1/180vo)")
            st.success(f"**Bonificación Ley:** `S/ {boleta['ing_boni_ley']:,.2f}`")
            
    # Desglose de descuentos en columnas
    with st.expander("Ver Desglose de Descuentos"):
        col1_desc, col2_desc = st.columns(2)
        with col1_desc:
            st.markdown(f"**Pensión ({boleta['sistema_pension']}):** `S/ {boleta['desc_pension']:,.2f}`")
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;(Base Afecta: S/ {boleta['base_pension_salud_mes']:.2f})")
            if boleta['sistema_pension'] != 'ONP':
                st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;Prima AFP aplicada hasta TMA S/ {TOPE_MAXIMO_ASEGURABLE_AFP_2025:,.2f}")
        
        with col2_desc:
            st.markdown(f"**Renta 5ta Cat. (Mes):** `S/ {boleta['desc_renta_quinta']:,.2f}`")
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;(Proy. Anual R5 Afecta): `S/ {boleta['proyeccion_anual_r5']:,.2f}`")
            if boleta['tiene_eps']:
                st.caption(f"&nbsp;&;&nbsp;&nbsp;(Proy. Base Salud: S/ {boleta['proyeccion_base_salud_anual']:.2f})")
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

# CSS para ocultar los botones +/- en st.number_input
st.markdown("""
    <style>
    /* Oculta los botones de subida/bajada dentro de stNumberInput */
    div[data-testid="stNumberInput"] button[data-testid*="Step"] {
        display: none;
    }
    /* Oculta los botones +/- en navegadores WebKit (Chrome, Safari) */
    input[type=number]::-webkit-inner-spin-button, 
    input[type=number]::-webkit-outer-spin-button { 
        -webkit-appearance: none; 
        margin: 0; 
    }
    /* Oculta los botones +/- en Firefox */
    input[type=number] {
        -moz-appearance: textfield;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("Calculadora de Planilla y BB.SS. Perú 2025")
st.info("Herramienta de cálculo referencial basada en la legislación peruana vigente a 2025.")

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
    
    with st.expander("Historial Semestral (Para Regularidad de Gratificación)"):
        st.warning("Importante: Estos datos solo se usan en Julio (Mes 7) y Diciembre (Mes 12) para el Principio de Regularidad (Art. 19, D.S. 001-97-TR).")
        st.write("Ingrese los montos de los 6 meses del semestre (Ene-Jun o Jul-Dic):")

        data_historial_boleta = {
            'Horas Extras (S/)': [0.0] * 6,
            'Bono Nocturno (S/)': [0.0] * 6,
            'Otros Afectos (S/)': [0.0] * 6,
            'Días Falta': [0] * 6
        }
        meses_semestre_boleta = [f"Mes {i+1}" for i in range(6)]
        df_historial_boleta = pd.DataFrame(data_historial_boleta, index=meses_semestre_boleta)

        # Capturar el DataFrame editado devuelto por la función
        historial_editado_boleta = st.data_editor(
            df_historial_boleta, 
            key="historial_boleta_editor"
        )
    
    with st.form("boleta_form"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("Datos del Empleado")
            in_sueldo_basico = st.number_input("Sueldo Básico Nominal", min_value=0.0, value=5300.0, step=100.0, help="Remuneración básica mensual, sin incluir bonos ni descuentos.")
            in_tiene_hijos = st.checkbox("¿Tiene Hijos? (Asig. Familiar)", value=False, help="Marcar si el trabajador tiene hijos menores de 18 años (o 24 estudiando). Base Legal: Ley N° 25129.")
            in_sistema_pension = st.selectbox("Sistema de Pensión", 
                                              SISTEMAS_PENSION,
                                              index=1,
                                              key="boleta_pension",
                                              help="Seleccione el sistema de pensiones: ONP (Público) o una AFP (Privado). Base Legal: D.L. N° 19990 (ONP), D.L. N° 25897 (SPP).")
            in_tiene_eps = st.checkbox("¿Tiene EPS?", value=True, key="boleta_eps", help="Marcar si el trabajador está afiliado a una Entidad Prestadora de Salud (EPS). Esto genera un crédito en Renta 5ta. Base Legal: Ley N° 26790.")

        with col2:
            st.subheader("Datos del Mes")
            in_mes_nombre = st.selectbox("Mes de Cálculo", options=MESES_LISTA, index=0, key="boleta_mes_nombre", help="Seleccione el mes para el cual desea calcular la boleta.")
            in_mes_actual = MESES_LISTA.index(in_mes_nombre) + 1
            in_dias_falta = st.number_input("Días de Falta Injustificada", min_value=0, max_value=30, value=0, step=1, help="Número de días de inasistencia injustificada en el mes. Se descuenta 1/30 del sueldo por día. Base Legal: D.L. 713.")
            in_horas_nocturnas = st.number_input("Total Horas Nocturnas en el Mes", min_value=0.0, value=0.0, step=1.0, help="Total de horas laboradas en jornada nocturna (10pm a 6am). Genera una sobretasa del 35%. Base Legal: Art. 8, D.S. N° 007-2002-TR.")
            in_he_25 = st.number_input("Total Horas Extras al 25%", min_value=0.0, value=0.0, step=0.5, help="Total de horas extra que corresponden a las dos primeras horas extra del día. Base Legal: Art. 9, D.S. N° 007-2002-TR.")
            in_he_35 = st.number_input("Total Horas Extras al 35%", min_value=0.0, value=0.0, step=0.5, help="Total de horas extra laboradas a partir de la tercera hora extra del día. Base Legal: Art. 9, D.S. N° 007-2002-TR.")
            in_he_100 = st.number_input("Total Horas Extras al 100% (Feriados)", min_value=0.0, value=0.0, step=0.5, help="Total de horas extra laboradas en días feriados o día de descanso semanal obligatorio. Base Legal: D.L. 713.")

        with col3:
            st.subheader("Otros Ingresos / Descuentos")
            in_otros_ingresos_afectos = st.number_input("Otros Bonos Afectos", min_value=0.0, value=0.0, step=50.0, help="Monto total de otros ingresos remunerativos (ej. Bono de productividad, comisiones) que sean afectos a Pensión, Salud y Renta 5ta.")
            in_movilidad = st.number_input("Ingreso No Remunerativo (Movilidad)", min_value=0.0, value=500.0, step=50.0, help="Monto por movilidad supeditada a la asistencia. No es base para Pensión/Salud, pero SÍ para Renta 5ta. Base Legal: Art. 34, LIR.")
            in_lpa = st.number_input("Prestación Alimentaria (LPA)", min_value=0.0, value=0.0, step=50.0, help="Ingreso por prestación alimentaria (ej. Tarjeta de alimentos). No es base para Pensión/Salud, pero SÍ para Renta 5ta. Base Legal: Ley N° 28051.")
            in_utilidades = st.number_input("Ingreso por Utilidades (Pago único)", min_value=0.0, value=0.0, step=100.0, help="Monto de utilidades pagado en el mes. No es base para Pensión/Salud, pero SÍ para Renta 5ta. Base Legal: D.L. N° 892.")
            in_subsidio = st.number_input("Ingreso por Subsidio (DM)", min_value=0.0, value=0.0, step=100.0, help="Monto de subsidio por Incapacidad Temporal (Descanso Médico). No es base para Pensión/Salud, pero SÍ para Renta 5ta. Base Legal: Ley N° 26790.")
            in_otros_descuentos = st.number_input("Otros Descuentos Fijos", min_value=0.0, value=0.0, step=10.0, help="Otros descuentos no relacionados a ley (ej. Cuota sindical, préstamos, adelantos).")

        st.subheader("Parámetros Costo Empleador")
        c1_costo, c2_costo, c3_costo = st.columns(3)
        with c1_costo:
            in_tasa_sctr = st.number_input("Tasa SCTR (%)", min_value=0.0, value=1.2, step=0.1, help="Tasa porcentual del Seguro Complementario de Trabajo de Riesgo. Ingrese 1.2 para 1.2%. Base Legal: D.S. N° 003-98-SA.")
        with c2_costo:
            in_tasa_senati = st.number_input("Tasa SENATI (%)", min_value=0.0, value=0.0, step=0.75, help="Aporte a SENATI (usualmente 0.75%) para empresas industriales. Base Legal: Ley N° 26272.")
        with c3_costo:
            in_prima_vida = st.number_input("Prima Seguro Vida Ley (Monto S/)", min_value=0.0, value=15.0, step=1.0, help="Monto fijo mensual de la prima del Seguro Vida Ley. Base Legal: D.L. N° 688.")

        # Layout en columnas para Gastos Deducibles
        gastos_data = _renderizar_gastos_deducibles(key_prefix="boleta")

        # Layout en columnas para Acumuladores
        with st.expander("Acumuladores Anuales (Para Renta 5ta)"):
            st.info("Para un cálculo preciso, ingrese los montos acumulados de Enero hasta el mes *anterior* al que está calculando.")
            
            col1_ac, col2_ac, col3_ac = st.columns(3)
            with col1_ac:
                in_acum_r5 = st.number_input("Acumulado Bruto Renta 5ta", min_value=0.0, value=0.0, step=1000.0, key="boleta_acum_r5", help="Suma de todos los ingresos brutos afectos a Renta 5ta (incluye CNR, LPA, etc.) pagados desde Enero hasta el mes anterior.")
            with col2_ac:
                in_acum_salud = st.number_input("Acumulado Base Afecta a Salud", min_value=0.0, value=0.0, step=1000.0, key="boleta_acum_salud", help="Suma de la base afecta a EsSalud/EPS pagada desde Enero hasta el mes anterior. Se usa para el crédito EPS.")
            with col3_ac:
                in_acum_retenciones = st.number_input("Acumulado Retenciones Renta 5ta", min_value=0.0, value=0.0, step=100.0, key="boleta_acum_ret", help="Suma de todas las retenciones de 5ta Categoría ya pagadas en el año.")

        submitted_boleta = st.form_submit_button("Calcular Boleta Mensual", type="primary")

    # --- Área de Resultados (Boleta) ---
    if submitted_boleta:
        with st.spinner("Calculando boleta..."):
            
            # 1. Poblar los dataclasses con los inputs del formulario
            empleado_data = EntradasEmpleado(
                sueldo_basico_nominal=in_sueldo_basico,
                tiene_hijos=in_tiene_hijos,
                sistema_pension=in_sistema_pension,
                tiene_eps=in_tiene_eps
            )
            mes_data = EntradasMes(
                mes_actual_num=in_mes_actual,
                dias_falta=in_dias_falta,
                horas_nocturnas_mes=in_horas_nocturnas,
                horas_25=in_he_25, horas_35=in_he_35, horas_100=in_he_100,
                otros_ingresos_afectos=in_otros_ingresos_afectos,
                ingresos_no_remunerativos=in_movilidad,
                ingreso_lpa=in_lpa,
                ingreso_utilidades=in_utilidades,
                ingreso_subsidio=in_subsidio,
                otros_descuentos_fijos=in_otros_descuentos
            )
            acumulados_data = EntradasAcumuladas(
                ingresos_brutos_acumulados_renta5=in_acum_r5,
                ingresos_afectos_salud_acumulados=in_acum_salud,
                retenciones_acumuladas_renta5=in_acum_retenciones
            )
            
            # El DataFrame 'historial_editado_boleta' ya está disponible desde fuera del form
            historial_data = EntradasHistorialSemestral(
                ing_sobretiempo_total=historial_editado_boleta['Horas Extras (S/)'].tolist(),
                ing_bonificacion_nocturna=historial_editado_boleta['Bono Nocturno (S/)'].tolist(),
                otros_ingresos_afectos=historial_editado_boleta['Otros Afectos (S/)'].tolist(),
                dias_falta=historial_editado_boleta['Días Falta'].tolist()
            )
            # 'gastos_data' ya es un dataclass (viene del helper)

            # 2. Llamar a la lógica con los dataclasses
            boleta_calculada = generar_boleta_mensual(
                empleado=empleado_data, mes=mes_data, acumulados=acumulados_data,
                gastos=gastos_data, historial=historial_data
            )
            
            # 3. Mostrar resultados
            mostrar_boleta_streamlit(boleta_calculada, in_mes_actual)
            
            # 4. Calcular y mostrar costo laboral
            st.header(f"Costo Laboral del Empleador ({MESES_LISTA[in_mes_actual-1]})")
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

    with st.expander("Historial de Variables (Últimos 6 Meses para Regularidad)"):
        st.warning("Ingrese los montos de los 6 meses *anteriores* al cese (para Principio de Regularidad 3 de 6). Base Legal: Art. 19, D.S. 001-97-TR.")
        
        data_historial_lqbs = {
            'Horas Extras (S/)': [0.0] * 6,
            'Bono Nocturno (S/)': [0.0] * 6,
            'Otros Afectos (S/)': [0.0] * 6,
            'Días Falta': [0] * 6 # Se usa para Grati Trunca
        }
        meses_semestre_lqbs = [f"Mes {i+1}" for i in range(6)]
        df_historial_lqbs = pd.DataFrame(data_historial_lqbs, index=meses_semestre_lqbs)

        # Capturar el DataFrame editado devuelto por la función
        historial_editado_lqbs = st.data_editor(
            df_historial_lqbs, 
            key="historial_lqbs_editor"
        )
    
    with st.form("lqbs_form"):
        col1_lq, col2_lq, col3_lq = st.columns(3)
        
        with col1_lq:
            st.subheader("Datos del Cese")
            today = datetime.now().date()
            in_lqbs_fecha_ingreso = st.date_input("Fecha de Ingreso", value=today - relativedelta(years=2, months=9, days=30), help="Fecha de inicio del vínculo laboral.")
            in_lqbs_fecha_cese = st.date_input("Fecha de Cese", value=today, help="Último día de labores.")
            in_lqbs_motivo = st.selectbox("Motivo de Cese", 
                                          ['RENUNCIA', 'DESPIDO_ARBITRARIO', 'FALTA_GRAVE', 'TERMINO_CONTRATO'], 
                                          index=1,
                                          help="El motivo 'DESPIDO_ARBITRARIO' activa el cálculo de indemnización (Art. 38, D.S. 003-97-TR).")
        
        with col2_lq:
            st.subheader("Bases Computables")
            st.caption("Bases de cálculo (Art. 19, D.S. 001-97-TR).")
            in_lqbs_rc_basica = st.number_input("RC Básica (Sueldo + AF)", min_value=0.0, value=5300.0, step=100.0, help="Remuneración Computable básica (Sueldo + Asig. Familiar) vigente al mes de cese.")
            in_lqbs_sexto_grati = st.number_input("Último 1/6 de Gratificación (CTS)", min_value=0.0, value=(5300/6), step=10.0, format="%.2f", help="1/6 de la última gratificación (Julio o Diciembre) percibida. Se usa para la RC de CTS.")

        with col3_lq:
            st.subheader("Regímenes y Faltas")
            st.caption("Opciones que modifican el cálculo.")
            in_lqbs_part_time = col3_lq.checkbox("¿Es Part-Time (< 4h/día)?", value=False, help="Marcar si el contrato es a tiempo parcial (menos de 4 horas diarias). Pierde derecho a CTS y Vacaciones. Base Legal: D.S. 001-97-TR y D.L. 713.", key="lqbs_part_time")
            in_lqbs_pierde_record = col3_lq.checkbox("¿Perdió Récord Vacacional?", value=False, help="Marcar si el trabajador no cumplió el récord vacacional (ej. +10 faltas). Pierde derecho a Vacaciones Truncas. Base Legal: Art. 10, D.L. 713.", key="lqbs_pierde_record")
            in_lqbs_faltas_sem_trunco = col3_lq.number_input("Faltas en Semestre Trunco", min_value=0, value=0, step=1, help="Total de días de falta en el semestre trunco (Ene-Cese o Jul-Cese). Se usa para descontar de la Grati Trunca (1/180vo). Base Legal: D.S. N° 005-2002-TR.")

        submitted_lqbs = st.form_submit_button("Calcular Liquidación (LQBS)", type="primary")

    if submitted_lqbs:
        with st.spinner("Calculando liquidación..."):
            
            datos_lqbs = EntradasLiquidacion(
                fecha_ingreso=in_lqbs_fecha_ingreso,
                fecha_cese=in_lqbs_fecha_cese,
                motivo_cese=in_lqbs_motivo,
                rc_basica=in_lqbs_rc_basica,
                ultimo_sexto_grati=in_lqbs_sexto_grati
            )
            opciones_lqbs = OpcionesLiquidacion(
                es_part_time_lt_4h=in_lqbs_part_time,
                ha_perdido_record_vacacional=in_lqbs_pierde_record,
                dias_falta_en_semestre_trunco=in_lqbs_faltas_sem_trunco
            )
            historial_data_lqbs = EntradasHistorialSemestral(
                ing_sobretiempo_total=historial_editado_lqbs['Horas Extras (S/)'].tolist(),
                ing_bonificacion_nocturna=historial_editado_llqbs['Bono Nocturno (S/)'].tolist(),
                otros_ingresos_afectos=historial_editado_lqbs['Otros Afectos (S/)'].tolist(),
                dias_falta=historial_editado_lqbs['Días Falta'].tolist()
            )
            
            lqbs_calculada = generar_liquidacion(
                datos=datos_lqbs,
                opciones=opciones_lqbs,
                historial=historial_data_lqbs
            )
            
            mostrar_liquidacion_streamlit(lqbs_calculada)


# --- PESTAÑA 3: RÉGIMEN INTEGRAL (RIA) ---
with tab_ria:
    st.header("Calculadora de Boleta Mensual (Régimen RIA)")
    st.info(f"Régimen opcional para trabajadores con remuneración promedio superior a 2 UIT (S/ {LIMITE_MINIMO_RIA_MENSUAL:,.2f} mensual). Base Legal: Art. 8, D.S. N° 003-97-TR.")
    
    with st.form("ria_form"):
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Datos del Empleado")
            in_ria_paquete_anual = st.number_input("Remuneración Integral Anual (Paquete)", min_value=0.0, value=192000.0, step=1000.0, help="Monto total anual pactado, que incluye sueldo, gratificaciones, CTS, etc.")
            in_ria_sistema_pension = st.selectbox("Sistema de Pensión", 
                                                  SISTEMAS_PENSION, 
                                                  key="ria_pension", index=3,
                                                  help="Sistema de pensiones al que aporta el trabajador.")
            in_ria_tiene_eps = st.checkbox("¿Tiene EPS?", value=False, key="ria_eps", help="Marcar si está afiliado a una EPS. Genera crédito en Renta 5ta.")
        with col2:
            st.subheader("Datos del Mes")
            in_ria_mes_nombre = st.selectbox("Mes de Cálculo", options=MESES_LISTA, index=0, key="ria_mes_nombre")
            in_ria_mes_actual = MESES_LISTA.index(in_ria_mes_nombre) + 1
            in_ria_acum_retenciones = st.number_input("Acumulado Retenciones Renta 5ta", min_value=0.0, value=0.0, step=100.0, key="ria_acum", help="Suma de retenciones de 5ta Cat. pagadas desde Enero hasta el mes anterior.")

        gastos_data_ria = _renderizar_gastos_deducibles(key_prefix="ria")

        submitted_ria = st.form_submit_button("Calcular Boleta RIA", type="primary")

    if submitted_ria:
        with st.spinner("Calculando boleta RIA..."):
            
            datos_ria = EntradasRIA(
                remuneracion_integral_anual=in_ria_paquete_anual,
                sistema_pension=in_ria_sistema_pension,
                tiene_eps=in_ria_tiene_eps,
                mes_actual_num=in_ria_mes_actual,
                retenciones_acumuladas_renta5=in_ria_acum_retenciones
            )
            
            boleta_ria_calculada = generar_boleta_ria(
                datos=datos_ria,
                gastos=gastos_data_ria
            )
            
            mostrar_boleta_ria_streamlit(boleta_ria_calculada, in_ria_mes_actual)


# --- PESTAÑA 4: INDEMNIZACIÓN POR VACACIONES NO GOZADAS ---
with tab_indemnizacion:
    st.header("Calculadora de Indemnización por Vacaciones No Gozadas")
    st.warning("Este pago aplica cuando un trabajador no disfruta de su descanso físico dentro del año siguiente a aquél en el que generó el derecho. Base Legal: Art. 23, D.L. N° 713.")
    
    with st.form("indemn_vacas_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Datos del Cálculo")
            in_indv_rc = st.number_input("Remuneración Computable Vacacional (RC)", min_value=0.0, value=4500.0, step=100.0, help="La Remuneración Computable para vacaciones (Sueldo + AF + Promedio Variables) vigente en el momento del pago.")
            in_indv_periodos = st.number_input("N° de Períodos Vencidos", min_value=1, value=1, step=1, help="Número de períodos vacacionales completos que no se gozaron a tiempo.")
            
        with col2:
            st.subheader("Regímenes y Excepciones")
            in_indv_part_time = st.checkbox("¿Es Part-Time (< 4h/día)?", value=False, help="Si marca esto, el pago será 0 (trabajadores Part-Time no tienen derecho a vacaciones).", key="indv_part_time")
            in_indv_pierde_record = st.checkbox("¿Perdió Récord Vacacional por Faltas?", value=False, help="Si marca esto, el pago será 0 (trabajador no llegó a generar el derecho que ahora se vencería).", key="indv_pierde_record")

        submitted_indv = st.form_submit_button("Calcular Indemnización", type="primary")

    if submitted_indv:
        with st.spinner("Calculando indemnización..."):
            indemnizacion_calculada = calcular_indemnizacion_vacaciones_no_gozadas(
                rc_vacacional=in_indv_rc,
                periodos_vencidos=in_indv_periodos,
                es_part_time_lt_4h=in_indv_part_time,
                ha_perdido_record_vacacional=in_indv_pierde_record
            )
            
            mostrar_indemnizacion_vacaciones_streamlit(indemnizacion_calculada)
