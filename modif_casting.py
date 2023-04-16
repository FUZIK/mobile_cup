import sys
import random
import string
import time
from enum import Enum
import collections
import logging

import requests

REVERSE = "reverse",
DOUBLE = "double",
SLOW = "slow",
SHUFFLE = "shuffle",
MIN = "min"

# Смена направления: за 40 очков направление (уменьшение или увеличение) указанного эндпоинта меняется на противоположное
# Удвоение: за 50 очков следующие 5 запросов от любых участников дадут удвоенное количество очков от каждого запроса на указанном эндпоинте
# Замедление: за 40 очков у указанного эндпоинта будет удвоенное время ответа на ближайшие 10 запросов
# Перетасовка: за 10 очков у заданного эндпоинта будет сброшено время задержки и сгенерировано новое (случайно)
# Обнуление: за 10 очков указанный эндпоинт 3 раза выдаст 1 очко. После этого поведение будет стандартным.


PIPE_DELTA_MIN = 0.1
PIPE_DELTA_MAX = 3.0
PIPE_DELTA_ERROR = PIPE_DELTA_MIN

PIPE_MAX_INDEX = 2

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S')

collect_count = 0
collect_hist = [collections.deque(maxlen=20), collections.deque(maxlen=20), collections.deque(maxlen=20)]
pipe_history = []
pipe_delta = [9999.0, 9999.0, 9999.0]
user_score = -1
current_pipe_index = -1
roboact_log = []


def main():
    global current_pipe_index
    server_addr = sys.argv[1] if 1 < len(sys.argv) else "127.0.0.1:8080"

    DEBUG = len(sys.argv) <= 1
    logging.info("DEBUG = %s", DEBUG)

    api_url = f"http://{server_addr}/api"

    token = sys.argv[2] if 2 < len(sys.argv) else ''.join(
        random.choice(string.ascii_lowercase) for _ in range(16))

    session = requests.Session()

    def collect(pipe_index):
        global user_score, collect_count
        collect_count += 1
        if DEBUG:
            time.sleep(0.1)
            pipe_delta[pipe_index] = random.uniform(0.1, 3)
            lleenn = len(collect_hist[pipe_index])
            if lleenn > 0:
                collect_hist[pipe_index].append(collect_hist[pipe_index][lleenn-1] + 1)
            else:
                collect_hist[pipe_index].append(1)
            user_score += 1
            return 1
        ini_time = time.time()
        response = session.put(f"{api_url}/pipe/{pipe_index+1}", headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            rjson = response.json()
            logging.info("http://collect/=>%s", rjson)
            rvalue = rjson["value"]
            pipe_delta[pipe_index] = time.time() - ini_time
            collect_hist[pipe_index].append(rvalue)
            user_score = user_score + rvalue
            return rvalue
        else:
            raise Exception(f"Unexpected status code {response.status_code}")

    def value(pipe_index):
        if DEBUG:
            return 1
        response = session.get(f"{api_url}/pipe/{pipe_index+1}/value",
                               headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            return response.json()["value"]
        else:
            raise Exception(f"Unexpected status code {response.status_code}")

    def modifier(pipe_index, type):
        response = session.post(f"{api_url}/pipe/{pipe_index}/modifier",
                                json={"type": type},
                                headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            return True
        elif response.status_code == 422:
            return False
        else:
            return False

    def print_usrstate():
        logging.info("collect_count = %s / score = %s / pipe_history = %s / roboact_log = %s", collect_count, user_score, pipe_history, roboact_log)

    def print_pipestate(pipe_index):
        logging.info('pipe_delta %s / history %s', pipe_delta[pipe_index], collect_hist[pipe_index])

    def get_optimal_pipe_by_delta(ignore_pipe=[]):
        min_i = 0
        for i in range(0, len(pipe_delta)):
            if pipe_delta[i] < pipe_delta[min_i] and i not in ignore_pipe:
                min_i = i
        return min_i

    def get_pipe_delta(pipe_index):
        return pipe_delta[pipe_index]

    def update_selected_pipe(pipe_index):
        global current_pipe_index
        pipe_history.append(pipe_index)
        current_pipe_index = pipe_index

    def detect_slow_mod_lite(actual_ping, before_ping):
        d = (actual_ping / 2) - before_ping
        if d <= PIPE_DELTA_ERROR:
            return True
        elif -d <= PIPE_DELTA_ERROR:
            return True
        return False

    for pipe_index in range(PIPE_MAX_INDEX + 1):
        collected = collect(pipe_index)
        print_pipestate(pipe_index)
        if PIPE_MAX_INDEX-1 > pipe_index:
            if get_pipe_delta(pipe_index) - PIPE_DELTA_MIN == PIPE_DELTA_ERROR:
                roboact_log.append("Force selected pipe %s" + str(pipe_index))
                break
    update_selected_pipe(get_optimal_pipe_by_delta())

    logging.info('Selected current_pipe_index %s', current_pipe_index)

    while True:
        before_ping = get_pipe_delta(current_pipe_index)
        collect(current_pipe_index)
        actual_ping = get_pipe_delta(current_pipe_index)
        delta_ping = before_ping - actual_ping
        logging.info("hist=>%s", collect_hist[current_pipe_index])

        is_delay_changed = delta_ping > PIPE_DELTA_ERROR or -delta_ping > PIPE_DELTA_ERROR
        is_min_mod = False
        is_shuffle_mod = False
        is_slow_mod = detect_slow_mod_lite(actual_ping, before_ping)


        if is_delay_changed:
            roboact_log.append("det_delay_changed")

        if is_slow_mod:
            roboact_log.append("det_slow_mod")

        if is_delay_changed:
            pindexes = [0, 1, 2]
            pindexes.remove(current_pipe_index)
            for pipe_index in pindexes:
                collect(pipe_index)
                print_pipestate(pipe_index)
            update_selected_pipe(get_optimal_pipe_by_delta())

        # подкинуть говно себе подноги
        if len(pipe_history) == 1:
            global user_score, collect_count
            if collect_count >= 10:
                if modifier(current_pipe_index, MIN):
                    roboact_log.append("govno_pod_nogi")
                    pindexes = [0, 1, 2]
                    pindexes.remove(current_pipe_index)
                    for pipe_index in pindexes:
                        collect(pipe_index)
                        print_pipestate(pipe_index)
                    update_selected_pipe(get_optimal_pipe_by_delta(ignore_pipe=[current_pipe_index]))

        print_usrstate()
        # print_pipestate(current_pipe_index)


if __name__ == "__main__":
    main()
