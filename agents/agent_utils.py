
"""
This file contains utility functions to generate prompts or retry runs
"""
def invoke_with_retry(agent, method, params, max_retries=1):
    retries = 0
    while retries <= max_retries:
        try:
            return getattr(agent, method)(params)
        except Exception as e:
            retries += 1
            if retries > max_retries:
                print(f"Failed after {max_retries + 1} attempts: {str(e)}")
                return "FAILED"

def generate_function_calling_prompt(input_instructions, functions, output_instructions):
    # Format the prompt's initial instructions
    prompt = f"{input_instructions}\n\n"

    # Add function details to the prompt
    for func_id, details in functions.items():
        if "usecase" not in details:
            continue
        if "function_calling" not in details["usecase"]:
            continue
        if "summary" in details['name']:
            continue
        prompt += f" Function ID: {func_id}\n"
        prompt += f"    {details['name']} ({', '.join(details['params'].keys())}):\n"
        prompt += f"        {details['description']}\n\n"
        if "function_call_instructions" in details:
            prompt += f"        {details['function_call_instructions']}\n\n"

        # Add arguments with descriptions
        prompt += "        Args:\n"
        for param, param_desc in details['params'].items():
            prompt += f"            {param} ({param_desc['type']}): {param_desc['description']}\n"

        # Add return values with descriptions
        prompt += "\n        Returns:\n"
        if isinstance(details['returns'], dict):
            for ret, ret_desc in details['returns'].items():
                prompt += f"            - {ret} ({ret_desc['type']}): {ret_desc['description']}\n"
        else:
            prompt += f"            {details['returns']}\n"
        prompt += "\n"

    # Add output instructions
    prompt += f"\n{output_instructions}"

    return prompt


def generate_code_generation_prompt(req_databases, functions, include_statements, function_imports):
    # Lazily fetch databases to avoid circular imports at module import time
    try:
        from agents.database_registry import get_all_databases
        dbs = get_all_databases()
        databases = {name: {"info": db.info, "device": db.device, "additional_instructions": db.additional_instructions}
                     for name, db in dbs.items()}
    except Exception:
        databases = {}

    prompt = f"""You are a helpful AI assistant responsible for computation on \n"""
    for d in req_databases:
        if d in databases:
            prompt += f" {d}: {databases[d]['info']}\n"
            prompt += f" Device: {databases[d]['device']}\n"
            if "additional_instructions" in databases[d] and databases[d]["additional_instructions"]:
                prompt += "additional instructions: "
                prompt += databases[d]["additional_instructions"]

    # prompt += "Your TASK: {user_query}\n\n"

    prompt += "You can fetch data from databases using following functions: \n\n"

    for func_id, details in functions.items():
        if "usecase" not in details or "code_generation" not in details["usecase"]:
            continue
        prompt += f" Function ID: {func_id}\n"
        prompt += f"    {details['name']} ({', '.join(details['params'].keys())}):\n"
        prompt += f"        {details['description']}\n\n"
        if "coding_instructions" in details:
            prompt += f"        {details['coding_instructions']}\n\n"

        # Add arguments with descriptions
        prompt += "        Args:\n"
        for param, param_desc in details['params'].items():
            prompt += f"            {param} ({param_desc['type']}): {param_desc['description']}\n"

        # Add return values with descriptions
        prompt += "\n        Returns:\n"
        if isinstance(details['returns'], dict):
            for ret, ret_desc in details['returns'].items():
                prompt += f"            - {ret} ({ret_desc['type']}): {ret_desc['description']}\n"
        else:
            prompt += f"            {details['returns']}\n"
        prompt += "\n example output:"
        if 'example' in details:
            prompt += f"            {details['example']}\n"
        prompt += "\n"

    prompt += f"""

        Assume the functions take date in format "%Y-%m-%d %H:%M:%S".

        DO NOT MOCK data or write code for functions mentioned above. 
        if not data can be retrived just say that but do not use MOCK data
        do not write placeholder functions for functions mentioned above.
        Assume that the code of functions mentioned above are available to fetch data. Just import the functions.


        {function_imports}
        Solve the task using your coding and language skills.
        In the following cases, suggest python code (in a python coding block) or shell script (in a sh coding block) for the user to execute.
            1. When you need to collect info, use the code to output the info you need, for example, browse or search the web, download/read a file, print the content of a webpage or a file, get the current date/time, check the operating system. After sufficient info is printed and the task is ready to be solved based on your language skill, you can solve the task by yourself.
            2. When you need to perform some task with code, use the code to perform the task and output the result. Finish the task smartly.
        Solve the task step by step if you need to. If a plan is not provided, explain your plan first. Be clear which step uses code, and which step uses your language skill.
        When using code, you must indicate the script type in the code block. The user cannot provide any other feedback or perform any other action beyond executing the code you suggest. The user can't modify your code. So do not suggest incomplete code which requires users to modify. Don't use a code block if it's not intended to be executed by the user.
        If you want the user to save the code in a file before executing it, put # filename: <filename> inside the code block as the first line. Use filename as "code_generation.py" or "code_generation.sh" for python and shell scripts respectively.
         Don't include multiple code blocks in one response. Do not ask users to copy and paste the result. Instead, use 'print' function for the output when relevant. Check the execution result returned by the user.

          Include these import statements in the top for your code:

            {include_statements} 


        If the result indicates there is an error, fix the error and output the code again. Suggest the full code instead of partial code or code changes. If the error can't be fixed or if the task is not solved even after the code is executed successfully, analyze the problem, revisit your assumption, collect additional info you need, and think of a different approach to try.
        When you find an answer, verify the answer carefully. Include verifiable evidence in your response if possible.
        After you get the results from executed code and you think that answers the query include "TERMINATE" in the end of the response.
        Reply "TERMINATE" in the end only when code has been executed and task is complete.
        if you can't call functions after multiple retries due to some issues just Reply "Fetching Data Failed TERMINATE".
        """

    return prompt




