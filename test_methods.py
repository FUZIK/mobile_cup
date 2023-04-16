import sys
import random
import string
import time
from enum import Enum
import collections
import logging

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


def main():
    server_addr = sys.argv[1] if 1 < len(sys.argv) else "127.0.0.1:8080"

    DEBUG = len(sys.argv) <= 1
    logging.info("DEBUG = %s", DEBUG)

    api_url = f"http://{server_addr}/api"

    token = sys.argv[2] if 2 < len(sys.argv) else ''.join(
        random.choice(string.ascii_lowercase) for _ in range(16))

    session = requests.Session()

    score = 1
    collect_hist = [collections.deque(maxlen=20), collections.deque(maxlen=20), collections.deque(maxlen=20)]
    pipe_ping = [0, 0, 0]

    def collect(pipe):
        if DEBUG:
            time.sleep(0.1)
            pipe_ping[pipe - 1] = 0.1
            return 1

        response = session.put(f"{api_url}/pipe/{pipe}", headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            pipe_ping[pipe-1] = response.delay.microseconds
            return response.json()["value"]
        else:
            raise Exception(f"Unexpected status code {response.status_code}")

    def value(pipe):
        if DEBUG:
            return 1

        response = session.get(f"{api_url}/pipe/{pipe}/value",
                               headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            return response.json()["value"]
        else:
            raise Exception(f"Unexpected status code {response.status_code}")

    def modifier(pipe, type):
        response = session.post(f"{api_url}/pipe/{pipe}/modifier",
                                json={"type": type},
                                headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            logging.info("Applied modifier $s to pipe $s", type, pipe)
        elif response.status_code == 422:
            logging.info("Failed to apply modifier")
        else:
            raise Exception(
                f"Unexpected status code {response.status_code}")

    def print_usrstate():
        logging.info("score = %s", score)

    def print_pipestate(pipe):
        logging.info('ping %s', pipe_ping[pipe-1])
        logging.info('history %s', collect_hist[pipe-1])

    while True:
        for i in range(1, 4, 1):
            print()
            logging.info('Selected pipe %s', i)

            valued = value(i)
            logging.info("Pipe value %s", valued)

            print_usrstate()
            print_pipestate(i)

            collected = collect(i)
            logging.info("Collected %s", collected)
            score += collected
            collect_hist[i - 1].append(collected)

            valued = value(i)
            logging.info("Pipe value %s}", valued)


if __name__ == "__main__":
    main()
