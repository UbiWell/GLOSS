"""
Contains a centralized registry for all databases and their functions.
"""

import os
import sys
import importlib
import inspect
from typing import Dict, List, Any, Callable
from dataclasses import dataclass

@dataclass
class DatabaseInfo:
    """Information about a database"""
    name: str
    info: str
    device: str
    additional_instructions: str = ""
    functions: Dict[str, Dict[str, Any]] = None  # Function metadata/definitions for LLMs
    function_refs: Dict[str, Callable] = None     # Actual function references
    import_path: str = ""  # Complete formatted import statement

class DatabaseRegistry:
    """Centralized registry for all databases and their functions"""
    
    def __init__(self):
        self.databases: Dict[str, DatabaseInfo] = {}
        self._load_databases()
    
    def _load_databases(self):
        """Automatically discover and load all databases from data_streams and models directories"""
        # Load from data_streams directory
        self._load_from_directory('data_streams')
        
        # Load from models directory (treating models as databases)
        self._load_from_directory('models')
    
    def _load_from_directory(self, directory_name: str):
        """Load databases from a specific directory"""
        directory_path = os.path.join(os.path.dirname(__file__), '..', directory_name)
        
        if not os.path.exists(directory_path):
            print(f"Warning: Directory {directory_path} does not exist")
            return
        
        # Get all Python files in the directory
        for filename in os.listdir(directory_path):
            if filename.endswith('.py') and not filename.startswith('__'):
                module_name = filename[:-3]  # Remove .py extension
                
                # Skip original data files that shouldn't be registered as databases
                if directory_name == 'data_streams' and not module_name.endswith('_database'):
                    continue
                
                try:
                    # Import the module
                    module = importlib.import_module(f'{directory_name}.{module_name}')
                    
                    # Check if module has database registration
                    if hasattr(module, 'register_database'):
                        module.register_database(self)
                    elif hasattr(module, 'functions') and hasattr(module, 'database_info'):
                        # Auto-register if module has functions and database_info
                        self._auto_register_database(module, module_name, directory_name)
                    elif hasattr(module, 'functions') and directory_name == 'models':
                        # Only auto-register models from models directory that have functions but no database_info
                        self._auto_register_model_as_database(module, module_name, directory_name)
                        
                except ImportError as e:
                    print(f"Warning: Could not import {directory_name}.{module_name}: {e}")
    
    def _auto_register_database(self, module, module_name: str, directory_name: str = 'data_streams'):
        """Auto-register database if it has standard structure"""
        if hasattr(module, 'functions') and hasattr(module, 'database_info'):
            db_info = module.database_info
            self.register_database(
                name=db_info.get('name', module_name),
                info=db_info.get('info', ''),
                device=db_info.get('device', 'Unknown'),
                additional_instructions=db_info.get('additional_instructions', ''),
                functions=module.functions,  # Function metadata/definitions
                function_refs=getattr(module, 'function_refs', {}),  # Actual function references
                import_path=db_info.get('import_path', '')
            )
    
    def _auto_register_model_as_database(self, module, module_name: str, directory_name: str = 'models'):
        """Auto-register model as database if it has functions but no database_info"""
        if hasattr(module, 'functions'):
            # Create default database info for models
            db_info = {
                'name': f"{module_name} database",
                'info': f"Contains functions from {module_name} model",
                'device': 'Model',
                'additional_instructions': f"This is a model-based database providing {module_name} functionality.",
                'import_path': f"\nUse following import for {module_name} database functions ({module_name.upper()})\nfrom {directory_name}.{module_name} import function_name"
            }
            
            self.register_database(
                name=db_info['name'],
                info=db_info['info'],
                device=db_info['device'],
                additional_instructions=db_info['additional_instructions'],
                functions=module.functions,  # Function metadata/definitions
                function_refs=getattr(module, 'function_refs', {}),  # Actual function references
                import_path=db_info['import_path']
            )
    
    
    def register_database(self, name: str, info: str, device: str, 
                         additional_instructions: str = "", 
                         functions: Dict[str, Dict[str, Any]] = None,
                         function_refs: Dict[str, Callable] = None,
                         import_path: str = ""):
        """Register a new database"""
        self.databases[name] = DatabaseInfo(
            name=name,
            info=info,
            device=device,
            additional_instructions=additional_instructions,
            functions=functions or {},
            function_refs=function_refs or {},
            import_path=import_path
        )
    
    def get_database(self, name: str) -> DatabaseInfo:
        """Get database by name"""
        return self.databases.get(name)
    
    def get_all_databases(self) -> Dict[str, DatabaseInfo]:
        """Get all registered databases"""
        return self.databases
    
    def get_database_names(self) -> List[str]:
        """Get list of all database names"""
        return list(self.databases.keys())
    
    def get_functions_for_database(self, database_name: str) -> Dict[str, Dict[str, Any]]:
        """Get function metadata/definitions for a specific database"""
        db = self.get_database(database_name)
        return db.functions if db else {}
    
    def get_function_refs_for_database(self, database_name: str) -> Dict[str, Callable]:
        """Get actual function references for a specific database"""
        db = self.get_database(database_name)
        return db.function_refs if db else {}
    
    def get_import_path_for_database(self, database_name: str) -> str:
        """Get import path for a specific database"""
        db = self.get_database(database_name)
        return db.import_path if db else ""
    
    def get_all_functions(self) -> Dict[str, Dict[str, Any]]:
        """Get all function metadata/definitions from all databases"""
        all_functions = {}
        for db in self.databases.values():
            all_functions.update(db.functions)
        return all_functions
    
    def get_all_function_refs(self) -> Dict[str, Callable]:
        """Get all actual function references from all databases"""
        all_function_refs = {}
        for db in self.databases.values():
            all_function_refs.update(db.function_refs)
        return all_function_refs
    
    def list_databases_by_device(self, device: str) -> List[str]:
        """List databases by device type"""
        return [name for name, db in self.databases.items() if db.device == device]
    
    def search_databases(self, query: str) -> List[str]:
        """Search databases by name or description"""
        query = query.lower()
        results = []
        for name, db in self.databases.items():
            if (query in name.lower() or 
                query in db.info.lower() or 
                query in db.device.lower()):
                results.append(name)
        return results

# Global registry instance
registry = DatabaseRegistry()

# Convenience functions
def get_database(name: str) -> DatabaseInfo:
    """Get database by name"""
    return registry.get_database(name)

def get_all_databases() -> Dict[str, DatabaseInfo]:
    """Get all registered databases"""
    return registry.get_all_databases()

def get_functions_for_database(database_name: str) -> Dict[str, Dict[str, Any]]:
    """Get function metadata/definitions for a specific database"""
    return registry.get_functions_for_database(database_name)

def get_function_refs_for_database(database_name: str) -> Dict[str, Callable]:
    """Get actual function references for a specific database"""
    return registry.get_function_refs_for_database(database_name)

def get_all_functions() -> Dict[str, Dict[str, Any]]:
    """Get all function metadata/definitions from all databases"""
    return registry.get_all_functions()

def get_all_function_refs() -> Dict[str, Callable]:
    """Get all actual function references from all databases"""
    return registry.get_all_function_refs()

def get_import_path_for_database(database_name: str) -> str:
    """Get import path for a specific database"""
    return registry.get_import_path_for_database(database_name)
