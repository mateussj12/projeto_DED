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

