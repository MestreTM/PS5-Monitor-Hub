import os
import importlib
import importlib.util
import sys
import subprocess
import threading
from app.utils import Logger

class PluginManager:
    def __init__(self, plugin_dir="plugins"):
        self.plugin_dir = plugin_dir
        self.plugins = [] 
        self.loaded_modules = {} # Track modules for reloading

    def discover_plugins(self):
        """Scans, installs dependencies, and loads plugins."""
        if not os.path.exists(self.plugin_dir):
            os.makedirs(self.plugin_dir)

        # Clear existing to allow reload
        self.plugins = []
        sys.path.append(self.plugin_dir)

        for filename in os.listdir(self.plugin_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                self._load_file(filename)
            elif os.path.isdir(os.path.join(self.plugin_dir, filename)):
                 if os.path.exists(os.path.join(self.plugin_dir, filename, "__init__.py")):
                     self._load_module(filename)

    def _load_file(self, filename):
        module_name = filename[:-3]
        file_path = os.path.join(self.plugin_dir, filename)
        
        try:
            # Dynamic Import
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            
            # If we already loaded this module before, reload it to get code changes
            if module_name in sys.modules:
                module = importlib.reload(sys.modules[module_name])
            else:
                sys.modules[module_name] = module
            
            spec.loader.exec_module(module)
            self._process_plugin(module)
            
        except Exception as e:
            Logger.log(f"Error loading plugin file {filename}: {e}")

    def _process_plugin(self, module):
        if hasattr(module, "Plugin"):
            try:
                # 1. Instantiate temporarily to read manifest
                temp_instance = module.Plugin()
                manifest = temp_instance.get_manifest()
                
                # 2. Check and Install Dependencies
                reqs = manifest.get("requirements", [])
                if reqs:
                    if self._install_dependencies(reqs):
                        # If we installed something, we MUST reload the module
                        # so the plugin can now import the new library
                        importlib.reload(module)
                        # Re-instantiate after reload
                        temp_instance = module.Plugin() 

                # 3. Register valid plugin
                self.plugins.append(temp_instance)
                Logger.log(f"Plugin loaded: {manifest['name']}")
                
            except Exception as e:
                Logger.log(f"Error instantiating plugin in {module}: {e}")

    def _install_dependencies(self, requirements):
        """Checks if packages are installed, if not, pip installs them."""
        installed_something = False
        for package in requirements:
            try:
                importlib.import_module(package)
            except ImportError:
                Logger.log(f"Installing missing dependency: {package}...")
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                    installed_something = True
                    Logger.log(f"Successfully installed {package}")
                except Exception as e:
                    Logger.log(f"Failed to install {package}: {e}")
        return installed_something

    def get_plugins(self):
        return self.plugins
    
    def unload_all(self):
        """Calls on_unload for all plugins before reloading."""
        for p in self.plugins:
            try: p.on_unload()
            except: pass
        self.plugins = []