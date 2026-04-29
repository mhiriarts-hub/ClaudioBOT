import os
import json
import logging
import re
from datetime import datetime
import pytz

from telegram import Update
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
GASTOS_FILE = "/tmp/gastos_martin.json"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Sistema de gastos persistente
def cargar_gastos():
    try:
        if os.path.exists(GASTOS_FILE):
            with open(GASTOS_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {"mes": "", "total_gastado": 0, "detalle": []}

def guardar_gastos(data):
    try:
        with open(GASTOS_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False)
    except:
        pass

def obtener_gastos_mes():
    now = datetime.now(TZ)
    mes_actual = now.strftime("%Y-%m")
    data = cargar_gastos()
    if data.get("mes") != mes_actual:
        data = {"mes": mes_actual, "total_gastado": 0, "detalle": []}
        guardar_gastos(data)
    return data

def registrar_gasto(descripcion, monto):
    now = datetime.now(TZ)
    data = obtener_gastos_mes()
    data["total_gastado"] += monto
    data["detalle"].append({
        "desc": descripcion,
        "monto": monto,
        "fecha": now.strftime("%d/%m %H:%M")
    })
    guardar_gastos(data)
    return data

# Recordatorios
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
    "2. El APV de $232.000 se descontio correctamente?\n"
    "3. El fondo matrimonio sumo $167.000?\n"
    "4. Alguna deuda nueva o gasto inesperado?\n"
    "5. Tarjeta de credito en cero?\n\n"
    "Trae estos numeros a Claude y te digo si estas en camino."
)

# Comandos
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"Hola Martin!\n\n"
        f"Soy tu bot de planificacion financiera.\n\n"
        f"Tu Chat ID es: {chat_id}\n\n"
        f"Comandos disponibles:\n"
        f"/estado - Resumen de tu plan\n"
        f"/proximos - Proximos recordatorios\n"
        f"/checklist - Tareas del mes\n"
        f"/presupuesto - Distribucion del sueldo\n"
        f"/consulta [gasto] [monto] - Puedo gastar esto?\n"
        f"/gaste [descripcion] [monto] - Registrar un gasto\n"
        f"/saldo - Ver cuanto te queda de ocio este mes"
    )

async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ)
    await update.message.reply_text(
        f"Estado de tu plan - {now.strftime('%B %Y')}\n\n"
        f"METAS:\n"
        f"- Independencia financiera (55 anos): $320.000.000\n"
        f"- Retiro total (70 anos): $857.000.000\n\n"
        f"SISTEMA AUTOMATICO:\n"
        f"- APV Regimen A: $232.000/mes\n"
        f"- Fondo matrimonio: $167.000/mes\n"
        f"- ESPP Uber: 15% del sueldo\n\n"
        f"PROXIMAS FECHAS CLAVE:\n"
        f"- 7 mayo: Subir ESPP a 15% en Shareworks\n"
        f"- 20 mayo: Vender acciones Uber ESPP\n"
        f"- 28 mayo: Bono Q1 - pagar tarjeta + APV\n"
        f"- 20 feb 2027: Matrimonio\n\n"
        f"Usa /proximos para ver todos los recordatorios."
    )

async def presupuesto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = obtener_gastos_mes()
    gastado = data["total_gastado"]
    disponible = max(0, OCIO_MENSUAL - gastado)
    await update.message.reply_text(
        f"Distribucion del sueldo mensual ($2.070.000)\n\n"
        f"GASTOS FIJOS:\n"
        f"- Arriendo: $1.050.000\n"
        f"- APV Regimen A: $232.000\n"
        f"- Fondo matrimonio: $167.000\n"
        f"- Alimentacion/basicos: $200.000\n"
        f"- Transporte/misc: $63.000\n"
        f"- TOTAL FIJOS: $1.712.000\n\n"
        f"OCIO DEL MES:\n"
        f"- Presupuesto: ${OCIO_MENSUAL:,}\n"
        f"- Gastado: ${gastado:,}\n"
        f"- Disponible: ${disponible:,}\n\n"
        f"Usa /saldo para ver el detalle de gastos."
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
        text += f"- {date_str} ({days} dias): {first_line}\n\n"
    if not upcoming:
        text += "No hay recordatorios pendientes."
    await update.message.reply_text(text)

async def checklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ)
    month = now.month
    checklists = {
        5: "Checklist Mayo 2026\n\n[ ] Abonar $500.000 a la tarjeta\n[ ] Subir ESPP a 15% en Shareworks (post-earnings 7/5)\n[ ] Vender TODAS las acciones Uber el 20/5\n[ ] Con el bono 28/5: pagar tarjeta + APV + Fintual\n[ ] Llamar a Security/BICE para rescatar fondos mutuos",
        6: "Checklist Junio 2026\n\n[ ] Activar APV automatico $232.000/mes en Fintual\n[ ] Abrir cuenta separada matrimonio\n[ ] Configurar transferencia $167.000/mes matrimonio\n[ ] Confirmar ESPP en 15%\n[ ] Confirmar fondos mutuos Security/BICE movidos a Fintual",
        8: "Checklist Agosto 2026\n\n[ ] Bono Q2 llega ~28 agosto\n[ ] $500.000 al fondo matrimonio\n[ ] $800.000 a Fintual\n[ ] $200.000 extra al APV\n[ ] Revisar saldo fondo matrimonio",
        11: "Checklist Noviembre 2026\n\n[ ] Vender acciones Uber ESPP el 20/11\n[ ] Bono Q3 llega ~28 noviembre\n[ ] $500.000 al fondo matrimonio\n[ ] $1.000.000 a Fintual\n[ ] Evaluar mantener ESPP 15% para mayo 2027",
    }
    msg = checklists.get(month, "Checklist mensual\n\n[ ] Revisar saldo Fintual\n[ ] Confirmar descuento APV en liquidacion\n[ ] Revisar saldo fondo matrimonio\n[ ] Tarjeta de credito en cero?\n[ ] Alguna deuda nueva?")
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
            "/consulta zapatillas 80000\n"
            "/consulta cena amigos 35000\n"
            "/consulta viaje 300000\n\n"
            "Si lo compras, avisame:\n"
            "/gaste descripcion monto\n\n"
            "Ver tu saldo: /saldo"
        )
        return

    monto = 0
    match = re.search(r"(\d[\d\.]*)\s*$", texto)
    if match:
        try:
            monto = int(match.group(1).replace(".", ""))
        except:
            monto = 0

    data = obtener_gastos_mes()
    gastado = data["total_gastado"]
    disponible = max(0, OCIO_MENSUAL - gastado)

    alerta_extra = ""
    if month == 5 and day < 28:
        disponible = min(disponible, 120000)
        alerta_extra = "\nALERTA MAYO: Tarjeta aun no pagada. Se conservador."

    if monto == 0:
        if disponible > 200000:
            emoji, resp, detalle = "SI", "PUEDES", f"Tienes ${disponible:,} disponibles para ocio."
        elif disponible > 80000:
            emoji, resp, detalle = "CUIDADO", "CON MODERACION", f"Te quedan ${disponible:,}. Evalua si es necesario."
        else:
            emoji, resp, detalle = "NO", "MEJOR NO", f"Solo te quedan ${disponible:,} para el mes."
    elif monto <= 15000:
        emoji, resp, detalle = "SI", "SIN PROBLEMA", f"${monto:,} es un gasto chico. No afecta el plan."
    elif monto <= disponible * 0.4:
        emoji, resp, detalle = "SI", "PUEDES", f"${monto:,} cabe bien. Te quedarian ${disponible - monto:,} para el resto del mes."
    elif monto <= disponible:
        emoji, resp, detalle = "CUIDADO", "ES EL LIMITE", f"${monto:,} consume casi todo tu ocio restante (${disponible:,}). Despues de esto, nada mas."
    elif monto <= disponible + 50000:
        emoji, resp, detalle = "NO IDEAL", "PASAS POR POCO", f"${monto:,} supera tu saldo (${disponible:,}) por poco. Considera reducir el gasto."
    elif monto <= 500000:
        emoji, resp, detalle = "NO", "ESPERA AL BONO", f"${monto:,} no cabe en ocio. Pagalo con el bono trimestral (~28 del mes)."
    else:
        emoji, resp, detalle = "NO", "NO ESTA EN EL PLAN", f"${monto:,} es un gasto grande. Conversalo con Claude primero."

    await update.message.reply_text(
        f"{emoji} - {resp}\n\n"
        f"Consulta: {texto}\n"
        f"Monto: ${monto:,}\n\n"
        f"{detalle}"
        f"{alerta_extra}\n\n"
        f"Presupuesto ocio: ${OCIO_MENSUAL:,}\n"
        f"Ya gastado: ${gastado:,}\n"
        f"Disponible: ${disponible:,}\n\n"
        f"Si lo compras: /gaste {texto}"
    )

async def gaste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    texto = " ".join(args) if args else ""

    if not texto:
        await update.message.reply_text("Uso: /gaste descripcion monto\nEjemplo: /gaste cena 35000")
        return

    monto = 0
    match = re.search(r"(\d[\d\.]*)\s*$", texto)
    if match:
        try:
            monto = int(match.group(1).replace(".", ""))
        except:
            monto = 0

    descripcion = re.sub(r"[\$]?\s*\d[\d\.]*\s*$", "", texto).strip() or "gasto"

    if monto == 0:
        await update.message.reply_text("No detecte el monto. Escribe el numero al final.\nEjemplo: /gaste cena 35000")
        return

    data = registrar_gasto(descripcion, monto)
    gastado = data["total_gastado"]
    disponible = max(0, OCIO_MENSUAL - gastado)

    if disponible > 200000:
        estado_saldo = "Vas bien, todavia tienes margen."
    elif disponible > 80000:
        estado_saldo = "Moderado. Cuida los proximos gastos."
    elif disponible > 0:
        estado_saldo = "Poco margen. Sin gastos extras hasta fin de mes."
    else:
        estado_saldo = "SALDO AGOTADO. Sin mas gastos de ocio este mes."

    await update.message.reply_text(
        f"Registrado!\n\n"
        f"Gasto: {descripcion} - ${monto:,}\n\n"
        f"Presupuesto ocio: ${OCIO_MENSUAL:,}\n"
        f"Total gastado: ${gastado:,}\n"
        f"Disponible: ${disponible:,}\n\n"
        f"{estado_saldo}"
    )

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = obtener_gastos_mes()
    gastado = data["total_gastado"]
    disponible = max(0, OCIO_MENSUAL - gastado)
    detalle = data.get("detalle", [])

    porcentaje = min(100, int((gastado / OCIO_MENSUAL) * 100))
    bloques = porcentaje // 10
    barra = "[" + "=" * bloques + "-" * (10 - bloques) + f"] {porcentaje}%"

    if disponible > 200000:
        estado = "Verde - Bien encaminado"
    elif disponible > 80000:
        estado = "Amarillo - Con cuidado"
    else:
        estado = "Rojo - Sin margen"

    historial = ""
    if detalle:
        historial = "\n\nUltimos gastos:\n"
        for g in detalle[-5:]:
            historial += f"- {g['fecha']}: {g['desc']} ${g['monto']:,}\n"
    else:
        historial = "\n\nAun no has registrado gastos este mes."

    await update.message.reply_text(
        f"Saldo de ocio - {datetime.now(TZ).strftime('%B %Y')}\n\n"
        f"{barra}\n\n"
        f"Presupuesto: ${OCIO_MENSUAL:,}\n"
        f"Gastado:     ${gastado:,}\n"
        f"Disponible:  ${disponible:,}\n\n"
        f"Estado: {estado}"
        f"{historial}"
    )

async def ajustar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Agrega un monto al gasto registrado. Util si gastaste mas de lo que reportaste."""
    args = context.args
    texto = " ".join(args) if args else ""
    monto = 0
    match = re.search(r"(\d[\d\.]*)", texto)
    if match:
        try:
            monto = int(match.group(1).replace(".", ""))
        except:
            monto = 0
    if monto == 0:
        await update.message.reply_text("Uso: /ajustar monto\nEjemplo: /ajustar 50000\n\nSirve para agregar gastos que olvidaste registrar.")
        return
    data = obtener_gastos_mes()
    data["total_gastado"] += monto
    data["detalle"].append({
        "desc": "ajuste manual",
        "monto": monto,
        "fecha": datetime.now(TZ).strftime("%d/%m %H:%M")
    })
    guardar_gastos(data)
    gastado = data["total_gastado"]
    disponible = max(0, OCIO_MENSUAL - gastado)
    await update.message.reply_text(
        f"Ajuste registrado: +${monto:,}\n\n"
        f"Total gastado ahora: ${gastado:,}\n"
        f"Disponible: ${disponible:,}"
    )

async def corregir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fija el total gastado a un monto exacto. Util para cuadrar el saldo real."""
    args = context.args
    texto = " ".join(args) if args else ""
    monto = 0
    match = re.search(r"(\d[\d\.]*)", texto)
    if match:
        try:
            monto = int(match.group(1).replace(".", ""))
        except:
            monto = 0
    if monto == 0:
        await update.message.reply_text(
            "Uso: /corregir monto\nEjemplo: /corregir 150000\n\n"
            "Fija el total gastado a ese monto exacto.\n"
            "Usalo cuando el saldo del bot no coincide con la realidad."
        )
        return
    data = obtener_gastos_mes()
    saldo_anterior = data["total_gastado"]
    data["total_gastado"] = monto
    data["detalle"].append({
        "desc": f"correccion manual (antes: ${saldo_anterior:,})",
        "monto": monto - saldo_anterior,
        "fecha": datetime.now(TZ).strftime("%d/%m %H:%M")
    })
    guardar_gastos(data)
    disponible = max(0, OCIO_MENSUAL - monto)
    await update.message.reply_text(
        f"Saldo corregido!\n\n"
        f"Antes: ${saldo_anterior:,} gastado\n"
        f"Ahora: ${monto:,} gastado\n"
        f"Disponible: ${disponible:,}\n\n"
        f"Usa /saldo para ver el detalle completo."
    )

async def borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Borra el ultimo gasto registrado."""
    data = obtener_gastos_mes()
    detalle = data.get("detalle", [])
    if not detalle:
        await update.message.reply_text("No hay gastos registrados este mes para borrar.")
        return
    ultimo = detalle.pop()
    data["total_gastado"] = max(0, data["total_gastado"] - ultimo["monto"])
    data["detalle"] = detalle
    guardar_gastos(data)
    disponible = max(0, OCIO_MENSUAL - data["total_gastado"])
    await update.message.reply_text(
        f"Ultimo gasto borrado!\n\n"
        f"Se elimino: {ultimo['desc']} - ${ultimo['monto']:,}\n\n"
        f"Total gastado ahora: ${data['total_gastado']:,}\n"
        f"Disponible: ${disponible:,}"
    )

async def resetear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reinicia el saldo del mes a cero."""
    args = context.args
    if not args or args[0].lower() != "confirmar":
        await update.message.reply_text(
            "Esto borrara TODOS los gastos del mes y empezara desde cero.\n\n"
            "Si estas seguro, escribe:\n/resetear confirmar"
        )
        return
    now = datetime.now(TZ)
    data = {"mes": now.strftime("%Y-%m"), "total_gastado": 0, "detalle": []}
    guardar_gastos(data)
    await update.message.reply_text(
        f"Saldo reiniciado!\n\n"
        f"Gastos del mes borrados.\n"
        f"Disponible: ${OCIO_MENSUAL:,}\n\n"
        f"Empieza a registrar con /gaste descripcion monto"
    )

async def send_reminder(app, message: str):
    if CHAT_ID:
        await app.bot.send_message(chat_id=CHAT_ID, text=message)
        logger.info(f"Recordatorio enviado: {message[:50]}...")

def setup_scheduler(app):
    scheduler = AsyncIOScheduler(timezone=TZ)
    for reminder in ONE_TIME_REMINDERS:
        dt = TZ.localize(datetime.strptime(reminder["date"], "%Y-%m-%d %H:%M:%S"))
        if dt > datetime.now(TZ):
            scheduler.add_job(send_reminder, trigger=DateTrigger(run_date=dt), args=[app, reminder["message"]])
    scheduler.add_job(send_reminder, trigger=CronTrigger(day=1, hour=9, minute=0), args=[app, MONTHLY_MESSAGE])
    scheduler.start()
    logger.info("Scheduler iniciado")
    return scheduler

def main():
    if not TOKEN:
        raise ValueError("Falta TELEGRAM_TOKEN")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("estado", estado))
    app.add_handler(CommandHandler("proximos", proximos))
    app.add_handler(CommandHandler("checklist", checklist))
    app.add_handler(CommandHandler("presupuesto", presupuesto))
    app.add_handler(CommandHandler("consulta", consulta))
    app.add_handler(CommandHandler("gaste", gaste))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("ajustar", ajustar))
    app.add_handler(CommandHandler("corregir", corregir))
    app.add_handler(CommandHandler("borrar", borrar))
    app.add_handler(CommandHandler("resetear", resetear))
    setup_scheduler(app)
    logger.info("Bot iniciado v4")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
