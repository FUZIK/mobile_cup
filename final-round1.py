import itertools
import sys
import random
import string
import time
import collections
import logging

import requests

def get_collect_normal_step(history):
    history_len = len(history)
    if history_len > 10:
        history = list(itertools.islice(history, history_len-10, history_len))
    history_len = len(history)
    steps = {}
    for i in range(history_len):
        if i > 0:
            step = history[i - 1] - history[i]
            if step < 0:
                step = -step
            if step in steps.keys():
                steps[step] += 1
            else:
                steps[step] = 1

    return max(steps, key=steps.value)


REVERSE = "reverse"
DOUBLE = "double"
SLOW = "slow"
SHUFFLE = "shuffle"
MIN = "min"

PIPE_DELTA_MIN = 0.1
PIPE_DELTA_MAX = 3.0
PIPE_DELTA_ERROR = 0.03

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
blockflag0 = 0


def main():
    global collect_count, pipe_delta, current_pipe_index, blockflag0
    server_addr = sys.argv[1] if 1 < len(sys.argv) else "127.0.0.1:8080"

    DEBUG = len(sys.argv) <= 1
    logging.info("DEBUG = %s", DEBUG)
    logging.info("VERSION = %s", "G")


    api_url = f"http://{server_addr}/api"

    token = sys.argv[2] if 2 < len(sys.argv) else ''.join(
        random.choice(string.ascii_lowercase) for _ in range(16))

    session = requests.Session()

    def collect(pipe_index):
        global user_score, collect_count, blockflag0
        collect_count += 1
        if blockflag0 > 0:
            blockflag0 = blockflag0 - 1
        if DEBUG:
            time.sleep(0.1)
            pipe_delta[pipe_index] = random.uniform(0.1,2.9)
            lleenn = len(collect_hist[pipe_index])
            if lleenn > 0:
                l = collect_hist[pipe_index][lleenn-1] + 1
                if l == 10:
                    collect_hist[pipe_index].append(1)
                else:
                    collect_hist[pipe_index].append(l)
            else:
                collect_hist[pipe_index].append(1)
            user_score += 1
            return 1
        ini_time = time.time()
        response = session.put(f"{api_url}/pipe/{pipe_index+1}", headers={"Authorization": f"Bearer {token}"})
        p_delta = time.time() - ini_time
        if response.status_code == 200:
            rjson = response.json()
            logging.info("http://collect/=>%s", rjson)
            rvalue = rjson["value"]

            if p_delta > pipe_delta[pipe_index]:
                if p_delta - pipe_delta[pipe_index] <= PIPE_DELTA_ERROR:
                    pass
                else:
                    pipe_delta[pipe_index] = p_delta
            else:
                pipe_delta[pipe_index] = p_delta

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
        global user_score
        if DEBUG:
            if type == SLOW:
                user_score -= 40
                roboact_log.append(f"{type}>{pipe_index}")
                return True
            elif type == SHUFFLE:
                user_score -= 10
                roboact_log.append(f"{type}>{pipe_index}")
                return True
            elif type == MIN:
                user_score -= 10
                roboact_log.append(f"{type}>{pipe_index}")
                return True
            return False

        response = session.post(f"{api_url}/pipe/{pipe_index}/modifier",
                                json={"type": type},
                                headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            if type == SLOW:
                user_score -= 40
            elif type == SHUFFLE:
                user_score -= 10
            elif type == MIN:
                user_score -= 10
            roboact_log.append(f"{type}>{pipe_index}")
            return True
        elif response.status_code == 422:
            return False
        else:
            return False

    def print_usrstate():
        logging.info("collect_count = %s / score = %s / pipe_history = %s / roboact_log = %s / pipe_delta = %s", collect_count, user_score, pipe_history, roboact_log, pipe_delta)

    def print_pipestate(pipe_index):
        logging.info('pipe_delta %s / history %s', pipe_delta[pipe_index], collect_hist[pipe_index])

    def get_optimal_pipe_by_delta(ignore_pipe=[]):
        min_i = 0
        global pipe_delta
        for i in range(0, len(pipe_delta)):
            if pipe_delta[i] < pipe_delta[min_i] and i not in ignore_pipe:
                min_i = i
        return min_i

    def get_pipe_delta(pipe_index):
        return pipe_delta[pipe_index]

    def update_selected_pipe(pipe_index):
        global current_pipe_index

        # чистим прочую историю
        PIPES = [0, 1, 2]
        PIPES.remove(pipe_index)
        for pipe_indexx in PIPES:
            collect_hist[pipe_indexx] = []

        pipe_history.append(pipe_index)
        current_pipe_index = pipe_index

    def get_last_collect(pipe_index):
        hist = collect_hist[pipe_index]
        return hist[len(hist)-1]

    def init_robo():
        PIPES = [0, 1, 2]
        random.shuffle(PIPES)
        for pipe_index in PIPES:
            collect(pipe_index)
            global user_score
            if user_score >= 10:
                if modifier(pipe_index, SHUFFLE):
                    collect(pipe_index)
            print_pipestate(pipe_index)

    # Смена направления: за 40 очков направление (уменьшение или увеличение) указанного эндпоинта меняется на противоположное
    # Удвоение: за 50 очков следующие 5 запросов от любых участников дадут удвоенное количество очков от каждого запроса на указанном эндпоинте
    # Замедление: за 40 очков у указанного эндпоинта будет удвоенное время ответа на ближайшие 10 запросов
    # Перетасовка: за 10 очков у заданного эндпоинта будет сброшено время задержки и сгенерировано новое (случайно)
    # Обнуление: за 10 очков указанный эндпоинт 3 раза выдаст 1 очко. После этого поведение будет стандартным.

    init_robo()
    print(get_optimal_pipe_by_delta())
    update_selected_pipe(get_optimal_pipe_by_delta())

    logging.info('Selected current_pipe_index %s', current_pipe_index)

    def detect_min_mod(pipe_index):
        h = collect_hist[pipe_index]
        l = len(h)
        if l >= 2:
            if h[l-1] == 1 and h[l-2] == 1:
                return True
            elif h[l-1] == 1:
                step = get_collect_normal_step(h)
                logging.info(f"step {step}")
                if h[l - 2] != 9 - step:
                    return True
                elif h[l - 1] != 10 - step:
                    return True

        logging.info(f"min False")
        return False

    def ping_is_changed(before_ping, actual_ping):
        delta_ping = before_ping - actual_ping
        return abs(delta_ping) > PIPE_DELTA_ERROR

    while True:
        before_ping = get_pipe_delta(current_pipe_index)
        collected = collect(current_pipe_index)
        actual_ping = get_pipe_delta(current_pipe_index)


        is_ping_changed = ping_is_changed(before_ping, actual_ping)
        is_slow_mod = actual_ping >= PIPE_DELTA_MAX or (actual_ping > before_ping and round(actual_ping / 2, 2) >= round(before_ping, 2) and round(actual_ping / 2, 2) <= round(before_ping, 2) + PIPE_DELTA_ERROR)
        is_min_mod = detect_min_mod(current_pipe_index)
        logging.info("detector: is_ping_changed=%s, is_slow_mod=%s, is_min_mod=%s", is_ping_changed, is_slow_mod, is_min_mod)

        print_usrstate()
        print_pipestate(current_pipe_index)



        if is_ping_changed: # пинг изменён
            if actual_ping > before_ping: # пинг увеличился
                if is_slow_mod: # пинг увеличился вдвое
                    PIPES = [0, 1, 2]
                    PIPES.remove(current_pipe_index)
                    for pipe_index in PIPES:
                        collect(pipe_index)
                    optimal = get_optimal_pipe_by_delta()
                    if optimal == current_pipe_index:
                        if modifier(optimal, SLOW):
                            pipe_delta[optimal] = pipe_delta[optimal] * (2 - PIPE_DELTA_ERROR)
                            update_selected_pipe(get_optimal_pipe_by_delta())
                        elif modifier(optimal, SHUFFLE):
                            collect(optimal)
                            if modifier(optimal, SLOW):
                                pipe_delta[optimal] = pipe_delta[optimal] * (2 - PIPE_DELTA_ERROR)
                            update_selected_pipe(get_optimal_pipe_by_delta())
                    else:
                        if modifier(optimal, SLOW):
                            pipe_delta[optimal] = pipe_delta[optimal] * (2-PIPE_DELTA_ERROR)
                            update_selected_pipe(get_optimal_pipe_by_delta())
                        elif modifier(optimal, SHUFFLE):
                            collect(optimal)
                            update_selected_pipe(get_optimal_pipe_by_delta())
                        else:
                            update_selected_pipe(optimal)
                else:
                    roboact_log.append("ничего не делая")
                    logging.info("ничего не делая")
                    pass
            else: # пинг уменьшился
                pass
        else:
            if blockflag0 == 0:
                if modifier(current_pipe_index, SHUFFLE):
                    for pipe_index in [0, 1, 2]:
                        collect(pipe_index)
                else:
                    PIPES = [0, 1, 2]
                    PIPES.remove(current_pipe_index)
                    for pipe_index in PIPES:
                        collect(pipe_index)
                update_selected_pipe(get_optimal_pipe_by_delta())
                blockflag0 = 5



        # if collect_count % 10 == 0:
        #     pass
        #
        # if actual_ping >= PIPE_DELTA_MAX:
        #     pass


        # if get_last_collect(current_pipe_index) == 1:
        #     pass


if __name__ == "__main__":
    main()