# Standard library imports
import base64
import json
import os
import threading
import time
import webbrowser

# Third-party imports
import streamlit as st

# Local imports
import sensemaking_process


def start_sense_making(query_input, presentation_instructions):
    """Start the sensemaking process with the given query and instructions"""
    if st.session_state.status == "Completed":
        reset_state()
        st.session_state.retain_results = False

    if 'sense_maker' not in st.session_state:
        st.session_state.sense_maker = sensemaking_process.SenseMaker(
            query_input,
            presentation_instructions
        )

    if not st.session_state.sensemaker_running:
        st.session_state.sensemaker_running = True
        st.session_state.status = "Running"

        threading.Thread(target=st.session_state.sense_maker.make_sense).start()


def reset_state():
    """Reset the session state"""
    for key in st.session_state.keys():
        if key == "sense_maker":
            del st.session_state[key]


def create_and_link_html(content, title="Page", filename="page.html"):
    """
    Creates a local HTML file dynamically and provides a clickable link to open it.
    Args:
        content (str): The content of the HTML page.
        title (str): The title of the HTML page.
        filename (str): The name of the file to save locally.
    """
    # Define the HTML structure with improved styling
    html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    margin: 0;
                    padding: 0;
                    background-color: #f4f7f6;
                    color: #333;
                    line-height: 1.6;
                    display: block;  /* Change from flex to block */
                    height: 100vh;
                    box-sizing: border-box;
                    overflow: hidden;
                }}
                .container {{
                    width: 80%;
                    max-width: 900px;
                    max-height: 90%;
                    background-color: #fff;
                    border-radius: 10px;
                    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
                    padding: 20px;
                    text-align: left;  /* Align text to the left */
                    overflow-y: auto; /* Enable vertical scrolling if content is too long */
                    margin: 0 auto;  /* Center container horizontally */
                }}
                h1 {{
                    color: #2c3e50;
                    font-size: 2em;
                    margin-bottom: 20px;
                    text-align: center;  /* Keep heading centered */
                }}
                .content-box {{
                    background-color: #ecf0f1;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
                    font-size: 1.1em;
                    color: #2c3e50;
                    white-space: pre-wrap; /* Preserve formatting */
                    text-align: left;  /* Ensure content is aligned to the left */
                }}
                .footer {{
                    margin-top: 20px;
                    font-size: 0.9em;
                    color: #7f8c8d;
                    text-align: center; /* Footer remains centered */
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{title}</h1>
                <div class="content-box">
                    \n{content}
                </div>
                <div class="footer">
                    <p>Presented by GLOSS Sensemaking System</p>
                </div>
            </div>
        </body>
        </html>
    """

    # Save the HTML file
    with open(filename, "w") as f:
        f.write(html_template)

    # Get the absolute path of the file
    file_path = os.path.abspath(filename)
    file_url = f"file://{file_path}"

    # Attempt to open the file in the default web browser
    try:
        webbrowser.open(file_url)
        print("success")
    except Exception as e:
        print(f"Error opening file: {e}")


def render_button():
    """Render the download buttons for different components"""
    with download_action_plan_container:
        if st.button("Open in New Tab", key=f"action_plan"):
            if "sense_maker" in st.session_state:
                create_and_link_html(st.session_state.sense_maker.action_plan, f"Action Plan")
                update_dashboard()

    with download_info_request_container:
        if st.button("Open in New Tab", key=f"ir"):
            if "sense_maker" in st.session_state:
                content = json.dumps(st.session_state.sense_maker.information_request)
                create_and_link_html(content, f"Information Requests")
                update_dashboard()

    with download_memory_container:
        if st.button("Open in New Tab", key=f"memory"):
            if "sense_maker" in st.session_state:
                create_and_link_html(st.session_state.sense_maker.memory, f"Memory")
                update_dashboard()

    with download_understanding_container:
        if st.button("Open in New Tab", key=f"understanding"):
            if "sense_maker" in st.session_state:
                create_and_link_html(st.session_state.sense_maker.understanding, f"Understanding")
                update_dashboard()

    with download_function_call_container:
        if st.button("Open in New Tab", key=f"function_calls"):
            if "sense_maker" in st.session_state:
                content = json.dumps(st.session_state.sense_maker.function_calls, indent=4)
                create_and_link_html(content, f"Funtion Calls")
                update_dashboard()


def update_dashboard():
    """Update the dashboard with current sensemaking state"""
    timestamp = time.time()
    with status_container:
        st.markdown(
            f'<div class="status-container"><span class="status-icon">🔄</span>Status: {st.session_state.status}</div>',
            unsafe_allow_html=True)

    with current_step_container:
        with st.expander("Current Step", expanded=True):
            st.markdown('<div class="box current-step"><p>{}</p></div>'.format(
                st.session_state.sense_maker.current_step), unsafe_allow_html=True)

    with action_plan_container:
        st.markdown(
            '<div class="box action-plan"><p>{}</p></div>'.format(
                st.session_state.sense_maker.action_plan),
            unsafe_allow_html=True)

    with info_request_container:
        info_request_content = "<ul>" + "".join(
            f"<li>{item}</li>" for item in st.session_state.sense_maker.information_request) + "</ul>"

        st.markdown(f'<div class="box information-request">{info_request_content}</div>',
                    unsafe_allow_html=True)

    with memory_container:
        st.markdown(
            '<div class="box memory"><p>{}</p></div>'.format(st.session_state.sense_maker.memory),
            unsafe_allow_html=True)

    with understanding_container:
        st.markdown(
            '<div class="box understanding"><p>{}</p></div>'.format(
                st.session_state.sense_maker.understanding),
            unsafe_allow_html=True)

    with function_call_container:
        function_call_content = "<ul>" + "".join(
            f"<li>{item}</li>" for item in st.session_state.sense_maker.function_calls) + "</ul>"

        st.markdown(f'<div class="box function-calls">{function_call_content}</div>',
                    unsafe_allow_html=True)


# Main UI Configuration
st.set_page_config(page_title="GLOSS: Sensemaking System", page_icon="🔍", layout="wide")

# CSS Styles
st.markdown("""
    <style>
        .vertical-line {
            border-left: 3px solid black; /* Bold black line */
            height: 10vh; /* Set height to 10% of viewport height */
            position: absolute; /* Ensure it takes up its column */
            left: 45%; /* Shift towards the left (adjust percentage as needed) */
            margin-top: -5vh; /* Adjust top margin to bring it closer to the heading */
            margin-bottom: 5vh; /* Maintain bottom margin */
        }
        .col2-container {
            padding-left: 20px; /* Add padding before col2 */
        }
        .column-container {
            position: relative; /* Parent container for proper alignment */
            display: flex; /* Ensure columns are aligned properly */
        }
        body {
            font-family: Arial, sans-serif;
        }
        .box {
            border-radius: 5px;
            padding: 15px;
            margin: 10px 0;
            color: inherit;  /* Adapts text color to current theme */
            overflow-y: auto;
            max-height: 300px;  /* Adjust height as needed */
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .action-plan {
            background-color: #e8f5e8;  /* Light green */
            border-left: 4px solid #4caf50;
        }
        .information-request {
            background-color: #fff3e0;  /* Light orange */
            border-left: 4px solid #ff9800;
        }
        .memory {
            background-color: #e3f2fd;  /* Light blue */
            border-left: 4px solid #2196f3;
        }
        .understanding {
            background-color: #f3e5f5;  /* Light purple */
            border-left: 4px solid #9c27b0;
        }
        .function-calls {
            background-color: #fff8e1;  /* Light yellow */
            border-left: 4px solid #ffc107;
        }
        .current-step {
            background-color: #fce4ec;  /* Light pink */
            border-left: 4px solid #e91e63;
        }
        .status-container {
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: bold;
            padding: 10px;
            border-radius: 5px;
            background-color: #f0f0f0;
        }
        .status-icon {
            font-size: 1.2em;
        }
    </style>
""", unsafe_allow_html=True)

# Page Title
st.title("GLOSS: Sensemaking System 🔍")

# Layout with padding and vertical line
col1, col2 = st.columns([3, 1], gap="medium")  # Adjust proportions for layout

# Wrap columns in a container for styling
st.markdown('<div class="column-container">', unsafe_allow_html=True)

# Column 1 content with additional padding
with col1:
    st.markdown('<div class="col2-container">', unsafe_allow_html=True)
    query_input = st.text_input("Enter your query:", placeholder="Type your question here...")
    presentation_instructions = st.text_input("Enter presentation instructions:",
                                              placeholder="Type instructions here...")
    st.markdown('</div>', unsafe_allow_html=True)
    if st.button("Start Sense-Making", key="start_button", help="Click to initiate the sense-making process."):
        start_sense_making(query_input, presentation_instructions)

st.markdown('</div>', unsafe_allow_html=True)  # Close the column container

# Initialize session state variables
if 'sensemaker_running' not in st.session_state:
    st.session_state.sensemaker_running = False

if 'retain_results' not in st.session_state:
    st.session_state.retain_results = False

if 'status' not in st.session_state:
    st.session_state.status = "Not started"

# Create containers for different sections
status_container = st.container()
current_step_container = st.container()

# Create columns for the dashboard
sense_cols = st.columns(2)

with sense_cols[0]:
    with st.expander("Action Plan", expanded=True):
        action_plan_container = st.empty()
        download_action_plan_container = st.empty()

with sense_cols[1]:
    with st.expander("Information Requests", expanded=True):
        info_request_container = st.empty()
        download_info_request_container = st.empty()

# Create more columns for additional sections
memory_cols = st.columns(2)

with memory_cols[0]:
    with st.expander("Memory", expanded=True):
        memory_container = st.empty()
        download_memory_container = st.empty()

with memory_cols[1]:
    with st.expander("Understanding", expanded=True):
        understanding_container = st.empty()
        download_understanding_container = st.empty()

# Function calls section
with st.expander("Function Calls", expanded=True):
    function_call_container = st.empty()
    download_function_call_container = st.empty()

# Render buttons and update dashboard
render_button()

# Keep the UI updating periodically while the process runs
if st.session_state.sensemaker_running:
    while st.session_state.sensemaker_running and st.session_state.sense_maker.current_step != "FINISH":
        update_dashboard()
        time.sleep(1)  # Smooth update every second

# Once the process is complete, display the final results
if st.session_state.sensemaker_running and st.session_state.sense_maker.current_step == "FINISH":
    with st.expander("Final Answer", expanded=True):
        st.session_state.status = "Completed"
        st.session_state.sensemaker_running = False
        st.session_state.retain_results = True
        update_dashboard()
        st.write(st.session_state.sense_maker.answer)  # Show the final answer in an expander
    st.success("Completed SenseMaking")
    st.balloons()

elif st.session_state.retain_results:
    with st.expander("Final Answer", expanded=True):
        st.write(st.session_state.sense_maker.answer)
    st.success("Completed SenseMaking")

# Footer with additional styling
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("<footer style='text-align: center;'>© 2024 GLOSS Sensemaking System</footer>", unsafe_allow_html=True)
