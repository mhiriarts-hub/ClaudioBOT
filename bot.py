import os
import logging
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

# Configuracion
TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TZ = pytz.timezone("America/Santiago")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Recordatorios puntuales
ONE_TIME_REMINDERS = [

    # MAYO 2026
    {
        "date": "2026-05-07 09:00:00",
        "message": (
            "ACCION URGENTE \xe2\x80\x94 ESPP Uber\n\n"
            "Ayer salieron los earnings de Uber. El blackout probablemente se levanto.\n\n"
            "1. Entra a Shareworks (via Okta)\n"
            "2. Ve a ESPP > Contribuciones\n"
            "3. Cambia de 5% a 15%\n\n"
            "La ventana puede cerrar en pocos dias. Hazlo hoy."
        ),
    },
    {
        "date": "2026-05-20 09:00:00",
        "message": (
            "HOY ES PURCHASE DATE \xe2\x80\x94 ESPP Uber\n\n"
            "Hoy Uber compra tus acciones con el descuento del 15%.\n\n"
            "1. Entra a Shareworks ahora\n"
            "2. Vende TODAS tus acciones (las nuevas + las 42 existentes)\n"
            "3. No las guardes mas de 24 horas\n\n"
            "Ganancia esperada: ~$130.000 CLP minimo garantizado.\n"
            "Guarda los USD - el bono llega en unos dias y distribuyes todo junto."
        ),
    },
    {
        "date": "2026-05-21 09:00:00",
        "message": (
            "Recordatorio: vendiste las acciones Uber ayer?\n\n"
            "Si aun no lo has hecho, entra a Shareworks y vendelas hoy.\n"
            "Cada dia que las guardas es riesgo innecesario."
        ),
    },
    {
        "date": "2026-05-28 09:00:00",
        "message": (
            "BONO TRIMESTRAL Q1 \xe2\x80\x94 Plan de distribucion exacto\n\n"
            "Con el bono (~$1.500.000) + lo del ESPP Uber, sigue estos pasos en orden:\n\n"
            "PASO 1 \xe2\x80\x94 Tarjeta de credito (PRIMERO)\n"
            "Quedan ~$3.200.000 pendientes (ya abonaste $500.000 con el sueldo).\n"
            "Retira $3.200.000 de Fintual y paga la tarjeta completa HOY.\n\n"
            "PASO 2 \xe2\x80\x94 Reponer Fintual con el bono\n"
            "$1.232.000 del bono van a Fintual\n\n"
            "PASO 3 \xe2\x80\x94 Primer deposito APV Regimen A\n"
            "$268.000 del bono van a APV en Fintual\n\n"
            "PASO 4 \xe2\x80\x94 Llamar a Security/BICE\n"
            "Pide rescatar todos tus fondos mutuos ($2.214.376) y moverlos a Fintual.\n\n"
            "Tarjeta = CERO. APV activo. Sistema listo."
        ),
    },

    # JUNIO 2026
    {
        "date": "2026-06-01 09:00:00",
        "message": (
            "Activar sistema automatico \xe2\x80\x94 Junio\n\n"
            "Este mes activas el piloto automatico:\n\n"
            "1. APV Regimen A: Configura debito automatico de $232.000/mes en Fintual\n"
            "2. Fondo matrimonio: Abre cuenta de ahorro separada y transfiere $167.000/mes\n"
            "3. Tarjeta: Usala solo si puedes pagar el total a fin de mes\n\n"
            "Una vez configurado, el sistema trabaja solo."
        ),
    },
    {
        "date": "2026-06-28 09:00:00",
        "message": (
            "Revision fin de mes \xe2\x80\x94 Junio\n\n"
            "Confirma que esto ocurrio este mes:\n\n"
            "- Se descontaron $232.000 de APV automatico?\n"
            "- Transferiste $167.000 al fondo matrimonio?\n"
            "- Tarjeta de credito en cero?\n"
            "- Fintual creciendo sin tocar?\n"
            "- Llamaste a Security/BICE para rescatar los fondos mutuos?\n\n"
            "Si algo fallo, trae los numeros a Claude y ajustamos."
        ),
    },

    # AGOSTO 2026 - BONO Q2
    {
        "date": "2026-08-26 09:00:00",
        "message": (
            "BONO TRIMESTRAL Q2 \xe2\x80\x94 Ya llego?\n\n"
            "Tu bono de ~$1.500.000 deberia llegar esta semana. Cuando llegue:\n\n"
            "1. Fondo matrimonio: $500.000\n"
            "   Llevaras ~$667.000 acumulados (meta: $2.000.000)\n"
            "2. Fintual: $800.000\n"
            "3. APV extra: $200.000 (adelantas cuotas)\n\n"
            "Faltan 2 bonos mas para cubrir el matrimonio."
        ),
    },

    # NOVIEMBRE 2026 - BONO Q3 + ESPP
    {
        "date": "2026-11-10 09:00:00",
        "message": (
            "DOS COSAS IMPORTANTES esta semana\n\n"
            "1. ESPP Uber \xe2\x80\x94 Purchase Date el 20 nov (en 10 dias)\n"
            "   - Prepárate para vender TODO el 20 de noviembre\n"
            "   - Confirma que tu % sigue en 15% en Shareworks\n"
            "   - Ten listo Fintual para recibir los fondos\n\n"
            "2. Bono Q3 llega ~28 nov. Plan:\n"
            "   - $500.000 al fondo matrimonio (llevaras ~$1.167.000)\n"
            "   - $1.000.000 a Fintual"
        ),
    },
    {
        "date": "2026-11-20 09:00:00",
        "message": (
            "HOY \xe2\x80\x94 2da Purchase Date ESPP Uber\n\n"
            "Se compran tus acciones con descuento 15%.\n\n"
            "1. Entra a Shareworks y vende TODO hoy\n"
            "2. Ganancia minima estimada: ~$370.000 CLP\n"
            "3. Transfiere a Fintual\n\n"
            "Luego evalua si mantener 15% para el siguiente periodo (mayo 2027)."
        ),
    },
    {
        "date": "2026-11-28 09:00:00",
        "message": (
            "BONO TRIMESTRAL Q3 \xe2\x80\x94 Distribucion\n\n"
            "Con el bono (~$1.500.000):\n\n"
            "1. Fondo matrimonio: $500.000\n"
            "   Llevas ~$1.167.000 acumulados (meta: $2.000.000)\n"
            "2. Fintual: $1.000.000\n\n"
            "Falta 1 bono mas para cubrir el matrimonio completamente."
        ),
    },

    # ENERO 2027
    {
        "date": "2027-01-10 09:00:00",
        "message": (
            "Matrimonio en 41 dias (20 febrero 2027)\n\n"
            "Checklist financiero:\n\n"
            "- Tienes los $2.000.000 en la cuenta separada?\n"
            "- Tienes colchon para imprevistos (+$300.000)?\n"
            "- El APV sigue corriendo automatico?\n"
            "- Fintual no fue tocado?\n"
            "- Tarjeta de credito en cero?\n\n"
            "Si todo esta ok: estas listo!"
        ),
    },

    # FEBRERO 2027
    {
        "date": "2027-02-21 09:00:00",
        "message": (
            "Felicitaciones! Post-matrimonio \xe2\x80\x94 Resetear el plan\n\n"
            "Ahora es momento de recalibrar:\n\n"
            "1. Cuanto quedo del fondo matrimonio? Va a Fintual\n"
            "2. Conversa con tu pareja sobre finanzas compartidas\n"
            "3. Los $167.000 del fondo matrimonio ahora van al APV o Fintual\n"
            "4. Actualiza tus gastos mensuales\n"
            "5. Ven a hablar con Claude para ajustar el plan\n\n"
            "El plan de jubilacion sigue corriendo!"
        ),
    },
    {
        "date": "2027-02-26 09:00:00",
        "message": (
            "BONO TRIMESTRAL Q4\n\n"
            "Con el bono (~$1.500.000):\n\n"
            "1. Completar fondo matrimonio si falta algo\n"
            "2. TODO el resto va a Fintual: $1.000.000+\n\n"
            "De aqui en adelante el 100% del ahorro va al portafolio largo plazo."
        ),
    },
]

# Recordatorio mensual recurrente - dia 1 de cada mes a las 9am
MONTHLY_MESSAGE = (
    "Revision mensual de tu portafolio\n\n"
    "Tomate 10 minutos para revisar:\n\n"
    "1. Cuanto tienes en Fintual hoy?\n"
    "2. El APV de $232.000 se descontó correctamente?\n"
    "3. El fondo matrimonio sumo $167.000?\n"
    "4. Alguna deuda nueva o gasto inesperado?\n"
    "5. Tarjeta de credito en cero?\n\n"
    "Trae estos numeros a Claude y te digo si estas en camino."
)


# Comandos del bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"Hola Martin!\n\n"
        f"Soy tu bot de planificacion financiera personal.\n\n"
        f"Tu Chat ID es: {chat_id}\n"
        f"(Guardalo, lo necesitas para configurar el bot)\n\n"
        f"Comandos disponibles:\n"
        f"/estado - Ver resumen de tu plan\n"
        f"/proximos - Ver proximos recordatorios\n"
        f"/checklist - Checklist del mes actual\n"
        f"/presupuesto - Ver distribucion del sueldo este mes"
    )


async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ)
    await update.message.reply_text(
        f"Estado de tu plan - {now.strftime('%B %Y')}\n\n"
        f"PATRIMONIO OBJETIVO:\n"
        f"- Meta independencia financiera (55 anos): $320.000.000\n"
        f"- Meta retiro total (70 anos): $857.000.000\n\n"
        f"SISTEMA AUTOMATICO:\n"
        f"- APV Regimen A: $232.000/mes\n"
        f"- Fondo matrimonio: $167.000/mes\n"
        f"- ESPP Uber: 15% del sueldo\n\n"
        f"PROXIMAS FECHAS CLAVE:\n"
        f"- 20 mayo 2026: Purchase Date ESPP\n"
        f"- 28 mayo 2026: Bono Q1 + pagar tarjeta\n"
        f"- 1 junio 2026: Activar APV automatico\n"
        f"- 20 feb 2027: Matrimonio\n\n"
        f"Usa /proximos para ver todos los recordatorios."
    )


async def presupuesto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Distribucion del sueldo mensual ($2.070.000)\n\n"
        f"GASTOS FIJOS:\n"
        f"- Arriendo: $1.050.000\n"
        f"- APV Regimen A: $232.000\n"
        f"- Fondo matrimonio: $167.000\n"
        f"- Alimentacion/basicos: $200.000\n"
        f"- Transporte/misc: $63.000\n\n"
        f"TOTAL FIJOS: $1.712.000\n\n"
        f"DISPONIBLE PARA OCIO: ~$358.000\n\n"
        f"REGLA DE ORO:\n"
        f"- Tarjeta: pagala completa a fin de mes\n"
        f"- No toques Fintual hasta el bono\n"
        f"- Los bonos son el motor del plan"
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
        5: (
            "Checklist Mayo 2026\n\n"
            "[ ] Abonar $500.000 a la tarjeta de credito\n"
            "[ ] Subir ESPP a 15% en Shareworks (post-earnings 6/5)\n"
            "[ ] Vender TODAS las acciones Uber el 20/5\n"
            "[ ] Con el bono del 28/5: pagar tarjeta completa + APV + Fintual\n"
            "[ ] Llamar a Security/BICE para rescatar fondos mutuos"
        ),
        6: (
            "Checklist Junio 2026\n\n"
            "[ ] Activar APV automatico $232.000/mes en Fintual\n"
            "[ ] Abrir cuenta separada para matrimonio\n"
            "[ ] Configurar transferencia $167.000/mes matrimonio\n"
            "[ ] Confirmar que ESPP esta en 15%\n"
            "[ ] Confirmar que fondos mutuos Security/BICE fueron movidos a Fintual"
        ),
        8: (
            "Checklist Agosto 2026\n\n"
            "[ ] Bono Q2 llega ~28 agosto\n"
            "[ ] $500.000 al fondo matrimonio\n"
            "[ ] $800.000 a Fintual\n"
            "[ ] $200.000 extra al APV\n"
            "[ ] Revisar saldo total del fondo matrimonio"
        ),
        11: (
            "Checklist Noviembre 2026\n\n"
            "[ ] Vender acciones Uber ESPP el 20/11\n"
            "[ ] Bono Q3 llega ~28 noviembre\n"
            "[ ] $500.000 al fondo matrimonio\n"
            "[ ] $1.000.000 a Fintual\n"
            "[ ] Evaluar mantener ESPP en 15% para mayo 2027"
        ),
    }
    msg = checklists.get(
        month,
        (
            "Checklist mensual\n\n"
            "[ ] Revisar saldo Fintual\n"
            "[ ] Confirmar descuento APV en liquidacion\n"
            "[ ] Revisar saldo fondo matrimonio\n"
            "[ ] Tarjeta de credito en cero?\n"
            "[ ] Alguna deuda nueva?"
        ),
    )
    await update.message.reply_text(msg)


# Funcion para enviar recordatorio
async def send_reminder(app, message: str):
    if CHAT_ID:
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=message,
        )
        logger.info(f"Recordatorio enviado: {message[:50]}...")


# Setup del scheduler
def setup_scheduler(app):
    scheduler = AsyncIOScheduler(timezone=TZ)

    for reminder in ONE_TIME_REMINDERS:
        dt = TZ.localize(datetime.strptime(reminder["date"], "%Y-%m-%d %H:%M:%S"))
        if dt > datetime.now(TZ):
            scheduler.add_job(
                send_reminder,
                trigger=DateTrigger(run_date=dt),
                args=[app, reminder["message"]],
            )

    # Recordatorio mensual - dia 1 de cada mes a las 9am
    scheduler.add_job(
        send_reminder,
        trigger=CronTrigger(day=1, hour=9, minute=0),
        args=[app, MONTHLY_MESSAGE],
    )

    scheduler.start()
    logger.info("Scheduler iniciado con todos los recordatorios")
    return scheduler


# Main
def main():
    if not TOKEN:
        raise ValueError("Falta TELEGRAM_TOKEN en las variables de entorno")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("estado", estado))
    app.add_handler(CommandHandler("proximos", proximos))
    app.add_handler(CommandHandler("checklist", checklist))
    app.add_handler(CommandHandler("presupuesto", presupuesto))

    setup_scheduler(app)

    logger.info("Bot iniciado v2")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
