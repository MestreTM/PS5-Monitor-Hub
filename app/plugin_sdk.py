import threading

class PluginBase:
    """
    Base class for all PS5 Monitor plugins.
    """
    def __init__(self):
        self.enabled = False
        self.config = {}
    
    def get_manifest(self):
        """
        Returns metadata and config layout for the GUI.
        Format:
        {
            "name": "My Plugin",
            "id": "my_plugin_id",
            "description": "Does something cool",
            "requirements": ["requests", "plyer"],
            "fields": [
                {"key": "url", "label": "Webhook URL", "type": "text", "default": ""},
                {"key": "auth_token", "label": "Token", "type": "password", "default": ""},
                {"key": "verbose", "label": "Verbose Mode", "type": "checkbox", "default": False}
            ]
        }
        """
        raise NotImplementedError

    def on_load(self, config_data):
        """Called when the app starts or settings are saved."""
        self.config = config_data
        self.enabled = self.config.get("enabled", False)
        # Custom initialization logic here

    def on_update(self, data):
        """
        Called when PS5 status changes. 
        'data' contains: {status, game: {...}, stats: {...}}
        """
        pass

    def on_unload(self):
        """Called when plugin is disabled or app closes."""
        pass