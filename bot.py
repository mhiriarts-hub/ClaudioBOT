import os
import json
import logging
import re
from datetime import datetime
import pytz

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TZ = pytz.timezone("America/Santiago")
OCIO_MENSUAL = 353000
DATOS_FILE = "/tmp/gastos_martin.json"
CUOTAS_FILE = "/tmp/cuotas_martin.json"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Helpers ────────────────────────────────────────────────────────────────────
def extraer_monto(texto):
    match = re.search(r"(\d[\d\.]*)\s*$", texto)
    if match:
        try:
            return int(match.group(1).replace(".", ""))
        except:
            return 0
    return 0

def estado_saldo(disponible):
    if disponible > 200000:
        return "Verde - Vas bien"
    elif disponible > 80000:
        return "Amarillo - Con cuidado"
    else:
        return "Rojo - Sin margen"

# ── Sistema de saldo (disponible) ──────────────────────────────────────────────
def cargar_datos():
    try:
        if os.path.exists(DATOS_FILE):
            with open(DATOS_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {"mes": "", "disponible": OCIO_MENSUAL, "detalle": []}

def guardar_datos(data):
    try:
        with open(DATOS_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False)
    except:
        pass

def obtener_datos_mes():
    now = datetime.now(TZ)
    mes_actual = now.strftime("%Y-%m")
    data = cargar_datos()
    if data.get("mes") != mes_actual:
        data = {"mes": mes_actual, "disponible": OCIO_MENSUAL, "detalle": []}
        guardar_datos(data)
    return data

def registrar_gasto(descripcion, monto):
    now = datetime.now(TZ)
    data = obtener_datos_mes()
    data["disponible"] = max(0, data["disponible"] - monto)
    data["detalle"].append({
        "desc": descripcion,
        "monto": -monto,
        "fecha": now.strftime("%d/%m %H:%M")
    })
    guardar_datos(data)
    return data

# ── Sistema de cuotas ──────────────────────────────────────────────────────────
def cargar_cuotas():
    try:
        if os.path.exists(CUOTAS_FILE):
            with open(CUOTAS_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {"cuotas": []}

def guardar_cuotas(data):
    try:
        with open(CUOTAS_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False)
    except:
        pass

def cuota_mensual_total():
    """Suma el total mensual comprometido en cuotas activas."""
    now = datetime.now(TZ)
    mes_actual = now.strftime("%Y-%m")
    data = cargar_cuotas()
    total = 0
    for c in data["cuotas"]:
        if c["cuotas_restantes"] > 0 and c["mes_inicio"] <= mes_actual:
            total += c["monto_cuota"]
    return total

def avanzar_cuotas():
    """Descuenta una cuota del mes a todas las deudas activas. Se llama el dia 1."""
    now = datetime.now(TZ)
    mes_actual = now.strftime("%Y-%m")
    data = cargar_cuotas()
    for c in data["cuotas"]:
        if c["cuotas_restantes"] > 0 and c["mes_inicio"] <= mes_actual:
            c["cuotas_restantes"] -= 1
    # Limpiar las que ya terminaron
    data["cuotas"] = [c for c in data["cuotas"] if c["cuotas_restantes"] > 0]
    guardar_cuotas(data)

# ── Recordatorios ──────────────────────────────────────────────────────────────
ONE_TIME_REMINDERS = [
    {"date": "2026-05-07 09:00:00", "message": "ACCION URGENTE - ESPP Uber\n\nAyer salieron los earnings de Uber. El blackout probablemente se levanto.\n\n1. Entra a Shareworks (via Okta)\n2. Ve a ESPP > Contribuciones\n3. Cambia de 5% a 15%\n\nLa ventana puede cerrar en pocos dias. Hazlo hoy."},
    {"date": "2026-05-20 09:00:00", "message": "HOY ES PURCHASE DATE - ESPP Uber\n\nHoy Uber compra tus acciones con el descuento del 15%.\n\n1. Entra a Shareworks ahora\n2. Vende TODAS tus acciones (las nuevas + las 42 existentes)\n3. No las guardes mas de 24 horas\n\nGanancia esperada: ~$130.000 CLP minimo garantizado.\nGuarda los USD - el bono llega en unos dias y distribuyes todo junto."},
    {"date": "2026-05-21 09:00:00", "message": "Vendiste las acciones Uber ayer?\n\nSi aun no lo has hecho, entra a Shareworks y vendelas hoy.\nCada dia que las guardas es riesgo innecesario."},
    {"date": "2026-05-28 09:00:00", "message": "BONO TRIMESTRAL Q1 - Plan de distribucion exacto\n\nCon el bono (~$1.500.000) + lo del ESPP Uber:\n\nPASO 1 - Tarjeta de credito (PRIMERO)\nQuedan ~$3.200.000 pendientes (ya abonaste $500.000).\nRetira $3.200.000 de Fintual y paga la tarjeta completa HOY.\n\nPASO 2 - Reponer Fintual\n$1.232.000 del bono van a Fintual\n\nPASO 3 - Primer deposito APV Regimen A\n$268.000 del bono van a APV en Fintual\n\nPASO 4 - Llamar a Security/BICE\nPide rescatar todos tus fondos mutuos ($2.214.376) y moverlos a Fintual.\n\nTarjeta = CERO. APV activo. Sistema listo."},
    {"date": "2026-06-01 09:00:00", "message": "Activar sistema automatico - Junio\n\n1. APV Regimen A: Debito automatico $232.000/mes en Fintual\n2. Fondo matrimonio: Cuenta separada $167.000/mes\n3. Tarjeta: Solo usarla si puedes pagar el total a fin de mes\n\nUna vez configurado, el sistema trabaja solo."},
    {"date": "2026-06-28 09:00:00", "message": "Revision fin de mes - Junio\n\n- Se descontaron $232.000 de APV automatico?\n- Transferiste $167.000 al fondo matrimonio?\n- Tarjeta de credito en cero?\n- Fintual creciendo sin tocar?\n- Llamaste a Security/BICE para rescatar los fondos mutuos?\n\nSi algo fallo, trae los numeros a Claude y ajustamos."},
    {"date": "2026-08-26 09:00:00", "message": "BONO TRIMESTRAL Q2 - Ya llego?\n\nCuando llegue el bono (~$1.500.000):\n\n1. Fondo matrimonio: $500.000 (llevaras ~$667.000, meta $2.000.000)\n2. Fintual: $800.000\n3. APV extra: $200.000\n\nFaltan 2 bonos mas para cubrir el matrimonio."},
    {"date": "2026-11-10 09:00:00", "message": "DOS COSAS IMPORTANTES esta semana\n\n1. ESPP Uber - Purchase Date el 20 nov (en 10 dias)\n   - Prepárate para vender TODO el 20 de noviembre\n   - Confirma que tu % sigue en 15% en Shareworks\n\n2. Bono Q3 llega ~28 nov:\n   - $500.000 al fondo matrimonio (llevaras ~$1.167.000)\n   - $1.000.000 a Fintual"},
    {"date": "2026-11-20 09:00:00", "message": "HOY - 2da Purchase Date ESPP Uber\n\n1. Entra a Shareworks y vende TODO hoy\n2. Ganancia minima estimada: ~$370.000 CLP\n3. Transfiere a Fintual\n\nLuego evalua si mantener 15% para el siguiente periodo (mayo 2027)."},
    {"date": "2026-11-28 09:00:00", "message": "BONO TRIMESTRAL Q3 - Distribucion\n\n1. Fondo matrimonio: $500.000 (llevas ~$1.167.000, meta $2.000.000)\n2. Fintual: $1.000.000\n\nFalta 1 bono mas para cubrir el matrimonio completamente."},
    {"date": "2027-01-10 09:00:00", "message": "Matrimonio en 41 dias (20 febrero 2027)\n\nChecklist:\n- Tienes los $2.000.000 en cuenta separada?\n- Tienes colchon para imprevistos (+$300.000)?\n- El APV sigue corriendo automatico?\n- Fintual no fue tocado?\n- Tarjeta de credito en cero?"},
    {"date": "2027-02-21 09:00:00", "message": "Felicitaciones! Post-matrimonio - Resetear el plan\n\n1. Cuanto quedo del fondo matrimonio? Va a Fintual\n2. Conversa con tu pareja sobre finanzas compartidas\n3. Los $167.000 del fondo matrimonio ahora van al APV o Fintual\n4. Ven a hablar con Claude para ajustar el plan\n\nEl plan de jubilacion sigue corriendo!"},
    {"date": "2027-02-26 09:00:00", "message": "BONO TRIMESTRAL Q4\n\n1. Completar fondo matrimonio si falta algo\n2. TODO el resto va a Fintual\n\nDe aqui en adelante el 100% del ahorro va al portafolio largo plazo."},
]

MONTHLY_MESSAGE = (
    "Revision mensual de tu portafolio\n\n"
    "1. Cuanto tienes en Fintual hoy?\n"
    "2. El APV de $232.000 se desconto correctamente?\n"
    "3. El fondo matrimonio sumo $167.000?\n"
    "4. Alguna deuda nueva o gasto inesperado?\n"
    "5. Tarjeta de credito en cero?\n\n"
    "Trae estos numeros a Claude y te digo si estas en camino."
)

# ── Comandos ───────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"Hola Martin!\n\n"
        f"Soy tu bot de planificacion financiera.\n"
        f"Tu Chat ID es: {chat_id}\n\n"
        f"Escribe / para ver todos los comandos disponibles."
    )

async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ)
    cuotas_mes = cuota_mensual_total()
    await update.message.reply_text(
        f"Estado de tu plan - {now.strftime('%B %Y')}\n\n"
        f"METAS:\n"
        f"- Independencia financiera (55 anos): $320.000.000\n"
        f"- Retiro total (70 anos): $857.000.000\n\n"
        f"SISTEMA AUTOMATICO:\n"
        f"- APV Regimen A: $232.000/mes\n"
        f"- Fondo matrimonio: $167.000/mes\n"
        f"- ESPP Uber: 15% del sueldo\n\n"
        f"COMPROMISOS EN CUOTAS:\n"
        f"- Total cuotas activas este mes: ${cuotas_mes:,}\n\n"
        f"PROXIMAS FECHAS:\n"
        f"- 7 mayo: Subir ESPP a 15%\n"
        f"- 20 mayo: Vender acciones Uber\n"
        f"- 28 mayo: Bono Q1 - pagar tarjeta\n"
        f"- 20 feb 2027: Matrimonio"
    )

async def presupuesto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = obtener_datos_mes()
    disponible = data["disponible"]
    gastado = OCIO_MENSUAL - disponible
    cuotas_mes = cuota_mensual_total()
    await update.message.reply_text(
        f"Distribucion del sueldo ($2.070.000)\n\n"
        f"GASTOS FIJOS:\n"
        f"- Arriendo:          $1.050.000\n"
        f"- APV Regimen A:       $232.000\n"
        f"- Fondo matrimonio:    $167.000\n"
        f"- Alimentacion:        $200.000\n"
        f"- Transporte/misc:      $63.000\n"
        f"- TOTAL FIJOS:       $1.712.000\n\n"
        f"OCIO DEL MES:\n"
        f"- Presupuesto:    ${OCIO_MENSUAL:,}\n"
        f"- Gastado:        ${gastado:,}\n"
        f"- En cuotas/mes:  ${cuotas_mes:,}\n"
        f"- DISPONIBLE:     ${disponible:,}\n\n"
        f"Usa /saldo para el detalle de gastos.\n"
        f"Usa /miscuotas para ver cuotas activas."
    )

async def proximos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ)
    upcoming = []
    for r in ONE_TIME_REMINDERS:
        dt = TZ.localize(datetime.strptime(r["date"], "%Y-%m-%d %H:%M:%S"))
        if dt > now:
            days_left = (dt.date() - now.date()).days
            upcoming.append((dt, days_left, r["message"]))
    upcoming.sort(key=lambda x: x[0])
    text = "Proximos recordatorios:\n\n"
    for dt, days, msg in upcoming[:5]:
        first_line = msg.split("\n")[0].strip()
        date_str = dt.strftime("%d/%m/%Y")
        text += f"- {date_str} ({days} dias)\n  {first_line}\n\n"
    if not upcoming:
        text += "No hay recordatorios pendientes."
    await update.message.reply_text(text)

async def checklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ)
    month = now.month
    checklists = {
        5: "Checklist Mayo 2026\n\n[ ] Abonar $500.000 a la tarjeta\n[ ] Subir ESPP a 15% en Shareworks\n[ ] Vender TODAS las acciones Uber el 20/5\n[ ] Con el bono 28/5: pagar tarjeta + APV + Fintual\n[ ] Llamar a Security/BICE para rescatar fondos mutuos",
        6: "Checklist Junio 2026\n\n[ ] Activar APV automatico $232.000/mes\n[ ] Abrir cuenta separada matrimonio\n[ ] Transferencia $167.000/mes matrimonio\n[ ] Confirmar ESPP en 15%\n[ ] Confirmar fondos Security/BICE movidos a Fintual",
        8: "Checklist Agosto 2026\n\n[ ] Bono Q2 llega ~28 agosto\n[ ] $500.000 al fondo matrimonio\n[ ] $800.000 a Fintual\n[ ] $200.000 extra al APV",
        11: "Checklist Noviembre 2026\n\n[ ] Vender acciones Uber ESPP el 20/11\n[ ] Bono Q3 llega ~28 noviembre\n[ ] $500.000 al fondo matrimonio\n[ ] $1.000.000 a Fintual",
    }
    msg = checklists.get(month, "Checklist mensual\n\n[ ] Revisar saldo Fintual\n[ ] Confirmar descuento APV\n[ ] Revisar saldo fondo matrimonio\n[ ] Tarjeta en cero?\n[ ] Alguna deuda nueva?")
    await update.message.reply_text(msg)

async def consulta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ)
    month = now.month
    day = now.day
    args = context.args
    texto = " ".join(args) if args else ""

    if not texto:
        await update.message.reply_text(
            "Como usar /consulta:\n\n"
            "Al contado:\n"
            "/consulta zapatillas 80000\n\n"
            "En cuotas sin interes:\n"
            "/consulta zapatillas 80000 6cuotas\n\n"
            "Si lo compras:\n"
            "/gaste descripcion monto (contado)\n"
            "/cuotas descripcion monto ncuotas (cuotas)\n\n"
            "Ver saldo: /saldo\n"
            "Ver cuotas: /miscuotas"
        )
        return

    # Detectar si viene con cuotas
    cuotas_match = re.search(r"(\d+)\s*cuotas?", texto, re.IGNORECASE)
    n_cuotas = int(cuotas_match.group(1)) if cuotas_match else 0
    texto_limpio = re.sub(r"\d+\s*cuotas?", "", texto, flags=re.IGNORECASE).strip()

    monto_total = extraer_monto(texto_limpio)
    descripcion = re.sub(r"[\$]?\s*\d[\d\.]*\s*$", "", texto_limpio).strip() or "compra"

    data = obtener_datos_mes()
    disponible = data["disponible"]
    cuotas_activas = cuota_mensual_total()

    alerta_extra = ""
    if month == 5 and day < 28:
        alerta_extra = "\nALERTA MAYO: Tarjeta aun no pagada. Se conservador."

    # Logica segun contado vs cuotas
    if n_cuotas > 0 and monto_total > 0:
        cuota = monto_total // n_cuotas
        impacto_hoy = cuota

        if cuotas_activas + cuota > 150000:
            riesgo_cuotas = "ALTO - Tienes muchas cuotas activas. Cuidado."
        elif cuotas_activas + cuota > 80000:
            riesgo_cuotas = "MODERADO - El compromiso mensual va subiendo."
        else:
            riesgo_cuotas = "BAJO - Cabe bien en el presupuesto."

        if impacto_hoy <= disponible * 0.3:
            emoji, resp = "SI", "PUEDES EN CUOTAS"
            detalle = f"La cuota mensual de ${cuota:,} cabe bien en tu ocio disponible (${disponible:,})."
        elif impacto_hoy <= disponible * 0.6:
            emoji, resp = "CUIDADO", "PUEDES PERO AJUSTADO"
            detalle = f"La cuota de ${cuota:,}/mes es manejable pero reduce bastante tu margen."
        else:
            emoji, resp = "NO IDEAL", "LA CUOTA ES ALTA"
            detalle = f"La cuota de ${cuota:,}/mes consume mucho de tu disponible (${disponible:,})."

        await update.message.reply_text(
            f"{emoji} - {resp}\n\n"
            f"Descripcion: {descripcion}\n"
            f"Precio total: ${monto_total:,}\n"
            f"Cuotas: {n_cuotas} x ${cuota:,}/mes\n\n"
            f"{detalle}\n"
            f"{alerta_extra}\n\n"
            f"--- Impacto en tu presupuesto ---\n"
            f"Disponible ahora: ${disponible:,}\n"
            f"Cuotas ya activas/mes: ${cuotas_activas:,}\n"
            f"Esta cuota nueva/mes: ${cuota:,}\n"
            f"Total comprometido/mes: ${cuotas_activas + cuota:,}\n\n"
            f"Riesgo cuotas: {riesgo_cuotas}\n\n"
            f"Si lo compras en cuotas:\n"
            f"/cuotas {descripcion} {monto_total} {n_cuotas}"
        )

    elif monto_total > 0:
        if monto_total <= 15000:
            emoji, resp, detalle = "SI", "SIN PROBLEMA", f"${monto_total:,} es un gasto chico."
        elif monto_total <= disponible * 0.4:
            emoji, resp, detalle = "SI", "PUEDES", f"Te quedarian ${disponible - monto_total:,} para el resto del mes."
        elif monto_total <= disponible:
            emoji, resp, detalle = "CUIDADO", "ES EL LIMITE", f"Consume casi todo tu disponible (${disponible:,}). Nada mas despues."
        elif monto_total <= disponible + 50000:
            emoji, resp, detalle = "NO IDEAL", "PASAS POR POCO", f"Supera tu disponible (${disponible:,}) por poco."
        elif monto_total <= 500000:
            emoji, resp, detalle = "NO", "ESPERA AL BONO", f"Pagalo con el bono trimestral (~28 del mes)."
        else:
            emoji, resp, detalle = "NO", "NO ESTA EN EL PLAN", f"Conversalo con Claude primero."

        await update.message.reply_text(
            f"{emoji} - {resp}\n\n"
            f"Descripcion: {descripcion}\n"
            f"Monto: ${monto_total:,}\n\n"
            f"{detalle}"
            f"{alerta_extra}\n\n"
            f"Disponible ahora: ${disponible:,} de ${OCIO_MENSUAL:,}\n\n"
            f"Si lo compras al contado: /gaste {descripcion} {monto_total}\n"
            f"Si prefieres cuotas: /consulta {descripcion} {monto_total} 6cuotas"
        )
    else:
        await update.message.reply_text(
            "No detecte el monto. Ejemplos:\n\n"
            "/consulta zapatillas 80000\n"
            "/consulta zapatillas 80000 6cuotas"
        )

async def gaste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    texto = " ".join(args) if args else ""
    if not texto:
        await update.message.reply_text("Uso: /gaste descripcion monto\nEjemplo: /gaste cena 35000")
        return
    monto = extraer_monto(texto)
    descripcion = re.sub(r"[\$]?\s*\d[\d\.]*\s*$", "", texto).strip() or "gasto"
    if monto == 0:
        await update.message.reply_text("No detecte el monto.\nEjemplo: /gaste cena 35000")
        return
    data = registrar_gasto(descripcion, monto)
    disponible = data["disponible"]
    await update.message.reply_text(
        f"Registrado!\n\n"
        f"Gasto: {descripcion} - ${monto:,}\n\n"
        f"Te quedan: ${disponible:,} de ${OCIO_MENSUAL:,}\n\n"
        f"{estado_saldo(disponible)}"
    )

async def cuotas_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    texto = " ".join(args) if args else ""
    if not texto:
        await update.message.reply_text(
            "Uso: /cuotas descripcion monto ncuotas\n"
            "Ejemplo: /cuotas zapatillas 80000 6\n\n"
            "Registra una compra en cuotas sin interes.\n"
            "El bot trackea cuantas cuotas te quedan cada mes."
        )
        return

    # Extraer numero de cuotas (ultimo numero)
    numeros = re.findall(r"\d[\d\.]*", texto)
    if len(numeros) < 2:
        await update.message.reply_text("Necesito el monto total y el numero de cuotas.\nEjemplo: /cuotas zapatillas 80000 6")
        return

    try:
        n_cuotas = int(numeros[-1])
        monto_total = int(numeros[-2].replace(".", ""))
    except:
        await update.message.reply_text("No pude leer los numeros.\nEjemplo: /cuotas zapatillas 80000 6")
        return

    descripcion = re.sub(r"[\$\s]*\d[\d\.]*", "", texto).strip() or "compra en cuotas"
    cuota = monto_total // n_cuotas
    now = datetime.now(TZ)

    data = cargar_cuotas()
    data["cuotas"].append({
        "desc": descripcion,
        "monto_total": monto_total,
        "monto_cuota": cuota,
        "n_cuotas": n_cuotas,
        "cuotas_restantes": n_cuotas,
        "mes_inicio": now.strftime("%Y-%m"),
        "fecha": now.strftime("%d/%m/%Y")
    })
    guardar_cuotas(data)

    total_cuotas_mes = cuota_mensual_total()
    await update.message.reply_text(
        f"Cuotas registradas!\n\n"
        f"Compra: {descripcion}\n"
        f"Total: ${monto_total:,}\n"
        f"Cuotas: {n_cuotas} x ${cuota:,}/mes\n\n"
        f"--- Impacto en tu presupuesto ---\n"
        f"Total comprometido en cuotas/mes: ${total_cuotas_mes:,}\n\n"
        f"El bot te recordara cada mes cuanto te queda.\n"
        f"Usa /miscuotas para ver todas tus cuotas activas."
    )

async def miscuotas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = cargar_cuotas()
    cuotas = data.get("cuotas", [])
    now = datetime.now(TZ)
    mes_actual = now.strftime("%Y-%m")

    activas = [c for c in cuotas if c["cuotas_restantes"] > 0 and c["mes_inicio"] <= mes_actual]

    if not activas:
        await update.message.reply_text(
            "No tienes cuotas activas registradas.\n\n"
            "Para registrar una compra en cuotas:\n"
            "/cuotas descripcion monto ncuotas\n"
            "Ejemplo: /cuotas zapatillas 80000 6"
        )
        return

    total_mes = sum(c["monto_cuota"] for c in activas)
    texto = "Tus cuotas activas:\n\n"
    for c in activas:
        pagadas = c["n_cuotas"] - c["cuotas_restantes"]
        texto += (
            f"- {c['desc']}\n"
            f"  ${c['monto_cuota']:,}/mes | {c['cuotas_restantes']} cuotas restantes ({pagadas}/{c['n_cuotas']} pagadas)\n\n"
        )
    texto += f"TOTAL COMPROMETIDO/MES: ${total_mes:,}\n\n"

    if total_mes > 150000:
        texto += "Alerta: Tienes muchas cuotas activas. Cuidado con nuevas compras."
    elif total_mes > 80000:
        texto += "Nivel moderado de cuotas. Evalua antes de agregar mas."
    else:
        texto += "Nivel bajo de cuotas. Bien controlado."

    await update.message.reply_text(texto)

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = obtener_datos_mes()
    disponible = data["disponible"]
    gastado = OCIO_MENSUAL - disponible
    detalle = data.get("detalle", [])
    cuotas_mes = cuota_mensual_total()

    porcentaje = min(100, int((gastado / OCIO_MENSUAL) * 100))
    bloques = porcentaje // 10
    barra = "[" + "=" * bloques + "-" * (10 - bloques) + f"] {porcentaje}% usado"

    historial = "\n\nUltimos movimientos:\n"
    if detalle:
        for g in detalle[-5:]:
            historial += f"- {g['fecha']}: {g['desc']} ${abs(g['monto']):,}\n"
    else:
        historial = "\n\nAun no has registrado gastos este mes."

    await update.message.reply_text(
        f"Saldo de ocio - {now_str()}\n\n"
        f"{barra}\n\n"
        f"Presupuesto total: ${OCIO_MENSUAL:,}\n"
        f"Gastado:          ${gastado:,}\n"
        f"DISPONIBLE:       ${disponible:,}\n"
        f"Cuotas/mes:       ${cuotas_mes:,}\n\n"
        f"{estado_saldo(disponible)}"
        f"{historial}\n\n"
        f"Ver cuotas activas: /miscuotas"
    )

def now_str():
    return datetime.now(TZ).strftime("%B %Y")

async def corregir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    texto = " ".join(args) if args else ""
    monto = extraer_monto(texto) if texto else 0
    if not texto or monto == 0:
        await update.message.reply_text(
            "Uso: /corregir monto\n"
            "Ejemplo: /corregir 200000\n\n"
            "Fija tu DISPONIBLE a ese monto exacto.\n"
            "Usalo cuando el saldo del bot no coincide con la realidad."
        )
        return
    data = obtener_datos_mes()
    anterior = data["disponible"]
    data["disponible"] = monto
    data["detalle"].append({
        "desc": f"correccion manual (antes: ${anterior:,})",
        "monto": monto - anterior,
        "fecha": datetime.now(TZ).strftime("%d/%m %H:%M")
    })
    guardar_datos(data)
    await update.message.reply_text(
        f"Saldo corregido!\n\n"
        f"Antes: ${anterior:,} disponibles\n"
        f"Ahora: ${monto:,} disponibles\n\n"
        f"{estado_saldo(monto)}"
    )

async def ajustar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    texto = " ".join(args) if args else ""
    monto = extraer_monto(texto) if texto else 0
    if not texto or monto == 0:
        await update.message.reply_text("Uso: /ajustar monto\nEjemplo: /ajustar 50000\n\nAgrega plata a tu disponible.")
        return
    data = obtener_datos_mes()
    data["disponible"] += monto
    data["detalle"].append({
        "desc": "ajuste / ingreso extra",
        "monto": monto,
        "fecha": datetime.now(TZ).strftime("%d/%m %H:%M")
    })
    guardar_datos(data)
    disponible = data["disponible"]
    await update.message.reply_text(
        f"Ajuste registrado: +${monto:,}\n\n"
        f"Disponible ahora: ${disponible:,}\n\n"
        f"{estado_saldo(disponible)}"
    )

async def borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = obtener_datos_mes()
    detalle = data.get("detalle", [])
    if not detalle:
        await update.message.reply_text("No hay movimientos registrados para deshacer.")
        return
    ultimo = detalle.pop()
    data["disponible"] -= ultimo["monto"]
    data["disponible"] = max(0, data["disponible"])
    data["detalle"] = detalle
    guardar_datos(data)
    disponible = data["disponible"]
    await update.message.reply_text(
        f"Ultimo movimiento deshecho!\n\n"
        f"Eliminado: {ultimo['desc']} ${abs(ultimo['monto']):,}\n\n"
        f"Disponible ahora: ${disponible:,}\n\n"
        f"{estado_saldo(disponible)}"
    )

async def resetear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or args[0].lower() != "confirmar":
        await update.message.reply_text(
            "Esto reinicia el saldo del mes a $353.000 y borra el historial.\n\n"
            "Si estas seguro:\n/resetear confirmar"
        )
        return
    now = datetime.now(TZ)
    data = {"mes": now.strftime("%Y-%m"), "disponible": OCIO_MENSUAL, "detalle": []}
    guardar_datos(data)
    await update.message.reply_text(f"Saldo reiniciado!\n\nDisponible: ${OCIO_MENSUAL:,}")

# ── Scheduler ──────────────────────────────────────────────────────────────────
async def send_reminder(app, message: str):
    if CHAT_ID:
        await app.bot.send_message(chat_id=CHAT_ID, text=message)
        logger.info(f"Recordatorio enviado: {message[:50]}...")

async def monthly_reset_cuotas(app):
    avanzar_cuotas()
    data = cargar_cuotas()
    activas = [c for c in data["cuotas"] if c["cuotas_restantes"] > 0]
    if activas:
        total = sum(c["monto_cuota"] for c in activas)
        msg = f"Nuevo mes - Cuotas activas:\n\n"
        for c in activas:
            msg += f"- {c['desc']}: ${c['monto_cuota']:,}/mes ({c['cuotas_restantes']} restantes)\n"
        msg += f"\nTotal comprometido: ${total:,}/mes"
        await app.bot.send_message(chat_id=CHAT_ID, text=msg)

def setup_scheduler(app):
    scheduler = AsyncIOScheduler(timezone=TZ)
    for reminder in ONE_TIME_REMINDERS:
        dt = TZ.localize(datetime.strptime(reminder["date"], "%Y-%m-%d %H:%M:%S"))
        if dt > datetime.now(TZ):
            scheduler.add_job(send_reminder, trigger=DateTrigger(run_date=dt), args=[app, reminder["message"]])
    scheduler.add_job(send_reminder, trigger=CronTrigger(day=1, hour=9, minute=0), args=[app, MONTHLY_MESSAGE])
    scheduler.add_job(monthly_reset_cuotas, trigger=CronTrigger(day=1, hour=9, minute=5), args=[app])
    scheduler.start()
    logger.info("Scheduler iniciado")
    return scheduler

# ── Main ───────────────────────────────────────────────────────────────────────
async def post_init(app):
    """Registra el menu de comandos en Telegram."""
    commands = [
        BotCommand("start", "Bienvenida y lista de comandos"),
        BotCommand("estado", "Resumen de tu plan de jubilacion"),
        BotCommand("proximos", "Ver proximos recordatorios"),
        BotCommand("checklist", "Tareas del mes actual"),
        BotCommand("presupuesto", "Distribucion del sueldo mensual"),
        BotCommand("consulta", "Puedo gastar esto? Ej: /consulta cafe 3000"),
        BotCommand("gaste", "Registrar gasto. Ej: /gaste cafe 3000"),
        BotCommand("cuotas", "Registrar compra en cuotas. Ej: /cuotas ropa 60000 3"),
        BotCommand("miscuotas", "Ver todas tus cuotas activas"),
        BotCommand("saldo", "Ver cuanto te queda de ocio este mes"),
        BotCommand("corregir", "Fijar disponible a monto exacto. Ej: /corregir 200000"),
        BotCommand("ajustar", "Agregar plata al disponible. Ej: /ajustar 50000"),
        BotCommand("borrar", "Deshacer el ultimo gasto registrado"),
        BotCommand("resetear", "Reiniciar el mes desde cero"),
    ]
    await app.bot.set_my_commands(commands)
    logger.info("Menu de comandos registrado en Telegram")

def main():
    if not TOKEN:
        raise ValueError("Falta TELEGRAM_TOKEN")
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("estado", estado))
    app.add_handler(CommandHandler("proximos", proximos))
    app.add_handler(CommandHandler("checklist", checklist))
    app.add_handler(CommandHandler("presupuesto", presupuesto))
    app.add_handler(CommandHandler("consulta", consulta))
    app.add_handler(CommandHandler("gaste", gaste))
    app.add_handler(CommandHandler("cuotas", cuotas_cmd))
    app.add_handler(CommandHandler("miscuotas", miscuotas))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("corregir", corregir))
    app.add_handler(CommandHandler("ajustar", ajustar))
    app.add_handler(CommandHandler("borrar", borrar))
    app.add_handler(CommandHandler("resetear", resetear))
    setup_scheduler(app)
    logger.info("Bot iniciado v6")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
