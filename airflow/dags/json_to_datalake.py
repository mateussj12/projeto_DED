import os
import json
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

# Diretório base do data lake
DATA_LAKE_PATH = "/opt/airflow/data_lake"

# Mapeamento dinâmico para transformação de chaves
KEY_MAPPING = {
    "taxes": "taxation",  # Exemplo: renomeia "taxes" para "taxation"
    # Adicione outros mapeamentos conforme necessário
}


# Função de transformação para ajustar chaves no JSON
def transform_json(json_data, key_mapping):
    """
    Transforma o JSON substituindo as chaves de acordo com o mapeamento.
    """
    if isinstance(json_data, dict):
        transformed_data = {}
        for key, value in json_data.items():
            # Substituir chave conforme o mapeamento
            new_key = key_mapping.get(key, key)
            # Aplicar recursivamente para valores que sejam dicionários ou listas
            transformed_data[new_key] = transform_json(value, key_mapping)
        return transformed_data
    elif isinstance(json_data, list):
        return [transform_json(item, key_mapping) for item in json_data]
    else:
        return json_data


# Função para salvar os dados no data lake
def save_to_datalake(endpoint, store_id, bus_dt, json_data):
    """
    Salva o JSON transformado no data lake em um diretório organizado.
    """
    # Criar o diretório baseado no endpoint, store_id e bus_dt
    output_dir = os.path.join(DATA_LAKE_PATH, "api_responses", endpoint, f"storeId={store_id}", f"busDt={bus_dt}")
    os.makedirs(output_dir, exist_ok=True)

    # Caminho do arquivo JSON
    output_file = os.path.join(output_dir, "response.json")
    
    # Salvar o arquivo JSON no formato apropriado
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=4, ensure_ascii=False)

    print(f"Dados salvos em {output_file}")


# Função para processar um arquivo JSON dinâmico
def process_json_file(file_path, endpoint, **kwargs):
    """
    Lê o arquivo JSON, aplica transformação e salva no data lake.
    """
    # Ler o JSON do arquivo
    with open(file_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)
    
    # Parâmetros dinâmicos do JSON (ajuste as chaves conforme necessário)
    for guest_check in json_data.get("guestChecks", []):
        store_id = json_data.get("locRef", "unknown_store")  # Ajustar conforme o JSON
        for detail in guest_check.get("detailLines", []):
            bus_dt = detail.get("busDt", "unknown_date")  # Pegar o busDt dentro de detailLines

            # Aplicar transformação no JSON
            transformed_data = transform_json(json_data, KEY_MAPPING)

            # Salvar no data lake
            save_to_datalake("getGuestChecks", store_id, bus_dt, transformed_data)


# Configuração da DAG
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
}
with DAG(
    "json_to_datalake",
    default_args=default_args,
    description="Processa JSON dinâmico com transformação e salva no data lake",
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    
    # Exemplo de caminho de um arquivo JSON dinâmico
    json_file_path = "/opt/airflow/config/ERP.json"

    # Operador Python para processar o arquivo JSON
    process_json = PythonOperator(
        task_id="process_json_file",
        python_callable=process_json_file,
        op_kwargs={
            "file_path": json_file_path,
            "endpoint": "getGuestChecks",  # Ajuste dinamicamente conforme o endpoint
        },
    )

    process_json
