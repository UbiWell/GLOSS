# Database Registry Conversion Summary

## Overview

Successfully converted all existing databases from hardcoded mappings to a centralized registry system. This makes it much easier to add new databases and functions without modifying core system files.

## What Was Changed

### 1. Created New Registry System

**`agents/database_registry.py`**
- Centralized registry that automatically discovers and loads all database modules
- **Function Metadata**: Stores function definitions/descriptions used for LLM prompts
- **Function References**: Stores actual function references for execution
- Provides functions to get databases, functions, and metadata
- Supports auto-discovery of database modules in `data_streams/` directory

### 2. Converted All Existing Databases

Created new database modules that use the registry system:

- `data_streams/location_database.py` - GPS location data
- `data_streams/app_usage_database.py` - Phone app usage data  
- `data_streams/activity_database.py` - Phone activity detection
- `data_streams/phone_steps_database.py` - Phone step counting
- `data_streams/garmin_steps_database.py` - Garmin watch steps
- `data_streams/garmin_hr_database.py` - Garmin heart rate data
- `data_streams/lock_unlock_database.py` - Phone lock/unlock events
- `data_streams/wifi_database.py` - WiFi connection data
- `data_streams/battery_database.py` - Phone battery data
- `data_streams/call_log_database.py` - Phone call history
- `data_streams/garmin_stress_database.py` - Garmin stress predictions
- `data_streams/brightness_database.py` - Phone screen brightness

### 3. Updated Core System Files

**`agents/generic_database_manager.py`**
- Removed hardcoded database mappings
- Now uses registry to get databases and functions dynamically
- Uses function metadata for LLM prompts
- Uses function references for actual execution
- Automatically normalizes database names

**`agents/constants.py`**
- Removed hardcoded `databases` dictionary
- Added `get_databases()` function that uses registry
- Maintains backward compatibility

**Updated Agent Files:**
- `agents/information_seeking_agent.py`
- `agents/rag_based_agent.py` 
- `agents/all_in_one_agent.py`
- `agents/hypothesis_generator_agent_alt_1.py`

**Updated Evaluation Files:**
- `evaluation/queries_generator.py`
- `evaluation/convert_queries.py`

**Updated Utility Files:**
- `agents/gpt_utils.py`

### 4. Created Templates and Examples

**`data_streams/database_template.py`**
- Template for creating new database modules
- Shows required structure with function metadata and references

**`data_streams/example_converted_database.py`**
- Example showing before/after conversion structure

## How to Add New Databases

### Method 1: Copy Template (Recommended)

1. Copy the template:
   ```bash
   cp data_streams/database_template.py data_streams/my_new_database.py
   ```

2. Fill in the metadata:
   ```python
   database_info = {
       "name": "my_new_database",
       "info": "Description of your database",
       "device": "Phone",  # or "Watch", "Sensor", etc.
       "additional_instructions": "Any special instructions"
   }
   ```

3. Add function metadata for LLMs:
   ```python
   functions = {
       "FUNC1": {
           "name": "get_my_data",
           "description": "Retrieves data from your database",
           "usecase": ["code_generation", "function_calling"],
           "params": {
               "user_id": {"type": "str", "description": "User identifier"},
               "start_time": {"type": "str", "description": "Start time"},
               "end_time": {"type": "str", "description": "End time"}
           },
           "returns": "A list of data records",
           "example": "[{'timestamp': '2024-01-01 12:00:00', 'value': 42.5}]"
       }
   }
   ```

4. Add your actual function implementations:
   ```python
   def get_my_data_function(user_id: str, start_time: str, end_time: str):
       # Your implementation here
       pass
   
   function_refs = {
       "get_my_data": get_my_data_function,
       # Add more functions
   }
   ```

5. That's it! The registry will automatically discover and load your new database.

### Method 2: Convert Existing Module

1. Add metadata to your existing module:
   ```python
   database_info = {
       "name": "your_database_name",
       "info": "Description",
       "device": "Device type",
       "additional_instructions": "Instructions"
   }
   ```

2. Import function metadata from original module:
   ```python
   from data_streams.your_original_module import functions
   ```

3. Add function references:
   ```python
   from data_streams.your_original_module import (
       get_your_function1,
       get_your_function2
   )
   
   function_refs = {
       "function_name1": get_your_function1,
       "function_name2": get_your_function2
   }
   ```

4. Optionally add registration function:
   ```python
   def register_database(registry):
       registry.register_database(
           name=database_info["name"],
           info=database_info["info"],
           device=database_info["device"],
           additional_instructions=database_info["additional_instructions"],
           functions=functions,  # Function metadata for LLMs
           function_refs=function_refs,  # Actual function references
           module_path="data_streams.your_module_name"
       )
   ```

## Benefits

### 1. **Plug-and-Play Database Addition**
- No need to modify `generic_database_manager.py`
- No need to update hardcoded mappings
- Just add a file to `data_streams/` with the right structure

### 2. **Auto-Discovery**
- Registry automatically finds and loads all database modules
- No manual registration required
- Supports both automatic and custom registration

### 3. **Type Safety**
- Structured data with proper typing
- Clear metadata structure
- Better IDE support and error checking

### 4. **Search & Filter**
- Easy to find databases by device type
- Search databases by name or description
- List all available databases programmatically

### 5. **Backward Compatibility**
- Old code continues to work
- Gradual migration possible
- No breaking changes to existing APIs

### 6. **Proper Function Handling**
- **Function Metadata**: Rich descriptions, parameters, examples for LLM prompts
- **Function References**: Actual callable functions for execution
- Clear separation of concerns

## Usage Examples

### List All Databases
```python
from agents.database_registry import get_all_databases

databases = get_all_databases()
for name, db in databases.items():
    print(f"{name}: {db.info}")
```

### Get Function Metadata for LLMs
```python
from agents.database_registry import get_functions_for_database

functions = get_functions_for_database("location database")
for func_id, func_metadata in functions.items():
    print(f"Function: {func_metadata['name']}")
    print(f"Description: {func_metadata['description']}")
```

### Get Function References for Execution
```python
from agents.database_registry import get_function_refs_for_database

function_refs = get_function_refs_for_database("location database")
for func_name, func_ref in function_refs.items():
    print(f"Function: {func_name} -> {type(func_ref).__name__}")
```

### Use Updated Database Manager
```python
from agents.generic_database_manager import GenericDatabaseManager

manager = GenericDatabaseManager()
response = manager.invoke({
    'user_query': "Get location data for user123",
    'databases': ["location database"]
})
```

## Testing

Run the test script to verify everything is working:
```bash
python test_registry.py
```

This will test:
- Database registry functionality
- Generic database manager
- Function metadata structure
- All database discoveries and function loading

## Migration Notes

### What's Different
1. **No more hardcoded mappings** in `generic_database_manager.py`
2. **Automatic discovery** of database modules
3. **Structured metadata** for each database
4. **Centralized registry** for all database operations
5. **Separate function metadata and references** for proper LLM integration

### What's the Same
1. **Same function signatures** - all existing functions work unchanged
2. **Same database names** - "location database", "app usage database", etc.
3. **Same API** - `GenericDatabaseManager.invoke()` works the same way
4. **Same results** - queries return the same data

### Backward Compatibility
- All existing code continues to work
- Database names remain the same
- Function names remain the same
- No breaking changes to public APIs

## Future Enhancements

1. **Database Categories** - Group databases by type (sensor, app, health, etc.)
2. **Validation** - Validate database metadata and function signatures
3. **Versioning** - Support multiple versions of the same database
4. **Configuration** - Allow configuration of registry behavior
5. **Hot Reloading** - Automatically reload databases when files change

## Troubleshooting

### Common Issues

1. **Database not found**: Check that the database module has the correct `database_info` and `functions` structure
2. **Functions not loading**: Ensure functions are properly imported and added to the `function_refs` dictionary
3. **Import errors**: Check that all required dependencies are installed and paths are correct
4. **Function metadata missing**: Ensure the `functions` dictionary contains proper metadata with `name`, `description`, `params`, etc.

### Debug Commands

```python
# List all discovered databases
from agents.database_registry import get_all_databases
print(get_all_databases().keys())

# Check specific database
from agents.database_registry import get_database
db = get_database("location database")
print(f"Function metadata: {len(db.functions)}")
print(f"Function references: {len(db.function_refs)}")

# Test registry loading
from agents.database_registry import registry
print(f"Registry loaded {len(registry.databases)} databases")
```

## Conclusion

The database registry conversion successfully modernizes the database management system while maintaining full backward compatibility. The key improvement is the proper separation of **function metadata** (for LLM prompts) and **function references** (for execution), making the system more robust and easier to extend. Adding new databases is now as simple as creating a new file with the right structure - no more hardcoded mappings or system file modifications required!
