"""
Modelo financiero de la propuesta RUT 2026 — Célula de consultoría
Pedro Pablo Galvis Ríos · Cristian David Bonilla Rojas · Andrés Juan Ramírez Ropero

Toda la lógica de cálculo vive aquí (sin Streamlit) para poder probarla y
explicarla línea por línea en la sustentación.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict

# ---------------------------------------------------------------------------
# Tarifas públicas (USD) — región AWS us-east-1, consultadas en noviembre 2026.
# Cada tarifa lleva su fuente para responder "¿de dónde sale este número?".
# ---------------------------------------------------------------------------
TARIFAS_USD = {
    "textract_queries_pagina": (0.015, "Amazon Textract AnalyzeDocument (Queries), primer millón de páginas/mes — aws.amazon.com/textract/pricing"),
    "lambda_gb_s": (0.0000166667, "AWS Lambda, precio por GB-segundo (x86) — aws.amazon.com/lambda/pricing"),
    "lambda_solicitud": (0.0000002, "AWS Lambda, USD 0,20 por millón de solicitudes"),
    "stepfunctions_transicion": (0.000025, "AWS Step Functions Standard, USD 0,025 por 1.000 transiciones"),
    "sqs_solicitud": (0.0000004, "Amazon SQS estándar, USD 0,40 por millón de solicitudes"),
    "apigw_solicitud": (0.000001, "Amazon API Gateway HTTP API, USD 1,00 por millón de solicitudes"),
    "eventbridge_evento": (0.000001, "Amazon EventBridge, USD 1,00 por millón de eventos"),
    "s3_put": (0.000005, "Amazon S3 PUT, USD 0,005 por 1.000 solicitudes"),
    "s3_gb_mes": (0.023, "Amazon S3 Standard, USD 0,023 por GB-mes"),
    "ses_correo": (0.0001, "Amazon SES, USD 0,10 por 1.000 correos"),
    "whatsapp_utility_co": (0.00092, "Meta WhatsApp Business Platform, plantilla 'utility' a número colombiano (tarifa 2026)"),
    "cognito_lite_mau": (0.0055, "Amazon Cognito Lite, por MAU sobre 10.000 MAU gratuitos"),
    "aurora_acu_hora": (0.12, "Aurora PostgreSQL Serverless v2, USD por ACU-hora"),
    "aurora_gb_mes": (0.10, "Aurora, almacenamiento USD por GB-mes"),
    "eks_control_hora": (0.10, "Amazon EKS, plano de control USD 0,10 por hora"),
    "ec2_t3medium_hora": (0.0416, "EC2 t3.medium bajo demanda, USD por hora"),
    "alb_hora": (0.0225, "Application Load Balancer, USD por hora (sin LCU)"),
    "nat_hora": (0.045, "NAT Gateway, USD por hora"),
}


def t(clave: str) -> float:
    return TARIFAS_USD[clave][0]


@dataclass
class Parametros:
    # --- Línea base As-Is (fijada por los Términos de Referencia, num. 2.3) ---
    smmlv: float = 2_000_000
    factor_prestacional: float = 1.5
    validadores_manual: int = 10
    agentes_cc_manual: int = 4
    meses_por_ciclo: int = 2
    ciclos_por_anio: int = 2
    aspirantes_por_ciclo: int = 45_000

    # --- Supuestos de operación To-Be ---
    trm: float = 3_300                 # COP por USD (TRM 18-nov-2026: 3.309,55)
    tasa_reenvio: float = 0.25          # fracción de aspirantes que subsana y vuelve a cargar
    paginas_por_documento: float = 1.0  # solo hoja principal del RUT va a Textract
    mensajes_whatsapp_por_doc: float = 1.2
    correos_por_doc: float = 1.0
    tamano_pdf_mb: float = 0.5
    anios_retencion: int = 5

    # Revisión humana residual (casos de excepción)
    tasa_revision_humana: float = 0.12  # baja confianza OCR, casilla no hallada, código 48, CIIU en alerta
    productividad_revisor_dia: int = 200
    dias_habiles_por_ciclo: int = 40
    agentes_mesa_ayuda: int = 1
    costo_mensual_operador: float | None = None  # si None se usa smmlv*factor

    # Transición (TOGAF fase F): primer ciclo con operación manual parcial en paralelo
    fraccion_manual_primer_ciclo: float = 0.5

    # --- CapEx (COP, costo empresa) ---
    meses_desarrollo: int = 3
    lider_tecnico_mes: float = 12_000_000
    desarrolladores: int = 2
    desarrollador_mes: float = 9_000_000
    qa_dedicacion: float = 0.5
    qa_mes: float = 7_000_000
    pruebas_carga: float = 4_000_000
    pruebas_seguridad: float = 12_000_000
    puesta_produccion: float = 6_000_000
    contingencia: float = 0.10

    # --- OpEx fijo (USD/mes salvo indicación) ---
    aurora_acu_base: float = 0.5
    aurora_acu_pico: float = 2.0
    aurora_gb: float = 20
    waf_usd_mes: float = 10.0          # 1 Web ACL (5) + 5 reglas (1 c/u)
    kms_secrets_usd_mes: float = 3.2    # 2 llaves KMS + 3 secretos
    monitoreo_usd_mes: float = 15.0     # CloudWatch alarmas/dashboards + CloudTrail data events
    dns_cdn_usd_mes: float = 2.0        # Route 53 + dominio prorrateado; CloudFront dentro de capa gratuita
    licencias_usd_mes: float = 50.0     # repositorio, CI/CD, monitoreo de errores
    factor_ambientes_no_prod: float = 0.30
    soporte_pct_desarrollo: float = 0.15  # mantenimiento anual = 15 % del costo de desarrollo

    horizonte_anios: int = 3
    meses_ciclo_en_anio: tuple = (2, 3, 7, 8)  # feb-mar y jul-ago


# ---------------------------------------------------------------------------
def costo_operador(p: Parametros) -> float:
    return p.costo_mensual_operador or p.smmlv * p.factor_prestacional


def linea_base(p: Parametros) -> dict:
    c = costo_operador(p)
    val = p.validadores_manual * c * p.meses_por_ciclo
    cc = p.agentes_cc_manual * c * p.meses_por_ciclo
    por_ciclo = val + cc
    anual = por_ciclo * p.ciclos_por_anio
    return {
        "costo_trabajador_mes": c,
        "validadores_ciclo": val,
        "contact_center_ciclo": cc,
        "por_ciclo": por_ciclo,
        "anual": anual,
        "tco": anual * p.horizonte_anios,
    }


def volumen(p: Parametros) -> dict:
    docs_ciclo = p.aspirantes_por_ciclo * (1 + p.tasa_reenvio)
    return {
        "aspirantes_anio": p.aspirantes_por_ciclo * p.ciclos_por_anio,
        "documentos_ciclo": docs_ciclo,
        "documentos_anio": docs_ciclo * p.ciclos_por_anio,
    }


def capex(p: Parametros) -> dict:
    equipo_mes = (p.lider_tecnico_mes + p.desarrolladores * p.desarrollador_mes
                  + p.qa_dedicacion * p.qa_mes)
    desarrollo = equipo_mes * p.meses_desarrollo
    subtotal = desarrollo + p.pruebas_carga + p.pruebas_seguridad + p.puesta_produccion
    cont = subtotal * p.contingencia
    return {
        "Desarrollo de software": desarrollo,
        "Pruebas de carga (45.000 radicaciones)": p.pruebas_carga,
        "Pruebas de seguridad / pentest": p.pruebas_seguridad,
        "Puesta en producción y capacitación": p.puesta_produccion,
        "Contingencia": cont,
        "total": subtotal + cont,
        "_desarrollo": desarrollo,
    }


def costo_unitario_usd(p: Parametros) -> dict:
    """Costo variable por documento procesado (USD)."""
    # Lambda: radicación 512 MB·1 s, extracción 256 MB·3 s, reglas 256 MB·0,3 s, notificación 256 MB·0,5 s
    gb_s = 0.5 * 1 + 0.25 * 3 + 0.25 * 0.3 + 0.25 * 0.5
    d = {
        "OCR / IDP (Textract Queries)": t("textract_queries_pagina") * p.paginas_por_documento,
        "Cómputo serverless (Lambda)": gb_s * t("lambda_gb_s") + 4 * t("lambda_solicitud"),
        "Orquestación (Step Functions)": 12 * t("stepfunctions_transicion"),
        "Colas y eventos (SQS + EventBridge)": 3 * t("sqs_solicitud") + 2 * t("eventbridge_evento"),
        "API de radicación (API Gateway)": 5 * t("apigw_solicitud"),
        "Escrituras en almacenamiento (S3 PUT)": 2 * t("s3_put"),
        "WhatsApp Business API": p.mensajes_whatsapp_por_doc * t("whatsapp_utility_co"),
        "Correo transaccional (SES)": p.correos_por_doc * t("ses_correo"),
    }
    d["total"] = sum(d.values())
    return d


def opex_variable_anual(p: Parametros) -> dict:
    v = volumen(p)
    u = costo_unitario_usd(p)
    por_doc = u["total"] * v["documentos_anio"] * p.trm
    # Identidad: MAU en meses de convocatoria (~60 % de aspirantes activos cada mes)
    mau = p.aspirantes_por_ciclo * 0.6
    meses_activos = p.meses_por_ciclo * p.ciclos_por_anio
    cognito = max(0, mau - 10_000) * t("cognito_lite_mau") * meses_activos * p.trm
    # Almacenamiento inmutable: GB acumulados (régimen estable con retención de N años)
    gb_anio = v["documentos_anio"] * p.tamano_pdf_mb / 1024
    gb_prom = gb_anio * min(p.anios_retencion, p.horizonte_anios) / 2 + gb_anio / 2
    s3 = gb_prom * t("s3_gb_mes") * 12 * p.trm
    return {
        "Procesamiento por documento": por_doc,
        "Identidad de aspirantes (Cognito)": cognito,
        "Almacenamiento inmutable (S3 Object Lock)": s3,
        "total": por_doc + cognito + s3,
    }


def opex_fijo_anual(p: Parametros) -> dict:
    meses_pico = p.meses_por_ciclo * p.ciclos_por_anio
    acu_h = (p.aurora_acu_base * 730 * 12
             + max(0, p.aurora_acu_pico - p.aurora_acu_base) * 730 * meses_pico)
    db_usd = acu_h * t("aurora_acu_hora") + p.aurora_gb * t("aurora_gb_mes") * 12
    infra_usd_mes = p.waf_usd_mes + p.kms_secrets_usd_mes + p.monitoreo_usd_mes + p.dns_cdn_usd_mes
    nube_prod = db_usd + infra_usd_mes * 12
    nube = nube_prod * (1 + p.factor_ambientes_no_prod) * p.trm
    licencias = p.licencias_usd_mes * 12 * p.trm
    soporte = capex(p)["_desarrollo"] * p.soporte_pct_desarrollo
    return {
        "Base de datos gestionada (Aurora Serverless v2)": db_usd * (1 + p.factor_ambientes_no_prod) * p.trm,
        "Seguridad, monitoreo y red (WAF, KMS, CloudWatch, DNS)": infra_usd_mes * 12 * (1 + p.factor_ambientes_no_prod) * p.trm,
        "Licencias y herramientas": licencias,
        "Soporte técnico y mantenimiento": soporte,
        "total": nube + licencias + soporte,
    }


def operacion_residual_anual(p: Parametros) -> dict:
    v = volumen(p)
    revisiones_ciclo = v["documentos_ciclo"] * p.tasa_revision_humana
    capacidad = p.productividad_revisor_dia * p.dias_habiles_por_ciclo
    revisores = max(1, math.ceil(revisiones_ciclo / capacidad))
    c = costo_operador(p)
    rev = revisores * c * p.meses_por_ciclo * p.ciclos_por_anio
    mesa = p.agentes_mesa_ayuda * c * p.meses_por_ciclo * p.ciclos_por_anio
    return {
        "revisiones_por_ciclo": revisiones_ciclo,
        "revisores_necesarios": revisores,
        "Validadores de excepciones": rev,
        "Mesa de ayuda (WhatsApp/correo)": mesa,
        "total": rev + mesa,
    }


def flujo_mensual(p: Parametros) -> list[dict]:
    """Flujo de caja mensual: mes 0 = inversión; meses 1..36 operación."""
    lb = linea_base(p)
    var = opex_variable_anual(p)["total"]
    fijo = opex_fijo_anual(p)["total"]
    res = operacion_residual_anual(p)["total"]
    meses_ciclo_anio = len(p.meses_ciclo_en_anio)
    manual_mes_ciclo = lb["anual"] / meses_ciclo_anio
    filas = [{"mes": 0, "manual": 0.0, "solucion": capex(p)["total"]}]
    primer_ciclo_vistos = 0
    for m in range(1, p.horizonte_anios * 12 + 1):
        mes_anio = (m - 1) % 12 + 1
        en_ciclo = mes_anio in p.meses_ciclo_en_anio
        sol = fijo / 12
        manual = 0.0
        if en_ciclo:
            manual = manual_mes_ciclo
            sol += var / meses_ciclo_anio + res / meses_ciclo_anio
            if primer_ciclo_vistos < p.meses_por_ciclo:   # transición: operación paralela
                sol += manual_mes_ciclo * p.fraccion_manual_primer_ciclo
                primer_ciclo_vistos += 1
        filas.append({"mes": m, "manual": manual, "solucion": sol})
    acum_m = acum_s = 0.0
    for f in filas:
        acum_m += f["manual"]
        acum_s += f["solucion"]
        f["acum_manual"] = acum_m
        f["acum_solucion"] = acum_s
        f["beneficio_acum"] = acum_m - acum_s
    return filas


def resumen(p: Parametros) -> dict:
    lb = linea_base(p)
    cx = capex(p)
    fl = flujo_mensual(p)
    tco_sol = fl[-1]["acum_solucion"]
    tco_man = fl[-1]["acum_manual"]
    payback = next((f["mes"] for f in fl if f["mes"] > 0 and f["beneficio_acum"] >= 0), None)
    ahorro = tco_man - tco_sol
    opex_anual = (opex_fijo_anual(p)["total"] + opex_variable_anual(p)["total"]
                  + operacion_residual_anual(p)["total"])
    v = volumen(p)
    return {
        "tco_manual": tco_man,
        "tco_linea_base_tdr": lb["tco"],
        "tco_solucion": tco_sol,
        "ahorro_3_anios": ahorro,
        "reduccion_pct": ahorro / tco_man if tco_man else 0,
        "capex": cx["total"],
        "roi": ahorro / cx["total"] if cx["total"] else 0,
        "payback_mes": payback,
        "opex_anual_regimen": opex_anual,
        "costo_total_por_documento": opex_anual / v["documentos_anio"],
        "costo_manual_por_documento": lb["anual"] / v["aspirantes_anio"],
    }


def comparar_computo(p: Parametros) -> dict:
    """Serverless vs Kubernetes (EKS) — costo anual de la capa de cómputo (USD)."""
    v = volumen(p)
    u = costo_unitario_usd(p)
    serverless = (u["Cómputo serverless (Lambda)"] + u["Orquestación (Step Functions)"]
                  + u["API de radicación (API Gateway)"]) * v["documentos_anio"]
    horas = 730 * 12
    meses_pico = p.meses_por_ciclo * p.ciclos_por_anio
    # EKS: plano de control + 2 nodos base todo el año + 4 nodos extra en picos + ALB + NAT
    k8s = (horas * (t("eks_control_hora") + 2 * t("ec2_t3medium_hora") + t("alb_hora") + t("nat_hora"))
           + 4 * t("ec2_t3medium_hora") * 730 * meses_pico)
    return {"serverless_usd": serverless, "kubernetes_usd": k8s,
            "serverless_cop": serverless * p.trm, "kubernetes_cop": k8s * p.trm}


if __name__ == "__main__":
    p = Parametros()
    import json
    def fmt(d):
        return {k: (round(v) if isinstance(v, float) and abs(v) > 10 else v) for k, v in d.items()}
    print("Línea base", fmt(linea_base(p)))
    print("Volumen", fmt(volumen(p)))
    print("CapEx", fmt(capex(p)))
    print("Unitario USD", {k: round(v, 6) for k, v in costo_unitario_usd(p).items()})
    print("Var", fmt(opex_variable_anual(p)))
    print("Fijo", fmt(opex_fijo_anual(p)))
    print("Residual", fmt(operacion_residual_anual(p)))
    print("Resumen", fmt(resumen(p)))
    print("Cómputo", fmt(comparar_computo(p)))
