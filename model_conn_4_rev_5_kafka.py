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
from kafka import KafkaConsumer, KafkaProducer
from kafka import TopicPartition, OffsetAndMetadata
import json
from copy import deepcopy
import tensorflow as tf
tf.get_logger().setLevel('ERROR')


# 전역 변수 선언
running_consumer_4 = True
# 전역 변수 선언
running_4 = True

# 테이블 변수
input_data = 'input_data_4'
rul = 'rul_4'
multi = 'multi_4'
file = 'file_4'
input_topic = 'input-topic-4'
consumer_group = 'consumer-group-4'

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
    if not data:
        return np.array([]), None

    # 첫 번째 아이템의 키 순서를 기준으로 사용
    base_keys = list(data[0].keys())
    if 'current_time' in base_keys:
        base_keys.remove('current_time')

    # 누락된 키에 대해 None을 기본값으로 사용
    normalized_data = [{key: item.get(key, None) for key in base_keys} for item in data]

    tmp_time = data[0]['current_time'] if 'current_time' in data[0] else None
    if tmp_time is not None:
        tmp_time = datetime.fromisoformat(tmp_time)

    return np.array([list(item.values()) for item in normalized_data]), tmp_time



def add_difference_to_data(data):
    """각 row에 대해 다음 행의 첫 번째 열과 두 번째 열의 차이를 계산하여 data의 마지막 열에 추가하는 함수"""
    tmp_data = deepcopy(data)
    tmp_data[0]['time_diff'] = 0
    for i in range(len(tmp_data)-1):
        diff = tmp_data[i+1]['time'] - tmp_data[i]['time']
        tmp_data[i+1]['time_diff'] = diff
        del tmp_data[i]['time']
    return tmp_data[1:] ## 0 값은 의미 없으므로 제거

def predict_with_xgb_model_optimized(data,length=1):
    """수명예측 모델로 예측하는 함수"""
    data_added = add_difference_to_data(data)

    sequences = data_added[0::5][:10]
    
    predictions = []
    
    transformed_data, tmp_time = dict_to_array(sequences)
    scaled_data_list = [scaler.transform(transformed_data) for scaler in SCALERS]
        
    sequence_predictions = []
    for model, scaled_data in zip(MODELS, scaled_data_list):
        pred_scaled = model.predict(scaled_data.reshape(-1,10,23))
        sequence_predictions.append(pred_scaled[0][0])
        
    
    return sequence_predictions, tmp_time

def predict_with_xgb_multi_model_optimized(data):
    """고장예측 모델로 예측하는 함수"""
    transformed_data, tmp_time = dict_to_array(data)
    scaled_data = multi_scaler.transform(transformed_data)  # 첫 번째 스케일러만 사용

    predictions = []
    for model in ABNORMAL_MODELS:
        predictions.append(model.predict(scaled_data))
        
    return predictions, tmp_time


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



#####################################################################################################################
#####################################################################################################################
#####################################################################################################################

# kafka comsumer loop 정의!!

def kafka_consumer_loop():

    global running_consumer_1 ## 전역변수사용
    running_consumer_1 = True

    connection = pymysql.connect(host='limemoni-2.cfcq69qzg7mu.ap-northeast-1.rds.amazonaws.com',  # DB 주소
                                 user='oneday',  # DB 유저명
                                 password='1234',  # 비밀번호
                                 db='j6database',  # 사용할 DB 이름
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)

    # Kafka Consumer 설정
    consumer = KafkaConsumer(
        input_topic,
        bootstrap_servers=['3.35.215.96:9092', '13.209.203.17:9092', '3.36.216.81:9092'],
        group_id=consumer_group, 
        auto_offset_reset='latest',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )
    # 필요한 컬럼 순서 정의
    columns_rul = [
        "time", "stage", "Lot", "runnum", "recipe", "recipe_step",
        "IONGAUGEPRESSURE", "ETCHBEAMVOLTAGE", "ETCHBEAMCURRENT",
        "ETCHSUPPRESSORVOLTAGE", "ETCHSUPPRESSORCURRENT", "FLOWCOOLFLOWRATE",
        "FLOWCOOLPRESSURE", "ETCHGASCHANNEL1READBACK", "ETCHPBNGASREADBACK",
        "FIXTURETILTANGLE", "ROTATIONSPEED", "ACTUALROTATIONANGLE",
        "FIXTURESHUTTERPOSITION", "ETCHSOURCEUSAGE", "ETCHAUXSOURCETIMER",
        "ETCHAUX2SOURCETIMER", "ACTUALSTEPDURATION","current_time"
    ]

    columns_multi = [
        'ACTUALROTATIONANGLE', 'ACTUALSTEPDURATION', 'ETCHBEAMCURRENT', 'ETCHGASCHANNEL1READBACK', 
                'ETCHPBNGASREADBACK', 'ETCHSOURCEUSAGE', 'FIXTURETILTANGLE', 'FLOWCOOLFLOWRATE', 'FLOWCOOLPRESSURE', 
                'IONGAUGEPRESSURE',"current_time"
    ]
    # 메시지 수신 및 처리
    window_size = 52
    rul_collected_data = []

    # kafka comsumer loop 시작
    cnt = 0

    while running_consumer_1:
        for message in consumer:
            # print("%s:%d:%d: key=%s value=%s" % (message.topic, message.partition,
            #                              message.offset, message.key,
            #                              message.value))
            data = message.value
            data_tuple_rul = {column:data.get(column) for column in columns_rul}
            data_tuple_multi = [{column:data.get(column) for column in columns_multi}]
            
            rul_collected_data.append(data_tuple_rul)
            cnt += 1

             # 윈도우 크기 유지
            if len(rul_collected_data) > window_size:
                rul_collected_data.pop(0)  # 가장 오래된 데이터 제거
                data_for_rul = rul_collected_data[::-1]
            else:
                data_for_rul = ''
            # print('data_for_rul 길이 : ',len(data_for_rul))
            
            if data_for_rul != '':
                # 가져온 데이터로 예측 실시
                rul_predictions, current_time_rul = predict_with_xgb_model_optimized(data_for_rul)
                insert_single_rul_data(connection, rul_predictions, current_time_rul)


            data_for_multi = data_tuple_multi
            # 가져온 데이터로 예측 실시
            multi_predictions, current_time_multi = predict_with_xgb_multi_model_optimized(data_for_multi)
            # print('current_time_multi : ',current_time_multi)
            insert_single_multi_data(connection, multi_predictions, current_time_multi)

            # 이동평균을 위한 예측 실시
            data_for_rul = fetch_recent_rul_logs()
            array_data,current_time_tmp = dict_to_array(data_for_rul)
            avg_data_0 = compute_moving_average(array_data[:,0],500)
            avg_data_1 = compute_moving_average(array_data[:,1],500)
            avg_data_2 = compute_moving_average(array_data[:,2],500)
            avg_pred = (float(avg_data_0),float(avg_data_1),float(avg_data_2))

            insert_single_rul_avg_data(connection, avg_pred, current_time_multi)
            # 종료 플래그 체크
            if not running_consumer_1:
                break
    # Kafka Consumer 종료
    consumer.close()

#####################################################################################################################
#####################################################################################################################
#####################################################################################################################

# Kafka Consumer 루프를 별도의 스레드에서 실행
consumer_thread = threading.Thread(target=kafka_consumer_loop)
consumer_thread.start()


#####################################################################################################################
#####################################################################################################################
#####################################################################################################################

# kafka producer 정의!!


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

    

    # Kafka Producer 설정
    producer = KafkaProducer(
        bootstrap_servers=['3.35.215.96:9092', '13.209.203.17:9092', '3.36.216.81:9092'],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )


    # CSV 파일 데이터를 Kafka로 전송하는 함수
    def send_data_to_kafka(topic, data):
        producer.send(topic, data)
        producer.flush()



    # CSV 파일 읽기
    df = pd.read_csv(f"./test_file/{file}.csv")
    df = df.iloc[:,1:]
    
    # DataFrame에서 튜플 리스트로 데이터 변환
    data_dicts = list(df.to_dict(orient='records'))
    while running_1:
        # 시작시 진행 상황 파일이 존재하는지 확인
        if os.path.exists(f'./test_file/progress_{file}.txt'):
            with open(f'./test_file/progress_{file}.txt', 'r') as f:
                last_processed = int(f.read())
                start_index = last_processed + 1
        else:
            start_index = 0

        


        ## 데이터를 한줄 씩 밀어넣으면서 진행하는 방식

        for index, single_data in enumerate(data_dicts[start_index:], start=start_index):
            if not running_1:
                break
            try:
                # 기준시간 잡기
                start_time = time.time()

                # dict data tuple로 변환
                tuple_data = tuple(single_data.values())

                # input_data db에 넣고 현재시간 생성
                current_time = insert_single_data(connection, tuple_data)

                # kafka 전송용 dict data 생성
                single_data['current_time'] = current_time

                # kafka single data 전송
                send_data_to_kafka(input_topic, single_data)

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