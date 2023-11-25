import pymysql
import pickle
import xgboost as xgb
import numpy as np
import pandas as pd
import time
import warnings
from datetime import datetime
import joblib
import random
import time


# 경고 숨기기
warnings.filterwarnings(action='ignore', category=UserWarning, module='xgboost')
warnings.filterwarnings("ignore", message="X does not have valid feature names, but StandardScaler was fitted with feature names")

# 현재 시간 가져오기
current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


## 랜덤데이터 생성


def generate_rul_data_rows():
    multi_rows = []
    rul_rows = []

    rul_fl = random.randint(300, 500)
    rul_pb = random.randint(300, 500)
    rul_ph = random.randint(300, 500)

    decrement_fl = random.randint(1, 20)
    decrement_pb = random.randint(1, 20)
    decrement_ph = random.randint(1, 20)

    for _ in range(1000):
        fl_value = 1 if 0 < rul_fl <= 100 else 0
        pb_value = 1 if 0 < rul_pb <= 100 else 0
        ph_value = 1 if 0 < rul_ph <= 100 else 0

        multi_row = (fl_value, pb_value, ph_value)
        multi_rows.append(multi_row)
        rul_row = (rul_fl, rul_pb, rul_ph)
        rul_rows.append(rul_row)

        rul_fl -= decrement_fl
        rul_pb -= decrement_pb
        rul_ph -= decrement_ph

        if rul_fl <= 0:
            rul_fl = random.randint(300, 500)
            decrement_fl = random.randint(1, 20)
        if rul_pb <= 0:
            rul_pb = random.randint(300, 500)
            decrement_pb = random.randint(1, 20)
        if rul_ph <= 0:
            rul_ph = random.randint(300, 500)
            decrement_ph = random.randint(1, 20)

    return multi_rows,rul_rows

def generate_multi_data_rows():
    data_rows = []

    for _ in range(1000):
        data_row = (generate_random_data(), generate_random_data(), generate_random_data())
        data_rows.append(data_row)

    return data_rows

def generate_random_data(prob=0.5):
    return 1 if random.random() < prob else 0


########################################################################################################################################
########################################################################################################################################
########################################################################################################################################

### 데이터 밀어 넣기

def insert_single_data(connection, single_data):
    try:
        with connection.cursor() as cursor:
            # 현재 시간 가져오기
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # 데이터 삽입 SQL.
            sql = f'''INSERT INTO input_data_1 (time, Tool, stage, Lot, runnum, recipe, recipe_step,
       IONGAUGEPRESSURE, ETCHBEAMVOLTAGE, ETCHBEAMCURRENT,
       ETCHSUPPRESSORVOLTAGE, ETCHSUPPRESSORCURRENT, FLOWCOOLFLOWRATE,
       FLOWCOOLPRESSURE, ETCHGASCHANNEL1READBACK, ETCHPBNGASREADBACK,
       FIXTURETILTANGLE, ROTATIONSPEED, ACTUALROTATIONANGLE,
       FIXTURESHUTTERPOSITION, ETCHSOURCEUSAGE, ETCHAUXSOURCETIMER,
       ETCHAUX2SOURCETIMER, ACTUALSTEPDURATION, input_time) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "{current_time}")'''
            cursor.execute(sql, single_data)
        connection.commit()
    except Exception as e:
        print(f"Error while inserting data: {e}")
        connection.rollback()
    return current_time

def insert_single_rul_data(connection, data, current_time):
    try:
        with connection.cursor() as cursor:
            # 데이터 삽입 SQL.
            sql = f'''INSERT INTO rul_1(rul_fl, rul_pb, rul_ph, input_time) 
                      VALUES (%s, %s, %s, "{current_time}")'''
            cursor.execute(sql, (data[0], data[1], data[2]))
        connection.commit()
    except Exception as e:
        print(f"Error while inserting data: {e}")
        connection.rollback()

def insert_single_multi_data(connection, data, current_time):
    try:
        with connection.cursor() as cursor:
            # 데이터 삽입 SQL.
            sql = f'''INSERT INTO multi_1(multi_pred_fl, multi_pred_pb, multi_pred_ph, input_time) 
                      VALUES (%s, %s, %s, "{current_time}")'''
            cursor.execute(sql, (data[0], data[1], data[2]))
        connection.commit()
    except Exception as e:
        print(f"Error while inserting data: {e}")
        connection.rollback()




def main():
    # 데이터베이스 연결 설정

    connection = pymysql.connect(host='limemoni-2.cfcq69qzg7mu.ap-northeast-1.rds.amazonaws.com',  # DB 주소
                                 user='oneday',  # DB 유저명
                                 password='1234',  # 비밀번호
                                 db='j6database',  # 사용할 DB 이름
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)
    
    # CSV 파일 읽기
    df = pd.read_csv("./model_data_input/test.csv")

    ## 데이터 생성

    multi_data,rul_data = generate_rul_data_rows()
    # multi_data = generate_multi_data_rows()

    ## 길이 기준
    # DataFrame에서 튜플 리스트로 데이터 변환
    data_tuples = list(df.itertuples(index=False, name=None))


    ## 데이터를 한줄 씩 밀어넣으면서 진행하는 방식

    for i in range(len(data_tuples)):
        try:
            start_time = time.time()
            current_time = insert_single_data(connection, data_tuples[i])

            insert_single_rul_data(connection, rul_data[i], current_time)
            insert_single_multi_data(connection, multi_data[i], current_time)


            elapsed_time = time.time() - start_time  # 루프 실행 시간 계산
            sleep_time = max(4 - elapsed_time, 0)  # 음수가 되지 않도록 최소값을 0으로 설정
            time.sleep(sleep_time)  # 조절된 sleep 시간만큼 대기


        except Exception as e:
            print(f"Error: {e}")

            
    
    # 연결 종료
    connection.close()    

  
  



if __name__ == "__main__":
    main()