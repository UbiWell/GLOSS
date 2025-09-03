#!/usr/bin/env python3
"""
Test script to verify the database registry is working correctly
"""

import sys
import os

# Add the project root to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

def test_registry():
    """Test the database registry functionality"""
    try:
        from agents.database_registry import get_all_databases, get_database, get_functions_for_database, get_function_refs_for_database
        
        print("Testing Database Registry...")
        print("=" * 50)
        
        # Test getting all databases
        databases = get_all_databases()
        print(f"Found {len(databases)} databases:")
        for name, db_info in databases.items():
            print(f"  - {name}")
            print(f"    Info: {db_info.info[:80]}...")
            print(f"    Device: {db_info.device}")
            print(f"    Function Metadata: {len(db_info.functions)}")
            print(f"    Function References: {len(db_info.function_refs)}")
            print()
        
        # Test getting a specific database
        if databases:
            first_db_name = list(databases.keys())[0]
            db = get_database(first_db_name)
            print(f"Testing get_database('{first_db_name}'):")
            print(f"  Success: {db is not None}")
            if db:
                print(f"  Name: {db.name}")
                print(f"  Device: {db.device}")
        
        # Test getting function metadata for a database
        if databases:
            first_db_name = list(databases.keys())[0]
            functions = get_functions_for_database(first_db_name)
            print(f"\nTesting get_functions_for_database('{first_db_name}'):")
            print(f"  Found {len(functions)} function metadata entries:")
            for func_id, func_metadata in functions.items():
                print(f"    - {func_id}: {func_metadata.get('name', 'Unknown')}")
                if 'description' in func_metadata:
                    print(f"      Description: {func_metadata['description'][:50]}...")
        
        # Test getting function references for a database
        if databases:
            first_db_name = list(databases.keys())[0]
            function_refs = get_function_refs_for_database(first_db_name)
            print(f"\nTesting get_function_refs_for_database('{first_db_name}'):")
            print(f"  Found {len(function_refs)} function references:")
            for func_name, func_ref in function_refs.items():
                print(f"    - {func_name}: {type(func_ref).__name__}")
        
        print("\nRegistry test completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error testing registry: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_generic_database_manager():
    """Test the updated generic database manager"""
    try:
        from agents.generic_database_manager import GenericDatabaseManager
        
        print("\nTesting Generic Database Manager...")
        print("=" * 50)
        
        manager = GenericDatabaseManager()
        print("✓ GenericDatabaseManager created successfully")
        
        # Test with a simple query
        test_response = manager.invoke({
            'user_query': 'test query',
            'databases': ['location database']
        })
        print(f"✓ Manager invoke completed: {type(test_response)}")
        
        return True
        
    except Exception as e:
        print(f"Error testing generic database manager: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_function_metadata_structure():
    """Test that function metadata has the correct structure"""
    try:
        from agents.database_registry import get_functions_for_database
        
        print("\nTesting Function Metadata Structure...")
        print("=" * 50)
        
        # Test location database functions
        location_functions = get_functions_for_database("location database")
        if location_functions:
            print("✓ Location database functions loaded")
            
            # Check structure of first function
            first_func_id = list(location_functions.keys())[0]
            first_func = location_functions[first_func_id]
            
            required_fields = ['name', 'description', 'params', 'returns']
            missing_fields = [field for field in required_fields if field not in first_func]
            
            if missing_fields:
                print(f"❌ Missing required fields: {missing_fields}")
                return False
            else:
                print("✓ Function metadata has correct structure")
                print(f"  Function: {first_func['name']}")
                print(f"  Description: {first_func['description'][:50]}...")
                print(f"  Parameters: {list(first_func['params'].keys())}")
        else:
            print("❌ No location database functions found")
            return False
        
        return True
        
    except Exception as e:
        print(f"Error testing function metadata structure: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Database Registry Conversion Test")
    print("=" * 50)
    
    registry_ok = test_registry()
    manager_ok = test_generic_database_manager()
    metadata_ok = test_function_metadata_structure()
    
    if registry_ok and manager_ok and metadata_ok:
        print("\n🎉 All tests passed! Database registry conversion successful.")
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
        sys.exit(1)
