import os
import json
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from azure.storage.filedatalake import DataLakeServiceClient
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("AVIATIONSTACK_API_KEY", "mock_key")
AZURE_CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING")
CONTAINER_NAME = "landing-zone"

ORIGINS = [
    {"iata": "GRU", "name": "Guarulhos International", "airline": "LATAM Airlines"},
    {"iata": "SCL", "name": "Arturo Merino Benítez", "airline": "SKY Airline"},
    {"iata": "MIA", "name": "Miami International", "airline": "American Airlines"},
    {"iata": "MAD", "name": "Adolfo Suárez Madrid-Barajas", "airline": "Iberia"},
    {"iata": "COR", "name": "Ingeniero Ambrosio Taravella", "airline": "Aerolineas Argentinas"},
    {"iata": "BRC", "name": "San Carlos de Bariloche", "airline": "Flybondi"},
    {"iata": "MDZ", "name": "El Plumerillo", "airline": "JetSMART"},
    {"iata": "RIO", "name": "Galeao Antonio Carlos Jobim", "airline": "Gol Transportes Aereos"},
    {"iata": "IGR", "name": "Cataratas del Iguazú", "airline": "Aerolineas Argentinas"},
    {"iata": "USH", "name": "Malvinas Argentinas", "airline": "Aerolineas Argentinas"}
]

def generate_mock_flights(airport_code, now_local):
    """Genera un volumen alto de vuelos de llegada simulando la estructura de Aviationstack,
       evolucionando sus estados (CDC) según la hora del día."""
    flights = []
    random.seed(now_local.hour + now_local.day)
    
    num_flights = 45
    
    for i in range(1, num_flights + 1):
        origin = random.choice(ORIGINS)
        flight_num = f"{random.randint(100, 999)} "
        
        flight_hour = (i * 2) % 24
        if flight_hour < now_local.hour:
            status = random.choices(["landed", "cancelled"], weights=[90, 10])[0]
        elif flight_hour == now_local.hour:
            status = random.choices(["active", "delayed"], weights=[75, 25])[0]
        else:
            status = "scheduled"

        flight_record = {
            "flight_date": now_local.strftime("%Y-%m-%d"),
            "flight_status": status,
            "departure": {
                "airport": origin["name"],
                "timezone": "America/Sao_Paulo",
                "iata": origin["iata"]
            },
            "arrival": {
                "airport": "Ministro Pistarini" if airport_code == "EZE" else "Aeroparque Jorge Newbery",
                "timezone": "America/Argentina/Buenos_Aires",
                "iata": airport_code
            },
            "airline": {
                "name": origin["airline"]
            },
            "flight": {
                "number": str(random.randint(1000, 9999)),
                "iata": f"AR{random.randint(1000, 9999)}"
            }
        }
        flights.append(flight_record)
        
    return flights

def upload_to_adls(data, folder_path, file_name):
    """Sube el JSON simulado a Azure Data Lake."""
    service_client = DataLakeServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    file_system_client = service_client.get_file_system_client(file_system=CONTAINER_NAME)
    
    directory_client = file_system_client.get_directory_client(folder_path)
    if not directory_client.exists():
        directory_client.create_directory()
        
    file_client = directory_client.get_file_client(file_name)
    json_data = json.dumps(data, indent=2)
    file_client.upload_data(json_data, overwrite=True)
    print(f"Archivo guardado en: {folder_path}/{file_name}")

def main():
    tz = ZoneInfo("America/Argentina/Cordoba")
    now_local = datetime.now(tz)
    
    flights_eze = generate_mock_flights("EZE", now_local)
    flights_aep = generate_mock_flights("AEP", now_local)
    all_flights = flights_eze + flights_aep
    
    year = now_local.strftime("%Y")
    month = now_local.strftime("%m")
    day = now_local.strftime("%d")
    hour = now_local.strftime("%H") 
    
    folder_path = f"raw/hourly_tracking/{year}/{month}/{day}/{hour}"
    file_name = f"flights_{now_local.strftime('%H%M%S')}.json"
    
    upload_to_adls(all_flights, folder_path, file_name)

if __name__ == "__main__":
    main()
