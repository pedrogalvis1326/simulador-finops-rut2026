"""
Simulador FinOps — Propuesta de automatización de validación RUT 2026
Licitación privada LP-2026-LOG-001 · Beneficiario final: ICFES
Célula de consultoría: Pedro Pablo Galvis Ríos, Cristian David Bonilla Rojas,
Andrés Juan Ramírez Ropero (Universidad Católica de Colombia)

Ejecutar:   pip install -r requirements.txt
            streamlit run app.py
"""
from dataclasses import replace

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import calculos as c

st.set_page_config(page_title="Simulador FinOps · RUT 2026", page_icon="📊", layout="wide")

AZUL = "#1F4E79"
VERDE = "#2E8B57"
GRIS = "#8C8C8C"
ROJO = "#B03A2E"


def cop(v: float) -> str:
    return "$" + f"{v:,.0f}".replace(",", ".")


def millones(v: float) -> str:
    return f"${v/1e6:,.1f} M".replace(",", "X").replace(".", ",").replace("X", ".")


def tabla(d: dict, col="Valor (COP)") -> pd.DataFrame:
    excluir = {"total", "revisiones_por_ciclo", "revisores_necesarios"}
    filas = [(k, v) for k, v in d.items() if k not in excluir and not k.startswith("_")]
    df = pd.DataFrame(filas, columns=["Concepto", col])
    df.loc[len(df)] = ["TOTAL", d["total"]]
    df[col] = df[col].map(cop)
    return df


def grafico(fig):
    """Compatible con versiones de Streamlit antes y después del retiro de use_container_width."""
    try:
        st.plotly_chart(fig, use_container_width=True)
    except TypeError:
        st.plotly_chart(fig, width="stretch")


def tabla_ui(df):
    try:
        st.dataframe(df, hide_index=True, use_container_width=True)
    except TypeError:
        st.dataframe(df, hide_index=True, width="stretch")


# ---------------------------------------------------------------------------
# Parámetros
# ---------------------------------------------------------------------------
base = c.Parametros()
st.sidebar.title("Parámetros")
st.sidebar.caption("Los valores por defecto son los del caso. Muévalos para ver la sensibilidad.")

with st.sidebar.expander("Línea base As-Is (Términos de Referencia 2.3)", expanded=False):
    smmlv = st.number_input("SMMLV 2026 (COP)", value=int(base.smmlv), step=50_000)
    factor = st.number_input("Factor prestacional", value=base.factor_prestacional, step=0.05)
    asp = st.number_input("Aspirantes por convocatoria", value=base.aspirantes_por_ciclo, step=1_000)
    st.caption("10 validadores + 4 agentes · 2 meses · 2 convocatorias/año")

with st.sidebar.expander("Volumen y operación To-Be", expanded=True):
    trm = st.number_input("TRM (COP/USD)", value=int(base.trm), step=50,
                          help="TRM del 18-nov-2026: $3.309,55")
    reenvio = st.slider("Tasa de reenvío por subsanación", 0.0, 0.6, base.tasa_reenvio, 0.05)
    revision = st.slider("Casos a revisión humana", 0.0, 0.5, base.tasa_revision_humana, 0.01,
                         help="Baja confianza OCR, casilla 23 no hallada, código 48, CIIU en alerta")
    prod = st.number_input("Revisiones por persona/día", value=base.productividad_revisor_dia, step=10)
    mesa = st.number_input("Agentes de mesa de ayuda", value=base.agentes_mesa_ayuda, step=1, min_value=0)
    wa = st.number_input("Mensajes WhatsApp por documento", value=base.mensajes_whatsapp_por_doc, step=0.1)
    paralelo = st.slider("Operación manual en paralelo en el 1.er ciclo", 0.0, 1.0,
                         base.fraccion_manual_primer_ciclo, 0.1,
                         help="Transición gradual (TOGAF fase F): se mantiene parte del equipo manual")

with st.sidebar.expander("CapEx (COP costo empresa)", expanded=False):
    meses_dev = st.number_input("Meses de desarrollo", value=base.meses_desarrollo, step=1, min_value=1)
    lider = st.number_input("Líder técnico / arquitecto (mes)", value=int(base.lider_tecnico_mes), step=500_000)
    ndev = st.number_input("Desarrolladores", value=base.desarrolladores, step=1, min_value=1)
    dev = st.number_input("Desarrollador (mes)", value=int(base.desarrollador_mes), step=500_000)
    carga = st.number_input("Pruebas de carga", value=int(base.pruebas_carga), step=500_000)
    seg = st.number_input("Pruebas de seguridad", value=int(base.pruebas_seguridad), step=500_000)
    prodn = st.number_input("Puesta en producción", value=int(base.puesta_produccion), step=500_000)
    cont = st.slider("Contingencia", 0.0, 0.3, base.contingencia, 0.05)

with st.sidebar.expander("OpEx fijo", expanded=False):
    acu_pico = st.number_input("ACU promedio en picos (Aurora)", value=base.aurora_acu_pico, step=0.5)
    soporte = st.slider("Soporte anual (% del desarrollo)", 0.0, 0.3, base.soporte_pct_desarrollo, 0.01)
    lic = st.number_input("Licencias y herramientas (USD/mes)", value=base.licencias_usd_mes, step=10.0)
    noprod = st.slider("Sobrecosto ambientes dev/staging", 0.0, 1.0, base.factor_ambientes_no_prod, 0.05)

p = replace(base, smmlv=smmlv, factor_prestacional=factor, aspirantes_por_ciclo=int(asp), trm=trm,
            tasa_reenvio=reenvio, tasa_revision_humana=revision, productividad_revisor_dia=int(prod),
            agentes_mesa_ayuda=int(mesa), mensajes_whatsapp_por_doc=wa, fraccion_manual_primer_ciclo=paralelo,
            meses_desarrollo=int(meses_dev), lider_tecnico_mes=lider, desarrolladores=int(ndev),
            desarrollador_mes=dev, pruebas_carga=carga, pruebas_seguridad=seg, puesta_produccion=prodn,
            contingencia=cont, aurora_acu_pico=acu_pico, soporte_pct_desarrollo=soporte,
            licencias_usd_mes=lic, factor_ambientes_no_prod=noprod)

lb = c.linea_base(p)
vol = c.volumen(p)
cx = c.capex(p)
uni = c.costo_unitario_usd(p)
var = c.opex_variable_anual(p)
fijo = c.opex_fijo_anual(p)
res = c.operacion_residual_anual(p)
r = c.resumen(p)
flujo = pd.DataFrame(c.flujo_mensual(p))

# ---------------------------------------------------------------------------
# Encabezado y KPI
# ---------------------------------------------------------------------------
st.title("Simulador FinOps · Validación automatizada de RUT 2026")
st.caption("LP-2026-LOG-001 · Consorcio Operador Logístico → ICFES · Horizonte de 3 años · Cifras en COP")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("TCO manual (3 años)", millones(r["tco_manual"]))
k2.metric("TCO solución (3 años)", millones(r["tco_solucion"]),
          delta=f"-{r['reduccion_pct']*100:.1f} %", delta_color="inverse")
k3.metric("CapEx", millones(r["capex"]))
k4.metric("ROI a 3 años", f"{r['roi']*100:.0f} %")
k5.metric("Payback", f"Mes {r['payback_mes']}" if r["payback_mes"] else "No se recupera")

st.caption(f"ROI = (TCO manual − TCO solución) ÷ CapEx · Payback = primer mes con beneficio acumulado ≥ 0, "
           f"contando el mes 0 como la inversión.")

tabs = st.tabs(["TCO y payback", "CapEx", "OpEx fijo", "Costo por documento",
                "Operación residual", "Serverless vs Kubernetes", "Supuestos y fuentes"])

# --- TCO y payback ---------------------------------------------------------
with tabs[0]:
    a, b = st.columns([3, 2])
    with a:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=flujo["mes"], y=flujo["acum_manual"] / 1e6, name="Manual (As-Is)",
                                 line=dict(color=GRIS, width=3)))
        fig.add_trace(go.Scatter(x=flujo["mes"], y=flujo["acum_solucion"] / 1e6, name="Solución (To-Be)",
                                 line=dict(color=AZUL, width=3)))
        if r["payback_mes"]:
            fig.add_vline(x=r["payback_mes"], line_dash="dash", line_color=VERDE,
                          annotation_text=f"Payback mes {r['payback_mes']}", annotation_position="top left")
        fig.update_layout(title="Costo acumulado (millones COP)", xaxis_title="Mes", yaxis_title="M COP",
                          height=420, legend=dict(orientation="h", y=-0.2), margin=dict(t=50, b=10))
        grafico(fig)
    with b:
        fig2 = go.Figure(go.Bar(
            x=["Manual", "Solución"], y=[r["tco_manual"] / 1e6, r["tco_solucion"] / 1e6],
            marker_color=[GRIS, AZUL],
            text=[millones(r["tco_manual"]), millones(r["tco_solucion"])], textposition="outside"))
        fig2.update_layout(title="TCO a 3 años", yaxis_title="M COP", height=420, margin=dict(t=50, b=10))
        grafico(fig2)

    fig3 = go.Figure(go.Bar(x=flujo["mes"], y=flujo["beneficio_acum"] / 1e6,
                            marker_color=[VERDE if v >= 0 else ROJO for v in flujo["beneficio_acum"]]))
    fig3.update_layout(title="Curva de recuperación: beneficio neto acumulado (M COP)", xaxis_title="Mes",
                       height=320, margin=dict(t=50, b=10))
    grafico(fig3)
    st.info("Los escalones aparecen en los meses de convocatoria (feb-mar y jul-ago): ahí es donde se "
            "deja de pagar la nómina manual. El primer ciclo incluye operación manual en paralelo "
            f"al {paralelo*100:.0f} % como medida de transición.")

# --- CapEx -----------------------------------------------------------------
with tabs[1]:
    st.subheader("Inversión inicial (CapEx)")
    tabla_ui(tabla(cx))
    st.caption("Equipo: líder técnico + desarrolladores + QA a media dedicación, costo empresa mensual. "
               "El CapEx es un gasto único en el mes 0; no se repite en los años siguientes.")

# --- OpEx fijo ---------------------------------------------------------------
with tabs[2]:
    st.subheader("OpEx fijo anual (se paga haya o no convocatoria)")
    tabla_ui(tabla(fijo))
    st.caption("Aurora Serverless v2: 0,5 ACU todo el año y subida a ACU de pico solo en los 4 meses de "
               "convocatoria. Soporte = 15 % anual del costo de desarrollo (práctica común de mantenimiento).")

# --- Costo por documento -----------------------------------------------------
with tabs[3]:
    st.subheader("OpEx variable: costo unitario por documento procesado")
    filas = [(k, v, v * p.trm) for k, v in uni.items() if k != "total"]
    df = pd.DataFrame(filas, columns=["Componente", "USD", "COP"])
    tot_usd = uni["total"]
    fig4 = go.Figure(go.Bar(y=df["Componente"], x=df["COP"], orientation="h", marker_color=AZUL,
                            text=[f"{v:,.2f}" for v in df["COP"]], textposition="outside"))
    fig4.update_layout(title=f"COP por documento · total {tot_usd*p.trm:,.1f} COP (USD {tot_usd:.4f})",
                       height=380, margin=dict(t=50, l=10))
    grafico(fig4)
    df["USD"] = df["USD"].map(lambda v: f"{v:.6f}")
    df["COP"] = df["COP"].map(lambda v: f"{v:,.2f}")
    tabla_ui(df)
    a, b, cc = st.columns(3)
    a.metric("Documentos procesados/año", f"{vol['documentos_anio']:,.0f}".replace(",", "."))
    b.metric("Costo total por documento (To-Be)", cop(r["costo_total_por_documento"]),
             help="Incluye fijo, variable y operación residual")
    cc.metric("Costo por aspirante (As-Is)", cop(r["costo_manual_por_documento"]))
    st.subheader("OpEx variable anual")
    tabla_ui(tabla(var))

# --- Operación residual ------------------------------------------------------
with tabs[4]:
    st.subheader("Personal que se conserva (no todo se automatiza)")
    a, b = st.columns(2)
    a.metric("Revisiones humanas por ciclo", f"{res['revisiones_por_ciclo']:,.0f}".replace(",", "."))
    b.metric("Validadores necesarios", res["revisores_necesarios"])
    tabla_ui(tabla(res))
    st.caption("Se pasa de 14 personas por ciclo a "
               f"{res['revisores_necesarios'] + p.agentes_mesa_ayuda}. La revisión humana solo atiende "
               "excepciones con el campo marcado, por eso la productividad es mayor que los 110 RUT/día manuales.")

# --- Serverless vs Kubernetes ------------------------------------------------
with tabs[5]:
    cmp = c.comparar_computo(p)
    st.subheader("Capa de cómputo: Serverless vs Kubernetes (EKS)")
    fig5 = go.Figure(go.Bar(x=["Serverless (Lambda + Step Functions)", "Kubernetes (EKS)"],
                            y=[cmp["serverless_cop"] / 1e6, cmp["kubernetes_cop"] / 1e6],
                            marker_color=[AZUL, GRIS],
                            text=[millones(cmp["serverless_cop"]), millones(cmp["kubernetes_cop"])],
                            textposition="outside"))
    fig5.update_layout(title="Costo anual de cómputo (M COP)", height=380, margin=dict(t=50))
    grafico(fig5)
    st.markdown(
        "- La demanda tiene **2 picos de 45.000 aspirantes** y 8 meses de casi cero uso.\n"
        "- Serverless cobra por invocación: en los meses sin convocatoria el cómputo cuesta casi $0.\n"
        "- EKS mantiene plano de control, nodos base, balanceador y NAT encendidos los 12 meses.\n"
        "- Trade-off aceptado: límites de tiempo de ejecución (15 min en Lambda) y arranques en frío; "
        "ninguno afecta un pipeline asíncrono de documentos de una página.")

# --- Supuestos y fuentes -----------------------------------------------------
with tabs[6]:
    st.subheader("Tarifas utilizadas")
    tabla_ui(pd.DataFrame([(k, v[0], v[1]) for k, v in c.TARIFAS_USD.items()],
                              columns=["Clave", "USD", "Fuente"]))
    st.subheader("Supuestos del equipo")
    st.markdown(
        f"- TRM {cop(p.trm)} por USD (TRM del 18-nov-2026: $3.309,55).\n"
        f"- {p.tasa_reenvio*100:.0f} % de aspirantes subsana y vuelve a cargar (cada reenvío se procesa de nuevo).\n"
        "- Solo la hoja principal del RUT se envía a Textract (1 página por documento).\n"
        f"- {p.tasa_revision_humana*100:.0f} % de los documentos va a revisión humana.\n"
        "- Convocatorias en feb-mar y jul-ago; el horizonte de 3 años empieza en enero.\n"
        "- Línea base manual tomada literalmente de los Términos de Referencia: $168 M/año, $504 M a 3 años.\n"
        "- Las tarifas cloud se deben revisar en la AWS Pricing Calculator antes de una oferta real.")
