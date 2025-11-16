import streamlit as st
import pandas as pd
import json
from datetime import datetime
import time
import requests
import os
import plotly.graph_objects as go

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="ClimateSense Live Dashboard",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- 2. THEME AND ANIMATION (No Change to CSS Block) ---

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
    "--danger-color": "#F44336",
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
    "--danger-color": "#D32F2F",
}

# Select theme based on session state
theme = dark_theme if st.session_state.dark_mode else light_theme

# --- NEW CSS with Variables, Animations, and Responsiveness (No Change to CSS Block) ---
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

    /* 3. Helper Classes for Risk Color Mapping --- */
    .risk-CRITICAL {{ color: var(--danger-color); font-weight: bold; }}
    .risk-HIGH {{ color: #FF5722; font-weight: bold; }} /* Orange-Red */
    .risk-MODERATE {{ color: #FFC107; font-weight: bold; }} /* Yellow-Orange */
    .risk-LOW {{ color: #4CAF50; font-weight: bold; }} /* Green */
    .risk-UNKNOWN {{ color: var(--text-color-muted); }}


    /* 4. Main app styling --- */
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }}
    .stApp {{
        background-color: var(--bg-color);
        color: var(--text-color);
        transition: background-color 0.3s ease, color 0.3s ease;
    }}

    /* 5. Card containers --- */
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: var(--bg-color-secondary);
        border-radius: 10px;
        padding: 1.25rem;
        border: 1px solid var(--border-color);
        animation: fadeIn 0.5s ease-out forwards;
        transition: all 0.3s ease;
    }}
    [data-testid="stVerticalBlockBorderWrapper"]:hover {{
        transform: translateY(-5px); 
        box-shadow: 0 8px 20px rgba(0,0,0,0.15);
    }}

    /* 6. Sidebar styling --- */
    [data-testid="stSidebar"] {{
        background-color: var(--bg-color-sidebar);
        border-right: 1px solid var(--border-color);
        transition: all 0.3s ease;
    }}

    /* 7. UI Elements --- */
    [data-testid="stTextInput"], [data-testid="stButton"] {{
        border-radius: 10px;
    }}

    /* 8. Metric styling --- */
    [data-testid="stMetricLabel"] {{
        color: var(--text-color-muted);
        font-size: 0.9rem;
        font-weight: 500; 
        text-transform: uppercase; 
    }}
    [data-testid="stMetricValue"] {{
        color: var(--text-color);
    }}

    /* 9. Info/Warning boxes --- */
    [data-testid="stInfo"] {{
        background-color: var(--info-bg-color);
        border: 1px solid var(--info-border-color);
    }}
    [data-testid="stWarning"] {{
        background-color: var(--warn-bg-color);
        border: 1px solid var(--warn-border-color);
    }}

    /* 10. Headers --- */
    h1, h2, h3 {{
        color: var(--text-color-light);
    }}

    /* 11. --- RESPONSIVE 5-Day Forecast --- */
    .forecast-container {{
        display: grid;
        grid-template-columns: repeat(5, 1fr); /* 5 columns on desktop */
        gap: 10px;
        min-width: 0; 
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

    /* 12. --- Gauge Styling --- */
    .aqi-gauge-caption {{
        text-align: center;
        font-size: 0.85rem;
        color: var(--text-color-muted);
        margin-top: -10px;
    }}

    /* 13. --- Risk Trend Fix: ensures wrapping for long text --- */
    .risk-trend-container {{
        font-size: 1.2rem;
        font-weight: 600;
        line-height: 1.4;
        margin-top: 5px;
        margin-bottom: 15px;
        word-wrap: break-word;
    }}


    /* 14. --- Media Queries for Responsiveness --- */
    @media (max-width: 992px) {{
        .forecast-container {{
            grid-template-columns: repeat(3, 1fr); 
        }}
    }}
    @media (max-width: 576px) {{
        .forecast-container {{
            grid-template-columns: repeat(2, 1fr); 
        }}
        [data-testid="stVerticalBlockBorderWrapper"] {{
            padding: 1rem; 
        }}
        .weather-icon {{
            font-size: 2.5rem; 
        }}
    }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATA & CONTROL FILES ---
MEMORY_FILE = "memory_log.json"
CONTROL_FILE = "control_file.json"
DEFAULT_LOCATION = "Kochi,IN"  # Default fallback
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

        # --- CRITICAL: Convert timestamp string to Pandas Timestamp object ---
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
        # NOTE: OpenWeather timestamps are in UTC, Streamlit runs in local time.
        # This will convert the UTC timestamp to a local readable string.
        return datetime.fromtimestamp(timestamp).strftime('%I:%M %p')
    except Exception:
        return "N/A"


def degrees_to_cardinal(d):
    """Converts wind degrees to a cardinal direction."""
    try:
        d = float(d)
        dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
        ix = int((d + 11.25) / 22.5)
        return dirs[ix % 16]
    except (ValueError, TypeError):
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


def get_aqi_color(aqi_index):
    """Returns color based on AQI (1-5 scale)."""
    if aqi_index == 1: return "#4CAF50"  # Good - Green
    if aqi_index == 2: return "#8BC34A"  # Fair - Light Green
    if aqi_index == 3: return "#FFC107"  # Moderate - Yellow/Orange
    if aqi_index == 4: return "#FF5722"  # Poor - Orange-Red
    if aqi_index == 5: return "#F44336"  # Very Poor - Red
    return "#a0a0a0"  # Muted


# --- 7. SIDEBAR (MODIFIED) ---

# Set initial location in session state
if 'current_location' not in st.session_state:
    st.session_state.current_location = get_initial_location()

with st.sidebar:
    st.title("ClimateSense")
    st.image("https://placehold.co/200x100/101419/FFFFFF?text=ClimateSense", use_container_width=True)

    # --- Theme Toggle ---
    st.toggle("Dark Mode", value=st.session_state.dark_mode, key="dark_mode")

    st.markdown("---")

    # --- Location Search ---
    st.subheader("Search Location")
    search_text = st.text_input(
        "Enter City,Country Code (e.g. London,UK)",
        value=st.session_state.current_location
    )

    if st.button("Search Location", use_container_width=True):
        if search_text:
            st.session_state.current_location = search_text
            write_control_file(search_text)
            st.cache_data.clear()  # Clear cache to force data reload
            st.info("Location updated. Backend will fetch new data on its next cycle.")
        else:
            st.warning("Please enter a location.")

    if st.button("Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.success("Data refreshed!")

    st.caption(f"Last UI load: {datetime.now().strftime('%H:%M:%S')}")
    st.caption("Data cache refreshes every 60s.")
    st.markdown("---")
    st.subheader("Location Info")
    # Location info will be dynamically populated below

# --- 8. MAIN DASHBOARD LAYOUT (MODIFIED) ---

# Load data FIRST, passing the selected location
latest_entry, df, is_file_missing = load_data(MEMORY_FILE, st.session_state.current_location)

if latest_entry:
    CITY_NAME = latest_entry.get('city', st.session_state.current_location)

    # Extract ALL necessary data
    risk_report = latest_entry.get("risk_report", {})
    heat_report = risk_report.get("heat_risk_report", {})
    air_quality_report = latest_entry.get("air_quality_report", {})
    raw_data = latest_entry.get("raw_data", {})
    details = risk_report.get("details", {})
    main_weather = raw_data.get("main", {})
    sys_data = raw_data.get("sys", {})

    # Use FINAL_LEVEL from Agent 11
    final_level = risk_report.get("final_level", "UNKNOWN")
    final_reasoning = risk_report.get("final_reasoning", risk_report.get("reasoning", "N/A"))
    primary_level = risk_report.get("primary_level", "N/A")
    trend_analysis = risk_report.get("trend", "N/A")  # Get trend here for easy access

    st.title(f"🌦️ ClimateSense Dashboard: {CITY_NAME}")

    # --- Sidebar Population ---
    with st.sidebar:
        st.metric("Country", sys_data.get('country', 'N/A'))
        st.metric("Sunrise", format_time(sys_data.get('sunrise')))
        st.metric("Sunset", format_time(sys_data.get('sunset')))
        st.metric("Latitude", f"{raw_data.get('coord', {}).get('lat', 'N/A'):.4f}")
        st.metric("Longitude", f"{raw_data.get('coord', {}).get('lon', 'N/A'):.4f}")

else:
    st.title(f"🌦️ ClimateSense Dashboard: {st.session_state.current_location}")
    # --- UPDATED: More helpful status messages ---
    if is_file_missing:
        st.error(f"Error: '{MEMORY_FILE}' not found.")
        st.info("Please run 'run_agent_loop.py' in your terminal and wait for it to complete one cycle.")
        st.warning(
            "Also, please check the terminal for 'run_agent_loop.py' to ensure there are no errors (like invalid API keys).")
    else:
        st.warning(f"No data found for '{st.session_state.current_location}' in the log file.")
        st.info(
            f"The backend is set to process this location. Please wait for its next run (this can be up to {LOOP_INTERVAL_SECONDS // 60} minutes) and then click 'Refresh Data'.")

if latest_entry:

    # --- 9. TOP ROW: (MODIFIED to 3-Column Layout) ---
    col1, col2, col3 = st.columns([1.2, 1, 1.5])

    # --- Card 1: Current Conditions ---
    with col1:
        st.subheader("Current Conditions")
        with st.container(border=True, height=420):
            icon_code = raw_data.get("weather", [{}])[0].get("icon")
            icon = get_weather_icon(icon_code)

            st.markdown(f"<div class='weather-icon' style='text-align: center;'>{icon}</div>", unsafe_allow_html=True)
            st.caption(
                f"<p style='text-align: center; font-size: 1.1rem;'><b>{details.get('description', 'N/A').title()}</b></p>",
                unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            c1.metric("Temperature", f"{details.get('temp_c', 'N/A')} °C")
            c2.metric("Feels Like", f"{main_weather.get('feels_like', 'N/A')} °C")
            c1.metric("Wind Speed", f"{details.get('wind_speed_ms', 'N/A')} m/s")
            c2.metric("Humidity", f"{main_weather.get('humidity', 'N/A')}%")

    # --- Card 2: Air Quality ---
    with col2:
        st.subheader("Air Quality & Heat")
        # --- FIX: Increased card height to 450 to comfortably fit gauge and text ---
        with st.container(border=True, height=450):
            aqi = air_quality_report.get('aqi', 'N/A')
            aqi_analysis = air_quality_report.get('analysis', 'N/A')

            # --- AQI Gauge Chart ---
            try:
                aqi_int = int(aqi)
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=aqi_int,
                    domain={'x': [0, 1], 'y': [0, 1]},
                    title={'text': "Current AQI Index (1-5)", 'font': {'size': 16}},
                    gauge={
                        'axis': {'range': [1, 5], 'tickwidth': 1, 'tickcolor': theme['--text-color']},
                        'bar': {'color': get_aqi_color(aqi_int)},
                        'steps': [
                            {'range': [1, 2], 'color': get_aqi_color(1)},  # Good/Fair
                            {'range': [2, 3], 'color': get_aqi_color(3)},  # Moderate
                            {'range': [3, 4], 'color': get_aqi_color(4)},  # Poor
                            {'range': [4, 5], 'color': get_aqi_color(5)}  # Very Poor
                        ],
                        'threshold': {'line': {'color': "white", 'width': 2}, 'thickness': 0.75, 'value': aqi_int}
                    }
                ))
                # --- FIX: Increased Plotly figure height and adjusted top margin to prevent clipping ---
                fig.update_layout(height=270, margin={'l': 10, 'r': 10, 't': 20, 'b': 0},
                                  paper_bgcolor=theme['--bg-color-secondary'],
                                  font={'color': theme['--text-color'], 'family': "Arial"})
                st.plotly_chart(fig, use_container_width=True)
                st.markdown(f"<div class='aqi-gauge-caption'>{aqi_analysis}</div>", unsafe_allow_html=True)
            except Exception:
                st.warning("AQI data N/A or invalid. (Plotly skipped)")

            st.markdown("---")
            st.metric("Heat Index", f"{heat_report.get('heat_index_c', 'N/A')} °C",
                      help=f"**Heat Risk:** {heat_report.get('heat_risk', 'N/A')}. {heat_report.get('warning', 'N/A')}")

    # --- Card 3: Safety Priority (FIXED HEIGHT AND TREND DISPLAY) ---
    with col3:
        st.subheader("Safety Priority")
        # Fixed height set back to 420 (sufficient without map).
        with st.container(border=True, height=420):
            # --- Risk Header (Final Level) ---
            st.markdown(f"""
                <h3 style='text-align: center; margin-top: 0;'>
                    <span class='risk-{final_level}'>{final_level}</span>
                </h3>
            """, unsafe_allow_html=True)

            st.markdown(f"**Reason:** {final_reasoning}")
            st.markdown("---")

            # --- FIX: Use CSS class for forced wrapping/flow to fix text cutoff ---
            st.caption("RISK TREND")
            st.markdown(f"<div class='risk-trend-container'>{trend_analysis}</div>", unsafe_allow_html=True)

            # --- Log Time separated and fixed ---
            st.caption(f"Last Log Time: {latest_entry['timestamp'].strftime('%b %d %I:%M %p')}")

    # --- 10. FORECAST & ALERTS TABS (MODIFIED) ---
    st.header("Detailed Analysis")

    tab1, tab2, tab3 = st.tabs(["Alerts & News", "5-Day Forecast", "Advanced Details"])

    # --- Tab 1: Alerts & News ---
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📋 Holistic Recommendations")
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
    with tab2:
        forecast_data = latest_entry.get("forecast_data")
        if forecast_data:
            daily_forecast = forecast_data.get('daily', [])
            if daily_forecast:
                # Use a list comprehension to build all card HTMLs
                cards_html = [
                    f"""<div class="forecast-day-card">
                        <div class="forecast-day">{datetime.fromtimestamp(day.get('dt')).strftime('%a, %b %d')}</div>
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
                forecast_html = f"""<div class="forecast-container">{''.join(cards_html)}</div>"""

                # Render the entire container at once
                st.markdown(forecast_html, unsafe_allow_html=True)
            else:
                st.warning("Daily forecast data is missing from the log.")
        else:
            st.warning("No forecast data available in the log. (Agent 1.5 may have failed or is still running)")

    # --- NEW: Tab 3 (Advanced Details) ---
    with tab3:
        st.subheader("Advanced Data Analysis")
        st.caption("Multimodal analysis, data validation, and satellite overview.")

        adv_col1, adv_col2 = st.columns(2)

        with adv_col1:
            st.markdown("#### Risk Breakdown")
            # NEW: Display Primary Risk Level
            st.metric("Primary Weather Risk", primary_level)
            st.metric("Current UV Index", latest_entry.get('advanced_fetch_data', {}).get('uv_index', 'N/A'))

            st.info(f"**Satellite Analysis:** {latest_entry.get('satellite_analysis', {}).get('analysis', 'N/A')}")
            st.warning(f"**Icon Analysis:** {latest_entry.get('icon_analysis', 'N/A')}")

        with adv_col2:
            st.markdown("#### Validation & Forecast")
            st.metric("Tomorrow's AQI Forecast", latest_entry.get('air_quality_report', {}).get('tomorrow_aqi', 'N/A'))
            st.success(f"**Data Validation Check:** {latest_entry.get('data_validation', 'N/A')}")

            st.markdown("---")
            st.subheader("Raw Wind & Atmosphere")
            wind_data = raw_data.get("wind", {})
            st.metric(
                "Wind Direction",
                f"{degrees_to_cardinal(wind_data.get('deg', 'N/A'))} ({wind_data.get('deg', 'N/A')}°)"
            )
            st.metric("Pressure", f"{main_weather.get('pressure', 'N/A')} hPa")
            st.metric("Cloudiness", f"{raw_data.get('clouds', {}).get('all', 'N/A')}%")

    # --- 11. MAP & RAW DATA LOG (MAP MOVED TO BOTTOM ROW) ---
    st.header("Geographic Overview & Data Log")

    # --- Map Section (Relocated to bottom) ---
    coord = raw_data.get("coord", {})
    map_data = pd.DataFrame({'lat': [coord.get('lat', 0)], 'lon': [coord.get('lon', 0)]})
    st.map(map_data, zoom=9, use_container_width=True)

    # --- Raw Data Expander ---
    with st.expander("Show Full Processed Data Log (Filtered)"):
        try:
            df_display = df.copy()  # df is already filtered
            # NEW: Use final_level
            df_display['Final Risk'] = df_display['risk_report'].apply(lambda x: x.get('final_level', 'N/A'))
            # NEW: Use Final Reason
            df_display['Final Reason'] = df_display['risk_report'].apply(
                lambda x: x.get('final_reasoning', x.get('reasoning', 'N/A')))
            df_display['Trend'] = df_display['risk_report'].apply(lambda x: x.get('trend', 'N/A'))
            df_display['Heat Risk'] = df_display['risk_report'].apply(lambda x: x.get('heat_risk', 'N/A'))
            df_display['AQI'] = df_display['air_quality_report'].apply(lambda x: x.get('aqi', 'N/A'))

            st.dataframe(df_display[
                             ['timestamp', 'city', 'Final Risk', 'Heat Risk', 'AQI', 'Final Reason', 'Trend',
                              'recommendations', 'analyzed_news']
                         ], use_container_width=True)
        except Exception as e:
            st.error(f"Error processing data frame: {e}")
            st.dataframe(df)