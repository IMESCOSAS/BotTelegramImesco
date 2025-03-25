import os
import json
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, MessageHandler, filters,
    ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler
)

# 🔹 Configurar conexión con Google Sheets usando variable de entorno
SHEET_ID = "1w6CEWXm7hAa21k2e0Tdb4EhBzBH5FXoCEKxI-DhmzIY"
SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Leer credenciales desde variable de entorno (Render)
service_account_info = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
client = gspread.authorize(creds)
sheet_base = client.open_by_key(SHEET_ID).worksheet("Base")

# 🔹 Función para obtener opciones desde Google Sheets
def obtener_opciones(hoja_nombre):
    try:
        hoja = client.open_by_key(SHEET_ID).worksheet(hoja_nombre)
        valores = hoja.col_values(1)  # toma desde A1
        return valores if valores else ["(Sin datos disponibles)"]
    except Exception as e:
        print(f"Error al obtener datos de {hoja_nombre}: {str(e)}")
        return ["(Error obteniendo datos)"]

# 🔹 Cargar opciones desde las hojas auxiliares
opciones_ctas_ingresos = obtener_opciones("CtasIngresos")
opciones_ctas_egresos = obtener_opciones("CtasEgresos")
opciones_unidad_negocio = obtener_opciones("UnidadNegocio")
opciones_monedas = obtener_opciones("Moneda")
opciones_clientes = obtener_opciones("Cliente")
opciones_metodos_pago = obtener_opciones("MetodosPago")

# 🔹 Estados de la conversación
FECHA, TIPO, CUENTA, UNIDAD_NEGOCIO, CLIENTE, CONCEPTO, MONEDA, VALOR, METODO_PAGO = range(9)

# 🔹 Funciones del flujo de conversación
async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("📅 Ingresa la fecha en formato DD/MM/YYYY:")
    return FECHA

async def recibir_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["fecha"] = update.message.text
    teclado = [
        [InlineKeyboardButton("Ingreso", callback_data="Ingreso")],
        [InlineKeyboardButton("Gasto", callback_data="Gasto")]
    ]
    await update.message.reply_text("📌 Selecciona el tipo de transacción:", reply_markup=InlineKeyboardMarkup(teclado))
    return TIPO

async def recibir_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["tipo"] = query.data

    opciones_cuenta = opciones_ctas_ingresos if query.data == "Ingreso" else opciones_ctas_egresos
    teclado = [[InlineKeyboardButton(op, callback_data=op)] for op in opciones_cuenta]
    await query.message.reply_text("📂 Selecciona la cuenta:", reply_markup=InlineKeyboardMarkup(teclado))
    return CUENTA

async def recibir_cuenta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["cuenta"] = query.data

    teclado = [[InlineKeyboardButton(op, callback_data=op)] for op in opciones_unidad_negocio]
    await query.message.reply_text("🏢 Selecciona la unidad de negocio:", reply_markup=InlineKeyboardMarkup(teclado))
    return UNIDAD_NEGOCIO

async def recibir_unidad_negocio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["unidad_negocio"] = query.data

    teclado = [[InlineKeyboardButton(op, callback_data=op)] for op in opciones_clientes]
    await query.message.reply_text("👤 Selecciona el cliente:", reply_markup=InlineKeyboardMarkup(teclado))
    return CLIENTE

async def recibir_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["cliente"] = query.data

    await query.message.reply_text("✍️ Ingresa el concepto de la transacción:")
    return CONCEPTO

async def recibir_concepto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["concepto"] = update.message.text

    teclado = [[InlineKeyboardButton(op, callback_data=op)] for op in opciones_monedas]
    await update.message.reply_text("💵 Selecciona la moneda:", reply_markup=InlineKeyboardMarkup(teclado))
    return MONEDA

async def recibir_moneda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["moneda"] = query.data

    await query.message.reply_text("💰 Ingresa el valor:")
    return VALOR

async def recibir_valor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["valor"] = update.message.text
    teclado = [[InlineKeyboardButton(op, callback_data=op)] for op in opciones_metodos_pago]
    await update.message.reply_text("💳 Selecciona el método de pago:", reply_markup=InlineKeyboardMarkup(teclado))
    return METODO_PAGO

async def recibir_metodo_pago(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["metodo_pago"] = query.data

    # Extraer datos
    tipo = context.user_data["tipo"]
    fecha = context.user_data["fecha"]
    cuenta = context.user_data["cuenta"]
    unidad_negocio = context.user_data["unidad_negocio"]
    cliente = context.user_data["cliente"]
    concepto = context.user_data["concepto"]
    divisa = context.user_data["moneda"]
    valor = context.user_data["valor"]
    metodo_pago = context.user_data["metodo_pago"]

    ingreso = valor if tipo == "Ingreso" else ""
    gasto = valor if tipo == "Gasto" else ""

    try:
        fecha_dt = datetime.strptime(fecha, "%d/%m/%Y")
        mes = fecha_dt.month
        año = fecha_dt.year
    except ValueError:
        await query.message.reply_text("⚠️ Error en la fecha. Usa el formato DD/MM/YYYY.")
        return ConversationHandler.END

    fila = [tipo, fecha, unidad_negocio, cuenta, cliente, concepto, divisa, ingreso, gasto, mes, año, metodo_pago]

    try:
        sheet_base.append_row(fila, value_input_option="USER_ENTERED")
        await query.message.reply_text("✅ Datos registrados correctamente en la planilla.")
    except Exception as e:
        await query.message.reply_text(f"❌ Error al guardar en la planilla: {str(e)}")

    return ConversationHandler.END

# 🔹 Iniciar el bot con el token desde variable de entorno
app = Application.builder().token(os.environ["BOT_TOKEN"]).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", iniciar)],
    states={
        FECHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_fecha)],
        TIPO: [CallbackQueryHandler(recibir_tipo)],
        CUENTA: [CallbackQueryHandler(recibir_cuenta)],
        UNIDAD_NEGOCIO: [CallbackQueryHandler(recibir_unidad_negocio)],
        CLIENTE: [CallbackQueryHandler(recibir_cliente)],
        CONCEPTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_concepto)],
        MONEDA: [CallbackQueryHandler(recibir_moneda)],
        VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_valor)],
        METODO_PAGO: [CallbackQueryHandler(recibir_metodo_pago)],
    },
    fallbacks=[],
)

app.add_handler(conv_handler)
app.run_polling()



