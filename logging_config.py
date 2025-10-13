import logging
import sys
import os

def setup_logging(script_name=None):
    """
    Configures the logging for the entire application.
    """
    log_name = script_name if script_name else 'EbookSort'
    logger = logging.getLogger(log_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.hasHandlers():
        # Clear existing handlers to avoid duplication
        logger.handlers.clear()

    # --- File Handler ---
    file_handler = logging.FileHandler('process.log', mode='a', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    # Add script name to the formatter
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # --- Console Handler (for stdout) ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)

    class InfoWarningFilter(logging.Filter):
        def filter(self, record):
            return record.levelno <= logging.WARNING

    console_handler.addFilter(InfoWarningFilter())
    logger.addHandler(console_handler)

    # --- Console Error Handler (for stderr) ---
    error_handler = logging.StreamHandler(sys.stderr)
    error_handler.setLevel(logging.ERROR)
    error_formatter = logging.Formatter('--- ERROR (%(name)s): %(message)s')
    error_handler.setFormatter(error_formatter)
    logger.addHandler(error_handler)

    return logger

# This function will be used at the start of each script
def get_logger(script_name):
    """Gets a logger and logs the start of the script execution."""
    # Extract just the filename
    base_name = os.path.basename(script_name)
    logger = setup_logging(base_name)
    logger.info(f"--- Starting execution of {base_name} ---")
    return logger

def close_logger(logger):
    """Logs the end of the script execution."""
    logger.info(f"--- Finished execution of {logger.name} ---")