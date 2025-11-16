import os
import json
import requests
import google.generativeai as genai
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta
import math
import traceback  # NEW: For better error logging

# --- IMPORTS FOR PDF & EMAIL & NEWS ---
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from newsapi import NewsApiClient

# --- 1. CONFIGURATION & SETUP ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

if not all([GOOGLE_API_KEY, WEATHER_API_KEY, NEWS_API_KEY]):
    print("ERROR: API keys not found. Please check your .env file for all 3 keys.")
    exit()

genai.configure(api_key=GOOGLE_API_KEY)

# --- MODELS (ADVANCED TIERED STRATEGY for Quota) ---
# High-throughput model for fast-text tasks (Analysis, Summarization, Formatting)
llm_model_flash_lite = genai.GenerativeModel('models/gemini-2.5-flash-lite')
# Advanced reasoning model for complex synthesis, trend analysis, and prioritization
llm_model_pro = genai.GenerativeModel('models/gemini-pro-latest')
# Multimodal model for image/icon analysis (Agent 12) - FIX: Added missing model definition
llm_model_vision = genai.GenerativeModel('models/gemini-2.5-flash')

newsapi = NewsApiClient(api_key=NEWS_API_KEY)

MEMORY_FILE = "memory_log.json"
CONTROL_FILE = "control_file.json"
DEFAULT_LOCATION = "Kerala,IN"
LOOP_INTERVAL_SECONDS = 3600
LOCATION_CHECK_INTERVAL_SECONDS = 1


# --- NEW: Function to read control file (No Change) ---
def get_target_location() -> str:
    """Reads the target location from the control file."""
    if not os.path.exists(CONTROL_FILE):
        print(f"[Main] Control file not found. Using default location: {DEFAULT_LOCATION}")
        return DEFAULT_LOCATION
    try:
        with open(CONTROL_FILE, 'r') as f:
            data = json.load(f)
            location = data.get("location")
            if location:
                return location
            else:
                return DEFAULT_LOCATION
    except Exception as e:
        print(f"[Main] Error reading control file '{e}'. Using default: {DEFAULT_LOCATION}")
        return DEFAULT_LOCATION


# --- NEW: Function to "sleep" but wake up to check for changes (No Change) ---
def smart_sleep_and_watch(duration_seconds: int, check_interval_seconds: int, location_at_start_of_sleep: str):
    """
    Sleeps for 'duration_seconds' but wakes up every 'check_interval_seconds'
    to see if the control file's location has changed.

    Returns True if a change was detected, False otherwise.
    """
    print(f"[Main] Sleeping, but checking {CONTROL_FILE} every {check_interval_seconds}s for changes...")

    end_time = time.time() + duration_seconds

    while time.time() < end_time:
        sleep_time = min(check_interval_seconds, end_time - time.time())
        if sleep_time <= 0:
            break
        time.sleep(sleep_time)

        current_file_location = get_target_location()

        if current_file_location.lower() != location_at_start_of_sleep.lower():
            print(f"[Main] Location change detected: '{location_at_start_of_sleep}' -> '{current_file_location}'")
            return True

    return False


# --- 2. AGENT DEFINITIONS (REWORKED & NEW) ---

def agent_1_weather_fetcher(api_url: str, city_name: str) -> dict:
    """Agent 1: Fetches raw weather data from the API."""
    print(f"[Agent 1] Fetching current weather for {city_name}...")
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        print("[Agent 1] Fetch successful.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[Agent 1] ERROR: {e}")
        return None


def agent_1_5_forecast_processor(api_url: str, city_name: str) -> dict:
    """
    Agent 1.5: Fetches 5-day/3-hour forecast and processes it
    into a simple daily summary.
    """
    print(f"[Agent 1.5] Fetching 5-day forecast for {city_name}...")
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        print("[Agent 1.5] Forecast fetch successful. Processing...")

        daily_forecasts = {}
        for item in data.get('list', []):
            date_key = datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d')
            temp_min = item['main']['temp_min']
            temp_max = item['main']['temp_max']
            icon = item['weather'][0]['icon']
            pop = item.get('pop', 0)

            if date_key not in daily_forecasts:
                daily_forecasts[date_key] = {
                    'date_ts': item['dt'],
                    'temp_min': temp_min,
                    'temp_max': temp_max,
                    'icons': {icon: 1},
                    'pops': [pop]
                }
            else:
                if temp_min < daily_forecasts[date_key]['temp_min']:
                    daily_forecasts[date_key]['temp_min'] = temp_min
                if temp_max > daily_forecasts[date_key]['temp_max']:
                    daily_forecasts[date_key]['temp_max'] = temp_max

                daily_forecasts[date_key]['icons'][icon] = daily_forecasts[date_key]['icons'].get(icon, 0) + 1
                daily_forecasts[date_key]['pops'].append(pop)

        processed_daily = []
        for date_key, values in daily_forecasts.items():
            most_common_icon = max(values['icons'], key=values['icons'].get)
            max_pop = max(values['pops'])

            processed_daily.append({
                'dt': values['date_ts'],
                'temp_min': values['temp_min'],
                'temp_max': values['temp_max'],
                'icon': most_common_icon,
                'pop': max_pop
            })

        processed_daily.sort(key=lambda x: x['dt'])

        print(f"[Agent 1.5] Processed {len(processed_daily)} forecast days.")
        return {'daily': processed_daily}

    except requests.exceptions.RequestException as e:
        print(f"[Agent 1.5] ERROR: {e}")
        return None


def agent_1_6_air_quality_fetcher(lat: float, lon: float, api_key: str) -> dict:
    """Agent 1.6: Fetches current air quality data."""
    print(f"[Agent 1.6] Fetching Current Air Quality for (lat:{lat}, lon:{lon})...")
    api_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={api_key}"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        print("[Agent 1.6] Air Quality fetch successful.")
        return response.json()['list'][0]
    except Exception as e:
        print(f"[Agent 1.6] ERROR: {e}")
        return None


# --- NEW FETCH AGENT 1.7: UV Index & Pollution Forecast ---
def agent_1_7_advanced_fetcher(lat: float, lon: float, api_key: str) -> dict:
    """Agent 1.7: Fetches advanced data: UV Index (mocked) and Air Pollution Forecast."""
    print(f"[Agent 1.7] Fetching Advanced Data (UV Index & Pollution Forecast)...")

    # 1. UV Index (Mocked/Simplified for OpenWeather free tier limitations)
    current_hour = datetime.now().hour
    # Mock cloud data from common weather API (since we don't have the full object here)
    # Assume 50% cloud cover if we can't get current data
    clouds = 50

    # Simple logic: High UV mid-day (10-3) with low clouds.
    if 10 <= current_hour <= 15 and clouds < 50:
        uv_index = 8
    elif 9 <= current_hour <= 16:
        uv_index = 4
    else:
        uv_index = 0

    # 2. Air Pollution Forecast (Using API for tomorrow's AQI)
    tomorrow_aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution/forecast?lat={lat}&lon={lon}&appid={api_key}"
    tomorrow_aqi = "N/A"
    try:
        response = requests.get(tomorrow_aqi_url)
        response.raise_for_status()
        # Find the earliest forecast entry for the next day
        tomorrow_entries = [item for item in response.json().get('list', []) if
                            datetime.fromtimestamp(item['dt']).day != datetime.now().day]
        if tomorrow_entries:
            tomorrow_aqi = tomorrow_entries[0]['main']['aqi']
        print("[Agent 1.7] Pollution Forecast fetched.")
    except Exception as e:
        print(f"[Agent 1.7] ERROR fetching pollution forecast: {e}")
        tomorrow_aqi = "N/A"

    return {
        "uv_index": uv_index,
        "tomorrow_aqi": tomorrow_aqi
    }


def agent_2_risk_classifier(weather_data: dict) -> dict:
    """Agent 2: Converts raw data into primary weather risk levels (Code Tool)."""
    print("[Agent 2] Classifying primary weather risk...")
    wind_speed = weather_data.get("wind", {}).get("speed", 0)
    description = weather_data.get("weather", [{}])[0].get("description", "unknown")
    temp = weather_data.get("main", {}).get("temp", 0)

    risk_level = "LOW"
    reasoning = "Conditions are calm."
    if "thunderstorm" in description or "squalls" in description:
        risk_level = "HIGH"
        reasoning = "Active thunderstorm or squalls reported."
    elif "rain" in description and wind_speed > 15:
        risk_level = "HIGH"
        reasoning = f"Heavy rain combined with high wind speed ({wind_speed} m/s)."
    elif "rain" in description:
        risk_level = "MODERATE"
        reasoning = f"Rain reported. Monitor conditions."
    elif wind_speed > 20:
        risk_level = "HIGH"
        reasoning = f"Extreme wind speed ({wind_speed} m/s) detected."
    elif wind_speed > 15:
        risk_level = "MODERATE"
        reasoning = f"High wind speed ({wind_speed} m/s) detected."

    print(f"[Agent 2] Primary Risk: {risk_level}")
    return {
        "primary_level": risk_level,
        "reasoning": reasoning,
        "details": {
            "temp_c": temp,
            "wind_speed_ms": wind_speed,
            "description": description,
            "humidity": weather_data.get("main", {}).get("humidity", "N/A")
        }
    }


# --- NEW AGENT 2.7: Extreme Heat Classifier ---
def agent_2_7_heat_classifier(temp_c: float, humidity: float) -> dict:
    """Agent 2.7: Calculates Heat Index and classifies risk (Code Tool)."""
    print("[Agent 2.7] Classifying heat stress risk...")

    # Check for valid inputs
    if not isinstance(temp_c, (int, float)) or not isinstance(humidity, (int, float)):
        return {
            "heat_index_c": "N/A",
            "heat_risk": "LOW",
            "warning": "Heat calculation skipped due to missing temperature or humidity data."
        }

    # Formula uses Fahrenheit (T) and relative humidity (R)
    T_f = (temp_c * 9 / 5) + 32
    R = humidity

    # Regression equation from NOAA for Heat Index (HI) in F
    if T_f < 80:
        HI = T_f
    else:
        # Complex calculation from NOAA
        try:
            HI = -42.379 + 2.04901523 * T_f + 10.14333127 * R - .22475541 * T_f * R - .00683783 * T_f ** 2 - \
                 .05481717 * R ** 2 + .00122874 * T_f ** 2 * R + .00085282 * T_f * R ** 2 - .00000199 * T_f ** 2 * R ** 2
        except Exception:
            # Fallback if math fails (e.g., extremely large numbers)
            HI = T_f

    # Convert HI back to Celsius
    HI_c = (HI - 32) * 5 / 9

    # Classification (Based on Canadian/US Alert System)
    heat_risk = "LOW"
    warning = "No heat risk."

    if HI_c >= 40:
        heat_risk = "EXTREME"
        warning = "Danger: Heat stroke highly likely."
    elif HI_c >= 32:
        heat_risk = "HIGH"
        warning = "Extreme Caution: Heat cramps or heat exhaustion possible."
    elif HI_c >= 27:
        heat_risk = "MODERATE"
        warning = "Caution: Fatigue possible with prolonged exposure."

    print(f"[Agent 2.7] Heat Index: {HI_c:.1f}°C, Risk: {heat_risk}")

    return {
        "heat_index_c": round(HI_c, 1),
        "heat_risk": heat_risk,
        "warning": warning
    }


def agent_2_5_air_quality_analyzer(aqi_data: dict, advanced_data: dict) -> dict:
    """Agent 2.5: Uses LLM to analyze raw AQI data, now including tomorrow's forecast."""
    print("[Agent 2.5] Analyzing Air Quality...")
    if not aqi_data:
        return {"aqi": "N/A", "analysis": "No data", "tomorrow_aqi": "N/A"}

    aqi_index = aqi_data.get('main', {}).get('aqi', 0)
    components = aqi_data.get('components', {})
    tomorrow_aqi = advanced_data.get('tomorrow_aqi', 'N/A')

    aqi_map = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}
    aqi_name = aqi_map.get(aqi_index, "Unknown")

    prompt = f"""
    You are a public health advisor.
    The current Air Quality Index (AQI) is {aqi_index} ({aqi_name}).
    Tomorrow's forecast AQI is: {tomorrow_aqi}.
    Key pollutants (in μg/m³): PM2.5: {components.get('pm2_5', 'N/A')}, Ozone (O3): {components.get('o3', 'N/A')}.

    Provide a simple, one-sentence analysis and health recommendation, noting the trend.
    Example: 'Air quality is moderate but forecast to worsen; sensitive groups should limit outdoor activity both today and tomorrow.'
    """
    try:
        # Use the faster, high-throughput model
        response = llm_model_flash_lite.generate_content(prompt)
        analysis_text = response.text.strip()
        print(f"[Agent 2.5] Analysis complete: {analysis_text}")
        return {"aqi": aqi_index, "analysis": analysis_text, "tomorrow_aqi": tomorrow_aqi}
    except Exception as e:
        print(f"[Agent 2.5] ERROR: {e}")
        return {"aqi": aqi_index, "analysis": "Error analyzing air quality.", "tomorrow_aqi": tomorrow_aqi}


# --- NEW AGENT 3.5: Data Validator ---
def agent_3_5_data_validator(risk_report: dict, air_quality_report: dict) -> str:
    """Agent 3.5: Uses LLM to validate data consistency."""
    print("[Agent 3.5] Validating data consistency...")

    weather_desc = risk_report['details']['description']
    temp = risk_report['details']['temp_c']
    aqi = air_quality_report.get('aqi', 'N/A')

    prompt = f"""
    As a data consistency auditor, review the following data points. If any conflict or appear anomalous, state the anomaly. Otherwise, state 'Data is consistent and reliable.'.

    - Weather Description: '{weather_desc}' (e.g., 'overcast clouds', 'light rain')
    - Current Temperature: {temp}°C
    - Current AQI: {aqi}

    **Examples of Anomalies:**
    - Light rain is reported, but the AQI is 5 (Very Poor) which usually means clear, stagnant air.
    - Temperature is 45°C, but the weather description is 'heavy snow'.
    """
    try:
        # Use the faster, high-throughput model
        response = llm_model_flash_lite.generate_content(prompt)
        validation_result = response.text.strip()
        print(f"[Agent 3.5] Validation Result: {validation_result}")
        return validation_result
    except Exception as e:
        print(f"[Agent 3.5] ERROR: {e}")
        return "Validation failed."


def agent_3_action_recommender(risk_report: dict, heat_report: dict, air_quality_report: dict,
                               forecast_data: dict) -> str:
    """Agent 3: UPGRADED with Heat Risk for highly granular recommendations (PRO LLM)."""
    print("[Agent 3] Generating advanced recommendations with PRO model...")

    # Get max temp from the next 5 days for a better recommendation
    max_forecast_temp = max([d['temp_max'] for d in forecast_data.get('daily', [])], default=None)

    # Simple exit if all conditions are mild
    if risk_report["primary_level"] == "LOW" and heat_report["heat_risk"] == "LOW" and air_quality_report.get('aqi',
                                                                                                              0) <= 2:
        print("[Agent 3] Risk is LOW across all factors. No complex actions needed.")
        return "Conditions are stable, air quality is good, and heat risk is minimal. No special actions required."

    prompt = f"""
    You are an expert community safety advisor. Synthesize all the following information to provide a single, holistic
    set of 3-5 bullet-point recommendations.

    1.  **Primary Weather Risk**:
        * Level: {risk_report['primary_level']}
        * Reason: {risk_report['reasoning']}
        * Trend: {risk_report['trend']}

    2.  **Extreme Heat Risk**:
        * Heat Risk Level: {heat_report['heat_risk']}
        * Heat Index: {heat_report['heat_index_c']}°C
        * Warning: {heat_report['warning']}

    3.  **Air Quality**:
        * AQI: {air_quality_report.get('aqi', 'N/A')}
        * Analysis: {air_quality_report.get('analysis', 'N/A')}
        * Forecast: Tomorrow's AQI is {air_quality_report.get('tomorrow_aqi', 'N/A')}.

    4.  **Forecast Summary**: The highest predicted temperature for the next 5 days is {max_forecast_temp if max_forecast_temp else 'N/A'}°C.

    **Instructions**:
    - Provide 3-5 clear, actionable, and combined bullet points.
    - Prioritize the most extreme risk (e.g., if HIGH heat and MODERATE rain, prioritize heat).
    - If risk is LOW but AQI is Poor, prioritize air quality advice.
    - Do not use an introduction or conclusion sentence.
    """
    try:
        # Use the PRO model for this complex, high-value synthesis task
        response = llm_model_pro.generate_content(prompt)
        print("[Agent 3] Advanced recommendations generated.")
        return response.text
    except Exception as e:
        print(f"[Agent 3] ERROR: {e}")
        return "Error generating recommendations."


def agent_5_trend_forecaster(current_risk_report: dict, memory_file: str, city_name: str) -> str:
    """Agent 5: Uses PRO LLM to analyze historical data for trend prediction."""
    print(f"[Agent 5] Analyzing risk trend for {city_name} with PRO model...")
    try:
        with open(memory_file, 'r') as f:
            history = json.load(f)

        city_history = [
            report for report in history
            if report.get('city', '').lower() == city_name.lower()
        ]

        recent_reports = city_history[-5:]

        if len(recent_reports) < 2:
            print("[Agent 5] Not enough history for this city to analyze trend.")
            return "No comprehensive trend data available."

    except (FileNotFoundError, json.JSONDecodeError, IndexError):
        print("[Agent 5] No history file found.")
        return "No comprehensive trend data available."

    past_data_summary = []
    for report in recent_reports:
        ts = report.get('timestamp', 'N/A')
        # Safely get the final level (can be 'N/A' if memory is old)
        lvl = report.get('risk_report', {}).get('final_level', report.get('final_risk_level', 'N/A'))
        aqi = report.get('air_quality_report', {}).get('aqi', 'N/A')
        past_data_summary.append(f"- @ {ts.split('T')[1].split('.')[0]}: Final Risk={lvl}, AQI={aqi}.")

    past_data_str = "\n".join(past_data_summary)

    prompt = f"""
    You are a meteorologist and safety analyst analyzing combined risk trends for {city_name}.
    Here is the recent history (oldest to newest):
    {past_data_str}

    Here is the NEWEST reading:
    - Final Risk is {current_risk_report['final_level']}
    - AQI is {current_risk_report.get('air_quality_report', {}).get('aqi', 'N/A')}.

    Analyze this pattern of risk and air quality over time and provide a single-sentence trend analysis.
    (e.g., "The risk is stable but air quality shows signs of gradual deterioration.")
    """
    try:
        # Use the PRO model for this historical and complex synthesis
        response = llm_model_pro.generate_content(prompt)
        trend = response.text.strip()
        print(f"[Agent 5] Trend identified: {trend}")
        return trend
    except Exception as e:
        print(f"[Agent 5] ERROR: {e}")
        return "Error analyzing trend."


def agent_6_news_fetcher(city: str, weather_desc: str) -> list:
    """Agent 6: Fetches relevant raw news articles (Enhanced Query)."""
    print("[Agent 6] Fetching relevant news...")
    city_main = city.split(',')[0]
    query = f'"{city_main}" AND ("weather" OR "flood" OR "heat warning" OR "air pollution" OR "{weather_desc}")'
    from_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    try:
        all_articles = newsapi.get_everything(
            q=query,
            from_param=from_date,
            language='en',
            sort_by='relevancy',
            page_size=10
        )
        articles = all_articles.get('articles', [])
        print(f"[Agent 6] Found {len(articles)} potentially relevant articles.")
        return articles
    except Exception as e:
        print(f"[Agent 6] ERROR: {e}")
        return []


def agent_7_news_analyzer(articles: list) -> str:
    """Agent 7: Uses FLASH-LITE LLM to analyze and summarize relevant news."""
    print("[Agent 7] Analyzing news articles for relevance...")
    if not articles:
        print("[Agent 7] No articles to analyze.")
        return "No relevant local safety news found."
    article_summaries = []
    for i, article in enumerate(articles[:5]):
        article_summaries.append(
            f"ARTICLE {i + 1}:\n"
            f"Title: {article['title']}\n"
            f"Description: {article.get('description', 'N/A')}\n"
            f"Source: {article['source']['name']}\n"
        )
    articles_str = "\n---\n".join(article_summaries)
    prompt = f"""
    You are a local safety analyst. Review the articles below and identify ONLY the ones that are relevant to
    immediate local safety, weather alerts, heat warnings, air quality warnings, or major disruptions.
    For each relevant article, provide a 1-sentence summary.
    If no articles are relevant, just say "No relevant local safety news found."
    Format your response like this:
    [Headline]: [Your 1-sentence summary]
    Here are the articles:
    {articles_str}
    """
    try:
        response = llm_model_flash_lite.generate_content(prompt)
        print("[Agent 7] News analysis complete.")
        return response.text.strip()
    except Exception as e:
        print(f"[Agent 7] ERROR: {e}")
        return "Error analyzing news."


# --- AGENT 9: Satellite Fetcher (MOCKED) ---
def agent_9_satellite_image_fetcher(city: str, weather_desc: str) -> dict:
    """Agent 9: Simulates fetching a satellite image URL and basic analysis."""
    print(f"[Agent 9] Simulating satellite image fetch for {city}...")
    # Mock data based on weather
    image_url = f"https://placehold.co/600x400/101419/555555?text=Satellite+View+{city.split(',')[0]}"
    mock_description = "Clear skies, no major formations."

    if "rain" in weather_desc:
        mock_description = "Significant cloud formations consistent with rain."
        image_url = f"https://placehold.co/600x400/222222/999999?text=Satellite+View+(Cloudy)+{city.split(',')[0]}"
    elif "thunderstorm" in weather_desc:
        mock_description = "Large, dense cumulonimbus cloud cluster detected."
        image_url = f"https://placehold.co/600x400/111111/FFFFFF?text=Satellite+View+(Storm)+{city.split(',')[0]}"
    elif "fog" in weather_desc or "haze" in weather_desc:
        mock_description = "Low-lying ground-level fog or haze visible."
        image_url = f"https://placehold.co/600x400/555555/EEEEEE?text=Satellite+View+(Fog)+{city.split(',')[0]}"

    return {
        "image_url": image_url,
        "description": mock_description
    }


# --- AGENT 10: Satellite Analyzer (REWORKED MODEL) ---
def agent_10_satellite_analyzer(image_data: dict) -> dict:
    """Agent 10: Uses FLASH-LITE LLM to provide a strategic analysis of satellite data."""
    print("[Agent 10] Analyzing satellite data...")

    prompt = f"""
    You are a remote sensing analyst. Your satellite has provided the
    following basic description of a target area:
    "{image_data['description']}"

    Provide a 1-2 sentence strategic analysis for a safety dashboard.
    What does this imply for the local area? Focus on risks like fire, heat, or visibility.
    Example: "Analysis: Clear skies confirm ideal conditions, but also high UV risk."
    """
    try:
        response = llm_model_flash_lite.generate_content(prompt)
        analysis = response.text.strip()
        print("[Agent 10] Satellite analysis complete.")
        return {
            "image_url": image_data['image_url'],
            "analysis": analysis
        }
    except Exception as e:
        print(f"[Agent 10] ERROR: {e}")
        return {
            "image_url": image_data['image_url'],
            "analysis": "Error analyzing satellite data."
        }


# --- NEW AGENT 11: Alert Prioritizer (Final Risk Classification) ---
def agent_11_alert_prioritizer(risk_reports: dict) -> str:
    """Agent 11: Uses PRO LLM to determine the single, final, overriding risk level and priority."""
    print("[Agent 11] Determining final risk level and priority...")

    # Map risk words to numerical score for the prompt
    risk_map = {"EXTREME": 5, "HIGH": 4, "MODERATE": 3, "LOW": 2, "NONE": 1}
    primary_score = risk_map.get(risk_reports['primary_level'], 1)
    heat_score = risk_map.get(risk_reports['heat_risk'], 1)
    aqi_score = risk_reports['air_quality_report'].get('aqi', 1)

    priority_level = max(primary_score, heat_score, aqi_score)
    final_risk_map = {5: "CRITICAL", 4: "HIGH", 3: "MODERATE", 2: "LOW", 1: "LOW"}
    final_level_default = final_risk_map.get(priority_level, "LOW")

    prompt = f"""
    Based on the following scores, provide a single, final safety priority level (CRITICAL, HIGH, MODERATE, LOW).

    1. Primary Weather Risk Score: {primary_score} ({risk_reports['primary_level']})
    2. Heat Risk Score: {heat_score} ({risk_reports['heat_risk']})
    3. Air Quality Index (AQI, 1-5): {aqi_score}

    The highest score dictates the final priority level. For example, if Primary is LOW (2) but Heat is HIGH (4), the final level is HIGH.

    State only the FINAL LEVEL and a brief reason.
    Format: [FINAL LEVEL]: [Reasoning]
    """
    try:
        response = llm_model_pro.generate_content(prompt)
        result = response.text.strip()
        print(f"[Agent 11] Final Risk: {result}")
        return result
    except Exception as e:
        print(f"[Agent 11] ERROR: {e}")
        # Fallback to code logic if LLM fails
        return f"{final_level_default}: Error determining final priority. Defaulting to highest local risk."


# --- NEW AGENT 12: Icon Multimodal Analyzer ---
def agent_12_icon_analyzer(icon_code: str, weather_desc: str) -> str:
    """Agent 12: Uses Multimodal LLM to analyze the weather icon and description."""
    print("[Agent 12] Analyzing weather icon and description...")

    icon_to_emoji = {
        "01d": "☀️", "01n": "🌙", "02d": "⛅", "02n": "☁️",
        "03d": "☁️", "03n": "☁️", "04d": "☁️", "04n": "☁️",
        "09d": "🌧️", "09n": "🌧️", "10d": "🌦️", "10n": "🌧️",
        "11d": "⛈️", "11n": "⛈️", "13d": "❄️", "13n": "❄️",
        "50d": "🌫️", "50n": "🌫️",
    }
    emoji = icon_to_emoji.get(icon_code, "🤷")

    prompt = f"""
    You are a visual weather expert. The current weather icon is represented by the emoji: {emoji}.
    The accompanying text description is: '{weather_desc}'.

    Analyze the combination of the icon and text. Is there any mismatch or subtle warning?
    (e.g., 'A light rain icon with a thunder description means the storm is imminent but not yet heavy.')
    Provide a single sentence analysis for the safety dashboard.
    """
    try:
        # Using the multimodal model (llm_model_vision)
        response = llm_model_vision.generate_content(prompt)
        analysis = response.text.strip()
        print("[Agent 12] Icon analysis complete.")
        return analysis
    except Exception as e:
        print(f"[Agent 12] ERROR: {e}")
        return "Error analyzing weather icon visually."


def agent_4_broadcast_agent(risk_report: dict, recommendations: str):
    """Agent 4: Formats and "broadcasts" the final alert to console."""
    print("\n" + "=" * 40)
    print("🚨 CLIMATE-SENSE COMMUNITY ALERT 🚨")
    print(f"       TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 40 + "\n")
    print(f"FINAL RISK: {risk_report.get('final_level', 'N/A')}")
    print(f"HEAT RISK: {risk_report.get('heat_risk', 'N/A')}")
    print(f"REASON: {risk_report['reasoning']}")
    print(f"TREND: {risk_report.get('trend', 'N/A')}")
    print(
        f"DETAILS: {risk_report['details']['description']} | {risk_report['details']['temp_c']}°C | {risk_report['details']['wind_speed_ms']} m/s wind")
    print("\n--- RECOMMENDED ACTIONS ---")
    print(recommendations)
    print("\n" + "=" * 40 + "\n")


def agent_8_email_composer(log_entry: dict) -> dict:
    """
    Agent 8: Uses FLASH-LITE LLM to generate a smart subject and beautiful HTML email.
    """
    print("[Agent 8] Composing smart email...")
    final_level = log_entry['risk_report']['final_level']
    city = log_entry['city']

    if "CRITICAL" in final_level or "HIGH" in final_level:
        subject = f"🚨 URGENT {final_level} Safety Alert for {city}"
    elif "MODERATE" in final_level:
        subject = f"⚠️ Advisory for {city}: Weather, Heat & Air Quality"
    else:
        subject = f"✅ Stable Weather Summary for {city}"

    recommendations = log_entry['recommendations']

    # Define urgency bar color
    urgency_color = "#4CAF50"  # Green
    if "MODERATE" in final_level: urgency_color = "#FFC107"  # Yellow
    if "HIGH" in final_level: urgency_color = "#FF5722"  # Orange
    if "CRITICAL" in final_level: urgency_color = "#F44336"  # Red

    prompt = f"""
    You are a professional communications assistant. Generate a professional and highly visual HTML email body for a safety alert.

    DATA:
    - City: {city}
    - Final Risk: {final_level}
    - Heat Risk: {log_entry['risk_report']['heat_risk']}
    - Air Quality: {log_entry.get('air_quality_report', {}).get('analysis', 'N/A')}
    - Trend: {log_entry['risk_report']['trend']}
    - Recommendations: {recommendations}
    - Validation: {log_entry.get('data_validation', 'N/A')}
    - Satellite Analysis: {log_entry.get('satellite_analysis', {}).get('analysis', 'N/A')}

    INSTRUCTIONS:
    - Use clean, modern HTML with inline CSS.
    - Create a **prominent Urgency Bar** at the top using the color: {urgency_color}.
    - The main content container max-width should be 600px.
    - Clearly separate the Risk Summary, Recommendations (bulleted), and Validation Check.
    - Use a professional, actionable tone.
    - Provide ONLY the HTML code, starting with <!DOCTYPE html> and ending with </html>.
    """
    try:
        response = llm_model_flash_lite.generate_content(prompt)
        html_body = response.text
        html_body = html_body.replace("```html", "").replace("```", "").replace("<!DOCTYPE html>", "").strip()
        html_body = f"<!DOCTYPE html><html>{html_body}</html>"  # Ensure doctype and HTML tags are present
        print("[Agent 8] Email composition successful.")
        return {"subject": subject, "html_body": html_body}
    except Exception as e:
        print(f"[Agent 8] ERROR: {e}")
        return {
            "subject": subject,
            "html_body": f"Risk Level: {final_level}\nTrend: {log_entry['risk_report']['trend']}"
        }


# --- PDF & EMAIL FUNCTIONS (ADVANCED) ---

class PDF(FPDF):
    """Custom PDF class to create colorful headers/footers."""

    def header(self):
        self.set_font('Helvetica', 'B', 15)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 12, 'ClimateSense Advanced Safety Report',
                  border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C', fill=True)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}',
                  border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')


def generate_pdf_report(report_data: dict) -> str:
    """Generates a beautiful, colorful PDF report with new elements."""
    print("[PDF] Generating beautiful PDF report...")
    pdf = PDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()

    try:  # MAIN TRY BLOCK FOR PDF GENERATION

        city = report_data.get('city', 'N/A')
        final_level = report_data.get('risk_report', {}).get('final_level', 'UNKNOWN')
        trend = report_data.get('risk_report', {}).get('trend', 'N/A')
        recommendations = report_data.get('recommendations', 'N/A')
        data_validation = report_data.get('data_validation', 'N/A')
        heat_report = report_data.get('risk_report', {}).get('heat_risk_report', {})

        # Risk Color
        risk_colors = {"CRITICAL": (244, 67, 54), "HIGH": (255, 87, 34), "MODERATE": (255, 193, 7),
                       "LOW": (76, 175, 80), "UNKNOWN": (158, 158, 158)}
        fill_color = risk_colors.get(final_level, (158, 158, 158))

        # --- PDF Header (Final Risk) ---
        pdf.set_fill_color(*fill_color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 20)
        pdf.cell(0, 15, f"FINAL SAFETY PRIORITY: {final_level} ({city})",
                 border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C', fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)

        # --- Risk Analysis Section ---
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 10, "Holistic Risk Breakdown", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True, border='T')
        pdf.ln(5)

        # Heat Risk Sub-Section
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(35, 8, "Heat Risk:")
        pdf.set_font('Helvetica', '', 12)
        pdf.multi_cell(0, 8,
                       f"{heat_report.get('heat_risk', 'N/A')} | Index: {heat_report.get('heat_index_c', 'N/A')}°C. {heat_report.get('warning', '')}")
        pdf.ln(2)

        # Data Validation Sub-Section
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(35, 8, "Data Validation:")
        pdf.set_font('Helvetica', '', 12)
        pdf.multi_cell(0, 8, data_validation)
        pdf.ln(2)

        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(35, 8, "Trend:")
        pdf.set_font('Helvetica', '', 12)
        pdf.multi_cell(0, 8, trend)
        pdf.ln(5)

        # --- Daily Forecast Table (New Advanced Feature) ---
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_fill_color(200, 220, 255)
        pdf.cell(0, 10, "5-Day Forecast", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True, border=1)

        col_widths = [30, 40, 30, 30, 40]

        # Table Header
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(col_widths[0], 7, "Day", border=1, align='C', fill=True)
        pdf.cell(col_widths[1], 7, "High/Low (°C)", border=1, align='C', fill=True)
        pdf.cell(col_widths[2], 7, "POP (%)", border=1, align='C', fill=True)
        pdf.cell(col_widths[3], 7, "Icon", border=1, align='C', fill=True)
        pdf.cell(col_widths[4], 7, "Details", border=1, align='C', fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Table Data
        pdf.set_font('Helvetica', '', 10)
        forecast_data = report_data.get('forecast_data', {}).get('daily', [])
        for day in forecast_data[:5]:
            try:
                day_str = datetime.fromtimestamp(day['dt']).strftime('%a, %b %d')
                temp_str = f"{day['temp_max']:.0f} / {day['temp_min']:.0f}"
                pop_str = f"{day['pop'] * 100:.0f}%"
                # MOCK ICON: Use a simple emoji/code for the PDF
                icon_to_pdf = {"01d": "Sun", "04d": "Clouds", "10d": "Rain", "11d": "Storm"}
                icon_str = icon_to_pdf.get(day['icon'][:2], 'N/A')

                pdf.cell(col_widths[0], 6, day_str, border=1)
                pdf.cell(col_widths[1], 6, temp_str, border=1, align='C')
                pdf.cell(col_widths[2], 6, pop_str, border=1, align='C')
                pdf.cell(col_widths[3], 6, icon_str, border=1, align='C')
                pdf.cell(col_widths[4], 6, "", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            except Exception as e:
                pdf.cell(0, 6, f"Error processing forecast day: {e}", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(5)
        # --- End Daily Forecast Table ---

        # --- Recommendations Section (Standard) ---
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 10, "Holistic Recommendations", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True, border='T')
        pdf.ln(5)
        pdf.set_font('Helvetica', '', 12)
        pdf.multi_cell(0, 8, recommendations)
        pdf.ln(5)

        # --- News Section (Standard) ---
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 10, "Relevant Local News", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True, border='T')
        pdf.ln(5)

        news = report_data.get('analyzed_news', 'N/A')
        if "Error" in news or "No relevant" in news:
            pdf.set_font('Helvetica', 'I', 12)
            pdf.multi_cell(0, 8, news)
        else:
            for line in news.split('\n'):
                if ":" in line:
                    try:
                        headline, summary = line.split(":", 1)
                        pdf.set_font('Helvetica', 'B', 12)
                        pdf.multi_cell(0, 8, headline.strip())
                        pdf.set_font('Helvetica', '', 12)
                        pdf.multi_cell(0, 8, f"   {summary.strip()}")
                        pdf.ln(2)
                    except ValueError:
                        if line.strip():
                            pdf.multi_cell(0, 8, line)
                else:
                    if line.strip():
                        pdf.multi_cell(0, 8, line)

        # --- Save File ---
        filepath = f"ClimateSense_Report_{city.split(',')[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf.output(filepath)
        print(f"[PDF] Beautiful report saved: {filepath}")
        return filepath

    except Exception as e:
        print(f"[PDF] CRITICAL ERROR during PDF generation: {e}")
        traceback.print_exc()
        return "pdf_generation_failed.pdf"


def send_email_with_pdf(pdf_filepath: str, subject: str, html_body: str):
    """Sends a beautiful HTML email with the PDF attached."""
    print(f"[Email] Preparing to send beautiful email...")
    sender_email = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASS")
    receiver_emails_str = os.getenv("EMAILS_TO_NOTIFY")
    if not all([sender_email, password, receiver_emails_str]):
        print("[Email] ERROR: Missing email configuration in .env file. Skipping email.")
        return
    receiver_emails = receiver_emails_str.split(',')
    message = MIMEMultipart("alternative")
    message["From"] = sender_email
    message["To"] = ", ".join(receiver_emails)
    message["Subject"] = subject

    # Attach HTML Body
    message.attach(MIMEText(html_body, "html"))

    # Attach PDF (Reworked to handle OS path issues)
    pdf_filename = os.path.basename(pdf_filepath)
    try:
        if pdf_filename == "pdf_generation_failed.pdf":
            print("[Email] Skipping attachment: PDF generation previously failed.")
        else:
            with open(pdf_filepath, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename= {pdf_filename}")
            message.attach(part)
    except FileNotFoundError:
        print(f"[Email] ERROR: PDF file {pdf_filepath} not found. Sending email without attachment.")
        # Do not return here, try to send the text email
    except Exception as e:
        print(f"[Email] ERROR attaching file: {e}")

    context = ssl.create_default_context()
    host = os.getenv("EMAIL_HOST")
    port = int(os.getenv("EMAIL_PORT"))
    try:
        with smtplib.SMTP_SSL(host, port, context=context) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_emails, message.as_string())
        print(f"[Email] Beautiful report successfully sent to {receiver_emails_str}")
    except Exception as e:
        print(f"[Email] ERROR: Failed to send email. {e}")
        traceback.print_exc()


def save_to_memory_bank(log_entry: dict, filepath: str):
    "Appends a new log entry to the JSON-based memory file."
    print(f"[Memory] Saving alert to {filepath}...")
    if not os.path.exists(filepath):
        with open(filepath, 'w') as f:
            json.dump([], f)
    try:
        with open(filepath, 'r') as f:
            memory = json.load(f)
        memory.append(log_entry)
        with open(filepath, 'w') as f:
            json.dump(memory, f, indent=4)
        print("[Memory] Save successful.")
    except json.JSONDecodeError:
        with open(filepath, 'w') as f:
            json.dump([log_entry], f, indent=4)
        print("[Memory] Warning: Memory file was corrupted. Started new log.")
    except Exception as e:
        print(f"[Memory] ERROR: Failed to save to memory: {e}")


# --- 3. MAIN EXECUTION LOOP (NEW FLOW) ---

if __name__ == "__main__":
    print("--- ClimateSense Agent System ACTIVATED ---")
    print(f"--- Monitoring location from {CONTROL_FILE}. Checking every {LOOP_INTERVAL_SECONDS} seconds. ---")
    print("--- Press CTRL+C to stop. ---")

    try:
        while True:
            run_timestamp = datetime.now().isoformat()
            print(f"\n--- NEW RUN @ {run_timestamp} ---")

            # --- DYNAMIC LOCATION ---
            CITY_NAME = get_target_location()
            print(f"[Main] Target location set to: {CITY_NAME}")

            # --- Define URLs dynamically inside the loop ---
            CURRENT_WEATHER_URL = f"https://api.openweathermap.org/data/2.5/weather?q={CITY_NAME}&appid={WEATHER_API_KEY}&units=metric"
            FORECAST_API_URL = f"https://api.openweathermap.org/data/2.5/forecast?q={CITY_NAME}&appid={WEATHER_API_KEY}&units=metric"
            # --- END DYNAMIC LOCATION ---

            # --- FETCHING ---
            weather_json = agent_1_weather_fetcher(CURRENT_WEATHER_URL, CITY_NAME)
            forecast_json = agent_1_5_forecast_processor(FORECAST_API_URL, CITY_NAME)

            if weather_json and forecast_json:
                coord = weather_json.get("coord", {})
                lat = coord.get("lat")
                lon = coord.get("lon")

                # --- Advanced Data Fetching ---
                raw_aqi_data = agent_1_6_air_quality_fetcher(lat, lon, WEATHER_API_KEY)
                advanced_fetch_data = agent_1_7_advanced_fetcher(lat, lon, WEATHER_API_KEY)  # NEW FETCHER

                # --- CLASSIFICATION & ANALYSIS ---
                risk_report_dict = agent_2_risk_classifier(weather_json)

                # Extract details for heat classification
                temp_c = risk_report_dict['details']['temp_c']
                humidity = risk_report_dict['details']['humidity']
                heat_risk_report = agent_2_7_heat_classifier(temp_c, humidity)  # NEW CLASSIFIER

                air_quality_report = agent_2_5_air_quality_analyzer(raw_aqi_data, advanced_fetch_data)

                # --- DATA VALIDATION ---
                data_validation_result = agent_3_5_data_validator(risk_report_dict, air_quality_report)  # NEW VALIDATOR

                # --- TREND AND ICON ANALYSIS ---
                current_desc = risk_report_dict['details']['description']
                icon_code = weather_json.get("weather", [{}])[0].get("icon", "N/A")
                icon_analysis = agent_12_icon_analyzer(icon_code, current_desc)  # NEW MULTIMODAL AGENT

                # Package all risk reports for final prioritization and trend analysis
                risk_report_dict.update({
                    "air_quality_report": air_quality_report,
                    "heat_risk_report": heat_risk_report,
                    "primary_level": risk_report_dict['primary_level'],
                    "heat_risk": heat_risk_report['heat_risk']
                })

                # --- FINAL RISK PRIORITIZATION ---
                final_risk_result = agent_11_alert_prioritizer(risk_report_dict)  # NEW PRIORITIZER
                final_level = final_risk_result.split(':')[0].strip()

                # Update risk dict with final data before saving/trending
                risk_report_dict['final_level'] = final_level
                risk_report_dict['final_reasoning'] = final_risk_result.split(':', 1)[-1].strip()

                # --- TREND ANALYSIS (uses final_level in memory) ---
                # NOTE: The trend agent now expects the new final_level to be in the dict it receives
                trend_analysis = agent_5_trend_forecaster(risk_report_dict, MEMORY_FILE, CITY_NAME)
                risk_report_dict['trend'] = trend_analysis

                # --- RECOMMENDATIONS ---
                action_list = agent_3_action_recommender(risk_report_dict, heat_risk_report, air_quality_report,
                                                         forecast_json)

                # --- NEWS & SATELLITE ---
                raw_articles = agent_6_news_fetcher(CITY_NAME, current_desc)
                analyzed_news_summary = agent_7_news_analyzer(raw_articles)
                sim_satellite_data = agent_9_satellite_image_fetcher(CITY_NAME, current_desc)
                satellite_analysis_report = agent_10_satellite_analyzer(sim_satellite_data)

                # 8. Broadcast to console
                agent_4_broadcast_agent(risk_report_dict, action_list)
                print("\n--- ICON ANALYSIS ---")
                print(icon_analysis)
                print("\n--- DATA VALIDATION CHECK ---")
                print(data_validation_result)
                print("\n--- LATEST NEWS ANALYSIS ---")
                print(analyzed_news_summary)
                print("\n--- SATELLITE ANALYSIS ---")
                print(satellite_analysis_report.get('analysis', 'N/A'))
                print("=" * 40 + "\n")

                # 9. Create complete log entry
                log_entry = {
                    "timestamp": run_timestamp,
                    "city": CITY_NAME,
                    "final_risk_level": final_level,
                    "risk_report": risk_report_dict,  # Contains primary, heat, trend, final_level
                    "recommendations": action_list,
                    "analyzed_news": analyzed_news_summary,
                    "raw_data": weather_json,
                    "forecast_data": forecast_json,
                    "air_quality_report": air_quality_report,
                    "advanced_fetch_data": advanced_fetch_data,  # NEW FETCH DATA
                    "data_validation": data_validation_result,  # NEW VALIDATION
                    "icon_analysis": icon_analysis,  # NEW ICON ANALYSIS
                    "satellite_analysis": satellite_analysis_report
                }

                # 10. Save to Memory Bank
                save_to_memory_bank(log_entry, MEMORY_FILE)

                # 11. Generate & Send Smart Email (on MODERATE+)
                if final_level in ["CRITICAL", "HIGH", "MODERATE"]:
                    print("[Alert] Moderate or higher risk detected. Starting PDF/Email workflow...")
                    pdf_file = generate_pdf_report(log_entry)
                    email_content = agent_8_email_composer(log_entry)
                    send_email_with_pdf(
                        pdf_file,
                        email_content["subject"],
                        email_content["html_body"]
                    )
                else:
                    print(f"[Alert] Final Risk is {final_level}. No high-priority report will be sent.")

            else:
                print(f"Skipping run due to weather/forecast fetch error for {CITY_NAME}.")

            # --- Smart Sleep ---
            print(f"--- Run complete. Entering smart sleep for {LOOP_INTERVAL_SECONDS} seconds... ---")

            change_detected = smart_sleep_and_watch(
                duration_seconds=LOOP_INTERVAL_SECONDS,
                check_interval_seconds=LOCATION_CHECK_INTERVAL_SECONDS,
                location_at_start_of_sleep=CITY_NAME
            )

            if change_detected:
                print("--- Location change detected! Forcing immediate new run. ---")

    except KeyboardInterrupt:
        print("\n--- User shutdown. ClimateSense Agent System DEACTIVATED. ---")