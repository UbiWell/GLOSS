import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

from datetime import datetime
from datetime import timedelta
import agents.generic_summarizer
import numpy as np
import pandas as pd
import pytz

from math import sin, cos, sqrt, atan2, radians

from geopy.distance import great_circle
from scipy import spatial
from geopy import distance
from shapely.geometry import MultiPoint
from sklearn.cluster import DBSCAN
from data_processing.data_processing_utils import fetch_documents_between_timestamps
from data_streams.constants import IOS_LOCATION, home_locations, GOOGLE_API_KEY
import folium
from geopy.geocoders import Nominatim
from geopy.geocoders import GoogleV3
from agents.coding_agent import run_coding_agent
from data_streams.constants import time_zone_dict

functions = {
    "LOC1": {
        "name": "get_location_records",
        "description": "Retrieves raw GPS location records for a specific user within a given time range.",
        "function_call_instructions": "call this only when the time range between start_time and end_time is less than 3 hours",
        "usecase": ["code_generation", "function_calling"],
        "params": {
            "uid": {"type": "str",
                    "description": "The unique identifier for the user whose location trace is to be fetched."},
            "start_time": {"type": "str",
                           "description": "The start of the time range for which location data is required."},
            "end_time": {"type": "str",
                         "description": "The end of the time range for which location data is required."}
        },
        "returns": "A list of GPS records per minute containing latitude, longitude, and altitude.",
        "example": "[{'timestamp': '2024-07-09 12:12:29', 'latitude': 42.329721, 'longitude': -71.091918, 'altitude': 15.27495}, {'timestamp': '2024-07-09 12:14:29', 'latitude': 42.329721, 'longitude': -71.091918, 'altitude': 15.274935}]"
    },
    "LOC2": {
        "name": "get_location_statistical_metrics",
        "description": "Calculates various statistical metrics related to the user's GPS location data within a specified time range.",
        "usecase": ["code_generation", "function_calling"],
        "params": {
            "uid": {"type": "str",
                    "description": "The unique identifier for the user whose location metrics are to be calculated."},
            "start_time": {"type": "str",
                           "description": "The start of the time range for which metrics are to be calculated."},
            "end_time": {"type": "str",
                         "description": "The end of the time range for which metrics are to be calculated."}
        },
        "returns": {
            "total_time_all_centers": {"type": "float",
                                       "description": "Total time spent at significant locations in minutes."},
            "max_displacement": {"type": "float",
                                 "description": "Maximum distance between significant locations in metres."},
            "distance_sum": {"type": "float",
                             "description": "Total distance traveled between significant locations in metres."},
            "num_loc_visited": {"type": "int",
                                "description": "Number of distinct significant locations visited."},
            "displacement_sum": {"type": "float",
                                 "description": "Sum of distances between successive significant locations in metres."},
            "radius_of_gyration": {"type": "float",
                                   "description": "Radius of gyration around the center of mass of significant locations."},
            "location_entropy": {"type": "float",
                                 "description": "Entropy of the distribution of time spent at significant locations."},
            "normalized_location_entropy": {"type": "float",
                                            "description": "Normalized entropy relative to the number of significant locations."}
        },
        "example": "{'time_spent_at_home': 3293.8166666666666, 'total_time_all_centers': 2.0, 'max_displacement': 3843.7037772737785, 'distance_sum': 22688.591635247525, 'num_loc_visited': 17, 'displacement_sum': 34083.0840341885, 'radius_of_gyration': 73153.20288111967, 'location_entropy': -14188.73749375572, 'nomalized_location_entropy': -5008.001788330625, 'max_displacement_from_home': 3996.07932168392}"
    },
    "LOC3": {
        "name": "get_location_paths",
        "description": "Extracts and organizes distinct paths taken by a user based on GPS location data within a specified time range.",
        "usecase": ["code_generation", "function_calling"],
        "params": {
            "uid": {"type": "str",
                    "description": "The unique identifier for the user whose location paths are to be retrieved."},
            "start_time": {"type": "str",
                           "description": "The start of the time range for which location data is to be analyzed."},
            "end_time": {"type": "str",
                         "description": "The end of the time range for which location data is to be analyzed."}
        },
        "returns": "GPS location of starting and end point of paths taken",
        "example": "[{'starting_point': {'timestamp': 1720541549, 'latitude': 42.329721, 'longitude': -71.091918, 'altitude': 15.27495}, 'end_point': {'timestamp': 1720541549, 'latitude': 42.329721, 'longitude': -71.091918, 'altitude': 15.27495}}, {'starting_point': {'timestamp': 1720565225, 'latitude': 42.331035, 'longitude': -71.09332, 'altitude': 13.192509}, 'end_point': {'timestamp': 1720566122, 'latitude': 42.340017, 'longitude': -71.09058, 'altitude': 6.118234}}]"
    },
    "LOC4": {
        "name": "get_address_from_coordinates",
        "usecase": ["function_calling"],
        "description": "Retrieves the address of a location given its latitude and longitude.",
        "code_generation_instructions": "Do all the processing in latitude and longitude values and only call this function when you need to fetch the address at the last. This is an expensive function to call. Call it at end for few latitude longitude pairs",
        "params": {
            "latitude": {"type": "float", "description": "The latitude of the location."},
            "longitude": {"type": "float", "description": "The longitude of the location."}
        },
        "returns": "The address of the location if found, otherwise an empty string."
    },
    "LOC5": {
        "name": "get_location_at_given_time",
        "description": "Retrieves the GPS location record closest to a given timestamp for a specific user.",
        "usecase": ["code_generation", "function_calling"],
        "params": {
            "uid": {"type": "str", "description": "The user ID for whom the location is to be fetched."},
            "given_time": {"type": "str",
                           "description": "The time (in '%Y-%m-%d %H:%M:%S' format) around which the location needs to be found."}
        },
        "returns": "A dictionary containing the location and its timestamp.",
        "example": "{'latitude': 42.329721, 'longitude': -71.091918, 'altitude': 15.27495, 'timestamp': '2024-07-09 12:12:00'}"
    },

    "LOC7": {
        "name": "get_location_summary",
        "usecase": ["function_calling"],
        "description": "Retrieves a summary of GPS location records for a specific user within a given time range based on instructions provided.",
        "function_call_instructions": "Use this function for qualitative/subjective requests. Only call this function when other functions can't answer the query. Do not call this function if startime and endtime are more than 24 hours apart",
        "params": {
            "uid": {"type": "str",
                    "description": "The unique identifier for the user whose location trace is to be fetched."},
            "start_time": {"type": "str",
                           "description": "The start of the time range for which location data is required."},
            "end_time": {"type": "str",
                         "description": "The end of the time range for which location data is required."},
            "instructions": {"type": "str", "description": "Instructions for summarizing the data."}
        },
        "returns": "A summary of location coordinates based on the provided instructions."
    },
}


def sort_pd_series(clusters):
    s = clusters.str.len().sort_values(ascending=False).index
    c = clusters.reindex(s)
    c = c.reset_index(drop=True)
    return c


def get_centermost_point(cluster):
    centroid = (MultiPoint(cluster).centroid.x, MultiPoint(cluster).centroid.y)
    centermost_point = min(cluster, key=lambda point: great_circle(point, centroid).m)
    return tuple(centermost_point)


def calc_location_distance(u, v):
    try:
        loc_dist = get_distance(u, v)
    except:
        loc_dist = spatial.distance.euclidean(u, v)

    return loc_dist


def get_distance(loc0, loc1):
    return distance.distance(loc0, loc1).m


def get_distance_manual(lat1, lon1, lat2, lon2):
    R = 6373.0

    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    distance = R * c
    return distance * 1000


def get_location_records(uid, start_time, end_time, select_one_from_minute=False):
    # Use New York time zone if the user's timezone is "est"
    user_timezone = time_zone_dict.get(uid, "est")
    timezone = pytz.timezone("America/New_York") if user_timezone == "est" else pytz.timezone(user_timezone)

    # Convert start and end time if they are strings
    if not isinstance(start_time, float):
        if isinstance(start_time, str):
            start_time = timezone.localize(datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
            end_time = timezone.localize(datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
        start_time = start_time.timestamp()
        end_time = end_time.timestamp()

    # Fetch GPS records
    gps_records = fetch_documents_between_timestamps(uid, start_time, end_time, IOS_LOCATION)

    last_timestamp = 0
    location_log = []
    for instance in gps_records:
        if instance['accuracy'] < 100:
            if select_one_from_minute:
                if instance['timestamp'] - last_timestamp > 65:
                    location_log.append(instance)
                    last_timestamp = instance['timestamp']
            else:
                location_log.append(instance)

    return process_records(uid, location_log)


def get_location_at_given_time(uid, given_time):
    given_time_ = datetime.strptime(given_time, "%Y-%m-%d %H:%M:%S")

    # Define the start and end time with a 5-minute range
    start_time = given_time_ - timedelta(minutes=10)
    end_time = given_time_ + timedelta(minutes=10)

    # Fetch activity records for the user within the given time window
    records = get_location_records(uid, start_time, end_time)

    # Find the closest record by comparing the time difference
    if (records):
        closest_record = min(records, key=lambda record: abs(
            datetime.strptime(record['timestamp'], "%Y-%m-%d %H:%M:%S") - given_time_))

        return {'latitude': closest_record['latitude'], 'longitude': closest_record['longitude'],
                'altitude': closest_record['altitude'], 'timestamp': given_time}
    else:
        return {}


def is_home(uid, location):
    # tmp_client = DbConfig().getTempClient()
    # tmp_db = tmp_client['pheno']
    home = home_locations[uid]
    auto_distance = get_distance(home['centroid'], [location['latitude'], location['longitude']])
    # manual_distance = get_distance_manual(home['centroid'][0], home['centroid'][1],
    #                                       phone['latitude'], phone['longitude'])
    if auto_distance < 50:
        return True
    return False


def get_home(uid):
    # tmp_client = DbConfig().getTempClient()
    # tmp_db = tmp_client['pheno']
    home = home_locations[uid]
    return home['centroid']


# def get_total_run_time(u, start_time, end_time):
#     # tmp_client = DbConfig().getTempClient()
#     # tmp_db = tmp_client['pheno']
#     location_checks = tmp_db[ANDROID_GENERAL].find(
#         {'uid': u, 'event_id': 199, 'timestamp': {'$gt': start_time - (60 * 16), '$lt': end_time}}).count()
#     total_time = 60 * 11 * location_checks
#     return min(total_time, end_time - start_time)

def get_total_run_time(uid, start_time, end_time):
    loc_trace = get_location_records(uid, start_time, end_time, True)

    first_item = loc_trace[0]  # Fetch the first document
    last_item = loc_trace[1]
    lt = datetime.strptime(last_item['timestamp'], "%Y-%m-%d %H:%M:%S").timestamp()
    ft = datetime.strptime(first_item['timestamp'], "%Y-%m-%d %H:%M:%S").timestamp()

    return min(lt - ft, end_time - start_time)


def get_time_spent_at_home(uid, start_time, end_time):
    loc_trace = get_location_records(uid, start_time, end_time, True)
    # tmp_client = DbConfig().getTempClient()
    # tmp_db = tmp_client['pheno']
    home_time = 0
    tmp_time = start_time
    for location in loc_trace:
        loc_time = datetime.strptime(location['timestamp'], "%Y-%m-%d %H:%M:%S").timestamp()
        if is_home(uid, location):
            time_diff = loc_time - tmp_time
            if time_diff < 60 * 30:
                home_time += time_diff
            tmp_time = loc_time
    end_time_delta = end_time - tmp_time
    if end_time_delta < 1000:
        home_time += end_time_delta
    total_time = get_total_run_time(uid, start_time, end_time)
    if total_time == 0:
        return 0, 0, np.NaN
    return home_time, total_time, float(home_time) / total_time


def is_query_location(query_location, location):
    auto_distance = get_distance(query_location, [location['latitude'], location['longitude']])
    # manual_distance = get_distance_manual(home['centroid'][0], home['centroid'][1],
    #                                       phone['latitude'], phone['longitude'])
    if auto_distance < 50:
        return True
    return False

    pass


def get_time_spent_at_location(uid, start_time, end_time, query_location, loc_trace):
    time_at_location = 0
    tmp_time = start_time
    for location in loc_trace:
        loc_time = datetime.strptime(location['timestamp'], "%Y-%m-%d %H:%M:%S").timestamp()
        if is_query_location(query_location, location):
            time_diff = loc_time - tmp_time
            if time_diff < 60 * 30:
                time_at_location += time_diff
            tmp_time = loc_time
    end_time_delta = end_time - tmp_time
    if end_time_delta < 1000:
        time_at_location += end_time_delta
    total_time = get_total_run_time(uid, start_time, end_time)
    if total_time == 0:
        return 0, 0, np.NaN
    return time_at_location, total_time, float(time_at_location) / total_time
    # return time_at_location, 0, 0


def calculate_radius_gyration(centermost_points, time_spent_at_centers, total_time_all_centers):
    points = MultiPoint(centermost_points)
    centroid = [points.centroid.x, points.centroid.y]
    summation = 0
    for i in range(len(time_spent_at_centers)):
        summation += time_spent_at_centers[i] * (get_distance(centroid, centermost_points[i]) ** 2)
    return np.sqrt(summation / total_time_all_centers)


def calc_max_displacement_from_home(uid, centermost_points):
    home_location = get_home(uid)
    max_displacement = 0
    for i in range(len(centermost_points)):
        current_disp = get_distance(home_location, centermost_points[i])
        if current_disp > 100 and current_disp > max_displacement:
            max_displacement = current_disp
    return max_displacement


def calc_entropy(time_spent_at_centers_ratio):
    entropy = 0
    for i in range(len(time_spent_at_centers_ratio)):
        value = time_spent_at_centers_ratio[i]
        if value > 0:
            entropy += value * np.log(value)
    return 0 - float(entropy)


def plot_map_points(coordinates, output_file, color='blue'):
    """
    Plots points on a map and saves it to an HTML file.

    Parameters:
    - coordinates (list of tuples): List of tuples containing (latitude, longitude) pairs.
    - output_file (str): Name of the output HTML file.
    - color (str): Color of the markers (default is 'blue').
    """
    # Initialize the map centered around the first coordinate pair
    if coordinates:
        center_lat, center_lon = coordinates[0]
    else:
        center_lat, center_lon = 0, 0

    mymap = folium.Map(location=[center_lat, center_lon], zoom_start=4)

    # Add markers for each coordinate pair with specified color
    for coord in coordinates:
        folium.Marker(location=coord, icon=folium.Icon(color=color)).add_to(mymap)

    current_dir = os.path.dirname(__file__)
    output_path = os.path.join(current_dir, output_file)

    # Save the map to an HTML file
    mymap.save(output_path)


def get_location_statistical_metrics(uid, start_time, end_time):
    loc_trace = get_location_records(uid, start_time, end_time, True)

    start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    end_time = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")

    start_time = start_time.timestamp()
    end_time = end_time.timestamp()

    # print(loc_trace)

    cord_list = []
    for item in loc_trace:
        cord_list.append([float(item['latitude']), float(item['longitude'])])

    if len(cord_list) < 2:
        return {
            "total_time_all_centers": np.NaN,
            "max_displacement": np.NaN,
            "distance_sum": np.NaN,
            "num_loc_visited": np.NaN,
            "displacement_sum": np.NaN,
            "radius_of_gyration": np.NaN,
            "location_entropy": np.NaN,
            "nomalized_location_entropy": np.NaN,
            "max_displacement_from_home": np.NaN
        }

    # plot_map_points(coordinates=cord_list, output_file="assets/all_coords.html")
    cord_list = np.array(cord_list)

    kms_per_radian = 6371.0088
    epsilon = 0.03 / kms_per_radian
    db_res = DBSCAN(eps=epsilon, min_samples=2, algorithm='ball_tree', metric='haversine', n_jobs=1).fit(
        np.radians(cord_list))
    labels = db_res.labels_
    num_clusters = len(set(labels) - {-1})
    clusters = pd.Series([cord_list[labels == n] for n in range(num_clusters)])
    centermost_points = []
    if num_clusters > 0:
        clusters = sort_pd_series(clusters)
        centermost_points = clusters.map(get_centermost_point)
    displacement_sum = 0
    max_displacement = 0
    time_spent_at_centers = np.zeros(num_clusters)
    total_time_all_centers = 0
    time_spent_at_centers_ratio = np.zeros(num_clusters)
    last_center = None
    for i in range(num_clusters):
        if i > 0:
            disp_distance = get_distance(centermost_points[i - 1], centermost_points[i])
            if disp_distance > max_displacement:
                max_displacement = disp_distance
            displacement_sum += disp_distance
        time_at_location, total_time, time_spent_ratio = get_time_spent_at_location(uid, start_time, end_time,
                                                                                    centermost_points[i], loc_trace)
        time_spent_at_centers[i] = time_at_location
        time_spent_at_centers_ratio[i] = time_spent_ratio
        if total_time > total_time_all_centers:
            total_time_all_centers = total_time
    # print(np.sum(time_spent_at_centers_ratio))
    # print(time_spent_at_centers_ratio)
    # time_spent_at_home, tmp, tmp1 = get_time_spent_at_home(uid, start_time, end_time)
    radius_of_gyration = 0
    if num_clusters > 0:
        radius_of_gyration = calculate_radius_gyration(centermost_points, time_spent_at_centers, total_time_all_centers)
    location_entropy = calc_entropy(time_spent_at_centers_ratio)
    nomalized_location_entropy = 0 if location_entropy == 0 or num_clusters <= 1 else location_entropy / np.log(
        num_clusters)
    # max_displacement_from_home = calc_max_displacement_from_home(uid, centermost_points)
    num_loc_visited = max(labels) + 1
    for i in range(num_loc_visited):
        cord_list[labels == i] = np.mean(cord_list[labels == i], axis=0)

    distance_sum = 0
    last_loc = None
    for loc in cord_list:
        if last_loc is None:
            last_loc = loc
            continue

        this_dist = get_distance(last_loc, loc)
        distance_sum = distance_sum + this_dist

        last_loc = loc
    return {
        "total_time_all_centers": total_time_all_centers / 60,
        "max_displacement": max_displacement,
        "distance_sum": distance_sum,
        "num_loc_visited": int(num_loc_visited),
        "displacement_sum": displacement_sum,
        "radius_of_gyration": float(radius_of_gyration),
        "location_entropy": location_entropy,
        "nomalized_location_entropy": nomalized_location_entropy,
    }


def process_records(uid, location_records):
    records = []
    uid_timezone = time_zone_dict.get(uid, 'est')  # Get UID-specific timezone or default to EST
    timezone = pytz.timezone("America/New_York") if uid_timezone == "est" else pytz.utc
    for r in location_records:
        d = {}
        time = datetime.fromtimestamp(r['timestamp'], pytz.utc).astimezone(timezone)

        # Format the timestamp and add it to the record
        d['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
        d['latitude'] = r['latitude']
        d['longitude'] = r['longitude']
        d['altitude'] = r['altitude']
        records.append(d)

    return records


def get_location_summary(uid, start_time, end_time, instructions):
    start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
    end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
    summarizer = agents.generic_summarizer.GenericSummarizer()

    summaries = []

    current_time = start_time
    last_summary = ""
    while current_time < end_time:
        print("summarizing for ", current_time)
        next_time = current_time + timedelta(hours=5)
        location_records = get_location_records(uid, current_time.timestamp(), next_time.timestamp(), True)
        summary = summarizer.invoke_granular(
            {'values': location_records, 'summary_n_1': last_summary, 'instructions': instructions, 'type': 'location',
             'window': "5"})
        summary = summary['summary']
        summaries.append(summary)
        last_summary = summary
        current_time = next_time

    if (len(summaries) > 1):
        summary = summarizer.invoke_combination(
            {'summaries': summaries, 'instructions': instructions, 'type': 'location', 'window': "5"})
        summary = summary['summary']

    return summary


def plot_paths_on_map(paths, save_path='assets/map.html'):
    """
    Plots multiple paths on a Folium map and saves it to an HTML file.

    Parameters:
    - paths (list): List of paths, where each path is a list of coordinates.
    - save_path (str): File path to save the HTML map.

    Returns:
    - None
    """
    map_center = [paths[0][0]['latitude'], paths[0][0]['longitude']]  # Center map on the first coordinate

    map_instance = folium.Map(location=map_center, zoom_start=12)

    colors = ['blue', 'red', 'green', 'purple', 'orange', 'darkred', 'darkblue', 'darkgreen']

    for i, path in enumerate(paths):
        points = [(coord['latitude'], coord['longitude']) for coord in path]
        color = colors[i % len(colors)]  # Cycle through colors for paths
        folium.PolyLine(points, color=color, weight=2.5, opacity=1).add_to(map_instance)

    current_dir = os.path.dirname(__file__)
    output_path = os.path.join(current_dir, save_path)

    map_instance.save(save_path)
    print(f"Map saved to {save_path}")


def get_address(latitude, longitude):
    geolocator = Nominatim(user_agent="phone_sensing")
    location = geolocator.reverse((latitude, longitude))
    return location.address


#

from datetime import datetime


def get_location_paths(uid, start_time, end_time):
    coords = get_location_records(uid, start_time, end_time, True)
    paths = []
    current_path = []
    last_moving_coord = coords[0]
    places_visited = []
    places_tracks = []

    # Convert the timestamp to Unix time
    for coord in coords:
        coord['timestamp'] = int(datetime.strptime(coord['timestamp'], '%Y-%m-%d %H:%M:%S').timestamp())

    for i in range(len(coords)):
        if i == 0 or get_distance([coords[i]['latitude'], coords[i]['longitude']],
                                  [coords[i - 1]['latitude'], coords[i - 1]['longitude']]) > 100:

            # Check if there is a gap of 10 minutes or more between current and last moving coordinates
            if (coords[i]['timestamp'] - last_moving_coord['timestamp'] >= 10 * 60):
                paths.append(current_path)
                places_visited.append(last_moving_coord)
                current_path = []

            current_path += [coords[i]]
            last_moving_coord = coords[i]

    # Add the last path if any
    if current_path:
        paths.append(current_path)

    # for p in places_visited:
    #     address = get_address(p['latitude'], p['longitude'])
    #     print(f"{address} visited at {datetime.fromtimestamp(p['timestamp'])}\n")

    user_timezone = time_zone_dict.get(uid, "est")
    # timezone = pytz.timezone("America/New_York") if user_timezone == "est" else pytz.timezone(user_timezone)

    for path in paths:
        if (len(path) > 1):
            duration = path[-1]['timestamp'] - path[0]['timestamp']
            path[0]['timestamp'] = datetime.fromtimestamp(path[0]['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            path[-1]['timestamp'] = datetime.fromtimestamp(path[-1]['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

            places_tracks.append({'starting_point': path[0], 'end_point': path[-1], 'duration': duration})

    return places_tracks


def get_address_from_coordinates(latitude, longitude):
    def get_place_name(lat, lng, api_key):
        geolocator = GoogleV3(api_key=api_key)
        location = geolocator.reverse((lat, lng), exactly_one=True)
        return location.address if location else ""

    # Convert latitude and longitude to float if they are strings
    if isinstance(latitude, str):
        latitude = float(latitude)
    if isinstance(longitude, str):
        longitude = float(longitude)

    api_key = GOOGLE_API_KEY
    place_name = get_place_name(latitude, longitude, api_key)
    return place_name


if __name__ == "__main__":
    start_datetime = datetime(2024, 7, 9, 0, 0, 0)
    end_datetime = datetime(2024, 7, 9, 12, 59, 59)

    start_datetime = "2024-11-25 00:00:00"
    end_datetime = "2024-11-25 23:45:00"

    lc = get_location_paths('test011', start_datetime, end_datetime)
    print(lc)
