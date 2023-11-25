import pymysql
import pickle
import xgboost as xgb
import numpy as np
import pandas as pd
import time
import warnings
from datetime import datetime

# XGBoost 관련 경고 숨기기
warnings.filterwarnings(action='ignore', category=UserWarning, module='xgboost')

# 현재 시간 가져오기
current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

## 길이 기준 설정
avg_len = 500

def fetch_recent_logs(length=avg_len):
    """mysql db에서 최근 로그를 가져오는 함수"""
    # mysql 데이터베이스에 연결
    # connection = pymysql.connect(host='127.0.0.1',  # DB 주소
    #                              user='root',  # DB 유저명
    #                              password='sejong131!#!',  # 비밀번호
    #                              db='ion',  # 사용할 DB 이름
    #                              charset='utf8mb4',
    #                              cursorclass=pymysql.cursors.DictCursor)
    connection = pymysql.connect(host='limemoni-2.cfcq69qzg7mu.ap-northeast-1.rds.amazonaws.com',  # DB 주소
                                 user='oneday',  # DB 유저명
                                 password='1234',  # 비밀번호
                                 db='j6database',  # 사용할 DB 이름
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)
    try:
        with connection.cursor() as cursor:
            # 가장 최근의 데이터부터 지정한 길이만큼 가져오는 SQL 쿼리
            sql = f'''SELECT IONGAUGEPRESSURE, ETCHBEAMVOLTAGE, ETCHBEAMCURRENT, ETCHSUPPRESSORVOLTAGE, ETCHSUPPRESSORCURRENT,
            FLOWCOOLFLOWRATE, FLOWCOOLPRESSURE, ETCHGASCHANNEL1READBACK, ETCHPBNGASREADBACK,
            FIXTURETILTANGLE, ROTATIONSPEED, ACTUALROTATIONANGLE,
            ETCHSOURCEUSAGE, ETCHAUXSOURCETIMER, ETCHAUX2SOURCETIMER,
            ACTUALSTEPDURATION FROM input_data ORDER BY input_time DESC LIMIT {length}'''
            cursor.execute(sql)
            results = cursor.fetchall()
    finally:
        connection.close()

    return results

def fetch_recent_logs_for_multi(length=avg_len):
    """mysql db에서 최근 로그를 가져오는 함수"""
    # mysql 데이터베이스에 연결
    # connection = pymysql.connect(host='127.0.0.1',  # DB 주소
    #                              user='root',  # DB 유저명
    #                              password='sejong131!#!',  # 비밀번호
    #                              db='ion',  # 사용할 DB 이름
    #                              charset='utf8mb4',
    #                              cursorclass=pymysql.cursors.DictCursor)
    connection = pymysql.connect(host='limemoni-2.cfcq69qzg7mu.ap-northeast-1.rds.amazonaws.com',  # DB 주소
                                 user='oneday',  # DB 유저명
                                 password='1234',  # 비밀번호
                                 db='j6database',  # 사용할 DB 이름
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)
    try:
        with connection.cursor() as cursor:
            # 가장 최근의 데이터부터 지정한 길이만큼 가져오는 SQL 쿼리
            sql = f'''SELECT ACTUALROTATIONANGLE, ACTUALSTEPDURATION, ETCHBEAMCURRENT, ETCHGASCHANNEL1READBACK, 
              ETCHPBNGASREADBACK, ETCHSOURCEUSAGE, FIXTURETILTANGLE, FLOWCOOLFLOWRATE, FLOWCOOLPRESSURE, 
              IONGAUGEPRESSURE FROM input_data ORDER BY input_time DESC LIMIT {length}'''
            cursor.execute(sql)
            results = cursor.fetchall()
    finally:
        connection.close()

    return results

def dict_to_array(data):
    """사전 형태의 데이터를 2차원 넘파이 배열로 변환하는 함수"""
    return np.array([list(item.values()) for item in data])


def predict_with_xgb_model(data):
    """xgboost 모델을 사용해 예측하는 함수"""
    # 데이터 형태 변환
    transformed_data = dict_to_array(data)

    """xgboost 모델을 사용해 예측하는 함수"""
    # 모델 불러오기
    with open('./model_data_input/xgboost_model.pkl', 'rb') as f:
        model = pickle.load(f)

    # 예측 실행
    predictions = model.predict(transformed_data)

    return predictions

def predict_with_xgb_multi_model(data):
    """xgboost 다중분류 모델을 사용해 예측하는 함수"""
    # 데이터 형태 변환
    transformed_data = dict_to_array(data)

    """xgboost 모델을 사용해 예측하는 함수"""
    # 모델 불러오기
    with open('./model_data_input/xgboost_multi_model.pkl', 'rb') as f:
        model = pickle.load(f)

    # 예측 실행
    predictions = model.predict(transformed_data)

    return predictions

def compute_moving_average(data, window_size=avg_len):
    """이동평균 계산하는 함수"""
    return np.convolve(data, np.ones(window_size)/window_size, mode='valid')

import numpy as np

def compute_moving_median(data, window_size):
    """이동 중앙값 계산하는 함수"""
    num_data = len(data)
    medians = []

    for i in range(num_data - window_size + 1):
        window_data = data[i:i+window_size]
        medians.append(np.median(window_data))

    return np.array(medians)

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
            sql = f'''INSERT INTO input_data (time, Tool, stage, Lot, runnum, recipe, recipe_step,
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

def insert_single_rul_data(connection, single_data, current_time):
    try:
        with connection.cursor() as cursor:
            # 현재 시간 가져오기
            current_time = current_time
            
            # 데이터 삽입 SQL.
            sql = f'''INSERT INTO rul(rul_time,input_time) VALUES (%s,"{current_time}")'''
            cursor.execute(sql, single_data)
        connection.commit()
    except Exception as e:
        print(f"Error while inserting data: {e}")
        connection.rollback()

def insert_single_multi_data(connection, single_data, current_time):
    try:
        with connection.cursor() as cursor:
            # 현재 시간 가져오기
            current_time = current_time
            
            # 데이터 삽입 SQL.
            sql = f'''INSERT INTO multi(multi_pred,input_time) VALUES (%s,"{current_time}")'''
            cursor.execute(sql, single_data)
        connection.commit()
    except Exception as e:
        print(f"Error while inserting data: {e}")
        connection.rollback()




def main():
    # 데이터베이스 연결 설정
    # connection = pymysql.connect(host='127.0.0.1',  # DB 주소
    #                              user='root',  # DB 유저명
    #                              password='sejong131!#!',  # 비밀번호
    #                              db='ion',  # 사용할 DB 이름
    #                              charset='utf8mb4',
    #                              cursorclass=pymysql.cursors.DictCursor)
    connection = pymysql.connect(host='limemoni-2.cfcq69qzg7mu.ap-northeast-1.rds.amazonaws.com',  # DB 주소
                                 user='oneday',  # DB 유저명
                                 password='1234',  # 비밀번호
                                 db='j6database',  # 사용할 DB 이름
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)
    
    # CSV 파일 읽기
    df = pd.read_csv("./model_data_input/test.csv")

    # DataFrame에서 튜플 리스트로 데이터 변환
    data_tuples = list(df.itertuples(index=False, name=None))

    ## 데이터를 한줄 씩 밀어넣으면서 진행하는 방식

    for single_data in data_tuples:

        try:
            # 데이터 삽입
            current_time = insert_single_data(connection, single_data)

            data = fetch_recent_logs(length=avg_len)
            data_for_multi = fetch_recent_logs_for_multi(length=avg_len)
            
            # 가져온 데이터를 기반으로 예측하기
            predictions = predict_with_xgb_model(data)
            predictions_for_multi = predict_with_xgb_multi_model(data_for_multi)
            
            # 이동평균 계산하기
            window_size = min(avg_len, len(predictions))  # 데이터 수와 avg_len 중 작은 값을 창 크기로 사용
            moving_avg = compute_moving_average(predictions, window_size=window_size)
            window_size_for_multi = min(avg_len, len(predictions_for_multi))  # 데이터 수와 avg_len 중 작은 값을 창 크기로 사용
            moving_avg_for_multi = compute_moving_average(predictions_for_multi, window_size=window_size_for_multi)
            
            # print(moving_avg)  # 계산된 이동평균을 출력합니다. 필요에 따라 다른 처리를 할 수 있습니다.
            
            # rul 데이터 삽입
            insert_single_rul_data(connection, moving_avg[0], current_time)
            insert_single_multi_data(connection, predictions_for_multi[0], current_time)
            # print(f"Inserted a row from CSV.")
            time.sleep(4)  # 4초 대기

        except Exception as e:
            print(f"Error: {e}")
    
    # 연결 종료
    connection.close()    



if __name__ == "__main__":
    main()