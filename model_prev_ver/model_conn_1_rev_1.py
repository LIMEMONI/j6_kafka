import pymysql
import pickle
import xgboost as xgb
import numpy as np
import pandas as pd
import time
import warnings
from datetime import datetime
import joblib


# 경고 숨기기
warnings.filterwarnings(action='ignore', category=UserWarning, module='xgboost')
warnings.filterwarnings("ignore", message="X does not have valid feature names, but StandardScaler was fitted with feature names")

# 현재 시간 가져오기
current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

## 길이 기준 설정
avg_len = 500

## 모델 경로
abnormal_models_path = ['./model/abnormal_detect/RF_model(FL).pkl','./model/abnormal_detect/RF_model(PB).pkl','./model/abnormal_detect/RF_model(PH).pkl']
rul_models_path = ['./model/RULmodel/231023_xgb_ss_df_fl.pickle','./model/RULmodel/231023_xgb_ss_df_pb.pickle','./model/RULmodel/231023_xgb_ss_df_fl.pickle']
inverse_scalers_path = ['./model/RULmodel/231023_ss_y_df_fl.pickle','./model/RULmodel/231023_ss_y_df_pb.pickle','./model/RULmodel/231023_ss_y_df_ph.pickle']
scalers_path = ['./model/RULmodel/231023_ss_x_df_fl.pickle','./model/RULmodel/231023_ss_x_df_pb.pickle','./model/RULmodel/231023_ss_x_df_ph.pickle']

# 모델 및 스케일러 미리 로드
MODELS = [joblib.load(path) for path in rul_models_path]
SCALERS = [joblib.load(path) for path in scalers_path]
INVERSE_SCALERS = [joblib.load(path) for path in inverse_scalers_path]
ABNORMAL_MODELS = [joblib.load(path) for path in abnormal_models_path]

def fetch_recent_logs(length=avg_len):
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
            sql = f'''SELECT ACTUALROTATIONANGLE, FIXTURETILTANGLE,
                        ETCHBEAMCURRENT,IONGAUGEPRESSURE,
                        ETCHGASCHANNEL1READBACK, ETCHPBNGASREADBACK,
                        ACTUALSTEPDURATION, ETCHSOURCEUSAGE,
                        FLOWCOOLFLOWRATE,FLOWCOOLPRESSURE FROM input_data_1 ORDER BY input_time DESC LIMIT {length}'''
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
              IONGAUGEPRESSURE FROM input_data_1 ORDER BY input_time DESC LIMIT {length}'''
            cursor.execute(sql)
            results = cursor.fetchall()
    finally:
        connection.close()

    return results

def dict_to_array(data):
    """사전 형태의 데이터를 2차원 넘파이 배열로 변환하는 함수"""
    return np.array([list(item.values()) for item in data])


def predict_with_xgb_model_optimized(data):
    """수명예측 모델로 예측하는 함수"""
    transformed_data = dict_to_array(data)
    scaled_data_list = [scaler.transform(transformed_data) for scaler in SCALERS]
    
    predictions = []
    for model, scaled_data, inverse_scaler in zip(MODELS, scaled_data_list, INVERSE_SCALERS):
        pred_scaled = model.predict(scaled_data)
        predictions.append(inverse_scaler.inverse_transform(pred_scaled.reshape(-1,1))[:,0])

    return predictions

def predict_with_xgb_multi_model_optimized(data):
    """고장예측 모델로 예측하는 함수"""
    transformed_data = dict_to_array(data)
    scaled_data = SCALERS[0].transform(transformed_data)  # 첫 번째 스케일러만 사용

    predictions = []
    for model in ABNORMAL_MODELS:
        predictions.append(model.predict(scaled_data))
        
    return predictions

def compute_moving_average(data, window_size=avg_len):
    """이동평균 예측 함수"""
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

    # DataFrame에서 튜플 리스트로 데이터 변환
    data_tuples = list(df.itertuples(index=False, name=None))


    ## 데이터를 한줄 씩 밀어넣으면서 진행하는 방식

    for single_data in data_tuples:
        try:
            start_time = time.time()
            current_time = insert_single_data(connection, single_data)
            data = fetch_recent_logs(length=avg_len)
            data_for_multi = fetch_recent_logs_for_multi()

            # 가져온 데이터로 예측 실시
            rul_predictions_raw = predict_with_xgb_model_optimized(data)
            # fetch로 가져온 데이터의 길이만큼 이동 평균 적용
            rul_predictions = [compute_moving_average(pred, window_size=len(data)) for pred in rul_predictions_raw]

            multi_predictions = predict_with_xgb_multi_model_optimized(data_for_multi)

            elapsed_time = time.time() - start_time  # 루프 실행 시간 계산
            sleep_time = max(4 - elapsed_time, 0)  # 음수가 되지 않도록 최소값을 0으로 설정
            time.sleep(sleep_time)  # 조절된 sleep 시간만큼 대기

            insert_single_rul_data(connection, rul_predictions, current_time)
            insert_single_multi_data(connection, multi_predictions, current_time)


        except Exception as e:
            print(f"Error: {e}")

            
    
    # 연결 종료
    connection.close()    

  
  



if __name__ == "__main__":
    main()