import streamlit as st
import pandas as pd
import json
from datetime import datetime
import time
import requests
import os

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="ClimateSense Live Dashboard",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- 2. THEME AND ANIMATION ---

# Initialize theme in session state
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True

# Define color themes
dark_theme = {
    "--bg-color": "#0E1117",
    "--bg-color-secondary": "#161B22",
    "--bg-color-sidebar": "#101419",
    "--bg-color-card": "#2b2b2b",
    "--text-color": "#ffffff",
    "--text-color-light": "#f0f0f0",
    "--text-color-muted": "#a0a0a0",
    "--border-color": "#30363D",
    "--info-bg-color": "rgba(0, 150, 255, 0.1)",
    "--info-border-color": "rgba(0, 150, 255, 0.5)",
    "--warn-bg-color": "rgba(255, 193, 7, 0.1)",
    "--warn-border-color": "rgba(255, 193, 7, 0.5)",
    "--precip-color": "#89CFF0",
}

light_theme = {
    "--bg-color": "#F0F2F6",
    "--bg-color-secondary": "#FFFFFF",
    "--bg-color-sidebar": "#F8F9FA",
    "--bg-color-card": "#E9ECEF",
    "--text-color": "#111111",
    "--text-color-light": "#333333",
    "--text-color-muted": "#555555",
    "--border-color": "#DEE2E6",
    "--info-bg-color": "rgba(0, 123, 255, 0.1)",
    "--info-border-color": "rgba(0, 123, 255, 0.5)",
    "--warn-bg-color": "rgba(255, 193, 7, 0.1)",
    "--warn-border-color": "rgba(255, 193, 7, 0.5)",
    "--precip-color": "#007BFF",
}

# Select theme based on session state
theme = dark_theme if st.session_state.dark_mode else light_theme

# --- NEW CSS with Variables, Animations, and Responsiveness ---
st.markdown(f"""
    <style>
    /* 1. CSS Variables --- */
    :root {{
        {'; '.join(f'{k}: {v}' for k, v in theme.items())};
    }}

    /* 2. Animations --- */
    @keyframes fadeIn {{
        from {{ 
            opacity: 0; 
            transform: translateY(15px); 
        }}
        to {{ 
            opacity: 1; 
            transform: translateY(0);
        }}
    }}

    /* 3. Main app styling --- */
    .stApp {{
        background-color: var(--bg-color);
        color: var(--text-color);
        transition: background-color 0.3s ease, color 0.3s ease;
    }}

    /* 4. Card containers --- */
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: var(--bg-color-secondary);
        border-radius: 10px;
        padding: 1.25rem;
        border: 1px solid var(--border-color);
        animation: fadeIn 0.5s ease-out forwards;
        transition: all 0.3s ease;
    }}
    [data-testid="stVerticalBlockBorderWrapper"]:hover {{
        transform: scale(1.01);
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }}

    /* 5. Sidebar styling --- */
    [data-testid="stSidebar"] {{
        background-color: var(--bg-color-sidebar);
        border-right: 1px solid var(--border-color);
        transition: all 0.3s ease;
    }}

    /* 6. UI Elements --- */
    [data-testid="stTextInput"], [data-testid="stButton"] {{
        border-radius: 10px;
    }}

    /* 7. Metric styling --- */
    [data-testid="stMetricLabel"] {{
        color: var(--text-color-muted);
        font-size: 0.9rem;
    }}
    [data-testid="stMetricValue"] {{
        color: var(--text-color);
    }}

    /* 8. Info/Warning boxes --- */
    [data-testid="stInfo"] {{
        background-color: var(--info-bg-color);
        border: 1px solid var(--info-border-color);
    }}
    [data-testid="stWarning"] {{
        background-color: var(--warn-bg-color);
        border: 1px solid var(--warn-border-color);
    }}

    /* 9. Headers --- */
    h1, h2, h3 {{
        color: var(--text-color-light);
    }}

    /* 10. --- RESPONSIVE 5-Day Forecast --- */
    .forecast-container {{
        display: grid;
        grid-template-columns: repeat(5, 1fr); /* 5 columns on desktop */
        gap: 10px;
        min-width: 0; /* Prevents overflow/layout issues */
    }}
    .forecast-day-card {{
        background-color: var(--bg-color-card);
        border-radius: 10px;
        padding: 15px 10px;
        text-align: center;
        border: 1px solid var(--border-color);
        min-height: 170px; 
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        transition: all 0.3s ease;
    }}
    .forecast-day-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }}
    .weather-icon {{
        font-size: 2.8rem;
        line-height: 1;
        margin-top: 5px;
        margin-bottom: 5px;
    }}
    .forecast-day {{
        font-weight: bold;
        font-size: 1rem;
        color: var(--text-color);
    }}
    .forecast-temp {{
        font-size: 1.3rem;
        color: var(--text-color-light);
        margin-top: 5px;
        font-weight: 600;
    }}
    .forecast-temp-min {{
        font-size: 0.9rem;
        color: var(--text-color-muted);
    }}
    .forecast-precip {{
        font-size: 0.8rem;
        color: var(--precip-color);
        margin-top: 5px;
    }}

    /* 11. --- Media Queries for Responsiveness --- */
    @media (max-width: 992px) {{
        .forecast-container {{
            grid-template-columns: repeat(3, 1fr); /* 3 columns on tablet */
        }}
    }}
    @media (max-width: 576px) {{
        .forecast-container {{
            grid-template-columns: repeat(2, 1fr); /* 2 columns on mobile */
        }}
        [data-testid="stVerticalBlockBorderWrapper"] {{
            padding: 1rem; /* Reduce padding on mobile */
        }}
        .weather-icon {{
            font-size: 2.5rem; /* Slightly smaller icon on mobile */
        }}
    }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATA & CONTROL FILES ---
MEMORY_FILE = "memory_log.json"
CONTROL_FILE = "control_file.json"
DEFAULT_LOCATION = "Kochi,IN"  # Default fallback
# --- NEW: Define loop interval here to avoid NameError ---
LOOP_INTERVAL_SECONDS = 3600  # Must match the value in run_agent_loop.py


# --- 4. LOCATION & CONTROL FUNCTIONS ---
@st.cache_data(ttl=3600)  # Cache current location for 1 hour
def get_current_location():
    """Fetches the user's current location based on IP."""
    try:
        response = requests.get("http://ip-api.com/json/")
        response.raise_for_status()
        data = response.json()
        city = data.get("city")
        country_code = data.get("countryCode")
        if city and country_code:
            return f"{city},{country_code}"
    except Exception as e:
        print(f"Could not fetch IP-based location: {e}")
    return DEFAULT_LOCATION  # Fallback


def write_control_file(location: str):
    """Writes the desired location to the control file for the backend."""
    try:
        with open(CONTROL_FILE, 'w') as f:
            json.dump({"location": location}, f)
        print(f"Control file updated with location: {location}")
    except Exception as e:
        st.error(f"Error writing control file: {e}")


def get_initial_location():
    """Gets location from control file, or IP, or default."""
    if os.path.exists(CONTROL_FILE):
        try:
            with open(CONTROL_FILE, 'r') as f:
                data = json.load(f)
                return data.get("location", DEFAULT_LOCATION)
        except Exception:
            pass  # Fallthrough to get current location

    # If control file doesn't exist or is invalid, get location
    new_loc = get_current_location()
    write_control_file(new_loc)  # Write this new default
    return new_loc


# --- 5. DATA LOADING FUNCTION (MODIFIED) ---

@st.cache_data(ttl=60)
def load_data(filepath, selected_location):
    """Loads and processes the memory log file, filtering by location."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        if not data:
            return None, pd.DataFrame(), False  # latest_entry, df, is_file_empty

        df = pd.DataFrame(data)

        # Filter by selected location (case-insensitive)
        df_filtered = df[df['city'].str.lower() == selected_location.lower()].copy()

        if df_filtered.empty:
            # Data file exists, but not for this city
            return None, df, False

        df_filtered['timestamp'] = pd.to_datetime(df_filtered['timestamp'])
        df_filtered = df_filtered.sort_values(by='timestamp', ascending=False)
        latest_entry = df_filtered.iloc[0].to_dict()

        return latest_entry, df_filtered, False
    except (FileNotFoundError, json.JSONDecodeError, IndexError):
        # File literally doesn't exist or is empty
        return None, pd.DataFrame(), True
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None, pd.DataFrame(), False


# --- 6. HELPER FUNCTIONS for UI ---
def format_time(timestamp):
    if not timestamp: return "N/A"
    try:
        return datetime.fromtimestamp(timestamp).strftime('%I:%M %p')
    except Exception:
        return "N/A"


def format_day(timestamp):
    if not timestamp: return "N/A"
    try:
        return datetime.fromtimestamp(timestamp).strftime('%a, %b %d')
    except Exception:
        return "N/A"


def format_hour(timestamp):
    if not timestamp: return "N/A"
    try:
        return datetime.fromtimestamp(timestamp).strftime('%I %p')  # e.g., "03 PM"
    except Exception:
        return "N/A"


def get_weather_icon(icon_code):
    """Maps OpenWeather icon codes to Streamlit emojis."""
    icon_map = {
        "01d": "☀️", "01n": "🌙",
        "02d": "⛅", "02n": "☁️",
        "03d": "☁️", "03n": "☁️",
        "04d": "☁️", "04n": "☁️",
        "09d": "🌧️", "09n": "🌧️",
        "10d": "🌦️", "10n": "🌧️",
        "11d": "⛈️", "11n": "⛈️",
        "13d": "❄️", "13n": "❄️",
        "50d": "🌫️", "50n": "🌫️",
    }
    return icon_map.get(icon_code, "🤷")


# --- 7. SIDEBAR (MODIFIED) ---

# Set initial location in session state
if 'current_location' not in st.session_state:
    st.session_state.current_location = get_initial_location()

with st.sidebar:
    st.title("ClimateSense")
    st.image("https://placehold.co/200x100/101419/FFFFFF?text=Logo", width='stretch')

    # --- NEW: Theme Toggle ---
    st.toggle("Dark Mode", value=st.session_state.dark_mode, key="dark_mode")

    st.markdown("---")
    st.subheader("Controls")

    # --- Location Search ---
    st.subheader("Search Location")
    search_text = st.text_input(
        "Enter City,Country Code (e.g. London,UK)",
        value=st.session_state.current_location
    )

    if st.button("Search Location", width='stretch'):
        if search_text:
            st.session_state.current_location = search_text
            write_control_file(search_text)
            st.cache_data.clear()  # Clear cache to force data reload
            st.info("Location updated. Backend will fetch new data on its next cycle.")
        else:
            st.warning("Please enter a location.")

    if st.button("Refresh Data", width='stretch'):
        st.cache_data.clear()
        st.success("Data refreshed!")

    st.caption(f"Last UI load: {datetime.now().strftime('%H:%M:%S')}")
    st.caption("Dashboard auto-refreshes every 60s.")
    st.markdown("---")
    st.subheader("Location Info")
    # We will add info here *after* loading data

# --- 8. MAIN DASHBOARD LAYOUT (MODIFIED) ---

# Load data FIRST, passing the selected location
latest_entry, df, is_file_missing = load_data(MEMORY_FILE, st.session_state.current_location)

if latest_entry:
    CITY_NAME = latest_entry.get('city', st.session_state.current_location)
    st.title(f"🌦️ ClimateSense Dashboard: {CITY_NAME}")
else:
    st.title(f"🌦️ ClimateSense Dashboard: {st.session_state.current_location}")

# --- UPDATED: More helpful status messages ---
if latest_entry is None:
    if is_file_missing:
        st.error(f"Error: '{MEMORY_FILE}' not found.")
        st.info("Please run 'run_agent_loop.py' in your terminal and wait for it to complete one cycle.")
        st.warning(
            "Also, please check the terminal for 'run_agent_loop.py' to ensure there are no errors (like invalid API keys).")
    else:
        st.warning(f"No data found for '{st.session_state.current_location}' in the log file.")
        # --- FIX: Use the variable defined above ---
        st.info(
            f"The backend is set to process this location. Please wait for its next run (this can be up to {LOOP_INTERVAL_SECONDS // 60} minutes) and then click 'Refresh Data'.")
else:

    # --- 9. TOP ROW: Current Weather & Map ---
    # --- MODIFIED: Added min-height for better responsiveness ---
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Current Conditions")
        with st.container(border=True, height=360):
            raw_data = latest_entry.get("raw_data", {})
            risk_report = latest_entry.get("risk_report", {})
            details = risk_report.get("details", {})
            main_weather = raw_data.get("main", {})

            icon = get_weather_icon(raw_data.get("weather", [{}])[0].get("icon"))
            st.markdown(f"<div class='weather-icon'>{icon}</div>", unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            c1.metric("Temperature", f"{details.get('temp_c', 'N/A')} °C")
            c2.metric("Feels Like", f"{main_weather.get('feels_like', 'N/A')} °C")
            c1.metric("Wind Speed", f"{details.get('wind_speed_ms', 'N/A')} m/s")
            c2.metric("Humidity", f"{main_weather.get('humidity', 'N/A')}%")

            st.caption(f"**Description:** {details.get('description', 'N/A')}")

    with col2:
        st.subheader("Location & Risk Trend")
        with st.container(border=True, height=360):
            raw_data = latest_entry.get("raw_data", {})  # Re-get for safety
            coord = raw_data.get("coord", {})
            trend_analysis = latest_entry.get("risk_report", {}).get("trend", "N/A")

            map_data = pd.DataFrame({'lat': [coord.get('lat', 0)], 'lon': [coord.get('lon', 0)]})
            st.map(map_data, zoom=9, width='stretch')
            st.metric("Risk Trend", trend_analysis)

            # --- Add Sidebar Location Info ---
            with st.sidebar:
                sys_data = raw_data.get("sys", {})
                st.metric("Country", sys_data.get('country', 'N/A'))
                st.metric("Sunrise", format_time(sys_data.get('sunrise')))
                st.metric("Sunset", format_time(sys_data.get('sunset')))
                st.metric("Latitude", coord.get('lat', 'N/A'))
                st.metric("Longitude", coord.get('lon', 'N/A'))

    # --- 10. FORECAST & ALERTS TABS ---
    st.header("Analysis & Forecast")

    tab1, tab2 = st.tabs(["Alerts & News", "5-Day Forecast"])

    # --- Tab 1: Alerts & News ---
    with tab1:
        risk_report = latest_entry.get("risk_report", {})
        risk_level = risk_report.get("risk_level", "UNKNOWN")
        reasoning = risk_report.get("reasoning", "N/A")

        st.subheader(f"Current Risk: {risk_level}")
        st.caption(f"**Reason:** {reasoning}")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📋 Recommended Actions")
            with st.container(border=True, height=300):
                recommendations = latest_entry.get("recommendations", "No actions required.")
                st.info(recommendations)
        with col2:
            st.subheader("📰 Automated News Analysis")
            with st.container(border=True, height=300):
                news_summary = latest_entry.get("analyzed_news", "No relevant local safety news found.")
                if "No relevant" in news_summary or "Error analyzing" in news_summary:
                    st.warning(news_summary)
                else:
                    for line in news_summary.split('\n'):
                        if ":" in line:
                            try:
                                headline, summary = line.split(":", 1)
                                st.markdown(f"**{headline.strip()}**")
                                st.caption(f"{summary.strip()}")
                            except ValueError:
                                st.write(line)
                        else:
                            st.write(line)

    # --- Tab 2: 5-Day Forecast (Daily) ---
    # --- REBUILT for Responsiveness ---
    with tab2:
        forecast_data = latest_entry.get("forecast_data")
        if forecast_data:
            daily_forecast = forecast_data.get('daily', [])
            if daily_forecast:
                # --- FIX: Removed leading/trailing whitespace from f-strings ---

                # Use a list comprehension to build all card HTMLs
                cards_html = [
                    # This f-string must NOT be indented
                    f"""<div class="forecast-day-card">
                        <div class="forecast-day">{format_day(day.get('dt'))}</div>
                        <div class="weather-icon">{get_weather_icon(day.get('icon'))}</div>
                        <div>
                            <div class="forecast-temp">{day.get('temp_max', 'N/A'):.0f}°</div>
                            <div class="forecast-temp-min">{day.get('temp_min', 'N/A'):.0f}°</div>
                        </div>
                        <div class="forecast-precip">☂️ {day.get('pop', 0) * 100:.0f}%</div>
                    </div>"""
                    for day in daily_forecast[:5]  # Get first 5 days
                ]

                # Join all cards and wrap them in the container
                # This f-string must also NOT be indented
                forecast_html = f"""<div class="forecast-container">
{''.join(cards_html)}
</div>"""

                # Render the entire container at once
                st.markdown(forecast_html, unsafe_allow_html=True)
            else:
                st.warning("Daily forecast data is missing from the log.")
        else:
            st.warning("No forecast data available in the log. (Agent 1.5 may have failed or is still running)")

    # --- 11. RAW DATA LOG (MODIFIED) ---
    with st.expander("Show Full Processed Data Log (Filtered)"):
        try:
            df_display = df.copy()  # df is already filtered
            df_display['Risk Level'] = df_display['risk_report'].apply(lambda x: x.get('risk_level', 'N/A'))
            df_display['Reason'] = df_display['risk_report'].apply(lambda x: x.get('reasoning', 'N/A'))
            df_display['Trend'] = df_display['risk_report'].apply(lambda x: x.get('trend', 'N/A'))
            df_display['News Summary'] = df['analyzed_news']
            st.dataframe(df_display[
                             ['timestamp', 'city', 'Risk Level', 'Reason', 'Trend', 'recommendations', 'News Summary']
                         ], width='stretch')
        except Exception as e:
            st.error(f"Error processing data frame: {e}")
            st.dataframe(df)

# --- 12. Auto-refresh (REMOVED) ---
# The time.sleep() and st.rerun() commands were blocking the app's
# rendering thread, causing visual bugs and unresponsiveness.
# The app will now rely on the @st.cache_data(ttl=60) decorator
# on the load_data() function, which correctly refreshes the data
# every 60 seconds when the user interacts with the app.