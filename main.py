import sys
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, ConversationHandler, CommandHandler, CallbackContext
import speech_recognition as sr
from pydub import AudioSegment

print("Script iniciado.", file=sys.stdout, flush=True)

# Conexión a Google Sheets
try:
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    print("Cargando credenciales...", file=sys.stdout, flush=True)
    creds = Credentials.from_service_account_file("credenciales.json", scopes=scope)
    print("Credenciales cargadas.", file=sys.stdout, flush=True)
    client = gspread.authorize(creds)
    print("Cliente gspread autorizado.", file=sys.stdout, flush=True)
    sheet = client.open_by_key("1w6CEWXm7hAa21k2e0Tdb4EhBzBH5FXoCEKxI-DhmzIY")
    print("Planilla abierta.", file=sys.stdout, flush=True)
except Exception as e:
    print(f"Error en la conexión a Google Sheets: {str(e)}", file=sys.stdout, flush=True)
    sys.exit(1)

# Función para obtener datos de las hojas auxiliares
def obtener_datos_hoja(nombre_hoja):
    try:
        hoja = sheet.worksheet(nombre_hoja)
        datos = hoja.col_values(1)[1:]  # Ignorar el encabezado
        return datos if datos else ["(Sin datos disponibles)"]
    except Exception as e:
        print(f"Error obteniendo datos de {nombre_hoja}: {str(e)}")
        return ["(Error obteniendo datos)"]

# Obtener opciones dinámicamente
try:
    opciones_unidad_negocio = obtener_datos_hoja("UnidadNegocio")
    opciones_monedas = obtener_datos_hoja("Moneda")
    opciones_clientes = obtener_datos_hoja("Cliente")
    opciones_ctas_ingresos = obtener_datos_hoja("CtasIngresos")
    opciones_ctas_egresos = obtener_datos_hoja("CtasEgresos")
    opciones_metodos_pago = obtener_datos_hoja("Met. Pago")  # <- Hoja de métodos de pago
    print("Opciones cargadas correctamente.")
except Exception as e:
    print(f"Error al cargar opciones: {e}")

# Estados para la conversación
TASA, OBRA, SUBCAT, CUENTA = range(4)

async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        print("Mensaje de texto recibido por el bot.", file=sys.stdout, flush=True)
        texto = update.message.text.lower()
        print(f"Texto completo recibido: {texto}", file=sys.stdout, flush=True)

        if "@contradormescopeguntabot" in texto:
            print("Detectado mensaje con mención.", file=sys.stdout, flush=True)
            partes = texto.replace("@contradormescopeguntabot", "").strip().split()
            
            if len(partes) >= 3 and partes[0] in ["me", "gasté", "gaste", "ingresé", "ingrese", "ingresaron"]:
                # Determinar tipo de operación
                tipo = "egreso" if "gaste" in partes or "gasté" in partes else "ingreso"

                # Determinar el monto
                monto_texto = partes[2].replace('$', '')
                if not monto_texto.replace('.', '').isdigit():
                    await update.message.reply_text("Formato no válido. El monto debe ser un número (ejemplo: '500').")
                    return ConversationHandler.END
                monto = monto_texto

                # Determinar la moneda
                moneda = "USD" if any(indicador in texto for indicador in ["usd", "dólares", "dolares"]) else "ARS"

                # Registrar datos básicos
                fecha = datetime.now().strftime("%d/%m/%Y")
                desc = " ".join(partes[3:]) if len(partes) > 3 else "Sin descripción"
                
                context.user_data.update({
                    "tipo": tipo, "monto": monto, "moneda": moneda, "desc": desc,
                    "row_index": len(sheet.sheet1.get_all_values()) + 1
                })

                opciones = "\n".join(opciones_unidad_negocio)
                await update.message.reply_text(f"¿A qué unidad de negocio pertenece este registro?\nOpciones:\n{opciones}")
                return OBRA

        else:
            await update.message.reply_text("Menciona @contradormescopeguntabot con 'me gasté/ingresé [monto] [descripción]'.")
            return ConversationHandler.END
    except Exception as e:
        print(f"Error al procesar el mensaje: {str(e)}", file=sys.stdout, flush=True)
        await update.message.reply_text(f"Error: {str(e)}")
        return ConversationHandler.END

async def obra(update: Update, context: CallbackContext) -> int:
    context.user_data["unidad_negocio"] = update.message.text
    opciones = "\n".join(opciones_clientes)
    await update.message.reply_text(f"¿Quién es el cliente?\nOpciones:\n{opciones}")
    return SUBCAT

async def subcat(update: Update, context: CallbackContext) -> int:
    context.user_data["cliente"] = update.message.text
    opciones = "\n".join(opciones_metodos_pago)
    await update.message.reply_text(f"¿Cuál es el método de pago?\nOpciones:\n{opciones}")
    return CUENTA

async def cuenta(update: Update, context: CallbackContext) -> int:
    context.user_data["metodo_pago"] = update.message.text

    # Guardar en Sheets
    fila = [
        datetime.now().strftime("%d/%m/%Y"), context.user_data["desc"], context.user_data["monto"], 
        context.user_data["tipo"], context.user_data["moneda"], "-", context.user_data["monto"], 
        context.user_data["unidad_negocio"], context.user_data["cliente"], context.user_data["metodo_pago"]
    ]
    sheet.sheet1.append_row(fila)

    await update.message.reply_text(f"¡Registro completado! {context.user_data['desc']} - {context.user_data['monto']} {context.user_data['moneda']}.")
    return ConversationHandler.END

async def cancelar(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Conversación cancelada.")
    return ConversationHandler.END

# Configuración del bot
try:
    print("Creando instancia del bot...", file=sys.stdout, flush=True)
    app = Application.builder().token("TU_BOT_TOKEN").build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje)],
        states={
            OBRA: [MessageHandler(filters.TEXT & ~filters.COMMAND, obra)],
            SUBCAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, subcat)],
            CUENTA: [MessageHandler(filters.TEXT & ~filters.COMMAND, cuenta)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)]
    )

    app.add_handler(conv_handler)
    print("Bot listo, iniciando polling...", file=sys.stdout, flush=True)
    app.run_polling()
except Exception as e:
    print(f"Error al iniciar el bot: {str(e)}", file=sys.stdout, flush=True)
    sys.exit(1)
