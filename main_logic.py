from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from PIL import Image, ImageDraw, ImageFont
import io
import logging
import gspread 
import os
from config import ALLOWED_USER_IDS, FONT_PATH
from sheet import (
    find_client_credits, get_credit_data, log_payment_and_update_credit,
    find_first_empty_log_row, connect_to_sheet 
)

# ---- Logger setup ----
logger = logging.getLogger(__name__)

# ---- Helper Functions ----
async def is_allowed_user(update: Update) -> bool:
    """Checks if the user interacting with the bot is in the ALLOWED_USER_IDS list."""
    user = update.effective_user
    if not user:
        logger.warning("Attempted interaction from a user with no effective_user object.")
        return False
    
    is_auth = user.id in ALLOWED_USER_IDS
    if is_auth:
        logger.debug(f"User {user.id} ({user.full_name}) is authorized.")
    else:
        logger.warning(f"Unauthorized access attempt by user ID: {user.id} ({user.full_name}).")
    return is_auth


def generate_ticket_image(ticket_text: str) -> io.BytesIO:
    """
    Generates a PNG image of a payment ticket from the provided text.
    
    Args:
        ticket_text: A string containing the formatted ticket information.
                     Lines starting with "**" and ending with "**" (or just starting with "**")
                     will be rendered in bold.
                     
    Returns:
        An io.BytesIO object containing the PNG image data.
    """
    width, height = 600, 900  # Dimensions of the ticket image
    bg_color = (255, 255, 255)  # White background
    text_color = (0, 0, 0)    # Black text
    image = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(image)

    # Font loading with fallback
    # FONT_PATH is configured in config.py, sourced from environment variable
    # Ensure arialbd.ttf (bold) and arial.ttf (regular) are in that path
    # or update with your desired font names.
    try:
        font_bold_path = os.path.join(FONT_PATH, "arialbd.ttf")
        font_regular_path = os.path.join(FONT_PATH, "arial.ttf")
        font_bold = ImageFont.truetype(font_bold_path, 24)
        font_regular = ImageFont.truetype(font_regular_path, 22)
        logger.debug(f"Successfully loaded fonts: Bold='{font_bold_path}', Regular='{font_regular_path}'")
    except IOError:
        logger.warning(
            f"Arial fonts not found in '{FONT_PATH}'. Trying Courier fallback. "
            "Place 'arial.ttf' and 'arialbd.ttf' in the FONT_PATH directory for optimal results."
        )
        try:
            font_bold_path = os.path.join(FONT_PATH, "courbd.ttf") # Courier Bold
            font_regular_path = os.path.join(FONT_PATH, "cour.ttf") # Courier Regular
            font_bold = ImageFont.truetype(font_bold_path, 24)
            font_regular = ImageFont.truetype(font_regular_path, 22)
            logger.debug(f"Successfully loaded Courier fonts: Bold='{font_bold_path}', Regular='{font_regular_path}'")
        except IOError:
            logger.error(
                f"Courier fonts also not found in '{FONT_PATH}'. Using default PIL font. Ticket appearance will be basic."
            )
            font_bold = ImageFont.load_default()
            font_regular = ImageFont.load_default()

    y_text_start = 25  # Initial Y position for text
    line_spacing = 32  # Space between lines
    current_y = y_text_start
    margin_x = 25

    for line in ticket_text.split("\n"):
        text_to_draw = line.strip()
        use_bold_font = False

        if text_to_draw.startswith("**") and text_to_draw.endswith("**"):
            use_bold_font = True
            text_to_draw = text_to_draw[2:-2] # Remove double asterisks
        elif text_to_draw.startswith("**"): # For lines like "**HEADER"
            use_bold_font = True
            text_to_draw = text_to_draw[2:]

        current_font_to_use = font_bold if use_bold_font else font_regular
        
        try:
            draw.text((margin_x, current_y), text_to_draw, fill=text_color, font=current_font_to_use)
        except Exception as e:
            error_msg = f"Error drawing text line: '{text_to_draw[:50]}...'"
            logger.error(f"{error_msg}: {e}", exc_info=True)
            # Draw an error message on the image itself for this line
            draw.text((margin_x, current_y), "[Error rendering this line]", fill=(255,0,0), font=font_regular)


        # Adjust spacing based on line content
        if line.strip().startswith("-----") or line.strip().startswith("*****"):
            current_y += line_spacing * 0.7  # Reduced spacing for separators
        elif not line.strip(): # Empty line
            current_y += line_spacing * 0.5  # Reduced spacing for empty lines
        else:
            current_y += line_spacing

        if current_y > height - 30: # Check if text exceeds image height
            logger.warning("Ticket content exceeds image height. Truncating.")
            draw.text((margin_x, current_y), "...", fill=text_color, font=font_regular)
            break
            
    img_buffer = io.BytesIO()
    image.save(img_buffer, format="PNG")
    img_buffer.seek(0) # Rewind buffer to the beginning
    logger.info("Payment ticket image generated successfully.")
    return img_buffer


# ---- Bot Command Handlers ----
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command. Greets authorized users."""
    if not await is_allowed_user(update):
        await update.message.reply_text("⛔ Access Denied. You are not authorized to use this bot.")
        return

    # Check Google Sheet connectivity on start (optional, but good for early feedback)
    sheet_conn = connect_to_sheet()
    if not sheet_conn:
        logger.critical(f"User {update.effective_user.id} issued /start, but Google Sheets connection failed.")
        await update.message.reply_text(
            "⚠️ **Critical Error:** Could not connect to the data source (Google Sheets).\n"
            "Please contact the administrator."
        )
        return

    logger.info(f"User {update.effective_user.id} ({update.effective_user.full_name}) initiated /start command.")
    await update.message.reply_text(
        "¡Hola! 👋 Welcome to TickSnap!\n\n"
        "To register a payment, please send the client's details and installments in this format:\n"
        "**FirstName LastName NumberOfInstallments**\n\n"
        "Example:\n`John Doe 3`\n\n"
        "🔹 Use spaces to separate parts.\n"
        "🔹 Number of installments must be greater than 0.",
        parse_mode='Markdown'
    )


async def process_payment_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processes incoming text messages to identify payment registration requests."""
    if not await is_allowed_user(update):
        # Silently ignore or reply with access denied, depending on desired behavior
        # await update.message.reply_text("⛔ Access Denied.")
        return

    user_id = update.effective_user.id
    user_message = update.message.text.strip()
    parts = user_message.split(maxsplit=2) # Splits into at most 3 parts: FirstName LastName NumberOfInstallments

    if len(parts) != 3:
        # If a reply is desired (optional, avoided for spamming non-commands in chat as the intro message already provides the format):
        # await update.message.reply_text(
        #     "Invalid format. Please use: `FirstName LastName NumberOfInstallments`\n"
        #     "Example: `John Doe 3`",
        #     parse_mode='Markdown'
        # )
        logger.debug(f"User {user_id} sent message with incorrect format: '{user_message}'")
        return

    nombre, apellido, cuotas_str = parts
    try:
        num_cuotas = int(cuotas_str)
        if num_cuotas <= 0:
            raise ValueError("Number of installments must be positive.")
    except ValueError:
        logger.warning(f"User {user_id} provided invalid number of installments: '{cuotas_str}'")
        await update.message.reply_text("❌ **Error:** 'Number of Installments' must be a whole number greater than 0.")
        return

    logger.info(f"User {user_id} requested payment registration for: {nombre} {apellido}, Installments: {num_cuotas}")

    try:
        client_credits = find_client_credits(nombre, apellido)
        if not client_credits:
            logger.info(f"No active credits found for {nombre} {apellido} (User: {user_id}).")
            await update.message.reply_text(
                f"❌ No active credits found for **{nombre} {apellido}**.\n"
                "Please check the name or add the credit to the master sheet.",
                parse_mode='Markdown'
            )
            return

        logger.info(f"Found {len(client_credits)} credit(s) for {nombre} {apellido}. Presenting options to user {user_id}.")
        
        keyboard_buttons = []
        response_text = (
            f"📄 Found {len(client_credits)} item(s) for **{nombre} {apellido}**.\n"
            f"Please select the item for which to register **{num_cuotas}** installment(s):\n"
        )

        for credit_match in client_credits:
            # Callback data format: "select_{row_index}_{num_cuotas}_{item_code}"
            # Item code added for potential display in processing message.
            callback_data = f"select_{credit_match['row_index']}_{num_cuotas}_{credit_match['codigo']}"
            button_label = f"{credit_match['articulo']} (Code: {credit_match['codigo']})"
            keyboard_buttons.append([InlineKeyboardButton(button_label, callback_data=callback_data)])
        
        reply_markup = InlineKeyboardMarkup(keyboard_buttons)
        await update.message.reply_text(response_text, reply_markup=reply_markup, parse_mode='Markdown')

    except ConnectionError as e: # Specific to gspread/network issues
        logger.error(f"Connection error during payment processing for {nombre} {apellido} (User: {user_id}): {e}", exc_info=True)
        await update.message.reply_text("⚠️ A database connection error occurred while searching for the client. Please try again later.")
    except gspread.exceptions.APIError as e: # Specific to Google API issues
        logger.error(f"Google Sheets API error during payment processing for {nombre} {apellido} (User: {user_id}): {e}", exc_info=True)
        await update.message.reply_text("⚠️ An error occurred with the data source (Google Sheets). Please try again or contact an administrator.")
    except Exception as e:
        logger.error(f"Unexpected error during payment processing for {nombre} {apellido} (User: {user_id}): {e}", exc_info=True)
        await update.message.reply_text("❌ An unexpected error occurred. Please try again.")


async def handle_item_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles callback queries from item selection buttons."""
    query = update.callback_query
    await query.answer() # Acknowledge the callback query

    if not await is_allowed_user(update):
        logger.warning(f"Unauthorized callback query attempt by user {update.effective_user.id if update.effective_user else 'Unknown'}.")
        try:
            await query.edit_message_text("⛔ Access Denied. You are not authorized for this action.")
        except Exception as e: # Can fail if message is too old or already changed
            logger.warning(f"Could not edit message for unauthorized callback: {e}")
        return

    user_id = update.effective_user.id
    callback_data_str = query.data
    logger.info(f"User {user_id} selected item via callback: {callback_data_str}")

    try:
        action, row_index_str, cuotas_a_pagar_str, item_code_str = callback_data_str.split('_', 3)
        if action != "select":
            raise ValueError("Invalid callback action.")
        
        row_index = int(row_index_str)
        cuotas_a_pagar = int(cuotas_a_pagar_str)

        if not (row_index > 1 and cuotas_a_pagar > 0): 
             raise ValueError("Invalid row index or number of installments from callback.")

    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing callback data '{callback_data_str}' for user {user_id}: {e}", exc_info=True)
        await query.edit_message_text("❌ **Error:** Invalid selection data. Please try the process again.")
        return
    
    try:
        # Edit message to show processing status
        await query.edit_message_text(
            f"⏳ Processing payment for item (Code: {item_code_str}), {cuotas_a_pagar} installment(s)...",
            parse_mode='Markdown'
        )
        # Call the main logic for generating receipt and logging
        await generate_and_send_receipt(update, context, row_index, cuotas_a_pagar)

    except Exception as e: # Catch-all for errors during receipt generation or sending
        logger.error(f"Critical error in handle_item_selection_callback for user {user_id} (Row: {row_index}, Cuotas: {cuotas_a_pagar}): {e}", exc_info=True)
        try:
            await query.edit_message_text("❌ An critical error occurred while processing your selection. Please contact an administrator.")
        except Exception as e_edit:
            logger.error(f"Failed to edit message with critical error notice: {e_edit}")
            # Fallback: send a new message if editing fails
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ An critical error occurred. Please contact an administrator."
            )

async def generate_and_send_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE, master_sheet_row_index: int, cuotas_a_pagar: int) -> None:
    """
    Fetches credit data, generates a payment ticket image, logs the payment, 
    and sends the ticket to the user.
    """
    effective_chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else "UnknownUser"
    
    remito_number_str = "N/A"
    log_sheet_next_row = None

    try:
        # 1. Determine Remito Number (based on next empty log row)
        # (Note: This Remito Number is optional and based on the client's preferences, but I suggest using it as a decent way to have an intern code, 
        # that both works as a ticket ID and a way to find easily the row & productID of that ticket on the sheet).
        try:
            log_sheet_next_row = find_first_empty_log_row()
            logger.info(f"Next available log row for Remito generation: {log_sheet_next_row} (User: {user_id})")
        except Exception as e_log_row:
            logger.error(f"Error determining next log row for Remito (User: {user_id}): {e_log_row}", exc_info=True)
            # Proceed without Remito if this fails, or handle as critical error 

        # 2. Fetch full credit data from Master Sheet
        logger.info(f"Fetching credit details for master row {master_sheet_row_index} to generate receipt (User: {user_id}).")
        credit = get_credit_data(master_sheet_row_index) 

        # 3. Construct Remito Number if possible
        if log_sheet_next_row and credit.get('id_articulo') and credit['id_articulo'] != "N/A":
            try:
                # Format: 000(ID_Articulo)/0000(LogRow)
                remito_number_str = f"{int(credit['id_articulo']):03d}/{log_sheet_next_row:04d}"
                logger.info(f"Generated Remito number: {remito_number_str} (User: {user_id})")
            except (ValueError, TypeError) as e_remito_format:
                logger.error(f"Error formatting Remito number (ID Art: {credit['id_articulo']}, Log Row: {log_sheet_next_row}): {e_remito_format}")
                remito_number_str = "Error/Format"
        
        # 4. Validate payment feasibility
        total_cuotas_sheet = credit['total_cuotas']
        cuotas_abonadas_antes_sheet = credit['cuotas_abonadas_antes']

        if cuotas_abonadas_antes_sheet >= total_cuotas_sheet:
            msg = (
                f"✅ **Credit Fully Paid!**\n"
                f"Item: {credit['articulo']} (Code: {credit['codigo']})\n"
                f"Client: {credit['nombre']} {credit['apellido']}\n"
                f"All {total_cuotas_sheet} installments already paid."
            )
            logger.warning(f"Attempt to pay for already completed credit. MasterRow: {master_sheet_row_index}, Art: {credit['articulo']}. (User:{user_id})")
            # If query exists (from button click), edit. Else, send new.
            if update.callback_query:
                await update.callback_query.edit_message_text(msg, parse_mode='Markdown')
            else:
                await context.bot.send_message(chat_id=effective_chat_id, text=msg, parse_mode='Markdown')
            return

        cuotas_restantes = total_cuotas_sheet - cuotas_abonadas_antes_sheet
        if cuotas_a_pagar > cuotas_restantes:
            msg = (
                f"⚠️ **Payment Exceeds Remaining Installments!**\n"
                f"Item: {credit['articulo']} (Code: {credit['codigo']})\n"
                f"Client: {credit['nombre']} {credit['apellido']}\n"
                f"Attempting to pay: **{cuotas_a_pagar}** installments.\n"
                f"Remaining installments: **{cuotas_restantes}**.\n\n"
                "Please restart the process (/start) with the correct number of installments."
            )
            logger.warning(f"Payment of {cuotas_a_pagar} exceeds remaining {cuotas_restantes}. MasterRow: {master_sheet_row_index}. (User:{user_id})")
            if update.callback_query:
                await update.callback_query.edit_message_text(msg, parse_mode='Markdown')
            else:
                await context.bot.send_message(chat_id=effective_chat_id, text=msg, parse_mode='Markdown')
            return

        # 5. Prepare data for the ticket
        cobrador_name = "John" # Username of the salesperson/user that handles the tickets
        current_installment_start_num = cuotas_abonadas_antes_sheet + 1
        current_installment_end_num = cuotas_abonadas_antes_sheet + cuotas_a_pagar
        rango_cuotas_pagadas_str = f"{current_installment_start_num} to {current_installment_end_num} of {total_cuotas_sheet}"
        if cuotas_a_pagar == 1:
             rango_cuotas_pagadas_str = f"{current_installment_start_num} of {total_cuotas_sheet}"


        saldo_pagado_total_actualizado = credit['importe_cuota'] * (cuotas_abonadas_antes_sheet + cuotas_a_pagar)
        total_monto_pago_actual = credit['importe_cuota'] * cuotas_a_pagar
        fecha_hora_ticket = datetime.now().strftime("%d/%m/%Y - %H:%M:%S")

        # Using the client's format as a simple and complete example, suitable for modifications including 
        # adding a business logo and/or other embedded graphic content.
        ticket_text_content = (
            f"**Comprobante de Pago**\n\n\n"
            f"**Fecha:** {fecha_hora_ticket}\n\n"
            f"**Cliente:** {credit['nombre']} {credit['apellido']}\n"
            f"**Comercio:** {credit['local_comercial']}\n"
            f"**Dirección:** {credit['direccion']}\n"
            f"------------------------------------------\n\n"
            f"**IMPORTE POR CUOTA: ${credit['importe_cuota']:,.2f}**\n" # Format currency
            f"**CUOTAS PAGADAS HOY: {cuotas_a_pagar}**\n"
            f"**ARTÍCULO: {credit['articulo']} (Código: {credit['codigo']})**\n"
            f"**PAGO DE CUOTAS NRO: {rango_cuotas_pagadas_str}**\n"
            f"**SALDO PAGADO TOTAL: ${saldo_pagado_total_actualizado:,.2f} de ${credit['total_credito']:,.2f}**\n"
            f"**REMITO Nro: {remito_number_str}**\n"
            f"------------------------------------------\n\n"
            f"**TOTAL PAGADO HOY: ${total_monto_pago_actual:,.2f}**\n"
            f"**COBRADOR: {cobrador_name}**\n\n"
            f"Exija y conserve este comprobante de pago.\n"
            f"**********************************\n\n"
            f"**¡ATENCIÓN!**\n"
            f"- Los pagos se realizan de Lunes a Sábado,\n  y feriados inclusive.\n"
            f"**********************************"
        )

        # 6. Generate and send ticket image
        ticket_image_bytes = generate_ticket_image(ticket_text_content)
        await context.bot.send_photo(
            chat_id=effective_chat_id, 
            photo=ticket_image_bytes, 
            caption=f"📄 Payment ticket for {credit['articulo']} (Code: {credit['codigo']})."
        )
        logger.info(f"Payment ticket sent for MasterRow {master_sheet_row_index}, {cuotas_a_pagar} installments. (User:{user_id})")

        # 7. Log payment (this also updates master sheet if that logic is enabled in sheet.py)
        log_payment_and_update_credit(credit_data=credit, cantidad_cuotas_pagadas=cuotas_a_pagar)
        logger.info(f"Payment logged successfully for MasterRow {master_sheet_row_index}. (User:{user_id})")
        
        # Confirmation message (edit original if from callback, else send new)
        success_message = f"✅ Payment of {cuotas_a_pagar} installment(s) for '{credit['articulo']}' registered successfully!"
        if update.callback_query:
            await update.callback_query.edit_message_text(success_message)
        else:
            await context.bot.send_message(chat_id=effective_chat_id, text=success_message)


    except ConnectionError as e:
        logger.error(f"Sheet Connection Error during receipt generation (MasterRow {master_sheet_row_index}, User {user_id}): {e}", exc_info=True)
        error_text = "⚠️ Database connection error. Payment might not be fully processed. Please verify."
        if update.callback_query: await update.callback_query.edit_message_text(error_text)
        else: await context.bot.send_message(chat_id=effective_chat_id, text=error_text)
    except gspread.exceptions.APIError as e:
        logger.error(f"Google Sheets API Error during receipt generation (MasterRow {master_sheet_row_index}, User {user_id}): {e}", exc_info=True)
        error_text = "⚠️ Google Sheets API error. Payment might not be fully processed. Please verify."
        if update.callback_query: await update.callback_query.edit_message_text(error_text)
        else: await context.bot.send_message(chat_id=effective_chat_id, text=error_text)
    except ValueError as e: # From get_credit_data or other data issues
        logger.error(f"Data Error during receipt generation (MasterRow {master_sheet_row_index}, User {user_id}): {e}", exc_info=True)
        error_text = f"❌ Data error: {e}. Payment not processed. Please check the master sheet or contact admin."
        if update.callback_query: await update.callback_query.edit_message_text(error_text)
        else: await context.bot.send_message(chat_id=effective_chat_id, text=error_text)
    except Exception as e:
        logger.critical(f"Unexpected CRITICAL error during receipt generation (MasterRow {master_sheet_row_index}, User {user_id}): {e}", exc_info=True)
        error_text = "❌ An unexpected critical error occurred. Payment status uncertain. Please contact an administrator immediately."
        if update.callback_query:
            try: await update.callback_query.edit_message_text(error_text)
            except Exception: await context.bot.send_message(chat_id=effective_chat_id, text=error_text) 
        else:
            await context.bot.send_message(chat_id=effective_chat_id, text=error_text)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Apologies, an unexpected error occurred while processing your request. "
                     "The admin has been notified. Please try again later."
            )
        except Exception as e_notify:
            logger.error(f"Failed to send error notification to user {update.effective_chat.id}: {e_notify}")


def setup_application(app: Application) -> None:
    """
    Configures the provided Telegram Bot Application instance with command,
    message, and callback query handlers.
    """
    if not app:
        logger.critical("setup_application received a null Application instance. Cannot set up handlers.")
        return

    # Command Handlers
    app.add_handler(CommandHandler(["start", "ayuda", "help", "reiniciar"], start_command))

    # Message Handler for processing payment requests (text, not commands)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_payment_request))

    # Callback Query Handler for item selections
    app.add_handler(CallbackQueryHandler(handle_item_selection_callback, pattern="^select_"))
    
    # Error Handler (catches errors within PTB's execution flow)
    app.add_error_handler(error_handler)

    logger.info("Telegram bot application handlers configured.")
