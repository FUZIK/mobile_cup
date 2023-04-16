import sys
import random
import string
import time
from enum import Enum
import collections
import logging

from datetime import datetime, timedelta

import requests


class Modifier(Enum):
    REVERSE = "reverse",
    DOUBLE = "double",
    SLOW = "slow",
    SHUFFLE = "shuffle",
    MIN = "min"


logger = logging.getLogger("logging_tryout2")
logging.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S")
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logging.addHandler(ch)

collect_hist = [collections.deque(maxlen=20), collections.deque(maxlen=20), collections.deque(maxlen=20)]
pipe_delta = [-1, -1, -1]
user_score = -1
current_pipe_index = -1


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
        global user_score
        if DEBUG:
            time.sleep(0.1)
            pipe_delta[pipe_index] = random.uniform(0.1, 3)
            collect_hist[pipe_index].append(1)
            user_score += 1
            return 1

        ini_time = datetime.now()
        response = session.put(f"{api_url}/pipe/{pipe_index+1}", headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            value = response.json()["value"]
            pipe_delta[pipe_index] = (datetime.now() - ini_time).microseconds
            collect_hist[pipe_index].append(value)
            user_score += 1
            return value
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
        response = session.post(f"{api_url}/pipe/{pipe_index+1}/modifier",
                                json={"type": type},
                                headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            logging.info("Applied modifier $s to pipe_index $s", type, pipe_index)
        elif response.status_code == 422:
            logging.info("Failed to apply modifier")
        else:
            raise Exception(
                f"Unexpected status code {response.status_code}")

    def print_usrstate():
        logging.info("score = %s", user_score)

    def print_pipestate(pipe_index):
        logging.info('pipe_delta %s', pipe_delta[pipe_index])
        logging.info('history %s', collect_hist[pipe_index])

    def get_optimal_pipe_by_delta():
        min_i = 0
        for i in range(0, len(pipe_delta)):
            if pipe_delta[i] < pipe_delta[min_i]:
                min_i = i
        return min_i

    def get_pipe_delta(pipe_index):
        return pipe_delta[pipe_index]

    for i in range(0, 3):
        collected = collect(i)
        logging.info("Collected %s", collected)
        print_pipestate(i)
    current_pipe_index = get_optimal_pipe_by_delta()

    while True:
        logging.info('')
        logging.info('Selected current_pipe_index %s', current_pipe_index)

        deltus = get_pipe_delta(current_pipe_index)

        collected = collect(current_pipe_index)
        logging.info("Collected %s", collected)

        logging.info("deltas times %s", deltus - get_pipe_delta(current_pipe_index))

        print_usrstate()
        print_pipestate(current_pipe_index)


if __name__ == "__main__":
    main()
