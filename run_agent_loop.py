import os
import json
import requests
import google.generativeai as genai
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta

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

# --- MODELS (UPGRADED) ---
# Use a standard, fast model for simple analysis
llm_model_fast = genai.GenerativeModel('models/gemini-pro-latest')
# Use a (hypothetical) more advanced model for complex recommendations
llm_model_advanced = genai.GenerativeModel('models/gemini-1.5-pro-latest')

newsapi = NewsApiClient(api_key=NEWS_API_KEY)

MEMORY_FILE = "memory_log.json"
CONTROL_FILE = "control_file.json"  # --- NEW: Control file ---
DEFAULT_LOCATION = "Kerala,IN"  # Fallback if control file is missing
LOOP_INTERVAL_SECONDS = 3600  # 3600 seconds = 1 hour. (Set to 60 for testing)

# --- NEW: Set check interval to 1 second for a near-instant response ---
LOCATION_CHECK_INTERVAL_SECONDS = 1


# --- NEW: Function to read control file ---
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


# --- NEW: Function to "sleep" but wake up to check for changes ---
def smart_sleep_and_watch(duration_seconds: int, check_interval_seconds: int, location_at_start_of_sleep: str):
    """
    Sleeps for 'duration_seconds' but wakes up every 'check_interval_seconds'
    to see if the control file's location has changed.

    Returns True if a change was detected, False otherwise.
    """
    print(f"[Main] Sleeping, but checking {CONTROL_FILE} every {check_interval_seconds}s for changes...")

    end_time = time.time() + duration_seconds

    while time.time() < end_time:
        # Calculate how long to sleep: either the check_interval or time
        # remaining, whichever is smaller.
        sleep_time = min(check_interval_seconds, end_time - time.time())

        if sleep_time <= 0:
            break  # Time's up

        time.sleep(sleep_time)

        # Now, check the file
        current_file_location = get_target_location()

        # Compare against the location we had when this run started
        if current_file_location.lower() != location_at_start_of_sleep.lower():
            print(f"[Main] Location change detected: '{location_at_start_of_sleep}' -> '{current_file_location}'")
            return True  # A change was detected!

    # If the loop finished without finding a change
    return False


# --- 2. AGENT DEFINITIONS (MODIFIED) ---

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


# --- UPDATED: AGENT 1.5 (Now uses free API) ---
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
            # Get the date (e.g., "2025-11-16")
            date_key = datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d')

            # Get the weather details for this 3-hour block
            temp_min = item['main']['temp_min']
            temp_max = item['main']['temp_max']
            icon = item['weather'][0]['icon']
            pop = item.get('pop', 0)  # Probability of precipitation

            if date_key not in daily_forecasts:
                # This is the first entry we've seen for this day
                daily_forecasts[date_key] = {
                    'date_ts': item['dt'],
                    'temp_min': temp_min,
                    'temp_max': temp_max,
                    'icons': {icon: 1},  # Count icons to find most common
                    'pops': [pop]
                }
            else:
                # Update existing day
                if temp_min < daily_forecasts[date_key]['temp_min']:
                    daily_forecasts[date_key]['temp_min'] = temp_min
                if temp_max > daily_forecasts[date_key]['temp_max']:
                    daily_forecasts[date_key]['temp_max'] = temp_max

                # Add icon to count
                daily_forecasts[date_key]['icons'][icon] = daily_forecasts[date_key]['icons'].get(icon, 0) + 1
                daily_forecasts[date_key]['pops'].append(pop)

        # Now, process the collected data into a clean list
        processed_daily = []
        for date_key, values in daily_forecasts.items():
            # Find the most common icon for the day
            most_common_icon = max(values['icons'], key=values['icons'].get)
            # Get the max probability of precipitation for the day
            max_pop = max(values['pops'])

            processed_daily.append({
                'dt': values['date_ts'],
                'temp_min': values['temp_min'],
                'temp_max': values['temp_max'],
                'icon': most_common_icon,
                'pop': max_pop
            })

        # --- FIX: Sort the forecast by date to ensure chronological order ---
        processed_daily.sort(key=lambda x: x['dt'])

        print(f"[Agent 1.5] Processed {len(processed_daily)} forecast days.")
        # Return a simple dictionary, matching the old structure
        return {'daily': processed_daily}

    except requests.exceptions.RequestException as e:
        print(f"[Agent 1.5] ERROR: {e}")
        return None


# --- NEW: AGENT 1.6 (Air Quality) ---
def agent_1_6_air_quality_fetcher(lat: float, lon: float, api_key: str) -> dict:
    """Agent 1.6: Fetches air quality data from the API."""
    print(f"[Agent 1.6] Fetching Air Quality for (lat:{lat}, lon:{lon})...")
    api_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={api_key}"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        print("[Agent 1.6] Air Quality fetch successful.")
        # The data is nested in 'list', we just want the first (and only) item
        return response.json()['list'][0]
    except Exception as e:
        print(f"[Agent 1.6] ERROR: {e}")
        return None


# --- END NEW AGENT ---


def agent_2_risk_classifier(weather_data: dict) -> dict:
    """Agent 2: Converts raw data into risk levels (Code Tool)."""
    print("[Agent 2] Classifying risk...")
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
    print(f"[Agent 2] Risk classified as: {risk_level}")
    return {
        "risk_level": risk_level,
        "reasoning": reasoning,
        "details": {
            "temp_c": temp,
            "wind_speed_ms": wind_speed,
            "description": description
        }
    }


# --- NEW: AGENT 2.5 (Air Quality Analysis) ---
def agent_2_5_air_quality_analyzer(aqi_data: dict) -> dict:
    """Agent 2.5: Uses LLM to analyze raw AQI data."""
    print("[Agent 2.5] Analyzing Air Quality...")
    if not aqi_data:
        return {"aqi": "N/A", "analysis": "No data"}

    aqi_index = aqi_data.get('main', {}).get('aqi', 0)
    components = aqi_data.get('components', {})

    # Map AQI index to a human-readable name
    aqi_map = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}
    aqi_name = aqi_map.get(aqi_index, "Unknown")

    prompt = f"""
    You are a public health advisor.
    The current Air Quality Index (AQI) is {aqi_index} ({aqi_name}).
    The key pollutants are (in μg/m³):
    - PM2.5: {components.get('pm2_5', 'N/A')}
    - Ozone (O3): {components.get('o3', 'N/A')}
    - Nitrogen Dioxide (NO2): {components.get('no2', 'N/A')}

    Provide a simple, one-sentence analysis and health recommendation
    for the general public.
    Example: 'Air quality is moderate; sensitive groups should limit outdoor activity.'
    """
    try:
        response = llm_model_fast.generate_content(prompt)
        analysis_text = response.text.strip()
        print(f"[Agent 2.5] Analysis complete: {analysis_text}")
        return {"aqi": aqi_index, "analysis": analysis_text}
    except Exception as e:
        print(f"[Agent 2.5] ERROR: {e}")
        # FIX: Return the NUMERIC index, not the string name, to avoid a TypeError
        return {"aqi": aqi_index, "analysis": "Error analyzing air quality."}


# --- END NEW AGENT ---


def agent_3_action_recommender(risk_report: dict, air_quality_report: dict) -> str:
    """Agent 3: UPGRADED to use trend and air quality (Advanced LLM)."""
    print("[Agent 3] Generating advanced recommendations with advanced model...")
    if risk_report["risk_level"] == "LOW" and air_quality_report.get('aqi', 0) <= 2:
        print("[Agent 3] Risk is LOW. No actions needed.")
        return "Conditions are calm and air quality is good. No special actions required."

    prompt = f"""
    You are an expert community safety advisor using an advanced reasoning model.
    Synthesize all of the following information to provide a single, holistic
    set of 3-5 bullet-point recommendations.

    1.  **Weather Risk**:
        * Level: {risk_report['risk_level']}
        * Reason: {risk_report['reasoning']}
        * Trend: {risk_report['trend']}
        * Details: {risk_report['details']}

    2.  **Air Quality**:
        * AQI: {air_quality_report.get('aqi', 'N/A')}
        * Analysis: {air_quality_report.get('analysis', 'N/A')}

    **Instructions**:
    - Combine the advice. If wind is high AND air quality is poor, be extra urgent.
    - If it's raining, mention it might help clear the poor air.
    - Be clear and actionable. Do not use an introduction.
    """
    try:
        # Use the more advanced model for this complex task
        response = llm_model_advanced.generate_content(prompt)
        print("[Agent 3] Advanced recommendations generated.")
        return response.text
    except Exception as e:
        print(f"[Agent 3] ERROR: {e}")
        return "Error generating recommendations."


def agent_4_broadcast_agent(risk_report: dict, recommendations: str):
    """Agent 4: Formats and "broadcasts" the final alert to console."""
    print("\n" + "=" * 40)
    print("🚨 CLIMATE-SENSE COMMUNITY ALERT 🚨")
    print(f"       TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 40 + "\n")
    print(f"RISK LEVEL: {risk_report['risk_level']}")
    print(f"REASON: {risk_report['reasoning']}")
    print(f"TREND: {risk_report.get('trend', 'N/A')}")
    print(
        f"DETAILS: {risk_report['details']['description']} | {risk_report['details']['temp_c']}°C | {risk_report['details']['wind_speed_ms']} m/s wind")
    print("\n--- RECOMMENDED ACTIONS ---")
    print(recommendations)
    print("\n" + "=" * 40 + "\n")


def agent_5_trend_forecaster(current_risk_report: dict, memory_file: str, city_name: str) -> str:
    """Agent 5: Uses LLM to analyze historical data for a specific city and predict a trend."""
    print(f"[Agent 5] Analyzing risk trend for {city_name}...")
    try:
        with open(memory_file, 'r') as f:
            history = json.load(f)

        # Filter history for the current city
        city_history = [
            report for report in history
            if report.get('city', '').lower() == city_name.lower()
        ]

        if len(city_history) < 2:
            print("[Agent 5] Not enough history for this city to analyze trend.")
            return "No trend data available."

        recent_reports = city_history[-3:]
    except (FileNotFoundError, json.JSONDecodeError, IndexError):
        print("[Agent 5] No history file found.")
        return "No trend data available."

    past_data_summary = []
    for report in recent_reports:
        ts = report.get('timestamp', 'N/A')
        lvl = report.get('risk_report', {}).get('risk_level', 'N/A')
        rsn = report.get('risk_report', {}).get('reasoning', 'N/A')
        past_data_summary.append(f"- At {ts}: Risk was {lvl} due to {rsn}.")

    past_data_str = "\n".join(past_data_summary)

    prompt = f"""
    You are a meteorologist analyzing weather trends for {city_name}.
    Here is the recent history (oldest to newest):
    {past_data_str}

    Here is the NEWEST reading:
    - Risk is {current_risk_report['risk_level']} due to {current_risk_report['reasoning']}.

    Analyze this pattern and provide a single-sentence trend analysis.
    (e.g., "Conditions are rapidly worsening," "The storm appears to be passing," "Risk remains high but stable.")
    """
    try:
        response = llm_model_fast.generate_content(prompt)
        trend = response.text.strip()
        print(f"[Agent 5] Trend identified: {trend}")
        return trend
    except Exception as e:
        print(f"[Agent 5] ERROR: {e}")
        return "Error analyzing trend."


def agent_6_news_fetcher(city: str, weather_desc: str) -> list:
    """Agent 6: Fetches relevant raw news articles."""
    print("[Agent 6] Fetching relevant news...")
    city_main = city.split(',')[0]
    query = f'"{city_main}" AND ("weather" OR "flood" OR "storm" OR "rain" OR "air quality" OR "{weather_desc}")'
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
    """Agent 7: Uses LLM to analyze and summarize relevant news."""
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
    You are a local safety analyst. I have provided a list of news articles
    below. Read them and identify ONLY the ones that are relevant to
    immediate local safety, weather alerts, air quality warnings, or major disruptions.
    For each relevant article, provide a 1-sentence summary.
    If no articles are relevant, just say "No relevant local safety news found."
    Format your response like this:
    [Headline]: [Your 1-sentence summary]
    Here are the articles:
    {articles_str}
    """
    try:
        response = llm_model_fast.generate_content(prompt)
        print("[Agent 7] News analysis complete.")
        return response.text.strip()
    except Exception as e:
        print(f"[Agent 7] ERROR: {e}")
        return "Error analyzing news."


def agent_8_email_composer(log_entry: dict) -> dict:
    """
    Agent 8: Uses LLM to generate a smart subject and beautiful HTML email.
    """
    print("[Agent 8] Composing smart email...")
    risk_level = log_entry['risk_report']['risk_level']
    city = log_entry['city']
    subject = ""
    if risk_level == "HIGH":
        subject = f"URGENT Safety Alert for {city}: {log_entry['risk_report']['reasoning']}"
    elif risk_level == "MODERATE":
        subject = f"Weather & Air Quality Advisory for {city}"
    else:
        subject = f"Weekly Weather & Safety Summary for {city}"

    recommendations = log_entry['recommendations']
    if "Error" in recommendations:
        recommendations = "N/A"
    news = log_entry['analyzed_news']
    if "Error" in news:
        news = "N/A"

    prompt = f"""
    You are a communications assistant. Generate a professional and colorful
    HTML email body for a weather alert.
    DATA:
    - City: {city}
    - Weather Risk: {risk_level}
    - Weather Reason: {log_entry['risk_report']['reasoning']}
    - Weather Trend: {log_entry['risk_report']['trend']}
    - Weather Details: {log_entry['risk_report']['details']}
    - Air Quality: {log_entry.get('air_quality_report', {}).get('analysis', 'N/A')}
    - Recommendations: {recommendations}
    - Local News: {news}
    INSTRUCTIONS:
    - Use a friendly but professional tone.
    - Use inline CSS for colors and styling (e.g., <div style="...">).
    - Create a main container (max-width: 600px).
    - Use a header with a main title.
    - Use a color bar at the top (RED for HIGH risk, ORANGE for MODERATE, GREEN for LOW).
    - Format "Weather Details" and "Air Quality" in a clean list or table.
    - Format "Recommendations" and "Local News" as bullet lists.
    - Add a footer: "Stay safe, The ClimateSense Team".
    Provide ONLY the HTML code, starting with <html> and ending with </html>.
    """
    try:
        response = llm_model_fast.generate_content(prompt)
        html_body = response.text
        html_body = html_body.replace("```html", "").replace("```", "").strip()
        print("[Agent 8] Email composition successful.")
        return {"subject": subject, "html_body": html_body}
    except Exception as e:
        print(f"[Agent 8] ERROR: {e}")
        # Fallback to a simple text email if AI fails
        return {
            "subject": subject,
            "html_body": f"Risk Level: {risk_level}\nReason: {log_entry['risk_report']['reasoning']}\nTrend: {log_entry['risk_report']['trend']}"
        }


# --- NEW: AGENT 9 (Satellite Fetcher - MOCKED) ---
def agent_9_satellite_image_fetcher(city: str, weather_desc: str) -> dict:
    """Agent 9: Simulates fetching a satellite image URL and basic analysis."""
    print(f"[Agent 9] Simulating satellite image fetch for {city}...")
    # In a real app, this would query NASA, ESA, or another satellite API

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


# --- END NEW AGENT ---

# --- NEW: AGENT 10 (Satellite Analyzer) ---
def agent_10_satellite_analyzer(image_data: dict) -> dict:
    """Agent 10: Uses LLM to provide a strategic analysis of satellite data."""
    print("[Agent 10] Analyzing satellite data...")

    prompt = f"""
    You are a remote sensing analyst. Your satellite has provided the
    following basic description of a target area:
    "{image_data['description']}"

    Provide a 1-2 sentence strategic analysis for a safety dashboard.
    What does this imply for the local area?
    Example: "Analysis: Clear skies confirm ideal conditions, but also high UV risk."
    Example: "Analysis: The large storm cell indicates an imminent threat."
    """
    try:
        response = llm_model_fast.generate_content(prompt)
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


# --- END NEW AGENT ---


# --- PDF & EMAIL FUNCTIONS ---

class PDF(FPDF):
    """Custom PDF class to create colorful headers/footers."""

    def header(self):
        self.set_font('Helvetica', 'B', 15)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 12, 'ClimateSense Weather Report',
                  border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C', fill=True)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}',
                  border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')


def generate_pdf_report(report_data: dict) -> str:
    """Generates a beautiful, colorful PDF report."""
    print("[PDF] Generating beautiful PDF report...")
    pdf = PDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()

    city = report_data.get('city', 'N/A')
    risk_level = report_data.get('risk_report', {}).get('risk_level', 'UNKNOWN')
    reason = report_data.get('risk_report', {}).get('reasoning', 'N/A')
    trend = report_data.get('risk_report', {}).get('trend', 'N/A')
    details = report_data.get('risk_report', {}).get('details', {})
    recommendations = report_data.get('recommendations', 'N/A')
    news = report_data.get('analyzed_news', 'N/A')
    air_quality = report_data.get('air_quality_report', {}).get('analysis', 'N/A')

    # --- PDF Header (Risk) ---
    if risk_level == "HIGH":
        pdf.set_fill_color(220, 50, 50)
        pdf.set_text_color(255, 255, 255)
    elif risk_level == "MODERATE":
        pdf.set_fill_color(255, 193, 7)
        pdf.set_text_color(0, 0, 0)
    else:
        pdf.set_fill_color(76, 175, 80)
        pdf.set_text_color(255, 255, 255)

    pdf.set_font('Helvetica', 'B', 20)
    pdf.cell(0, 15, f"CURRENT RISK: {risk_level} ({city})",
             border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C', fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    # --- Risk Analysis Section ---
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 10, "Risk Analysis", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True, border='T')
    pdf.ln(5)

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(35, 8, "Weather Reason:")
    pdf.set_font('Helvetica', '', 12)
    pdf.multi_cell(0, 8, reason)
    pdf.ln(2)

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(35, 8, "Weather Trend:")
    pdf.set_font('Helvetica', '', 12)
    pdf.multi_cell(0, 8, trend)
    pdf.ln(2)

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(35, 8, "Weather Details:")
    pdf.set_font('Helvetica', '', 12)
    pdf.multi_cell(0, 8,
                   f"Temp: {details.get('temp_c', 'N/A')}°C | "
                   f"Wind: {details.get('wind_speed_ms', 'N/A')} m/s | "
                   f"Desc: {details.get('description', 'N/A')}"
                   )
    pdf.ln(2)

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(35, 8, "Air Quality:")
    pdf.set_font('Helvetica', '', 12)
    pdf.multi_cell(0, 8, air_quality)
    pdf.ln(5)

    # --- Recommendations Section ---
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 10, "Holistic Recommendations", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True, border='T')
    pdf.ln(5)
    pdf.set_font('Helvetica', '', 12)
    pdf.multi_cell(0, 8, recommendations)
    pdf.ln(5)

    # --- News Section ---
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 10, "Relevant Local News", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True, border='T')
    pdf.ln(5)

    # Check for error and display nicely
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
    filepath = f"ClimateSense_Report_{city.split(',')[0]}_{datetime.now().strftime('%Y%m%d')}.pdf"
    pdf.output(filepath)
    print(f"[PDF] Beautiful report saved: {filepath}")
    return filepath


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
    message.attach(MIMEText(html_body, "html"))
    try:
        with open(pdf_filepath, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename= {pdf_filepath}")
        message.attach(part)
    except FileNotFoundError:
        print(f"[Email] ERROR: PDF file {pdf_filepath} not found. Sending email without attachment.")
        return
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


# --- HELPER FUNCTION FOR MEMORY ---

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


# --- 3. MAIN EXECUTION (--- MODIFIED ---) ---

if __name__ == "__main__":
    print("--- ClimateSense Agent System ACTIVATED ---")
    print(f"--- Monitoring location from {CONTROL_FILE}. Checking every {LOOP_INTERVAL_SECONDS} seconds. ---")
    print("--- Press CTRL+C to stop. ---")

    try:
        while True:
            run_timestamp = datetime.now().isoformat()
            print(f"\n--- NEW RUN @ {run_timestamp} ---")

            # --- DYNAMIC LOCATION (NEW) ---
            CITY_NAME = get_target_location()
            print(f"[Main] Target location set to: {CITY_NAME}")

            # --- Define URLs dynamically inside the loop ---
            CURRENT_WEATHER_URL = f"https://api.openweathermap.org/data/2.5/weather?q={CITY_NAME}&appid={WEATHER_API_KEY}&units=metric"
            # --- FIX: Added '://' to the URL ---
            FORECAST_API_URL = f"https://api.openweathermap.org/data/2.5/forecast?q={CITY_NAME}&appid={WEATHER_API_KEY}&units=metric"
            # --- END DYNAMIC LOCATION ---

            # 1. Fetch current weather
            weather_json = agent_1_weather_fetcher(CURRENT_WEATHER_URL, CITY_NAME)

            # 1.5. Call new forecast agent
            forecast_json = agent_1_5_forecast_processor(FORECAST_API_URL, CITY_NAME)

            if weather_json:
                # --- Get Coords for other APIs ---
                coord = weather_json.get("coord", {})
                lat = coord.get("lat")
                lon = coord.get("lon")

                # 1.6. Fetch Air Quality
                raw_aqi_data = None
                if lat and lon:
                    raw_aqi_data = agent_1_6_air_quality_fetcher(lat, lon, WEATHER_API_KEY)
                else:
                    print("[Agent 1.6] Skipping air quality, no lat/lon from weather.")

                # 2. Classify current risk
                risk_report_dict = agent_2_risk_classifier(weather_json)

                # 2.5 Analyze Air Quality
                air_quality_report = agent_2_5_air_quality_analyzer(raw_aqi_data)

                # 3. Analyze trend using history (now city-specific)
                trend_analysis = agent_5_trend_forecaster(risk_report_dict, MEMORY_FILE, CITY_NAME)
                risk_report_dict['trend'] = trend_analysis

                # 4. Get recommendations (now trend-aware AND air-quality-aware)
                action_list = agent_3_action_recommender(risk_report_dict, air_quality_report)

                # 5. Fetch relevant news
                current_desc = risk_report_dict['details']['description']
                raw_articles = agent_6_news_fetcher(CITY_NAME, current_desc)

                # 6. Analyze and summarize news
                analyzed_news_summary = agent_7_news_analyzer(raw_articles)

                # 7. (Agents 9 & 10) Get Satellite Analysis
                sim_satellite_data = agent_9_satellite_image_fetcher(CITY_NAME, current_desc)
                satellite_analysis_report = agent_10_satellite_analyzer(sim_satellite_data)

                # 8. Broadcast to console
                agent_4_broadcast_agent(risk_report_dict, action_list)
                print("\n--- LATEST NEWS ANALYSIS ---")
                print(analyzed_news_summary)
                print("\n--- AIR QUALITY ANALYSIS ---")
                print(air_quality_report.get('analysis', 'N/A'))
                print("\n--- SATELLITE ANALYSIS ---")
                print(satellite_analysis_report.get('analysis', 'N/A'))
                print("=" * 40 + "\n")

                # 9. Create log entry for memory
                log_entry = {
                    "timestamp": run_timestamp,
                    "city": CITY_NAME,  # --- CRITICAL: Save the dynamic city name ---
                    "risk_report": risk_report_dict,
                    "recommendations": action_list,
                    "analyzed_news": analyzed_news_summary,
                    "raw_data": weather_json,
                    "forecast_data": forecast_json,
                    "air_quality_report": air_quality_report,  # --- NEW DATA
                    "satellite_analysis": satellite_analysis_report  # --- NEW DATA
                }

                # 10. Save to Memory Bank
                save_to_memory_bank(log_entry, MEMORY_FILE)

                # 11. UPGRADED: Generate & Send Smart Email
                if risk_report_dict['risk_level'] in ["MODERATE", "HIGH", "EXTREME"]:
                    print("[Alert] High risk detected. Starting PDF/Email workflow...")
                    pdf_file = generate_pdf_report(log_entry)
                    email_content = agent_8_email_composer(log_entry)
                    send_email_with_pdf(
                        pdf_file,
                        email_content["subject"],
                        email_content["html_body"]
                    )
                else:
                    print("[Alert] Risk is LOW. No report will be sent.")

            else:
                print(f"Skipping run due to weather fetch error for {CITY_NAME}.")

            # --- MODIFIED: Replaced time.sleep() with smart_sleep_and_watch() ---
            print(f"--- Run complete. Entering smart sleep for {LOOP_INTERVAL_SECONDS} seconds... ---")

            change_detected = smart_sleep_and_watch(
                duration_seconds=LOOP_INTERVAL_SECONDS,
                check_interval_seconds=LOCATION_CHECK_INTERVAL_SECONDS,
                location_at_start_of_sleep=CITY_NAME
            )

            if change_detected:
                print("--- Location change detected! Forcing immediate new run. ---")
            # The loop will now restart immediately
            # --- END MODIFICATION ---

    except KeyboardInterrupt:
        print("\n--- User shutdown. ClimateSense Agent System DEACTIVATED. ---")