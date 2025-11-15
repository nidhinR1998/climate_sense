import datetime
import os
import json
import requests
import google.generativeai as genai
from dotenv import load_dotenv
from datetime import datetime

# --- 1. CONFIGURATION & SETUP ---

# Load API keys from .env file
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

# Configure the Gemini LLM
genai.configure(api_key=GOOGLE_API_KEY)
llm_model = genai.GenerativeModel('gemini-1.5-flash')

# Constants
CITY_NAME = "Kerala,IN"  # <-- Change this to your target city
WEATHER_API_URL = f"https://api.openweathermap.org/data/2.5/weather?q={CITY_NAME}&appid={WEATHER_API_KEY}&units=metric"


# --- 2. AGENT DEFINITIONS (as functions) ---

def agent_1_weather_fetcher(api_url: str) -> dict:
    """
    Agent 1: Fetches raw weather data from the API.
    This is our OpenAPI Tool integration.
    """
    print(f"[Agent 1] Fetching weather for {CITY_NAME}...")
    try:
        response = requests.get(api_url)
        # Raise an error if the request failed
        response.raise_for_status()
        print("[Agent 1] Fetch successful.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[Agent 1] ERROR: {e}")
        return None


def agent_2_risk_classifier(weather_data: dict) -> dict:
    """
    Agent 2: Converts raw data into risk levels.
    This acts as our 'Code Execution Tool' for logical analysis.
    """
    print("[Agent 2] Classifying risk...")

    # Extract data
    # Using .get() provides a default (0 or "unknown") if the key is missing
    wind_speed = weather_data.get("wind", {}).get("speed", 0)
    description = weather_data.get("weather", [{}])[0].get("description", "unknown")
    temp = weather_data.get("main", {}).get("temp", 0)

    # Simple risk logic (our 'code tool')
    risk_level = "LOW"
    reasoning = "Conditions are calm."

    if "thunderstorm" in description or "squalls" in description:
        risk_level = "HIGH"
        reasoning = "Active thunderstorm or squalls reported."
    elif "rain" in description and wind_speed > 15:  # > 15 m/s is ~54 km/h
        risk_level = "HIGH"
        reasoning = f"Heavy rain combined with high wind speed ({wind_speed} m/s)."
    elif "rain" in description:
        risk_level = "MODERATE"
        reasoning = f"Rain reported. Monitor conditions."
    elif wind_speed > 20:  # > 20 m/s is ~72 km/h
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


def agent_3_action_recommender(risk_report: dict) -> str:
    """
    Agent 3: Uses the LLM to generate actionable advice.
    This is our 'Agent powered by an LLM'.
    """
    print("[Agent 3] Generating recommendations from LLM...")

    # Do not call the LLM if risk is low
    if risk_report["risk_level"] == "LOW":
        print("[Agent 3] Risk is LOW. No actions needed.")
        return "Conditions are calm. No special actions required."

    # Craft a clear prompt for the LLM
    prompt = f"""
    You are an expert community safety advisor.
    A weather risk has been identified for a local community.

    Risk Level: {risk_report['risk_level']}
    Reason: {risk_report['reasoning']}
    Weather Details: {risk_report['details']}

    Based ONLY on this information, provide a short, clear, and actionable
    list of 3-5 recommendations for residents.
    Use bullet points. Do not use an introduction.
    """

    try:
        response = llm_model.generate_content(prompt)
        print("[Agent 3] Recommendations generated.")
        return response.text
    except Exception as e:
        print(f"[Agent 3] ERROR: {e}")
        return "Error generating recommendations."


def agent_4_broadcast_agent(risk_report: dict, recommendations: str):
    """
    Agent 4: Formats and "broadcasts" the final alert.
    For this project, it just prints to the console.
    """
    print("\n" + "=" * 40)
    print("🚨 CLIMATE-SENSE COMMUNITY ALERT 🚨")
    print(f"       TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 40 + "\n")

    print(f"RISK LEVEL: {risk_report['risk_level']}")
    print(f"REASON: {risk_report['reasoning']}")
    print(
        f"DETAILS: {risk_report['details']['description']} | {risk_report['details']['temp_c']}°C | {risk_report['details']['wind_speed_ms']} m/s wind")

    print("\n--- RECOMMENDED ACTIONS ---")
    print(recommendations)
    print("\n" + "=" * 40 + "\n")


# --- 3. MAIN EXECUTION (The Sequential Pipeline) ---

if __name__ == "__main__":
    # This is the "sequential agent" flow

    # 1. Agent 1 runs
    weather_json = agent_1_weather_fetcher(WEATHER_API_URL)

    if weather_json:
        # 2. Agent 2 runs, using Agent 1's output
        risk_report_dict = agent_2_risk_classifier(weather_json)

        # 3. Agent 3 runs, using Agent 2's output
        action_list = agent_3_action_recommender(risk_report_dict)

        # 4. Agent 4 runs, using Agents 2 & 3's output
        agent_4_broadcast_agent(risk_report_dict, action_list)