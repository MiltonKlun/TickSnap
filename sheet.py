import gspread
from datetime import datetime
import logging
from config import SHEET_ID, get_google_credentials 

# ---- Logger setup ----
logger = logging.getLogger(__name__)

# ---- Global variable for the sheet connection ----
google_sheet_instance = None

# ---- Column Constants (adjust if your sheet structure differs) ----
# Master Credit Data Table 
COL_MASTER_NOMBRE = 'M'
COL_MASTER_APELLIDO = 'N'
COL_MASTER_ARTICULO = 'P'
COL_MASTER_CODIGO = 'Q'
COL_MASTER_ID_ARTICULO = 'R'
COL_MASTER_COMERCIO = 'S'
COL_MASTER_DIRECCION = 'T'
COL_MASTER_TOTAL_CREDITO = 'U' 
COL_MASTER_IMPORTE_CUOTA = 'V' 
COL_MASTER_TOTAL_CUOTAS = 'W'
COL_MASTER_CUOTAS_ABONADAS = 'X'
# COL_MASTER_CUOTAS_RESTANTES = 'Y' # Calculated inside Google Sheet
# COL_MASTER_SALDO_RESTANTE = 'Z'   # Calculated inside Google Sheet

# Payment Log Table
COL_LOG_FECHA = 'A'
COL_LOG_NOMBRE = 'B'
COL_LOG_APELLIDO = 'C'
COL_LOG_ARTICULO = 'D'
COL_LOG_ID_ARTICULO = 'E'
COL_LOG_COMERCIO = 'F'
COL_LOG_DIRECCION = 'G'
COL_LOG_IMPORTE_CUOTA = 'H'
COL_LOG_CANT_CUOTAS_PAGADAS = 'I' 


def connect_to_sheet():
    """
    Establishes and returns a connection to the Google Sheet.
    Uses a global variable to cache the connection.
    """
    global google_sheet_instance
    if google_sheet_instance:
        try:
            # Simple check to see if connection is alive
            google_sheet_instance.title
            logger.debug("Reusing existing Google Sheets connection.")
            return google_sheet_instance
        except Exception as e:
            logger.warning(f"Existing Google Sheets connection seems stale ({e}), re-establishing.")
            google_sheet_instance = None # Force re-connection

    credentials = get_google_credentials()
    if not credentials:
        logger.critical("Failed to obtain Google credentials. Sheet operations will fail.")
        return None
    if not SHEET_ID:
        logger.critical("Google SHEET_ID is not configured. Sheet operations will fail.")
        return None

    try:
        gc = gspread.authorize(credentials)
        google_sheet_instance = gc.open_by_key(SHEET_ID).sheet1 # Assuming data is on the first sheet
        logger.info(f"Successfully connected to Google Sheet: '{google_sheet_instance.title}' (ID: {SHEET_ID})")
        return google_sheet_instance
    except gspread.exceptions.APIError as e:
        logger.critical(f"Google Sheets API Error during connection: {e}", exc_info=True)
    except Exception as e:
        logger.critical(f"Critical error initializing Google Sheets connection: {e}", exc_info=True)
    
    google_sheet_instance = None # Ensure it's None if connection failed
    return None

def col_to_index(col_letter: str) -> int:
    """Converts a column letter (e.g., 'A', 'Z', 'AA') to a 0-based index."""
    index = 0
    power = 1
    for char_val in reversed(col_letter.upper()):
        index += (ord(char_val) - ord('A') + 1) * power
        power *= 26
    return index - 1


def find_client_credits(nombre_buscar: str, apellido_buscar: str) -> list:
    """
    Searches for active client credits in the master data table.
    Returns a list of dictionaries, each containing 'row_index', 'articulo', 
    'id_articulo', and 'codigo' for matching credits.
    """
    sheet = connect_to_sheet()
    if not sheet:
        logger.error("find_client_credits: Sheet connection not available.")
        raise ConnectionError("Google Sheet connection not available.")

    try:
        # Define the range to read based on columns used for matching and display
        range_to_read = f'{COL_MASTER_NOMBRE}2:{COL_MASTER_ID_ARTICULO}500'
        logger.info(f"Searching for client: '{nombre_buscar} {apellido_buscar}' in range {range_to_read}")
        
        all_data = sheet.get_values(range_to_read)
        matches = []

        # Relative column indices within the fetched `all_data`
        # Assuming COL_MASTER_NOMBRE is the first column in `range_to_read`
        base_col_index = col_to_index(COL_MASTER_NOMBRE)
        idx_nombre_rel = col_to_index(COL_MASTER_NOMBRE) - base_col_index
        idx_apellido_rel = col_to_index(COL_MASTER_APELLIDO) - base_col_index
        idx_articulo_rel = col_to_index(COL_MASTER_ARTICULO) - base_col_index
        idx_codigo_rel = col_to_index(COL_MASTER_CODIGO) - base_col_index
        idx_id_articulo_rel = col_to_index(COL_MASTER_ID_ARTICULO) - base_col_index

        for i, row_values in enumerate(all_data):
            # Ensure row has enough columns for all required fields
            if len(row_values) <= max(idx_nombre_rel, idx_apellido_rel, idx_articulo_rel, idx_codigo_rel, idx_id_articulo_rel):
                # logger.debug(f"Skipping row {i+2}: not enough columns (has {len(row_values)}).")
                continue

            nombre_sheet = row_values[idx_nombre_rel].strip()
            apellido_sheet = row_values[idx_apellido_rel].strip()

            if nombre_sheet.lower() == nombre_buscar.lower() and apellido_sheet.lower() == apellido_buscar.lower():
                articulo = row_values[idx_articulo_rel].strip() if idx_articulo_rel < len(row_values) else "N/A"
                codigo = row_values[idx_codigo_rel].strip() if idx_codigo_rel < len(row_values) else "N/A"
                id_articulo = row_values[idx_id_articulo_rel].strip() if idx_id_articulo_rel < len(row_values) else "N/A"
                
                # Critical: Only consider entries with a valid ID Articulo and Codigo
                if not id_articulo or id_articulo == "N/A" or id_articulo == "":
                    logger.warning(f"Client '{nombre_sheet} {apellido_sheet}' in master sheet row {i+2} skipped: missing ID Articulo.")
                    continue
                if not codigo or codigo == "N/A" or codigo == "":
                    logger.warning(f"Client '{nombre_sheet} {apellido_sheet}' in master sheet row {i+2} skipped: missing Codigo Articulo.")
                    continue

                matches.append({
                    "row_index": i + 2, 
                    "articulo": articulo,
                    "id_articulo": id_articulo,
                    "codigo": codigo
                })
        
        logger.info(f"Found {len(matches)} potential credit(s) for '{nombre_buscar} {apellido_buscar}'.")
        return matches

    except gspread.exceptions.APIError as e:
        logger.error(f"Google Sheets API Error while finding client credits: {e}", exc_info=True)
        raise ConnectionError(f"API Error during client search: {e}")
    except Exception as e:
        logger.error(f"Unexpected error finding client credits: {e}", exc_info=True)
        raise # Re-raise to be caught by a higher level handler


def get_credit_data(row_index: int) -> dict:
    """
    Retrieves full credit data for a specific row from the master data table.
    """
    sheet = connect_to_sheet()
    if not sheet:
        logger.error("get_credit_data: Sheet connection not available.")
        raise ConnectionError("Google Sheet connection not available.")

    try:
        # Define the full range for a single row of credit data
        range_to_read = f'{COL_MASTER_NOMBRE}{row_index}:{COL_MASTER_CUOTAS_ABONADAS}{row_index}' 
        logger.info(f"Fetching credit data for master sheet row {row_index}, range {range_to_read}")
        
        row_values = sheet.row_values(row_index)
        if not row_values:
            logger.error(f"No data found for master sheet row {row_index}.")
            raise ValueError(f"No data found in master sheet at row {row_index}")
        
        # logger.debug(f"Raw values for row {row_index}: {row_values}")

        def _get_cell_value(col_letter: str, default_val=None, data_type=str):
            """Helper to get value from `row_values` by column letter, with type conversion and error handling."""
            try:
                cell_idx = col_to_index(col_letter)
                if cell_idx < len(row_values):
                    val_str = str(row_values[cell_idx]).strip()
                    if not val_str: # Empty string
                        return default_val
                    
                    if data_type == int:
                        # Handle potential currency symbols or thousand separators if users input them
                        cleaned_val = val_str.replace('$', '').replace('.', '').split(',')[0] # Assumes , as decimal for conversion (configure if using another conversion unit)
                        return int(cleaned_val)
                    if data_type == float:
                        cleaned_val = val_str.replace('$', '').replace('.', '').replace(',', '.')
                        return float(cleaned_val)
                    return data_type(val_str)
                else:
                    logger.warning(f"Column {col_letter} (index {cell_idx}) out of bounds for row {row_index} (length {len(row_values)}). Returning default.")
                    return default_val
            except (ValueError, TypeError) as e:
                logger.error(f"Error converting value '{row_values[cell_idx]}' from col {col_letter} (row {row_index}) to {data_type}: {e}. Returning default.")
                return default_val

        credit = {
            "row_index": row_index, # Keep track of the original row
            "nombre": _get_cell_value(COL_MASTER_NOMBRE, "N/A", str),
            "apellido": _get_cell_value(COL_MASTER_APELLIDO, "N/A", str),
            "articulo": _get_cell_value(COL_MASTER_ARTICULO, "N/A", str),
            "codigo": _get_cell_value(COL_MASTER_CODIGO, "N/A", str),
            "id_articulo": _get_cell_value(COL_MASTER_ID_ARTICULO, "N/A", str),
            "local_comercial": _get_cell_value(COL_MASTER_COMERCIO, "N/A", str),
            "direccion": _get_cell_value(COL_MASTER_DIRECCION, "N/A", str),
            "total_credito": _get_cell_value(COL_MASTER_TOTAL_CREDITO, 0.0, float),
            "importe_cuota": _get_cell_value(COL_MASTER_IMPORTE_CUOTA, 0.0, float),
            "total_cuotas": _get_cell_value(COL_MASTER_TOTAL_CUOTAS, 0, int),
            "cuotas_abonadas_antes": _get_cell_value(COL_MASTER_CUOTAS_ABONADAS, 0, int),
        }
        
        # Critical data validation
        if not credit["id_articulo"] or credit["id_articulo"] == "N/A":
            msg = f"ID Articulo is missing or invalid for credit at master row {row_index}."
            logger.error(msg)
            raise ValueError(msg)
        if not credit["codigo"] or credit["codigo"] == "N/A":
            msg = f"Codigo Articulo is missing or invalid for credit at master row {row_index}."
            logger.error(msg)
            raise ValueError(msg)
        if credit["importe_cuota"] <= 0:
            msg = f"Importe Cuota is invalid (must be > 0) for credit at master row {row_index}."
            logger.error(msg)
            raise ValueError(msg)
        if credit["total_cuotas"] <= 0:
            msg = f"Total Cuotas is invalid (must be > 0) for credit at master row {row_index}."
            logger.error(msg)
            raise ValueError(msg)

        logger.info(f"Successfully fetched and parsed credit data for master row {row_index}.")
        # logger.debug(f"Parsed credit data: {credit}")
        return credit

    except gspread.exceptions.APIError as e:
        logger.error(f"Google Sheets API Error getting credit data for row {row_index}: {e}", exc_info=True)
        raise ConnectionError(f"API Error getting credit data: {e}")
    except ValueError as e: # Catch specific ValueErrors from parsing or validation
        logger.error(f"Data validation error for credit data at row {row_index}: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting credit data for row {row_index}: {e}", exc_info=True)
        raise


def find_first_empty_log_row() -> int:
    """
    Finds the first row in the payment log table (cols A:D) that is considered empty.
    This is primarily used for generating the 'Remito' number.
    Returns the 1-based row index.
    """
    sheet = connect_to_sheet()
    if not sheet:
        logger.error("find_first_empty_log_row: Sheet connection not available.")
        raise ConnectionError("Google Sheet connection not available.")

    try:
        range_to_check = f'{COL_LOG_FECHA}2:{COL_LOG_ARTICULO}1000'
        logger.info(f"Scanning for first empty log row in range {range_to_check}.")
        log_table_preview = sheet.get_values(range_to_check)

        for i, row_content in enumerate(log_table_preview):
            # A row is empty if all relevant cells (A-D for this check) are empty strings
            if all(not str(cell).strip() for cell in row_content):
                empty_row_index = i + 2  
                logger.info(f"Found first empty log row at index: {empty_row_index}.")
                return empty_row_index
        
        # If loop finishes, all scanned rows have some data; append after the last scanned row.
        next_row_index = len(log_table_preview) + 2
        logger.info(f"No completely empty row found in scanned range. Next available log row: {next_row_index}.")
        return next_row_index

    except gspread.exceptions.APIError as e:
        logger.error(f"Google Sheets API Error while finding empty log row: {e}", exc_info=True)
        raise ConnectionError(f"API Error finding empty log row: {e}")
    except Exception as e:
        logger.error(f"Unexpected error finding empty log row: {e}", exc_info=True)
        raise


def log_payment_and_update_credit(credit_data: dict, cantidad_cuotas_pagadas: int) -> None:
    """
    Logs the payment details to the payment log table (Sheet1, cols A:I).
    IMPORTANT: This function, as originally designed, does NOT update the master credit record (cols M:X).
               It only logs the transaction. Updating the master record would be a separate step.
    """
    sheet = connect_to_sheet()
    if not sheet:
        logger.error("log_payment_and_update_credit: Sheet connection not available.")
        raise ConnectionError("Google Sheet connection not available.")

    if not credit_data or not isinstance(credit_data, dict):
        logger.error("log_payment_and_update_credit: Invalid or missing 'credit_data'.")
        raise ValueError("Invalid credit_data provided for logging.")
    if not isinstance(cantidad_cuotas_pagadas, int) or cantidad_cuotas_pagadas <= 0:
        logger.error(f"log_payment_and_update_credit: Invalid 'cantidad_cuotas_pagadas': {cantidad_cuotas_pagadas}.")
        raise ValueError("Invalid cantidad_cuotas_pagadas provided.")

    try:
        log_row_to_write = find_first_empty_log_row() # For Remito and where to write log
        
        current_datetime = datetime.now()
        fecha_log = current_datetime.strftime("%d/%m/%Y") 

        # Prepare data for logging, ensuring all values are strings for gspread
        log_entry_data = [
            fecha_log,
            str(credit_data.get("nombre", "N/A")),
            str(credit_data.get("apellido", "N/A")),
            str(credit_data.get("articulo", "N/A")),
            str(credit_data.get("id_articulo", "N/A")),
            str(credit_data.get("local_comercial", "N/A")),
            str(credit_data.get("direccion", "N/A")),
            f"{credit_data.get('importe_cuota', 0.0):.2f}".replace('.', ','), # Format as currency string
            str(cantidad_cuotas_pagadas)
        ]

        # Define the range for writing the log entry (e.g., A<row>:I<row>)
        log_range_to_update = f"{COL_LOG_FECHA}{log_row_to_write}:{COL_LOG_CANT_CUOTAS_PAGADAS}{log_row_to_write}"
        logger.info(f"Logging payment to row {log_row_to_write}, range {log_range_to_update}.")
        logger.debug(f"Log data: {log_entry_data}")
        sheet.update(log_range_to_update, [log_entry_data], value_input_option='USER_ENTERED')
        logger.info(f"Payment successfully logged for Articulo ID: {credit_data.get('id_articulo')} at log row {log_row_to_write}.")

    except gspread.exceptions.APIError as e:
        err_msg = f"Google Sheets API Error during payment logging: {e}"
        logger.error(err_msg, exc_info=True)
        raise ConnectionError(err_msg)
    except Exception as e:
        err_msg = f"Unexpected error during payment logging: {e}"
        logger.error(err_msg, exc_info=True)
        raise RuntimeError(err_msg) 
