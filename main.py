import os
import json
import requests
from datetime import datetime, timedelta
from azure.storage.filedatalake import DataLakeServiceClient
from dotenv import load_dotenv

load_dotenv()

# Variables de entorno (Configuradas en GitHub Secrets)
API_KEY = os.getenv("AVIATIONSTACK_API_KEY")
AZURE_CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING")
CONTAINER_NAME = "landing-zone"

def get_flights(airport_code):
    """Obtiene los vuelos de un aeropuerto específico."""
    url = f"http://api.aviationstack.com/v1/flights?access_key={API_KEY}&arr_iata={airport_code}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get('data', [])
    return []

def upload_to_adls(data, folder_path, file_name):
    """Sube el JSON a Azure Data Lake."""
    service_client = DataLakeServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    file_system_client = service_client.get_file_system_client(file_system=CONTAINER_NAME)
    
    # Crear ruta de directorio
    directory_client = file_system_client.get_directory_client(folder_path)
    if not directory_client.exists():
        directory_client.create_directory()
        
    # Crear archivo y subir datos
    file_client = directory_client.get_file_client(file_name)
    json_data = json.dumps(data)
    file_client.upload_data(json_data, overwrite=True)
    print(f"Archivo guardado en: {folder_path}/{file_name}")

def main():
    # Obtener datos de EZE y AEP
    flights_eze = get_flights("EZE")
    flights_aep = get_flights("AEP")
    all_flights = flights_eze + flights_aep
    
    # Mañana (para planificar la flota)
    tomorrow = datetime.now() + timedelta(days=1)
    year, month, day = tomorrow.strftime("%Y"), tomorrow.strftime("%m"), tomorrow.strftime("%d")
    
    # Subir a la ruta particionada
    folder_path = f"raw/daily_schedule/{year}/{month}/{day}"
    upload_to_adls(all_flights, folder_path, "schedule.json")

if __name__ == "__main__":
    main()