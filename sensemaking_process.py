import os
from re import VERBOSE
import sys
import json
from termios import VERASE
import time

import agents.sensemaking_agent

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'agents')))

from agents import sensemaking_agent, information_seeking_agent, \
    action_plan_generation_agent, generic_database_manager, presentation_agent
from agents.database_registry import get_all_databases
from agents.next_step_agent import NextStepAgent
from agents.config import VERBOSE

max_iters = 3


def print_welcome():
    """Print welcome message and supported databases"""
    print("\n" + "="*80)
    print("🤖 WELCOME TO SENSEMAKING PROCESS USING GLOSS 🤖")
    print("="*80)

    # Get all available databases
    databases = get_all_databases()

    print(f"\n📊 SUPPORTED DATABASES ({len(databases)} total):")
    print("-" * 60)

    # Group databases by device type
    device_groups = {}
    for name, db in databases.items():
        device = db.device
        if device not in device_groups:
            device_groups[device] = []
        device_groups[device].append((name, db.info))

    for device, db_list in device_groups.items():
        print(f"\n📱 {device.upper()} DATABASES:")
        for name, info in db_list:
            print(f"   • {name}: {info[:60]}{'...' if len(info) > 60 else ''}")

    print("\n" + "="*80 + "\n")


def print_step(step_name, content="", verbose=True):
    """Print a step with pretty formatting"""
    if not verbose:
        return

    print(f"\n{'🔹' * 20} {step_name} {'🔹' * 20}")
    if content:
        print(content)
    print("-" * 60)


def print_memory(memory, verbose=True):
    """Print memory with pretty formatting"""
    if not verbose or not memory.strip():
        return

    print("MEMORY:")
    print("-" * 60)
    print(memory.strip())


def print_understanding(understanding, verbose=True):
    """Print understanding with pretty formatting"""
    if not verbose or not understanding.strip():
        return

    print("UNDERSTANDING:")
    print("-" * 60)
    print(understanding.strip())

class SenseMaker:
    def __init__(self, question, presentation_instructions):
        self.user_query = question
        self.presentation_instructions = presentation_instructions
        self.memory = ''
        self.answer = ''
        self.current_step = ""
        self.understanding = ''
        self.action_plan = ''
        self.function_calls = []
        self.information_request = []
        self.step_history = []
        self.sense_making_agent = agents.sensemaking_agent.SenseMakingAgent()
        self.information_seeking_agent = agents.information_seeking_agent.InformationSeekingAgent()
        self.generic_db_manager = agents.generic_database_manager.GenericDatabaseManager()
        self.presentation_agent = agents.presentation_agent.PresentationAgent()
        self.next_step_agent = NextStepAgent()
        self.state_dict = {"INF": "INFORMATION SEEKING", "END": "END"}

        self.action_plan_generator_agent = agents.action_plan_generation_agent.ActionPlanGenerationAgent()

    def make_sense(self, verbose=True):
        # Print welcome message and supported databases
        print_welcome()

        self.current_step = "START"
        self.step_history.append(self.current_step)
        time.sleep(1)

        if self.user_query == "" or self.presentation_instructions == "":
            self.answer = "Incomplete query or instructions"
            self.current_step = "FINISH"
            return

        self.current_step = "ACTION PLAN GENERATION"
        self.step_history.append(self.current_step)
        print_step("ACTION PLAN GENERATION", verbose=verbose)

        action_plans = self.invoke_with_retry(self.action_plan_generator_agent, 'invoke', {'user_query': self.user_query})

        # invoke_with_retry returns the string "FAILED" once retries are spent.
        # Without this check the "NOT POSSIBLE" test below reads as a substring
        # match, falls through, and indexes a string.
        if action_plans == "FAILED":
            self.answer = ("Could not generate an action plan: the language model call failed. "
                           "Check that GATEWAY_API_KEY is set and the model gateway is reachable.")
            if verbose:
                print(f"❌ {self.answer}")
            self.current_step = "FINISH"
            return

        if "NOT POSSIBLE" in action_plans:
            if verbose:
                print("❌ Not possible to answer the question with current data")
        else:
            if verbose:
                print(f"📋 Action plan: {action_plans['action_plan']}")
            self.action_plan = action_plans["action_plan"]
            if (self.action_plan == "The query cannot be answered with given datasets"):
                self.answer = "The query cannot be answered with given datasets"
                self.current_step = "FINISH"
                return

        num_iters = 0

        while self.current_step != "END":

            # Counts attempts, not successes. The increment used to sit deep in
            # the success path, so a failing step left it at zero, the
            # num_iters >= max_iters exit below could never fire, and the loop
            # spun indefinitely making LLM calls the whole time.
            num_iters += 1

            if num_iters > max_iters:
                # Budget spent: stop asking what to do next and go present
                # whatever understanding was built up.
                if verbose:
                    print(f"⚠️  Reached the {max_iters}-iteration limit without finishing; "
                          f"presenting what is known so far")
                state = "END"
            else:
                response = self.invoke_with_retry(self.next_step_agent, 'invoke_next_step', {
                    'user_query': self.user_query,
                    'memory': self.memory,
                    'understanding': self.understanding,
                    'action_plan': self.action_plan
                })

                state = None
                try:
                    # response_dict = json.loads(response)
                    if isinstance(response, dict) and "next_step" in response:
                        state = response["next_step"]
                except Exception as e:
                    if verbose:
                        print(f"❌ Error in response: {str(e)}")
                    continue

                # A failed call returns the string "FAILED", not a dict, so state
                # stays None. Retrying is fine; falling through would either raise
                # UnboundLocalError or silently reuse the previous state.
                if state is None or state not in self.state_dict:
                    if verbose:
                        print(f"❌ Next-step agent gave no usable state (got {response!r}); "
                              f"attempt {num_iters} of {max_iters}")
                    continue

                if verbose:
                    print(f"🔄 Returned state: {state}")

            self.current_step = self.state_dict[state]
            self.step_history.append(self.current_step)

            if state == "INF" or state == 'INF':
                state = "INF"
                if verbose:
                    print_step("INFORMATION SEEKING", verbose=verbose)

                response = self.invoke_with_retry(self.information_seeking_agent, 'invoke', {
                    'understanding': self.understanding,
                    'user_query': self.user_query,
                    'action_plan': self.action_plan,
                    'memory': self.memory
                })

                if 'NOT POSSIBLE' in response:
                    self.memory += f"\n\nNot possible to answer {self.user_query} using the available data. CODE-999."
                    self.understanding += f"\n\nNot possible to answer {self.user_query} using the available data. CODE-999."
                    continue

                if not "database" in response:
                    continue
                database = response["database"]
                request = response["request"]
                database = database.split(',')
                database = [d.strip() for d in database]
                self.information_request.append(f"{database}: {request}")

                if verbose:
                    print(f"🔍 Querying databases: {database}")
                    print(f"📝 Request: {request}")

                results = None

                results = self.invoke_with_retry(self.generic_db_manager, 'invoke',
                                                 {'user_query': request, 'databases': database})
                if results == "FAILED":
                    results = None

                elif database == "NOT POSSIBLE":
                    self.memory += f"\n\nNot possible to answer {request} using the available data. CODE-999."

                if results:
                    if ("NOT POSSIBLE" in results):
                        local_sense = f"Failed to generate results because {results['NOT POSSIBLE']}"
                    else:
                        for res in results:
                            if ('func' in res):
                                self.function_calls.append(res['func'])

                        if verbose:
                            print_step("LOCAL SENSEMAKING", verbose=verbose)
                            print("Creating natural language interpretation of code results and updating memory...")


                        self.current_step = "LOCAL SENSEMAKING"
                        self.step_history.append(self.current_step)

                        response = self.invoke_with_retry(self.sense_making_agent, 'invoke_local_sense', {
                            'results': results,
                            'data_type': database,
                            'user_query': request
                        })
                        if (response != "FAILED"):
                            if ("NOT POSSIBLE" not in response):
                                local_sense = response["summary"]
                            else:
                                local_sense = f"Failed to generate local sense of results because {response['NOT POSSIBLE']}"
                        else:
                            local_sense = f"Failed to generate local sense of results because of LLM call failure"

                    question_and_sense = f"Question: \n {request} \n\n Database: \n {database} \n\n Answer: \n {local_sense}\n\n"
                    self.memory += "\n\n" + question_and_sense

                    print_memory(self.memory, verbose)

                    if verbose:
                        print_step("GLOBAL SENSEMAKING", verbose=verbose)
                        print("Updating understanding...")

                    self.current_step = "GLOBAL SENSEMAKING"
                    self.step_history.append(self.current_step)

                    response = self.invoke_with_retry(self.sense_making_agent, 'invoke_global_sense', {
                        'user_query': self.user_query,
                        'understanding': self.understanding,
                        'memory': self.memory,
                        "action_plan": self.action_plan
                    })
                    if (response != "FAILED"):
                        self.understanding = response['understanding']
                    # num_iters is incremented at the top of the loop now, so
                    # that failing iterations also count against the budget.
                    if verbose:
                        print(f"🔄 Number of iterations: {num_iters}")
                    print_understanding(self.understanding, verbose)

            if state == "END" or state == 'END' or num_iters >= max_iters:
                state = "END"
                if verbose:
                    print("\n" + "🎯" * 20 + " END OF SENSEMAKING " + "🎯" * 20)
                    print_understanding(self.understanding, verbose)

                self.current_step = "PRESENTATION"
                self.step_history.append(self.current_step)

                if verbose:
                    print_step("PRESENTATION", verbose=verbose)

                answer = self.invoke_with_retry(self.presentation_agent, 'invoke', {
                    'user_query': self.user_query,
                    'understanding': self.understanding,
                    'instructions': self.presentation_instructions
                })
                # Same "FAILED" sentinel as the action-plan call. This one fires
                # at the very end, so rather than lose a completed run to a
                # TypeError, fall back to the understanding built up so far.
                if answer == "FAILED" or not isinstance(answer, dict) or "response" not in answer:
                    self.answer = (self.understanding or
                                   "No answer could be produced.") + \
                                  "\n\n(Presentation step failed; showing the raw understanding.)"
                else:
                    self.answer = answer["response"]

                print("\n" + "🎉" * 20 + " FINAL ANSWER " + "🎉" * 20)
                print(self.answer)
                print("🎉" * 50)

                self.current_step = "FINISH"
                self.step_history.append(self.current_step)
                break
            if state != "END" and state != 'INF':
                if verbose:
                    print("❌ Invalid state")
                    print(state)
                self.step_history.append("INVALID STATE")

    def invoke_with_retry(self, agent, method, params, max_retries=1):
        retries = 0
        while retries <= max_retries:
            try:
                return getattr(agent, method)(params)
            except Exception as e:
                retries += 1
                if retries > max_retries:
                    print(f"Failed after {max_retries + 1} attempts: {str(e)}")
                    return "FAILED"


if __name__ == "__main__":


    presentation_instructions_ = '''
    clear and concise
    '''
    # ---- EDIT THIS: ask your own question, then re-run the script ----------
    # The user id in the sample data is always "user1". Data spans 2019-2022;
    # 2020-11-02 is a well-populated day to start from.
    # The closing ''' is kept on its own line so the question can be replaced
    # outright -- in vi, cc on that line -- without retyping the quotes.
    query = '''
    on nov 2 2020, for user1 how many text messages were sent and received, and how many hours were spent at home?
    '''
    SenseMaker(
        query,
        presentation_instructions_).make_sense(verbose=VERBOSE)
