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

# ── Configuración ──────────────────────────────────────────────────────────────
TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TZ = pytz.timezone("America/Santiago")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Recordatorios puntuales (fecha exacta) ─────────────────────────────────────
ONE_TIME_REMINDERS = [
    {
        "date": "2026-05-07 09:00:00",
        "message": (
            "🔔 *ACCIÓN URGENTE — ESPP Uber*\n\n"
            "Ayer salieron los earnings de Uber\\. El blackout probablemente se levantó\\.\n\n"
            "✅ Entra a *Shareworks* \\(vía Okta\\)\n"
            "✅ Ve a tu ESPP → Contribuciones\n"
            "✅ Cambia de *5% → 15%*\n\n"
            "⏰ La ventana puede cerrar en pocos días\\. Hazlo hoy\\."
        ),
    },
    {
        "date": "2026-05-20 09:00:00",
        "message": (
            "🚨 *HOY ES PURCHASE DATE — ESPP Uber*\n\n"
            "Hoy Uber compra tus acciones con el descuento del 15%\\.\n\n"
            "✅ Entra a *Shareworks* ahora\n"
            "✅ Vende *TODAS* tus acciones \\(las nuevas \\+ las 42 existentes\\)\n"
            "✅ No las guardes más de 24 horas\n\n"
            "💰 Ganancia esperada: ~\\$130\\.000 CLP mínimo garantizado\\.\n"
            "Luego transfiere todo a Fintual\\."
        ),
    },
    {
        "date": "2026-05-21 09:00:00",
        "message": (
            "📋 *Recordatorio — ¿Vendiste las acciones Uber ayer?*\n\n"
            "Si aún no lo has hecho, entra a Shareworks y véndelas hoy\\.\n"
            "Cada día que las guardas es riesgo innecesario\\."
        ),
    },
    {
        "date": "2026-05-28 09:00:00",
        "message": (
            "💰 *Distribución del bono trimestral*\n\n"
            "Tu bono de ~\\$1\\.500\\.000 debería haber llegado\\. Distribúyelo así:\n\n"
            "1\\. 💳 Reponer Fintual: *\\$1\\.232\\.000* \\(repones lo de la tarjeta\\)\n"
            "2\\. 📈 Primer depósito APV: *\\$268\\.000* \\(Régimen A en Fintual\\)\n\n"
            "¿Ya pagaste la tarjeta de crédito \\(\\$3\\.700\\.000\\)? Si no, ese es el paso 0\\."
        ),
    },
    {
        "date": "2026-06-01 09:00:00",
        "message": (
            "🏦 *Activar sistema automático — Junio*\n\n"
            "Este mes debes dejar todo en piloto automático:\n\n"
            "1\\. 📈 *APV Régimen A*: Configura débito automático de *\\$232\\.000/mes* en Fintual\n"
            "2\\. 💍 *Fondo matrimonio*: Abre cuenta separada \\(Cuenta 2 AFP o DAP\\) y transfiere *\\$167\\.000/mes*\n"
            "3\\. 📊 *Fintual*: El resto de tu ahorro mensual va aquí\n\n"
            "Una vez configurado, no tienes que pensar hasta octubre\\."
        ),
    },
    {
        "date": "2026-07-20 09:00:00",
        "message": (
            "💰 *Bono trimestral Q2 — ¿Ya llegó?*\n\n"
            "Si recibiste el bono \\(~\\$1\\.500\\.000\\), distribúyelo:\n\n"
            "1\\. 💍 *Fondo matrimonio*: \\$500\\.000\n"
            "2\\. 📊 *Fintual/ETFs*: \\$1\\.000\\.000\n\n"
            "Van *\\$500\\.000* acumulados para el matrimonio\\. Meta: \\$2\\.000\\.000\\."
        ),
    },
    {
        "date": "2026-10-01 09:00:00",
        "message": (
            "💰 *Bono trimestral Q3 — Distribución*\n\n"
            "Si recibiste el bono \\(~\\$1\\.500\\.000\\):\n\n"
            "1\\. 💍 *Fondo matrimonio*: \\$500\\.000 → Ya tienes los *\\$2\\.000\\.000* ✅\n"
            "2\\. 📊 *Inversión largo plazo*: \\$1\\.000\\.000 → 100% Fintual o ETFs\n\n"
            "🎉 Matrimonio financiado\\. De aquí en adelante TODO el ahorro va al portafolio\\."
        ),
    },
    {
        "date": "2026-11-10 09:00:00",
        "message": (
            "🔔 *ESPP Uber — Próxima purchase date en 10 días*\n\n"
            "El *20 de noviembre* se compran tus acciones automáticamente\\.\n\n"
            "✅ Prepárate para vender todo el mismo día 20/11\n"
            "✅ Confirma que tu % sigue en 15% en Shareworks\n"
            "✅ Ten listo Fintual para recibir los fondos"
        ),
    },
    {
        "date": "2026-11-20 09:00:00",
        "message": (
            "🚨 *HOY — 2da Purchase Date ESPP Uber*\n\n"
            "Se compran tus acciones con descuento 15%\\.\n\n"
            "✅ Entra a Shareworks y vende *TODO* hoy\n"
            "✅ Ganancia mínima estimada: ~\\$370\\.000 CLP\n"
            "✅ Transfiere a Fintual o ETFs globales\n\n"
            "Luego evalúa si mantener 15% para el siguiente período\\."
        ),
    },
    {
        "date": "2027-01-10 09:00:00",
        "message": (
            "💍 *Matrimonio en 41 días \\(20 febrero 2027\\)*\n\n"
            "Checklist financiero:\n\n"
            "✅ ¿Tienes los \\$2\\.000\\.000 en la cuenta separada?\n"
            "✅ ¿Tienes colchón para imprevistos \\(\\+\\$300\\.000\\)?\n"
            "✅ ¿El APV sigue corriendo automático?\n"
            "✅ ¿Fintual/portafolio no fue tocado?\n\n"
            "Si todo está ok: ¡estás listo! 🎉"
        ),
    },
    {
        "date": "2027-02-21 09:00:00",
        "message": (
            "🎉 *Post\\-matrimonio — Resetear el plan*\n\n"
            "¡Felicitaciones\\! Ahora es momento de recalibrar:\n\n"
            "✅ ¿Cuánto quedó del fondo matrimonio? → Va a Fintual\n"
            "✅ Conversa con tu pareja sobre finanzas compartidas\n"
            "✅ Actualiza tus gastos mensuales \\(pueden haber cambiado\\)\n"
            "✅ Ven a hablar conmigo para ajustar el plan con la nueva situación\n\n"
            "El plan de jubilación sigue corriendo 💪"
        ),
    },
]

# ── Recordatorios mensuales recurrentes ────────────────────────────────────────
# Se disparan el día 1 de cada mes a las 9am
MONTHLY_MESSAGE = (
    "📊 *Revisión mensual de tu portafolio*\n\n"
    "Tómate 10 minutos para revisar:\n\n"
    "1\\. 💰 ¿Cuánto tienes en Fintual hoy?\n"
    "2\\. 📈 ¿El APV de \\$232\\.000 se descontó correctamente?\n"
    "3\\. 💍 ¿El fondo matrimonio sumó \\$167\\.000?\n"
    "4\\. 📋 ¿Alguna deuda nueva o gasto inesperado?\n\n"
    "Trae estos números a Claude y te digo si estás en camino\\. 🎯"
)


# ── Comandos del bot ───────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"👋 *Hola Martín\\!*\n\n"
        f"Soy tu bot de planificación financiera personal\\.\n\n"
        f"Tu Chat ID es: `{chat_id}`\n"
        f"\\(Guárdalo, lo necesitas para configurar el bot\\)\n\n"
        f"Comandos disponibles:\n"
        f"/estado — Ver resumen de tu plan\n"
        f"/proximos — Ver próximos recordatorios\n"
        f"/checklist — Checklist del mes actual",
        parse_mode="MarkdownV2",
    )


async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ)
    await update.message.reply_text(
        f"📊 *Estado de tu plan — {now.strftime('%B %Y')}*\n\n"
        f"*Patrimonio objetivo:*\n"
        f"├ Meta IF \\(55 años\\): \\$320\\.000\\.000\n"
        f"├ Meta retiro \\(70 años\\): \\$857\\.000\\.000\n\n"
        f"*Sistema automático:*\n"
        f"├ APV Régimen A: \\$232\\.000/mes\n"
        f"├ Fondo matrimonio: \\$167\\.000/mes\n"
        f"├ ESPP Uber: 15% del sueldo\n\n"
        f"*Próximas fechas clave:*\n"
        f"├ 20 mayo 2026: Purchase Date ESPP\n"
        f"├ 20 feb 2027: Matrimonio 💍\n"
        f"├ 20 nov 2026: Purchase Date ESPP \\#2\n\n"
        f"Usa /proximos para ver todos los recordatorios\\.",
        parse_mode="MarkdownV2",
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
    text = "📅 *Próximos recordatorios:*\n\n"
    for dt, days, msg in upcoming[:5]:
        first_line = msg.split("\n")[0].replace("*", "").replace("🔔", "").replace("🚨", "").replace("💰", "").replace("💍", "").replace("🎉", "").strip()
        date_str = dt.strftime("%d/%m/%Y").replace("-", "\\-").replace("/", "\\/")
        text += f"📌 *{date_str}* \\({days} días\\)\n_{first_line}_\n\n"

    if not upcoming:
        text += "No hay recordatorios pendientes\\."

    await update.message.reply_text(text, parse_mode="MarkdownV2")


async def checklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ)
    month = now.month
    checklists = {
        5: (
            "✅ *Checklist Mayo 2026*\n\n"
            "□ Pagar tarjeta de crédito \\(\\$3\\.700\\.000\\) con Fintual\n"
            "□ Subir ESPP a 15% en Shareworks \\(post\\-earnings 6/5\\)\n"
            "□ Vender TODAS las acciones Uber el 20/5\n"
            "□ Distribuir bono trimestral \\(Fintual \\+ APV\\)"
        ),
        6: (
            "✅ *Checklist Junio 2026*\n\n"
            "□ Activar APV automático \\$232\\.000/mes en Fintual\n"
            "□ Abrir cuenta separada para matrimonio\n"
            "□ Configurar transferencia \\$167\\.000/mes matrimonio\n"
            "□ Confirmar que ESPP está en 15%"
        ),
    }
    msg = checklists.get(
        month,
        (
            "✅ *Checklist mensual*\n\n"
            "□ Revisar saldo Fintual\n"
            "□ Confirmar descuento APV en liquidación\n"
            "□ Revisar saldo fondo matrimonio\n"
            "□ ¿Alguna deuda nueva?"
        ),
    )
    await update.message.reply_text(msg, parse_mode="MarkdownV2")


# ── Función para enviar recordatorio ──────────────────────────────────────────
async def send_reminder(app, message: str):
    if CHAT_ID:
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode="MarkdownV2",
        )
        logger.info(f"Recordatorio enviado: {message[:50]}...")


# ── Setup del scheduler ────────────────────────────────────────────────────────
def setup_scheduler(app):
    scheduler = AsyncIOScheduler(timezone=TZ)

    # Recordatorios puntuales
    for reminder in ONE_TIME_REMINDERS:
        dt = TZ.localize(datetime.strptime(reminder["date"], "%Y-%m-%d %H:%M:%S"))
        if dt > datetime.now(TZ):
            scheduler.add_job(
                send_reminder,
                trigger=DateTrigger(run_date=dt),
                args=[app, reminder["message"]],
            )

    # Recordatorio mensual — día 1 de cada mes a las 9am
    scheduler.add_job(
        send_reminder,
        trigger=CronTrigger(day=1, hour=9, minute=0),
        args=[app, MONTHLY_MESSAGE],
    )

    scheduler.start()
    logger.info("Scheduler iniciado con todos los recordatorios")
    return scheduler


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    if not TOKEN:
        raise ValueError("Falta TELEGRAM_TOKEN en las variables de entorno")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("estado", estado))
    app.add_handler(CommandHandler("proximos", proximos))
    app.add_handler(CommandHandler("checklist", checklist))

    setup_scheduler(app)

    logger.info("Bot iniciado ✓")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
