import os
import json
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from azure.storage.filedatalake import DataLakeServiceClient
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("AVIATIONSTACK_API_KEY")
AZURE_CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING")
CONTAINER_NAME = "landing-zone"

def get_flights(airport_code, target_date):
    """Obtiene TODOS los vuelos (sin filtrar estado) para capturar demoras y cancelaciones."""
 
    url = f"http://api.aviationstack.com/v1/flights?access_key={API_KEY}&arr_iata={airport_code}&flight_date={target_date}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get('data', [])
    return []

def upload_to_adls(data, folder_path, file_name):
    """Sube el JSON a Azure Data Lake."""
    service_client = DataLakeServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    file_system_client = service_client.get_file_system_client(file_system=CONTAINER_NAME)
    
    directory_client = file_system_client.get_directory_client(folder_path)
    if not directory_client.exists():
        directory_client.create_directory()
        
    file_client = directory_client.get_file_client(file_name)
    json_data = json.dumps(data)
    file_client.upload_data(json_data, overwrite=True)
    print(f"Archivo guardado en: {folder_path}/{file_name}")

def main():

    tz = ZoneInfo("America/Argentina/Cordoba")
    now_local = datetime.now(tz)
    current_hour = now_local.hour
    

    today_str = now_local.strftime("%Y-%m-%d")
    
    flights_eze_today = get_flights("EZE", today_str)
    flights_aep_today = get_flights("AEP", today_str)
    all_flights_today = flights_eze_today + flights_aep_today
    
    year_t = now_local.strftime("%Y")
    month_t = now_local.strftime("%m")
    day_t = now_local.strftime("%d")
    hour_str = now_local.strftime("%H") 
    
    folder_path_today = f"raw/hourly_tracking/{year_t}/{month_t}/{day_t}/{hour_str}"
    file_name_today = f"flights_{now_local.strftime('%H%M%S')}.json"
    
    upload_to_adls(all_flights_today, folder_path_today, file_name_today)


    if current_hour == 18:
        tomorrow = now_local + timedelta(days=1)
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")
        
        flights_eze_tom = get_flights("EZE", tomorrow_str)
        flights_aep_tom = get_flights("AEP", tomorrow_str)
        all_flights_tom = flights_eze_tom + flights_aep_tom
        
        year_tm = tomorrow.strftime("%Y")
        month_tm = tomorrow.strftime("%m")
        day_tm = tomorrow.strftime("%d")
        
        folder_path_tom = f"raw/hourly_tracking/{year_tm}/{month_tm}/{day_tm}/baseline_18hs"
        file_name_tom = "flights_baseline.json"
        
        upload_to_adls(all_flights_tom, folder_path_tom, file_name_tom)

if __name__ == "__main__":
    main()
