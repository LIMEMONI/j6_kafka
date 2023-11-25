import pymysql
import pickle
import xgboost as xgb
import numpy as np
import pandas as pd
import time
import warnings
from datetime import datetime
import joblib
from keras.models import load_model
import os
import threading



# 테이블 변수
input_data = 'input_data_1'
rul = 'rul_1'
multi = 'multi_1'
file = 'file_1'

# 경고 숨기기
warnings.filterwarnings(action='ignore', category=UserWarning, module='xgboost')
warnings.filterwarnings("ignore", message="X does not have valid feature names, but StandardScaler was fitted with feature names")

# 현재 시간 가져오기
import pytz
seoul_timezone = pytz.timezone('Asia/Seoul')
current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
# current_time = datetime.now(seoul_timezone).strftime('%Y-%m-%d %H:%M:%S')

## 길이 기준 설정
avg_len = 500

## 모델 경로
rul_models_path = ['./model/rul_deep/lstm_fl_total.h5', './model/rul_deep/lstm_pd_total.h5', './model/rul_deep/lstm_ph_total.h5']
scalers_path = ['./model/rul_deep/X_scaler_fl.pkl','./model/rul_deep/X_scaler_pd.pkl','./model/rul_deep/X_scaler_ph.pkl']
abnormal_models_path = ['./model/abnormal_detect/RF_model(FL).pkl','./model/abnormal_detect/RF_model(PB).pkl','./model/abnormal_detect/RF_model(PH).pkl']
multi_scalers_path = './model/abnormal_detect/StandardScaler.pkl'

# 모델 및 스케일러 미리 로드
MODELS = [load_model(path) for path in rul_models_path]
ABNORMAL_MODELS = [joblib.load(path) for path in abnormal_models_path]
SCALERS = [joblib.load(path) for path in scalers_path]
multi_scaler = joblib.load(multi_scalers_path)

def fetch_recent_logs(length=1):
    """mysql db에서 최근 로그를 가져오는 함수"""
    # mysql 데이터베이스에 연결

    connection = pymysql.connect(host='limemoni-2.cfcq69qzg7mu.ap-northeast-1.rds.amazonaws.com',  # DB 주소
                                 user='oneday',  # DB 유저명
                                 password='1234',  # 비밀번호
                                 db='j6database',  # 사용할 DB 이름
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)
    try:
        with connection.cursor() as cursor:
            # 가장 최근의 데이터부터 지정한 길이만큼 가져오는 SQL 쿼리
            sql = f'''SELECT time, stage, Lot, runnum, recipe, recipe_step,
       IONGAUGEPRESSURE, ETCHBEAMVOLTAGE, ETCHBEAMCURRENT,
       ETCHSUPPRESSORVOLTAGE, ETCHSUPPRESSORCURRENT, FLOWCOOLFLOWRATE,
       FLOWCOOLPRESSURE, ETCHGASCHANNEL1READBACK, ETCHPBNGASREADBACK,
       FIXTURETILTANGLE, ROTATIONSPEED, ACTUALROTATIONANGLE,
       FIXTURESHUTTERPOSITION, ETCHSOURCEUSAGE, ETCHAUXSOURCETIMER,
       ETCHAUX2SOURCETIMER, ACTUALSTEPDURATION FROM {input_data} ORDER BY input_time DESC LIMIT {length+51}'''
            cursor.execute(sql)
            results = cursor.fetchall()
    finally:
        connection.close()

    return results

def fetch_recent_rul_logs(length=avg_len):
    """mysql db에서 rul 최근 로그를 가져오는 함수"""
    # mysql 데이터베이스에 연결

    connection = pymysql.connect(host='limemoni-2.cfcq69qzg7mu.ap-northeast-1.rds.amazonaws.com',  # DB 주소
                                 user='oneday',  # DB 유저명
                                 password='1234',  # 비밀번호
                                 db='j6database',  # 사용할 DB 이름
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)
    try:
        with connection.cursor() as cursor:
            # 가장 최근의 데이터부터 지정한 길이만큼 가져오는 SQL 쿼리
            sql = f'''SELECT rul_fl, rul_pb, rul_ph FROM {rul} ORDER BY input_time DESC LIMIT {length}'''
            cursor.execute(sql)
            results = cursor.fetchall()
    finally:
        connection.close()

    return results

def fetch_recent_logs_for_multi(length=1):
    """mysql db에서 최근 로그를 가져오는 함수"""
    # mysql 데이터베이스에 연결

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
              IONGAUGEPRESSURE FROM {input_data} ORDER BY input_time DESC LIMIT {length}'''
            cursor.execute(sql)
            results = cursor.fetchall()
    finally:
        connection.close()

    return results

def dict_to_array(data):
    """사전 형태의 데이터를 2차원 넘파이 배열로 변환하는 함수"""
    return np.array([list(item.values()) for item in data])


def add_difference_to_data(data):
    """각 row에 대해 다음 행의 첫 번째 열과 두 번째 열의 차이를 계산하여 data의 마지막 열에 추가하는 함수"""
    data[0]['time_diff'] = 0
    for i in range(len(data)-1):
        diff = data[i+1]['time'] - data[i]['time']
        data[i+1]['time_diff'] = diff
        del data[i]['time']
    return data[1:] ## 0 값은 의미 없으므로 제거

def predict_with_xgb_model_optimized(data,length=1):
    """수명예측 모델로 예측하는 함수"""
    data = add_difference_to_data(data)
    # 슬라이딩 윈도우를 적용하여 시퀀스 생성
    sequences = [data[i::5][:10] for i in range(length)]
    
    predictions = []
    
    for sequence in sequences:
        transformed_data = dict_to_array(sequence)
        scaled_data_list = [scaler.transform(transformed_data) for scaler in SCALERS]
        
        sequence_predictions = []
        for model, scaled_data in zip(MODELS, scaled_data_list):
            pred_scaled = model.predict(scaled_data.reshape(-1,10,23))
            sequence_predictions.append(pred_scaled[0][0])
        
        predictions.append(sequence_predictions)
    
    return predictions[0]

def predict_with_xgb_multi_model_optimized(data):
    """고장예측 모델로 예측하는 함수"""
    transformed_data = dict_to_array(data)
    scaled_data = multi_scaler.transform(transformed_data)  # 첫 번째 스케일러만 사용

    predictions = []
    for model in ABNORMAL_MODELS:
        predictions.append(model.predict(scaled_data))
        
    return predictions


def compute_moving_average(data, window_size=None):
    """이동평균 예측 함수"""
    
    if window_size is None or window_size > len(data):
        window_size = len(data)
        
    return np.convolve(data, np.ones(window_size)/window_size, mode='valid')

def compute_moving_median(data, window_size):
    """이동 중앙값 계산 함수"""
    tmp_data = data.reshape(1,-1)
    num_data = len(tmp_data)
    medians = []

    for i in range(num_data - window_size + 1):
        window_data = tmp_data[i:i+window_size]
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
            sql = f'''INSERT INTO {input_data} (time, Tool, stage, Lot, runnum, recipe, recipe_step,
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
            sql = f'''INSERT INTO {rul}(rul_fl, rul_pb, rul_ph, input_time) 
                      VALUES (%s, %s, %s, "{current_time}")'''
            cursor.execute(sql, (data[0], data[1], data[2]))
        connection.commit()
    except Exception as e:
        print(f"Error while inserting data: {e}")
        connection.rollback()

def insert_single_rul_avg_data(connection, data, current_time):
    try:
        with connection.cursor() as cursor:
            # 데이터 삽입 SQL.
            sql = f'''INSERT INTO {rul}_avg(rul_fl, rul_pb, rul_ph, input_time) 
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
            sql = f'''INSERT INTO {multi}(multi_pred_fl, multi_pred_pb, multi_pred_ph, input_time) 
                      VALUES (%s, %s, %s, "{current_time}")'''
            cursor.execute(sql, (data[0], data[1], data[2]))
        connection.commit()
    except Exception as e:
        print(f"Error while inserting data: {e}")
        connection.rollback()

# 전역 변수 선언
running_1 = True

def main():

    global running_1 ## 전역변수사용
    running_1 = True

    # 데이터베이스 연결 설정

    connection = pymysql.connect(host='limemoni-2.cfcq69qzg7mu.ap-northeast-1.rds.amazonaws.com',  # DB 주소
                                 user='oneday',  # DB 유저명
                                 password='1234',  # 비밀번호
                                 db='j6database',  # 사용할 DB 이름
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)
    # CSV 파일 읽기
    df = pd.read_csv(f"./test_file/{file}.csv")
    df = df.iloc[:,1:]
    
    # DataFrame에서 튜플 리스트로 데이터 변환
    data_tuples = list(df.itertuples(index=False, name=None))
    while running_1:
        # 시작시 진행 상황 파일이 존재하는지 확인
        if os.path.exists(f'./test_file/progress_{file}.txt'):
            with open(f'./test_file/progress_{file}.txt', 'r') as f:
                last_processed = int(f.read())
                start_index = last_processed + 1
        else:
            start_index = 0
    


        ## 데이터를 한줄 씩 밀어넣으면서 진행하는 방식

        for index, single_data in enumerate(data_tuples[start_index:], start=start_index):
            if not running_1:
                break
            try:
                start_time = time.time()
                current_time = insert_single_data(connection, single_data)
                data = fetch_recent_logs(length=avg_len)
                data_for_multi = fetch_recent_logs_for_multi()

                # 가져온 데이터로 예측 실시
                rul_predictions = predict_with_xgb_model_optimized(data)
                multi_predictions = predict_with_xgb_multi_model_optimized(data_for_multi)

                insert_single_rul_data(connection, rul_predictions, current_time)
                insert_single_multi_data(connection, multi_predictions, current_time)

                # 이동평균을 위한 예측 실시
                data_for_rul = fetch_recent_rul_logs()
                array_data = dict_to_array(data_for_rul)
                avg_data_0 = compute_moving_average(array_data[:,0],500)
                avg_data_1 = compute_moving_average(array_data[:,1],500)
                avg_data_2 = compute_moving_average(array_data[:,2],500)
                avg_pred = (float(avg_data_0),float(avg_data_1),float(avg_data_2))

                insert_single_rul_avg_data(connection, avg_pred, current_time)

                elapsed_time = time.time() - start_time  # 루프 실행 시간 계산
                sleep_time = max(4 - elapsed_time, 0)  # 음수가 되지 않도록 최소값을 0으로 설정
                time.sleep(sleep_time)  # 조절된 sleep 시간만큼 대기

                # 진행 상황을 파일에 기록
                with open(f'./test_file/progress_{file}.txt', 'w') as f:
                    f.write(str(index))


            except Exception as e:
                print(f"Error: {e}")
            
            if not running_1:
                break

        # 모든 데이터를 처리한 후 진행 상황 파일을 삭제하거나 리셋합니다.
        # if os.path.exists(f'./test_file/progress_{file}.txt'):
        #     os.remove(f'./test_file/progress_{file}.txt')
            
    
    # 연결 종료
    connection.close()    

# 외부에서 호출하여 main() 함수의 무한루프를 중단시키는 함수

def stop():
    global running_1  # 전역 변수 사용 선언
    running_1 = False

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    stop()