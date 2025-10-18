import configparser
import os

class ConfigManager:
    def __init__(self, config_file='config.ini'):
        self.config = configparser.ConfigParser()
        # Ensure the config file path is absolute, relative to this file's location
        config_path = os.path.join(os.path.dirname(__file__), config_file)
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        self.config.read(config_path, encoding='utf-8')

    def _get_list(self, section, option):
        """Gets a comma-separated string from config and returns a list of stripped strings."""
        value = self.config.get(section, option)
        return [item.strip() for item in value.split(',') if item.strip()]

    @property
    def general(self):
        return {
            'audio_extensions': tuple(self._get_list('General', 'audio_extensions')),
            'image_extensions': tuple(self._get_list('General', 'image_extensions')),
            'log_filename': self.config.get('General', 'log_filename'),
            'authors_filename': self.config.get('General', 'authors_filename'),
        }

    @property
    def gemini(self):
        return {
            'model_name': self.config.get('Gemini', 'model_name'),
            'prompt': self.config.get('Gemini', 'prompt'),
            'api_cooldown': self.config.getint('Gemini', 'api_cooldown'),
        }

    @property
    def validation(self):
        return {
            'junk_words': self._get_list('Validation', 'junk_words'),
            'name_separators': self._get_list('Validation', 'name_separators'),
            'short_name_word_count': self.config.getint('Validation', 'short_name_word_count'),
            'ambiguous_name_word_count': self.config.getint('Validation', 'ambiguous_name_word_count'),
        }

    @property
    def tagging(self):
        return {
            'marker_filename': self.config.get('Tagging', 'marker_filename'),
            'album_title_format': self.config.get('Tagging', 'album_title_format'),
            'track_title_format': self.config.get('Tagging', 'track_title_format'),
        }

    @property
    def m4b(self):
        return {
            'audio_bitrate': self.config.get('M4B', 'audio_bitrate'),
        }

    @property
    def inventory(self):
        return {
            'inventory_filename': self.config.get('Inventory', 'inventory_filename'),
            'csv_delimiter': self.config.get('Inventory', 'csv_delimiter'),
        }

# Create a single, importable instance of the config manager
# This allows other scripts to just do `from config_manager import config`
try:
    config = ConfigManager()
except FileNotFoundError as e:
    # This will provide a clear error message if config.ini is missing
    print(f"CRITICAL ERROR: {e}")
    config = None
