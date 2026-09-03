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

def generate_consistent_flights(airport_code, target_date_str, current_local_hour):
    """
    Genera la grilla de vuelos para un día objetivo de forma consistente.
    Usa la fecha como semilla para que los vuelos sean siempre los mismos,
    pero evalúa la hora actual para actualizar sus estados y demoras de forma realista.
    """
    # Semilla fija basada en la fecha (ej: "2026-09-04-EZE") para mantener la misma flota todo el día
    seed_string = f"{target_date_str}-{airport_code}"
    random.seed(seed_string)
    
    flights = []
    num_flights = 40  # Volumen robusto para procesar en Databricks
    
    for i in range(1, num_flights + 1):
        origin = random.choice(ORIGINS)
        
        # Asignamos una hora de llegada fija a cada vuelo distribuida en el día (00 a 23 hs)
        scheduled_hour = (i * 3) % 24
        scheduled_minute = (i * 17) % 60
        
        # Armar strings de horario ISO
        sched_time_str = f"{target_date_str}T{scheduled_hour:02d}:{scheduled_minute:02d}:00+00:00"
        
        # Lógica de CDC (Evolución de estado según el tiempo transcurrido)
        estimated_time_str = sched_time_str
        actual_time_str = None
        
        if current_local_hour < scheduled_hour:
            # El vuelo todavía no pasó: su estado es programado
            status = "scheduled"
            
        elif current_local_hour == scheduled_hour:
            # El vuelo está en la franja horaria actual: puede estar activo o sufrir una demora
            status = random.choices(["active", "delayed"], weights=[70, 30])[0]
            if status == "delayed":
                # Si se demora, sumamos 45 minutos al estimado
                estimated_time_str = f"{target_date_str}T{scheduled_hour:02d}:{(scheduled_minute+45)%60:02d}:00+00:00"
        else:
            # El vuelo ya pasó de su hora programada: ya aterrizó o fue cancelado
            status = random.choices(["landed", "cancelled"], weights=[92, 8])[0]
            if status == "landed":
                actual_time_str = sched_time_str

        flight_record = {
            "flight_date": target_date_str,
            "flight_status": status,
            "departure": {
                "airport": origin["name"],
                "timezone": "America/Sao_Paulo",
                "iata": origin["iata"],
                "scheduled": f"{target_date_str}T{(scheduled_hour-2)%24:02d}:{scheduled_minute:02d}:00+00:00",
                "estimated": f"{target_date_str}T{(scheduled_hour-2)%24:02d}:{scheduled_minute:02d}:00+00:00"
            },
            "arrival": {
                "airport": "Ministro Pistarini" if airport_code == "EZE" else "Aeroparque Jorge Newbery",
                "timezone": "America/Argentina/Buenos_Aires",
                "iata": airport_code,
                "scheduled": sched_time_str,
                "estimated": estimated_time_str,
                "actual": actual_time_str,
                "terminal": "A" if airport_code == "EZE" else "B",
                "gate": str(random.randint(1, 15))
            },
            "airline": {
                "name": origin["airline"]
            },
            "flight": {
                "number": str(1000 + i),
                "iata": f"AR{2000 + i}"
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
    current_hour = now_local.hour
    
    # ---------------------------------------------------------
    # REGLA DE NEGOCIO SOLICITADA:
    # A partir de las 18:00 hs, empezamos a capturar el cronograma 
    # oficial del DÍA SIGUIENTE. Antes de las 00:00 y durante todo 
    # el día siguiente, hacemos el tracking de ese mismo día.
    # ---------------------------------------------------------
    if current_hour >= 18:
        target_date_obj = now_local + timedelta(days=1)
    else:
        target_date_obj = now_local
        
    target_date_str = target_date_obj.strftime("%Y-%m-%d")
    
    # Generar la grilla consistente evaluando la hora actual del ciclo
    flights_eze = generate_consistent_flights("EZE", target_date_str, current_hour)
    flights_aep = generate_consistent_flights("AEP", target_date_str, current_hour)
    all_flights = flights_eze + flights_aep
    
    # Particionamiento estructurado en la carpeta del día objetivo y hora de corrida
    year = target_date_obj.strftime("%Y")
    month = target_date_obj.strftime("%m")
    day = target_date_obj.strftime("%d")
    hour_str = now_local.strftime("%H") 
    
    folder_path = f"raw/hourly_tracking/{year}/{month}/{day}/{hour_str}"
    file_name = f"flights_{now_local.strftime('%H%M%S')}.json"
    
    upload_to_adls(all_flights, folder_path, file_name)

if __name__ == "__main__":
    main()
