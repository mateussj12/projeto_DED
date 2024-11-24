### README: Configuração do Airflow com Docker-Compose e Organização de Credenciais

Este guia detalha como configurar o Apache Airflow utilizando Docker Compose no Windows, mantendo as credenciais seguras em arquivos não versionados. Além disso, inclui instruções para armazenar dados em um Data Lake e um banco de dados PostgreSQL.

## **Visão Geral**
Com o Airflow, você pode criar, agendar e monitorar pipelines de dados. Este repositório foi configurado para:

1. Organizar dados em um Data Lake estruturado.
2. Armazenar credenciais sensíveis fora do controle de versão (Git).
3. Automatizar o processamento e carregamento de dados para o PostgreSQL.


## **Pré-requisitos**

Antes de começar, certifique-se de que você possui:

- **Docker Desktop** instalado e configurado no Windows.
- **Python 3.8+** instalado para possíveis scripts auxiliares.
- **Git** para versionamento de código (opcional).


## **1. Configurando o Airflow com Docker Compose**

### **1.1. Clone o repositório**
Clone este repositório em sua máquina local:
```bash
git clone https://github.com/mateussj12/projeto_DED-main.git
cd projeto_DED-main
```

### **1.2. Estrutura de diretórios**
Certifique-se de que o repositório tem a seguinte estrutura:
```
.
├── dags/                  # Contém as DAGs do Airflow
├── plugins/               # Plugins personalizados do Airflow
├── logs/                  # Logs gerados pelo Airflow
├── config/                # Pasta com arquivos de configuração
├── docker-compose.yaml    # Arquivo de configuração do Docker Compose
├── data_lake/             # Dados armazenados localmente
└── README.md              # Este arquivo
```

### **1.3. Configure o Docker Compose**
Certifique-se de que o arquivo `docker-compose.yaml` tem a seguinte configuração mínima para o Airflow:

```yaml
x-airflow-common:
  &airflow-common
  image: ${AIRFLOW_IMAGE_NAME:-apache/airflow:2.10.3}
  environment:
    &airflow-common-env
    AIRFLOW__CORE__EXECUTOR: CeleryExecutor
    AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres/airflow
    AIRFLOW__CELERY__RESULT_BACKEND: db+postgresql://airflow:airflow@postgres/airflow
    AIRFLOW__CELERY__BROKER_URL: redis://:@redis:6379/0
    AIRFLOW__CORE__FERNET_KEY: ''
    AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: 'true'
    AIRFLOW__CORE__LOAD_EXAMPLES: 'true'
    AIRFLOW__API__AUTH_BACKENDS: 'airflow.api.auth.backend.basic_auth,airflow.api.auth.backend.session'
    AIRFLOW__SCHEDULER__ENABLE_HEALTH_CHECK: 'true'
    _PIP_ADDITIONAL_REQUIREMENTS: ${_PIP_ADDITIONAL_REQUIREMENTS:-}
  volumes:
    - ${AIRFLOW_PROJ_DIR:-.}/dags:/opt/airflow/dags
    - ${AIRFLOW_PROJ_DIR:-.}/logs:/opt/airflow/logs
    - ${AIRFLOW_PROJ_DIR:-.}/config:/opt/airflow/config
    - ${AIRFLOW_PROJ_DIR:-.}/plugins:/opt/airflow/plugins
    - ${AIRFLOW_PROJ_DIR:-.}/data_lake:/opt/airflow/data_lake
  user: "${AIRFLOW_UID:-50000}:0"
  depends_on:
    &airflow-common-depends-on
    redis:
      condition: service_healthy
    postgres:
      condition: service_healthy
```

**Nota:** Todas as configurações são padrões conforme a documentação oficial: https://airflow.apache.org/docs/docker-stack/entrypoint.html#entrypoint-commands


## **2. Configurando Credenciais do Banco de Dados**

Para acessar o arquivo de configuração do banco de dados acesse esse link: https://drive.google.com/file/d/1jEhX4Eqj-tgv8N15pN27LaiXuDhOgR19/view?usp=sharing

Após solicitar o acesso poderá adicionar a pasta config/

Exemplo do arquivo `config.py`:
```python
DB_CONFIG = {
    "host": "localhost",
    "database": "database",
    "user": "username",
    "password": "password"
}
```


## **3. Executando o Ambiente no Docker**

### **3.1. Inicialize o ambiente do Airflow**
No terminal, execute os comandos a seguir para inicializar os serviços:
```bash
docker-compose up -d
```

### **3.2. Acesse o Airflow**
- Acesse a interface web do Airflow em [http://localhost:8080](http://localhost:8080).
- Usuário padrão: `airflow`
- Senha padrão: `airflow`


## **4. Integração das Credenciais no Código**

No código Python principal (`main.py`), importe o arquivo `db_config.py` para usar as credenciais:
```python
from db_config import DB_CONFIG

connection = psycopg2.connect(
    host=DB_CONFIG["host"],
    port=DB_CONFIG["port"],
    database=DB_CONFIG["database"],
    user=DB_CONFIG["user"],
    password=DB_CONFIG["password"]
)
```


## **5. Configurando e Salvando Dados no Data Lake**

### **5.1. Estrutura do Data Lake**
Os dados das APIs serão armazenados no seguinte formato:
```
/data_lake/
    └── api_responses/
        ├── getFiscalInvoice/
        ├── getGuestChecks/
        │   ├── storeId=99 CB CB/
        │   │   ├── busDt=2024-11-01/
        │   │   │   ├── response.json
        │   │   ├── busDt=2024-11-02/
        │   │       ├── response.json
        ├── getChargeBack/
        ├── getTransactions/
        ├── getCashManagementDetails/
```


### **5.2. Código para salvar no Data Lake**
No Airflow, uma DAG processa os arquivos JSON para estruturar e salvar os dados no Data Lake.
Exemplo de função Python utilizada:
```python
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
```


## **6. Configurando e Salvando Dados no PostgreSQL**

### **6.1. Código SQL para criar as tabelas**
**Tabela 1:** guestChecks
```sql
CREATE TABLE guestChecks (
    guestCheckId BIGINT PRIMARY KEY,
    chkNum INT,
    opnBusDt DATE,
    opnUTC TIMESTAMP,
    opnLcl TIMESTAMP,
    clsdBusDt DATE,
    clsdUTC TIMESTAMP,
    clsdLcl TIMESTAMP,
    lastTransUTC TIMESTAMP,
    lastTransLcl TIMESTAMP,
    lastUpdatedUTC TIMESTAMP,
    lastUpdatedLcl TIMESTAMP,
    clsdFlag BOOLEAN,
    gstCnt INT,
    subTtl DECIMAL(10, 2),
    nonTxblSlsTtl DECIMAL(10, 2),
    chkTtl DECIMAL(10, 2),
    dscTtl DECIMAL(10, 2),
    payTtl DECIMAL(10, 2),
    balDueTtl DECIMAL(10, 2),
    rvcNum INT,
    otNum INT,
    ocNum INT,
    tblNum INT,
    tblName VARCHAR(50),
    empNum BIGINT,
    numSrvcRd INT,
    numChkPrntd INT
);
```

**Tabela 2:** taxes
```sql
CREATE TABLE taxes (
    taxId SERIAL PRIMARY KEY,
    guestCheckId BIGINT REFERENCES guestChecks(guestCheckId),
    taxNum INT,
    txblSlsTtl DECIMAL(10, 2),
    taxCollTtl DECIMAL(10, 2),
    taxRate DECIMAL(5, 2),
    type INT
);
```

**Tabela 3:** detailLines
```sql
CREATE TABLE detailLines (
    guestCheckLineItemId BIGINT PRIMARY KEY,
    guestCheckId BIGINT REFERENCES guestChecks(guestCheckId),
    rvcNum INT,
    dtlOtNum INT,
    dtlOcNum INT,
    lineNum INT,
    dtlId INT,
    detailUTC TIMESTAMP,
    detailLcl TIMESTAMP,
    lastUpdateUTC TIMESTAMP,
    lastUpdateLcl TIMESTAMP,
    busDt DATE,
    wsNum INT,
    dspTtl DECIMAL(10, 2),
    dspQty INT,
    aggTtl DECIMAL(10, 2),
    aggQty INT,
    chkEmpId BIGINT,
    chkEmpNum INT,
    svcRndNum INT,
    seatNum INT
);
```

**Tabela 4:** menuItem
```sql
CREATE TABLE menuItem (
    miNum INT PRIMARY KEY,
    guestCheckLineItemId BIGINT REFERENCES detailLines(guestCheckLineItemId),
    modFlag BOOLEAN,
    inclTax DECIMAL(10, 6),
    activeTaxes VARCHAR(50),
    prcLvl INT
);
```

### **6.2. Código para salvar no banco de dados PostgreSQL**
Exemplo de função Python para carregar dados no PostgreSQL:
```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from db_config import DB_CONFIG
import psycopg2
import json

def process_and_load_json(**kwargs):
    # Caminho para o arquivo JSON
    json_file = "/opt/airflow/config/ERP.json"
    
    # Leitura do JSON
    with open(json_file, 'r') as f:
        data = json.load(f)

    # Processa os guestChecks e os insere no banco
    connection = psycopg2.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"]
     )
    cursor = connection.cursor()

    for guest_check in data['guestChecks']:
        # Inserção na tabela guestChecks
        cursor.execute("""
            INSERT INTO guestChecks (
                guestCheckId, chkNum, opnBusDt, opnUTC, opnLcl, clsdBusDt, clsdUTC, clsdLcl, 
                lastTransUTC, lastTransLcl, lastUpdatedUTC, lastUpdatedLcl, clsdFlag, 
                gstCnt, subTtl, nonTxblSlsTtl, chkTtl, dscTtl, payTtl, balDueTtl, rvcNum, 
                otNum, ocNum, tblNum, tblName, empNum, numSrvcRd, numChkPrntd
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            guest_check['guestCheckId'],
            guest_check['chkNum'],
            guest_check['opnBusDt'],
            guest_check['opnUTC'],
            guest_check['opnLcl'],
            guest_check['clsdBusDt'],
            guest_check['clsdUTC'],
            guest_check['clsdLcl'],
            guest_check['lastTransUTC'],
            guest_check['lastTransLcl'],
            guest_check['lastUpdatedUTC'],
            guest_check['lastUpdatedLcl'],
            guest_check['clsdFlag'],
            guest_check['gstCnt'],
            guest_check['subTtl'],
            guest_check.get('nonTxblSlsTtl'),  # Pode ser null
            guest_check['chkTtl'],
            guest_check['dscTtl'],
            guest_check['payTtl'],
            guest_check.get('balDueTtl'),  # Pode ser null
            guest_check['rvcNum'],
            guest_check['otNum'],
            guest_check.get('ocNum'),  # Pode ser null
            guest_check['tblNum'],
            guest_check['tblName'],
            guest_check['empNum'],
            guest_check['numSrvcRd'],
            guest_check['numChkPrntd']
        ))

        # Inserção na tabela taxes
        for tax in guest_check.get('taxes', []):
            cursor.execute("""
                INSERT INTO taxes (
                    guestCheckId, taxNum, txblSlsTtl, taxCollTtl, taxRate, type
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                guest_check['guestCheckId'],
                tax['taxNum'],
                tax['txblSlsTtl'],
                tax['taxCollTtl'],
                tax['taxRate'],
                tax['type']
            ))

        # Inserção na tabela detailLines
        for detail in guest_check.get('detailLines', []):
            cursor.execute("""
                INSERT INTO detailLines (
                    guestCheckLineItemId, guestCheckId, rvcNum, dtlOtNum, dtlOcNum, lineNum, 
                    dtlId, detailUTC, detailLcl, lastUpdateUTC, lastUpdateLcl, busDt, wsNum, 
                    dspTtl, dspQty, aggTtl, aggQty, chkEmpId, chkEmpNum, svcRndNum, seatNum
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                        %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                detail['guestCheckLineItemId'],
                guest_check['guestCheckId'],
                detail['rvcNum'],
                detail['dtlOtNum'],
                detail.get('dtlOcNum'),  # Pode ser null
                detail['lineNum'],
                detail['dtlId'],
                detail['detailUTC'],
                detail['detailLcl'],
                detail['lastUpdateUTC'],
                detail['lastUpdateLcl'],
                detail['busDt'],
                detail['wsNum'],
                detail['dspTtl'],
                detail['dspQty'],
                detail['aggTtl'],
                detail['aggQty'],
                detail['chkEmpId'],
                detail['chkEmpNum'],
                detail['svcRndNum'],
                detail['seatNum']
            ))

            # Inserção na tabela menuItem
            if 'menuItem' in detail:
                menu_item = detail['menuItem']
                cursor.execute("""
                    INSERT INTO menuItem (
                        miNum, guestCheckLineItemId, modFlag, inclTax, activeTaxes, prcLvl
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    menu_item['miNum'],
                    detail['guestCheckLineItemId'],
                    menu_item['modFlag'],
                    menu_item['inclTax'],
                    menu_item['activeTaxes'],
                    menu_item['prcLvl']
                ))


    connection.commit()
    cursor.close()
    connection.close()

# Definição da DAG
with DAG(
    'json_to_postgres',
    default_args={
        'owner': 'airflow',
        'start_date': datetime(2024, 1, 1),
    },
    schedule_interval=None,
) as dag:
    load_json_task = PythonOperator(
        task_id='process_and_load_json',
        python_callable=process_and_load_json,
    )
```


## **7. Conclusão**

Agora você tem um ambiente configurado para usar o Airflow com Docker Compose, armazenar credenciais de forma segura, organizar dados no Data Lake e no banco de dados postgresql. 

Siga estas etapas para manter o sistema seguro e funcional:

1. **Não compartilhe o arquivo `db_config.py`.**
2. **Utilize variáveis de ambiente para maior segurança (opcional).**
3. **Monitore o Airflow regularmente para garantir a execução correta das DAGs.**
