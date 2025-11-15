import os
import json
import requests
import google.generativeai as genai
from dotenv import load_dotenv
from datetime import datetime, timedelta
from newsapi import NewsApiClient

# --- 1. CONFIGURATION & SETUP ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# Check for all keys
if not all([GOOGLE_API_KEY, WEATHER_API_KEY, NEWS_API_KEY]):
    print("ERROR: API keys not found in .env file.")
    # In a real app, you'd have Streamlit show an error

genai.configure(api_key=GOOGLE_API_KEY)
llm_model = genai.GenerativeModel('models/gemini-pro-latest')
newsapi = NewsApiClient(api_key=NEWS_API_KEY)


# --- 2. AGENT DEFINITIONS ---
# All agents now accept 'city_name' as a parameter

def agent_1_weather_fetcher(city_name: str) -> dict:
    """Agent 1: Fetches raw weather data from the API."""
    print(f"[Agent 1] Fetching current weather for {city_name}...")
    api_url = f"https://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={WEATHER_API_KEY}&units=metric"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        print("[Agent 1] Fetch successful.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[Agent 1] ERROR: {e}")
        return {"error": str(e)}


def agent_1_5_forecast_processor(city_name: str) -> dict:
    """
    Agent 1.5: Fetches 5-day/3-hour forecast and processes it
    into a simple daily summary.
    """
    print(f"[Agent 1.5] Fetching 5-day forecast for {city_name}...")
    api_url = f"https://api.openweathermap.org/data/2.5/forecast?q={city_name}&appid={WEATHER_API_KEY}&units=metric"
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
                    'date_ts': item['dt'], 'temp_min': temp_min, 'temp_max': temp_max,
                    'icons': {icon: 1}, 'pops': [pop]
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
                'dt': values['date_ts'], 'temp_min': values['temp_min'],
                'temp_max': values['temp_max'], 'icon': most_common_icon, 'pop': max_pop
            })

        print(f"[Agent 1.5] Processed {len(processed_daily)} forecast days.")
        return {'daily': processed_daily}

    except requests.exceptions.RequestException as e:
        print(f"[Agent 1.5] ERROR: {e}")
        return {"error": str(e)}


def agent_2_risk_classifier(weather_data: dict) -> dict:
    """Agent 2: Converts raw data into risk levels (Code Tool)."""
    # (This agent is simplified as it no longer has history to compare)
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
        "trend": "On-demand search. No trend data.",  # Trend agent is disabled in this on-demand model
        "details": {
            "temp_c": temp,
            "wind_speed_ms": wind_speed,
            "description": description
        }
    }


def agent_3_action_recommender(risk_report: dict) -> str:
    """Agent 3: Simple LLM recommender based on current risk."""
    print("[Agent 3] Generating recommendations...")
    if risk_report["risk_level"] == "LOW":
        print("[Agent 3] Risk is LOW. No actions needed.")
        return "Conditions are calm. No special actions required."
    prompt = f"""
    You are an expert community safety advisor.
    The current risk level is: {risk_report['risk_level']}
    The reason is: {risk_report['reasoning']}
    Based ONLY on this, provide a short, clear, and actionable
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


def agent_6_news_fetcher(city_name: str, weather_desc: str) -> list:
    """Agent 6: Fetches relevant raw news articles."""
    print("[Agent 6] Fetching relevant news...")
    city_main = city_name.split(',')[0]
    query = f'"{city_main}" AND ("weather" OR "flood" OR "storm" OR "rain" OR "{weather_desc}")'
    from_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    try:
        all_articles = newsapi.get_everything(
            q=query, from_param=from_date, language='en',
            sort_by='relevancy', page_size=10
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
    You are a local safety analyst. Read the articles and identify ONLY
    the ones relevant to immediate local safety, weather alerts, or 
    major disruptions.
    For each relevant article, provide a 1-sentence summary.
    If no articles are relevant, just say "No relevant local safety news found."
    Format: [Headline]: [Your 1-sentence summary]
    Here are the articles:
    {articles_str}
    """
    try:
        response = llm_model.generate_content(prompt)
        print("[Agent 7] News analysis complete.")
        return response.text.strip()
    except Exception as e:
        print(f"[Agent 7] ERROR: {e}")
        return "Error analyzing news."


# --- 3. MASTER PIPELINE FUNCTION ---

def run_full_analysis(city_name: str) -> dict:
    """
    Runs the full agent pipeline for a given city and returns
    all data in a single dictionary.
    """
    print(f"--- RUNNING FULL ANALYSIS FOR: {city_name} ---")

    # Run pipeline
    weather_json = agent_1_weather_fetcher(city_name)
    forecast_json = agent_1_5_forecast_processor(city_name)

    if "error" in weather_json:
        return {"error": f"Failed to get weather: {weather_json['error']}"}

    risk_report = agent_2_risk_classifier(weather_json)
    recommendations = agent_3_action_recommender(risk_report)

    current_desc = risk_report['details']['description']
    raw_articles = agent_6_news_fetcher(city_name, current_desc)
    analyzed_news = agent_7_news_analyzer(raw_articles)

    # Compile all data into one clean object
    all_data = {
        "city": city_name,
        "risk_report": risk_report,
        "recommendations": recommendations,
        "analyzed_news": analyzed_news,
        "raw_data": weather_json,
        "forecast_data": forecast_json
    }

    print(f"--- ANALYSIS COMPLETE FOR: {city_name} ---")
    return all_data