from matplotlib import pyplot as plt
from datetime import datetime
import matplotlib.dates as mdates

def plot_blocks(blocks, name):
    """
    Plots the  blocks on a timeline with different colors for different activities.

    Parameters:
    - blocks: List of blocks, each defined by an type, start time, and end time.
    """
    color_list = ['red', 'green', 'blue', 'yellow', 'orange', 'purple', 'brown', 'pink', 'gray', 'cyan']

    # Create a mapping of activities to colors
    types = list(set(block[0] for block in blocks))
    colors = {block: color for block, color in zip(types, color_list)}

    fig, ax = plt.subplots()

    # Convert timestamps to datetime objects for plotting
    for block in blocks:
        type = block[0]
        start_time = datetime.fromtimestamp(block[1])
        end_time = datetime.fromtimestamp(block[2])
        color = colors.get(type, 'black')  # Default to black if  not found

        # Plotting each  block
        plt.plot([start_time, end_time], [1, 1], color=color, linewidth=10, solid_capstyle='butt')

    # Improve the x-axis with date formatting
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

    plt.yticks([])  # Hide y-axis ticks
    plt.title(f'{name} Timeline')
    plt.xlabel('Time')

    # Creating a custom legend
    custom_lines = [plt.Line2D([0], [0], color=color, lw=4) for color in color_list[:len(types)]]
    plt.legend(custom_lines, types)

    plt.tight_layout()
    plt.show()
