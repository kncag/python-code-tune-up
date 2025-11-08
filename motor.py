# -*- coding: utf-8 -*-
"""
==============================================================================
=== PARTE 1: MOTOR DE CÁLCULO (REFACTORIZADO) ===
==============================================================================

Este archivo contiene toda la lógica pura de Python.
No debe contener NINGUNA importación o código de Streamlit (st.).

Mejoras:
- Se usan dataclasses para agrupar los parámetros de entrada.
- Se ha eliminado todo el código de UI (funciones 'mostrar_...').
"""

# --- 0. IMPORTACIONES NECESARIAS ---
from __future__ import annotations
import math
from typing import Dict, Any, Tuple, List
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass, field

# --- 1. CONSTANTES GLOBALES (Valores oficiales 2025) ---
# ... (Tu sección de constantes permanece igual, está muy bien) ...
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

# (NUEVO) Constante para los sistemas de pensión
SISTEMAS_PENSION = ['ONP', 'INTEGRA', 'PRIMA', 'HABITAT', 'PROFUTURO']

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
TASA_APORTE_AFP = 0.10 # Aporte obligatorio al fondo
TASA_PRIMA_SEGURO_AFP = 0.0174 # Tasa promedio (varía por AFP/licitación)
TOPE_MAXIMO_ASEGURABLE_AFP_2025 = 12234.34 

# Limite 3 UIT (Art. 46, LIR)
LIMITE_3_UIT = 3 * UIT_2025 # 3 * 5350 = 16,050

# (NUEVO) Base Legal: Art. 8, D.S. N° 003-97-TR
LIMITE_MINIMO_RIA_UIT = 2.0
LIMITE_MINIMO_RIA_MENSUAL = LIMITE_MINIMO_RIA_UIT * UIT_2025 # 10,700


# ==============================================================================
# --- (NUEVO) 2. CLASES DE DATOS (DATACLASSES) ---
# ==============================================================================
# Usamos dataclasses para agrupar parámetros. En lugar de 26 argumentos,
# la función principal recibirá 5 objetos bien definidos.

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
# (Estas funciones ya eran modulares y limpias, se mantienen igual)

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
    """
    monto_25 = horas_25 * valor_hora * (1 + TASA_SOBRETIEMPO_25)
    monto_35 = horas_35 * valor_hora * (1 + TASA_SOBRETIEMPO_35)
    monto_100 = horas_100 * valor_hora * (1 + TASA_SOBRETIEMPO_100) 
    
    return (monto_25 + monto_35 + monto_100), monto_25, monto_35, monto_100

def calcular_asignacion_familiar(tiene_hijos: bool) -> float:
    """
    Calcula la asignación familiar.
    Base Legal: Ley N° 25129. Es el 10% de la RMV.
    """
    return RMV_2025 * PORC_ASIG_FAMILIAR if tiene_hijos else 0

def calcular_bonificacion_nocturna(valor_hora: float, horas_nocturnas_mes: float) -> float:
    """
    Calcula la bonificación nocturna (BN).
    Base Legal: Art. 8, D.S. N° 007-2002-TR.
    """
    if horas_nocturnas_mes <= 0 or valor_hora <= 0:
        return 0
    
    sobretasa_nocturna_por_hora = valor_hora * TASA_BONIFICACION_NOCTURNA
    return sobretasa_nocturna_por_hora * horas_nocturnas_mes

# ==============================================================================
# --- 4. FUNCIONES DE CÁLCULO DE DESCUENTOS ---
# ==============================================================================
# (Estas funciones ya eran modulares y limpias)

def calcular_descuento_pension(sueldo_bruto_afecto: float, sistema_pension: str) -> float:
    """
    Calcula el descuento de AFP u ONP sobre la base afecta.
    (REFINADO) Incluye el Tope Máximo Asegurable (TMA) para la Prima.
    """
    sistema_pension = sistema_pension.upper()
    
    if sistema_pension == 'ONP':
        return sueldo_bruto_afecto * PORC_ONP
    elif sistema_pension in SISTEMAS_PENSION:
        # Lógica de AFP Refinada con TMA (Tope Máximo Asegurable)
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
    """
    Función interna: Calcula el impuesto anual basado en los tramos
    y aplica el crédito EPS si corresponde.
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
        credito_eps = proyeccion_base_salud_anual * CREDITO_POR_EPS # 2.25%
        impuesto_anual = max(0, impuesto_anual - credito_eps)
        
    return impuesto_anual

def calcular_retencion_renta_quinta(
    ingresos_proyectados_anuales: float,
    proyeccion_base_salud_anual: float,
    gastos: EntradasGastosDeducibles, # <- REFACTORIZADO
    tiene_eps: bool = False, 
    mes_actual_num: int = 1, 
    retenciones_acumuladas: float = 0.0
) -> float:
    """
    Calcula la retención de 5ta categoría para el mes actual.
    (REFACTORIZADO) Acepta un dataclass 'EntradasGastosDeducibles'.
    """
    
    # 1. Base Imponible: Renta Bruta Anual
    renta_bruta = ingresos_proyectados_anuales
    
    # 2. Deducción de 7 UIT (Art. 46, TUO LIR)
    deduccion_7_uit = 7 * UIT_2025
    
    # 3. (NUEVO) Deducción de 3 UIT adicionales (Art. 46, TUO LIR)
    deduccion_arrendamiento = gastos.arrendamiento * 0.30
    deduccion_honorarios_medicos = gastos.honorarios_medicos * 0.30
    deduccion_servicios_profesionales = gastos.servicios_profesionales * 0.30
    deduccion_essalud_hogar = gastos.essalud_hogar * 1.00
    deduccion_hoteles_rest = gastos.hoteles_rest * 0.15
    
    total_deduccion_adicional_calculada = (
        deduccion_arrendamiento +
        deduccion_honorarios_medicos +
        deduccion_servicios_profesionales +
        deduccion_essalud_hogar +
        deduccion_hoteles_rest
    )
    
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
    """
    (REFACTORIZADO) Aplica el Principio de Regularidad (Art. 19, D.S. 001-97-TR).
    Acepta un dataclass 'EntradasHistorialSemestral'.
    """
    promedio_total = 0.0
    
    # Convertir el dataclass en un dict para iterar
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
    """
    Calcula una gratificación semestral (Julio o Diciembre).
    Refinamiento: Descuento por faltas (1/180vo)
    """
    if meses_completos <= 0:
        return 0, 0
    
    grati_bruta = (sueldo_computable / 6) * meses_completos
    descuento_por_faltas = (sueldo_computable / 180) * dias_falta_semestre
    grati_neta_a_pagar = max(0, grati_bruta - descuento_por_faltas)
    
    tasa_bonificacion = BONI_LEY_EPS if tiene_eps else BONI_LEY_ESSALUD
    bonificacion = grati_neta_a_pagar * tasa_bonificacion
    
    return grati_neta_a_pagar, bonificacion

def calcular_cts_semestral(remuneracion_computable_cts: float, meses_completos: int) -> float:
    """
    Calcula el depósito de CTS semestral (Mayo u Octubre).
    Base Legal: D.S. N° 001-97-TR (TUO Ley de CTS).
    """
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
    # Bases ya calculadas del mes actual
    base_renta_quinta_mes: float,
    base_pension_salud_mes: float
) -> Tuple[float, float]:
    """
    (REFACTORIZADO) Función interna para modularizar la lógica de proyección anual.
    Acepta dataclasses para mayor limpieza.
    """
    
    # 1. Calcular la base fija para los meses futuros
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
    
    # 2. Calcular Ingresos Futuros Proyectados (Renta 5ta)
    ingresos_reales_acumulados_R5 = acumulados.ingresos_brutos_acumulados_renta5 + base_renta_quinta_mes
    meses_futuros = 12 - mes.mes_actual_num
    ingresos_futuros_proyectados_R5 = base_proyeccion_mes_normal_R5 * meses_futuros
    ingresos_proyectados_anuales_r5 = ingresos_reales_acumulados_R5 + ingresos_futuros_proyectados_R5
    
    # 3. Calcular Proyección de Base Salud (para Crédito EPS)
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
    """
    (REFACTORIZADO) Genera un cálculo detallado de una boleta de pago mensual.
    Acepta 5 dataclasses en lugar de 26 argumentos.
    """
    
    boleta: Dict[str, Any] = {} # Inicializa el diccionario de resultados

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
    
    ing_bonificacion_nocturna = calcular_bonificacion_nocturna(
        valor_hora_calculado, mes.horas_nocturnas_mes
    )
    
    ing_sobretiempo_total, m25, m35, m100 = calcular_sobretiempo(
        valor_hora_calculado, mes.horas_25, mes.horas_35, mes.horas_100
    )
    
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
    
    # 1.4. Gratificación (si corresponde)
    ing_gratificacion = 0.0
    ing_boni_ley = 0.0
    es_mes_grati = (mes.mes_actual_num == 7 or mes.mes_actual_num == 12)
    dias_faltas_totales_semestre = 0
    
    if es_mes_grati:
        promedio_variables_regulares = _calcular_promedio_regularidad(historial)
        
        rem_computable_grati = (
            ing_basico_ajustado + 
            ing_asig_familiar + 
            promedio_variables_regulares
        )
        boleta['rem_computable_grati'] = rem_computable_grati
        
        dias_faltas_totales_semestre = sum(historial.dias_falta)
        
        ing_gratificacion, ing_boni_ley = calcular_gratificacion(
            rem_computable_grati, 
            6, 
            empleado.tiene_eps,
            dias_falta_semestre=dias_faltas_totales_semestre
        )
    else:
         boleta['rem_computable_grati'] = 0.0

    boleta['ing_gratificacion'] = ing_gratificacion
    boleta['ing_boni_ley'] = ing_boni_ley
    boleta['dias_falta_semestre_grati'] = dias_faltas_totales_semestre
    
    # --- 2. CÁLCULO DE BASES AFECTAS (Este Mes) ---
    base_pension_salud_mes = (
        ing_basico_ajustado + 
        ing_asig_familiar + 
        ing_bonificacion_nocturna + 
        ing_sobretiempo_total +    
        mes.otros_ingresos_afectos
    )
    
    base_renta_quinta_mes = (
        base_pension_salud_mes +
        mes.ingresos_no_remunerativos +
        mes.ingreso_lpa +
        mes.ingreso_utilidades +
        mes.ingreso_subsidio
    )
    
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
        empleado, mes, acumulados,
        base_renta_quinta_mes=base_renta_quinta_mes,
        base_pension_salud_mes=base_pension_salud_mes
    )
    
    boleta['proyeccion_anual_r5'] = proyeccion_anual_r5
    boleta['proyeccion_base_salud_anual'] = proyeccion_base_salud_anual
    
    # --- 4. CÁLCULO DE DESCUENTOS ---
    desc_pension = calcular_descuento_pension(base_pension_salud_mes, empleado.sistema_pension)
    boleta['desc_pension'] = desc_pension
    
    desc_lpa = mes.ingreso_lpa
    boleta['desc_lpa'] = desc_lpa
    
    desc_renta_quinta = calcular_retencion_renta_quinta(
        ingresos_proyectados_anuales=proyeccion_anual_r5,
        proyeccion_base_salud_anual=proyeccion_base_salud_anual,
        gastos=gastos, # Pasa el dataclass
        tiene_eps=empleado.tiene_eps,
        mes_actual_num=mes.mes_actual_num,
        retenciones_acumuladas=acumulados.retenciones_acumuladas_renta5
    )
    boleta['desc_renta_quinta'] = desc_renta_quinta
    boleta['otros_descuentos_fijos'] = mes.otros_descuentos_fijos
    
    # --- 5. TOTALES ---
    total_descuentos = (
        desc_pension + 
        desc_renta_quinta + 
        desc_lpa +
        mes.otros_descuentos_fijos 
    )
    neto_a_pagar = total_ingresos_boleta - total_descuentos
    
    boleta['total_descuentos'] = total_descuentos
    boleta['neto_a_pagar'] = neto_a_pagar
    boleta['sistema_pension'] = empleado.sistema_pension
    boleta['tiene_eps'] = empleado.tiene_eps

    # --- 6. RATIOS DE EFICIENCIA (TRABAJADOR) ---
    boleta['ratio_neto_vs_bruto'] = (neto_a_pagar / total_ingresos_boleta) if total_ingresos_boleta > 0 else 0.0
    boleta['ratio_neto_vs_sueldo_nominal'] = (neto_a_pagar / empleado.sueldo_basico_nominal) if empleado.sueldo_basico_nominal > 0 else 0.0

    return boleta


# ==============================================================================
# --- 7. FUNCIONES DE LIQUIDACIÓN DE BENEFICIOS SOCIALES (LQBS) ---
# ==============================================================================
# (Funciones internas _calcular_tiempo_servicio, _calcular_truncos_cts, etc.
#  se mantienen igual que en tu versión original, ya son modulares)

def _calcular_tiempo_servicio(fecha_inicio: datetime.date, fecha_fin: datetime.date) -> relativedelta:
    """Helper: Calcula el tiempo total de servicio usando relativedelta."""
    try:
        inicio = fecha_inicio
        fin = fecha_fin + relativedelta(days=1) # El cese es inclusivo
        return relativedelta(fin, inicio)
    except Exception as e:
        print(f"Error al calcular tiempo de servicio: {e}. Asegúrese que las fechas sean válidas.")
        return relativedelta()

def _calcular_truncos_cts(rc_cts: float, fecha_ingreso: datetime.date, fecha_cese: datetime.date) -> Tuple[float, int, int]:
    """Calcula la CTS Trunca."""
    
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
    """Calcula la Gratificación Trunca."""

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
    """Calcula las Vacaciones Truncas."""
    
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
    """(CORREGIDO) Calcula la indemnización por despido arbitrario."""
    
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
    """
    (REFACTORIZADO) Genera el cálculo completo de una LQBS.
    Acepta 3 dataclasses.
    """
    
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
        rc_grati_vacas, 
        datos.fecha_cese,
        opciones.dias_falta_en_semestre_trunco
    )
    
    lqbs['vacas_truncas'], lqbs['vacas_meses'], lqbs['vacas_dias'] = _calcular_truncos_vacaciones(
        rc_grati_vacas, 
        datos.fecha_ingreso, 
        datos.fecha_cese,
        opciones.ha_perdido_record_vacacional
    )
    
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
    """
    Calcula los aportes mensuales del empleador (Costo Laboral).
    Toma el diccionario de boleta_mes como input.
    """
    
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
    
    # --- Ratios de Costo (Empleador) ---
    base_nominal = boleta.get('sueldo_basico_nominal', 0.0)
    base_bruta = boleta.get('total_ingresos_brutos_mes', 0.0)
    
    costos['ratio_costo_vs_sueldo_nominal'] = (costo_laboral_total_mes / base_nominal) if base_nominal > 0 else 0.0
    costos['ratio_costo_vs_bruto'] = (costo_laboral_total_mes / base_bruta) if base_bruta > 0 else 0.0
    
    return costos


# ==============================================================================
# --- (NUEVO) 9. FUNCIONES DE REMUNERACIÓN INTEGRAL ANUAL (RIA) ---
# ==============================================================================

def generar_boleta_ria(
    datos: EntradasRIA,
    gastos: EntradasGastosDeducibles
) -> Dict[str, Any]:
    """
    (REFACTORIZADO) Genera un cálculo de boleta para el régimen RIA.
    Acepta dataclasses.
    """
    
    boleta_ria = {}
    pago_mensual_integral = datos.remuneracion_integral_anual / 12
    
    # 1. Validación Legal
    if pago_mensual_integral < LIMITE_MINIMO_RIA_MENSUAL:
        boleta_ria['error'] = f"Error: El pago mensual (S/ {pago_mensual_integral:.2f}) no supera las 2 UIT (S/ {LIMITE_MINIMO_RIA_MENSUAL:.2f}). No califica para RIA."
        return boleta_ria

    boleta_ria['ingreso_integral_mensual'] = pago_mensual_integral
    
    # 2. Bases Afectas (En RIA, todo es base)
    base_pension_salud_mes = pago_mensual_integral
    base_renta_quinta_mes = pago_mensual_integral
    boleta_ria['base_pension_salud_mes'] = base_pension_salud_mes
    boleta_ria['base_renta_quinta_mes'] = base_renta_quinta_mes
    
    # 3. Descuentos
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
    
    # 4. Totales
    total_descuentos = desc_pension + desc_renta_quinta
    neto_a_pagar = pago_mensual_integral - total_descuentos
    
    boleta_ria['total_descuentos'] = total_descuentos
    boleta_ria['neto_a_pagar'] = neto_a_pagar
    
    return boleta_ria


# ==============================================================================
# --- (NUEVO) 10. FUNCIONES DE CASOS ESPECIALES (INDEMNIZACIONES) ---
# ==============================================================================
# (Esta función ya era modular y limpia, se mantiene igual)

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
