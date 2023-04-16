import itertools
import logging
import random
import statistics
import string
import sys
import threading
import time
from enum import Enum
from statistics import mean
from typing import List

import requests

DEBUG = len(sys.argv) >= 3
HOST = sys.argv[1] if 1 < len(sys.argv) else "127.0.0.1:8080"
API = f"http://{HOST}/api"
TOKEN = sys.argv[2] if 2 < len(sys.argv) else ''.join(
    random.choice(string.ascii_lowercase) for _ in range(16))

PING_ERROR = 0.02
VALUE_PING = 0.2
MODIFIER_PING = 0
MIN_COLLECT_PING = 0.1
MAX_COLLECT_PING = 3.0

MAX_PLAYERS = 4
MAX_PIPE_VALUE = 10
MIN_PIPE_VALUE = 1
MAX_PIPE_COUNT = 3

UNDEFINED_VALUE = -1

SECS_TO_SKIP_COLLECT = 0.1

session = requests.Session()


class PipeModifier:
    def __init__(self, name, cost):
        self.name = name
        self.cost = cost


class PipeDirection(Enum):
    UP = "up"
    DOWN = "down"


class CollectResult:
    def __init__(self, value, delay):
        self.value = value
        self.delay = delay
        self.time = time.time()

    def __str__(self):
        return f"(value = {self.value}, delay = {self.delay}, time = {self.time})"


class ValueResult:
    def __init__(self, value, delay):
        self.value = value
        self.delay = delay
        self.time = time.time()

    def __str__(self):
        return f"(value = {self.value}, delay = {self.delay}, time = {self.time})"


class ModifierResult:
    def __init__(self, applied, alreadyOrEnoughScore, delay):
        self.applied = applied
        self.alreadyOrEnoughScore = alreadyOrEnoughScore
        self.delay = delay
        self.time = time.time()

    def __str__(self):
        return f"(applied = {self.applied}, alreadyOrEnoughScore = {self.alreadyOrEnoughScore}, delay = {self.delay}, time = {self.time})"


class Pipe:
    _debug_value = random.randint(1, 10)
    _debug_value_up = True
    _debug_collect = _debug_value
    _debug_base_delay = random.uniform(0.1, 3)

    def _d_next_value(self):
        if self._debug_value_up:
            if self._debug_value < 10:
                self._debug_value += 1
            else:
                self._debug_value = 1
        else:
            if self._debug_value > 1:
                self._debug_value -= 1
            else:
                self._debug_value = 10

    def _d_collect(self) -> int:
        c = self._debug_value
        self._d_next_value()
        return c

    def __init__(self, index):
        self.index = index
        self.i = index - 1

    def collect(self) -> CollectResult:
        ping = time.time()
        response = session.put(f"{API}/pipe/{self.index}", headers={"Authorization": f"Bearer {TOKEN}"})
        ping = time.time() - ping
        if response.status_code == 200:
            rjson = response.json()
            rvalue = rjson["value"]
            return CollectResult(rvalue, ping)
        else:
            raise Exception(f"Unexpected status code {response.status_code}")

    def value(self) -> ValueResult:
        ping = time.time()
        response = session.get(f"{API}/pipe/{self.index}/value",
                               headers={"Authorization": f"Bearer {TOKEN}"})
        ping = time.time() - ping
        if response.status_code == 200:
            rjson = response.json()
            rvalue = rjson["value"]
            return ValueResult(rvalue, ping)
        else:
            raise Exception(f"Unexpected status code {response.status_code}")

    def modifier(self, modifier: PipeModifier) -> ModifierResult:
        ping = time.time()
        response = session.post(f"{API}/pipe/{self.index}/modifier",
                                json={"type": modifier.name},
                                headers={"Authorization": f"Bearer {TOKEN}"})
        ping = time.time() - ping
        if response.status_code == 200:
            return ModifierResult(True, False, ping)
        elif response.status_code == 422:
            return ModifierResult(False, True, ping)
        else:
            return ModifierResult(False, False, ping)


class PipeLog:
    def __init__(self):
        self._collect: List[CollectResult] = []
        self._value: List[ValueResult] = []
        self._modifier: List[ModifierResult] = []

    def log_collect(self, result: CollectResult):
        self._collect.append(result)

    def log_value(self, result: ValueResult):
        self._value.append(result)

    def log_modifier(self, result: ModifierResult):
        self._modifier.append(result)


class DelayChanged:
    def __init__(self, is_changed, to_upper):
        self.is_changed = is_changed
        self.to_upper = to_upper

    def __str__(self):
        return f"(is_changed = {self.is_changed}, to_upper = {self.to_upper})"


class PipeDetector(PipeLog):
    def __init__(self):
        super().__init__()
        self._calculated_ping_value = 0

    def get_collect_counts(self):
        return len(self._collect)

    def _sosuns_between_collects(self, collect1, collect2):
        d = collect1.value - collect2.value
        m = abs(d)
        if m == 1 or m == 9:
            return 1
        elif m == 2 or m == 8:
            return 2
        elif m == 3 or m == 7:
            return 3
        elif m == 4 or m == 6:
            return 4
        return UNDEFINED_VALUE

    def get_patsaki(self):
        s = len(self._collect)
        if s >= 2:
            return self._sosuns_between_collects(self._collect[s - 2], self._collect[s - 1])
        return UNDEFINED_VALUE

    # todo даёт ошибку если кол-во сосунов не меняется
    def sosuns_changed_from(self, r_value):
        collects = self._collect
        len_c = len(collects)
        if len_c > 1:
            d = 0
            for i in range(len_c):
                c = collects[len_c - 1 - i]
                if len_c - i >= 0:
                    before_c = collects[len_c - 1 - i - 1]
                    sos = self._sosuns_between_collects(before_c, c)
                    if sos == r_value:
                        break
                    else:
                        d += 1
                else:
                    return d
            return d
        return UNDEFINED_VALUE

    def passive_calculate_pipe_profit_by_collect(self):
        sosuns = self.get_patsaki()
        if sosuns != UNDEFINED_VALUE:
            s = len(self._collect)
            if s > 0:
                last = self._collect[s - 1]
                return 1 / last.delay / sosuns
        return UNDEFINED_VALUE

    def get_pipe_direction(self) -> PipeDirection:
        pass

    def _split(a, n):
        k, m = divmod(len(a), n)
        return (a[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))

    def _get_collect_batches(self):
        collect_len = len(self._collect)
        _batch = []
        batches = []
        for i in range(collect_len):
            curr = self._collect[i]
            if i == collect_len - 1:
                prev = self._collect[i - 1]
                if prev.value < curr.value:
                    _batch.append(curr)
                    batches.append(_batch)
                else:
                    batches.append([curr])
            else:
                next = self._collect[i + 1]
                if curr.value < next.value:
                    _batch.append(curr)
                else:
                    _batch.append(curr)
                    batches.append(_batch)
                    _batch = []
        return batches

    # []
    def calculate_pipe_k(self):
        for batch in self._get_collect_batches():
            l = list(map(lambda c: c.value, batch))
            logging.info(f"Cobach={l}={sum(l)}")
        cvten = list(map(lambda c: c.value, self._collect[len(self._collect) - 10:]))
        logging.info(f"{cvten}={sum(cvten)}")
        return f"/{cvten}={sum(cvten)}"

    def pipe_alitycs_data(self):
        splited_value = []
        current_value = self._value[0]
        current_temp = []
        value_len = len(self._value)
        for i in range(0, value_len):
            valued = self._value[i]
            if valued.value != current_value.value:
                splited_value.append(current_temp)
                current_value = valued
                current_temp = []
            current_temp.append(valued)
            if value_len - 1 == i:
                splited_value.append(current_temp)

        logging.info(f"hist = {list(map(lambda v: v.value, self._value))}")

        # решение 3
        # считает разницу первой 4 и первой 5 [4, 4, 4, 5, 5, 5]
        splited_len = len(splited_value)

        # nn = {}
        # for i in range(0, splited_len):
        #     value_list = splited_value[i]

        # mean = statistics.mean(list(filter(lambda i: i < MAX_PIPE_VALUE * 2 + PING_ERROR, map(lambda v: v., self._value))))
        # logging.info(f"Avg = {mean}")

        ss = []
        for i in range(0, splited_len):
            summ_of_ping = []
            value_list = splited_value[i]
            if i - 1 >= 0 and splited_len - 1 >= i - 1:
                prev_value_list = splited_value[i - 1]
                first_val = prev_value_list[0]
                last_val = value_list[0]
                ping = last_val.time - first_val.time
                if ping < MAX_COLLECT_PING * 2 + PING_ERROR:
                    summ_of_ping.append(ping)
                logging.info(f"{first_val.value} <-{ping}-> {last_val.value}")
            if splited_len - 1 >= i + 1:
                next_value_list = splited_value[i + 1]
                first_val = value_list[0]
                last_val = next_value_list[0]
                ping = last_val.time - first_val.time
                if ping < MAX_COLLECT_PING * 2 + PING_ERROR:
                    summ_of_ping.append(ping)
                logging.info(f"{first_val.value} <-{ping}-> {last_val.value}")
            if len(summ_of_ping) > 0:
                ss.append(statistics.mean(summ_of_ping))
            logging.info(f"splited / {list(map(lambda v: v.value, value_list))}")
            # logging.info(f"Avg {statistics.mean(summ_of_ping)}")
        if len(ss) > 0:
            logging.info(f"Avg {statistics.mean(ss)}")

        # решение 2
        # считает разницу последней 4 и первой 5 [4, 4, 4, 5, 5, 5]
        # splited_len = len(splited_value)
        # for i in range(0, splited_len):
        #     value_list = splited_value[i]
        #     value_len = len(value_list)
        #     if i - 1 >= 0 and splited_len - 1 >= i - 1:
        #         prev_value_list = splited_value[i - 1]
        #         prev_len = len(prev_value_list)
        #         ping = value_list[0].time - prev_value_list[prev_len - 1].time
        #         first_val = prev_value_list[prev_len - 1].value
        #         last_val = value_list[0].value
        #         logging.info(f"{first_val} <-{ping}-> {last_val}")
        #     if splited_len - 1 >= i + 1:
        #         next_value_list = splited_value[i + 1]
        #         ping = next_value_list[0].time - value_list[value_len - 1].time
        #         first_val = value_list[value_len - 1].value
        #         last_val = next_value_list[0].value
        #         logging.info(f"{first_val} <-{ping}-> {last_val}")
        #
        #     ping = value_list[value_len - 1].time - value_list[0].time
        #     first_val = value_list[0].value
        #     last_val = value_list[value_len - 1].value
        #     logging.info(f"{first_val} --{ping}-- {last_val}")

        # вариант 1
        # calc_ping = []
        # for i in range(0, len(splited_value)):
        #     value_list = splited_value[i]
        #     l = len(value_list)
        #     if l >= 2:
        #         p = value_list[l-1].time - value_list[0].time
        #         calc_ping.append(p)
        #     else:
        #         p = UNDEFINED_VALUE
        #     logging.info(f"splited / {p} / {list(map(lambda v: v.value, value_list))}")
        # logging.info(f"mediana {statistics.median(calc_ping)}")
        # logging.info(f"average {statistics.mean(calc_ping)}")

    # detecting modifiers

    def _is_delay_changed(self):
        s = len(self._collect)
        if s >= 2:
            last = self._collect[s - 1]
            before = self._collect[s - 2]
            changed = abs(last.delay - before.delay) > PING_ERROR
            if changed:
                upper = last.delay > before.delay
                return DelayChanged(changed, upper)
        return DelayChanged(False, False)

    def passive_detect_min(self):
        pass

    def passive_detect_double(self):
        pass

    def passive_detect_shuffle(self):
        delay_changed = self._is_delay_changed()
        logging.info(f'{delay_changed}')
        if delay_changed.is_changed:
            if not self.passive_detect_slow():
                return delay_changed
        return DelayChanged(False, False)

    def passive_detect_slow(self):
        s = len(self._collect)
        if s >= 1:
            last = self._collect[s - 1]
            if last.delay > MAX_COLLECT_PING:
                return True
            elif s >= 2:
                before = self._collect[s - 2]
                if last.delay > before.delay:
                    d = last.delay / before.delay
                    if round(d) == 2:
                        return True
        return False

    # todo:
    def passive_detect_revert(self):
        s = len(self._collect)
        c = self.get_patsaki()
        logging.info(f"Sousung on pipe = {c}")
        if s >= 2:
            last = self._collect[s - 1]
            before = self._collect[s - 2]
            if last.value == before.value:
                return True
            elif s >= 3:
                bbefore = self._collect[s - 3]
                return bbefore.value == last.value
        pass

    # todo:
    def get_ping_error(self):
        v_len = len(self._value)
        c_len = len(self._collect)
        error_p = 0
        if v_len >= 2:
            error_p = max(map(lambda v: v.delay - VALUE_PING, self._value))
        elif c_len >= 2:
            last_delay = self._collect[c_len - 1].delay
            error_cup = []
            for c_i in range(c_len):
                c_i *= -1
                c = self._collect[c_i]
                error = abs(c.delay - last_delay)
                if error <= PING_ERROR:
                    error_cup.append(error)
            error_p = max(error_cup)
        if error_p > 0:
            if self._calculated_ping_value >= error_p:
                return self._calculated_ping_value
            else:
                self._calculated_ping_value = error_p
                return error_p
        return PING_ERROR

    # deprecated

    def get_last_collect(self) -> CollectResult:
        return self._collect[-1]

    def calculate_prog_score(self):
        batches = self._get_collect_batches()
        l = len(batches)
        if l > 0:
            s = 0
            for i in range(l):
                bat = batches[i]
                f = bat[0]
                if l - 1 == i:
                    now = time.time()
                    a = now - (f.time - f.delay)
                    b = round(a / f.delay)
                    c = b * (55 / 10)
                else:
                    next_bat = batches[i + 1]
                    next_f = next_bat[0]
                    a = (next_f.time - next_f.delay) - (f.time - f.delay)
                    b = round(a / f.delay)
                    c = b * (55 / 10)
                s += c
            return s
        return UNDEFINED_VALUE


class Gravitsapa:
    def __init__(self):
        self._pipe1 = Pipe(1)
        self._pipe2 = Pipe(2)
        self._pipe3 = Pipe(3)
        self._pipes = (self._pipe1, self._pipe2, self._pipe3)

        self._detector1 = PipeDetector()
        self._detector2 = PipeDetector()
        self._detector3 = PipeDetector()
        self._detectors = (self._detector1, self._detector2, self._detector3)

        self._targetPipe_i = 0

        self.score = 0
        self.gameSeconds = 0

        self._all_selects = list(map(self._pipe_to_select, self._pipes))

        other = list(filter(lambda p: p.i != self._targetPipe_i, self._pipes))
        self._other = list(map(self._pipe_to_select, other))

    def _collect(self, pipe: Pipe):
        response = pipe.collect()
        self.gameSeconds += response.delay
        self._get_detector(pipe).log_collect(response)
        logging.info(f"Collected value {response.value} ({response.delay:.2f})")
        self.score += response.value
        return response

    def _value(self, pipe: Pipe):
        response = pipe.value()
        self.gameSeconds += response.delay
        self._get_detector(pipe).log_value(response)
        logging.info(f"Check value {response.value} ({response.delay:.2f})")
        return response

    def _modifier(self, pipe: Pipe, modifier: PipeModifier):
        response = pipe.modifier(modifier)
        self.gameSeconds += response.delay
        self._get_detector(pipe).log_modifier(response)
        if response.applied:
            logging.info(f"Modifier {modifier.name} to {pipe.index} ({response.delay})")
        elif response.alreadyOrEnoughScore:
            if self.score >= modifier.cost:
                logging.info(f"No cost for modifier {modifier.name} to {pipe.index} ({response.delay})")
            else:
                logging.info(f"Modifier {modifier.name} already on {pipe.index} ({response.delay})")
        else:
            pass
        if response.applied:
            self.score -= modifier.cost
        return response

    def _target_pipe(self):
        return self._pipes[self._targetPipe_i]

    def _select(self, pipe_i: int):
        logging.info(f'Select Pipe {pipe_i + 1}')
        self._targetPipe_i = pipe_i

    # pub

    def collect(self):
        return self._collect(self._target_pipe())

    def value(self):
        return self._value(self._target_pipe())

    def modifier(self, modifier: PipeModifier):
        return self._modifier(self._target_pipe(), modifier)

    def smart_collect(self):
        last_collect = self.get_detector().get_last_collect()
        patsaki = self.get_detector().get_patsaki()
        if patsaki != UNDEFINED_VALUE:
            if patsaki == 2:
                if last_collect.value % 2 != 0:
                    time.sleep(0.11)
        return self.collect()

    # select

    def get_all(self):
        return self._all_selects

    def _pipe_to_select(self, p: Pipe):
        if p.index == 1:
            return self.select1
        elif p.index == 2:
            return self.select2
        elif p.index == 3:
            return self.select3

    def get_other(self):
        return self._other

    # detector

    def _get_detector(self, pipe: Pipe) -> PipeDetector:
        return self._detectors[pipe.i]

    def get_detector(self) -> PipeDetector:
        return self._detectors[self._targetPipe_i]

    # ping

    def get_ping_error(self):
        error_cup = []
        for d in self._detectors:
            error = d.get_ping_error()
            if error != PING_ERROR:
                error_cup.append(error)
        if len(error_cup) > 0:
            return max(error_cup)
        else:
            return PING_ERROR

    # ext

    def current(self):
        index = self._targetPipe_i + 1
        if index == 1:
            return self.select1
        elif index == 2:
            return self.select2
        elif index == 3:
            return self.select3

    def select(self, pipe_index):
        self._select(pipe_index - 1)

    def select1(self):
        self._select(0)

    def select2(self):
        self._select(1)

    def select3(self):
        self._select(2)


# Смена направления: за 30 очков направление (уменьшение или увеличение) указанного эндпоинта меняется на противоположное
MREVERSE = PipeModifier("reverse", 30)
# Удвоение: за 40 очков следующие 8 запросов от любых участников дадут удвоенное количество очков от каждого запроса на указанном эндпоинте
MDOUBLE = PipeModifier("souble", 40)
# Замедление: за 40 очков у указанного эндпоинта будет удвоенное время ответа на ближайшие 10 запросов
MSLOW = PipeModifier("slow", 40)
# Перетасовка: за 10 очков у заданного эндпоинта будет сброшено время задержки и сгенерировано новое (случайно)
MSHUFFLE = PipeModifier("shuffle", 10)
# Обнуление: за 10 очков указанный эндпоинт 3 раза выдаст 1 очко. После этого поведение будет стандартным.
MMIN = PipeModifier("min", 10)

gravitsapa = Gravitsapa()

if DEBUG:
    handler = logging.StreamHandler()
    handler.terminator = "Ъ"
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.INFO,
        datefmt='%H:%M:%S',
        handlers=[handler])
else:
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.INFO,
        datefmt='%H:%M:%S')
logging.info("DEBUG = %s", DEBUG)
logging.info("VERSION = %s", "G")


def sorted_pipes_by_value():
    valstat = {}
    for select in gravitsapa.get_all():
        select()
        valstat[select] = gravitsapa.value().value
    return sorted(valstat, key=valstat.get)


def best_pipe_by_value():
    valstat = {}
    for select in gravitsapa.get_all():
        select()
        value = gravitsapa.value().value
        if value == MAX_PIPE_VALUE:
            return select
        else:
            valstat[select] = value
    return max(valstat, key=valstat.get)


def best_pipe_by_delay():
    valstat = {}
    for select in gravitsapa.get_all():
        select()
        valstat[select] = gravitsapa.get_detector().get_last_collect().delay
    return min(valstat, key=valstat.get)


def huiplet():
    zalupa_mute = 0

    while True:
        for select in gravitsapa.get_all():
            select()
            gravitsapa.collect()
        best_pipe_by_delay()()

        while True:
            if gravitsapa.gameSeconds <= zalupa_mute:
                zalupa_mute = 0
            if zalupa_mute == 0 and random.choice((True, False)) and gravitsapa.score >= MMIN.cost:
                if gravitsapa.modifier(MMIN).applied:
                    for select in gravitsapa.get_other():
                        select()
                        gravitsapa.collect()
                    best_pipe_by_delay()()
                    zalupa_mute = gravitsapa.gameSeconds + 15 * gravitsapa.get_detector().get_last_collect().delay
            elif random.choice((True, False)) and gravitsapa.score >= MSHUFFLE.cost:
                ping = gravitsapa.get_detector().get_last_collect().delay
                if gravitsapa.modifier(MSHUFFLE).applied:
                    gravitsapa.collect()
                    if ping < gravitsapa.get_detector().get_last_collect().delay:
                        for select in gravitsapa.get_other():
                            select()
                            gravitsapa.collect()
                        best_pipe_by_delay()()
                    zalupa_mute = gravitsapa.gameSeconds + 15 * gravitsapa.get_detector().get_last_collect().delay
            elif random.choice((True, False)) and gravitsapa.score >= MREVERSE.cost:
                gravitsapa.modifier(MREVERSE)
            gravitsapa.collect()


def huipletOnlyShuffle():
    zalupa_mute = 0

    while True:
        for select in gravitsapa.get_all():
            select()
            gravitsapa.collect()
        best_pipe_by_delay()()

        while True:
            if gravitsapa.gameSeconds <= zalupa_mute:
                zalupa_mute = 0
            if gravitsapa.score >= MSHUFFLE.cost:
                ping = gravitsapa.get_detector().get_last_collect().delay
                if gravitsapa.modifier(MSHUFFLE).applied:
                    gravitsapa.collect()
                    if ping < gravitsapa.get_detector().get_last_collect().delay:
                        for select in gravitsapa.get_other():
                            select()
                            gravitsapa.collect()
                        best_pipe_by_delay()()
                    zalupa_mute = gravitsapa.gameSeconds + 15 * gravitsapa.get_detector().get_last_collect().delay
            gravitsapa.collect()


def pepelats():
    # todo добавить условий на проверку, если это лучшая из возможных труб, вернуть сразу
    def pipe_is_best():
        last_collect = gravitsapa.get_detector().get_last_collect()
        last_delay = last_collect.delay
        return last_delay <= MIN_COLLECT_PING + PING_ERROR

    def _get_min_delay():
        min_delay = UNDEFINED_VALUE
        for select in gravitsapa.get_all():
            select()
            delay = gravitsapa.get_detector().get_last_collect().delay
            if min_delay > delay:
                min_delay = delay
        return min_delay

    def _select_by_delay(select_list):
        curr = gravitsapa.current()
        delay_by_select = {}
        for select in select_list:
            select()
            delay_by_select[select] = gravitsapa.get_detector().get_last_collect().delay
        curr()
        return delay_by_select

    def select_by_min_delay(select_list):
        delay_by_select = _select_by_delay(select_list)
        return min(delay_by_select, key=delay_by_select.get)

    def select_by_middle_delay(select_list):
        delay_by_select = _select_by_delay(select_list)
        mind = min(delay_by_select, key=delay_by_select.get)
        maxd = max(delay_by_select, key=delay_by_select.get)
        for select in delay_by_select:
            if select != mind and select != maxd:
                return select

    def select_by_max_delay(select_list):
        delay_by_select = _select_by_delay(select_list)
        return max(delay_by_select, key=delay_by_select.get)

    # проверено
    def passive_ping_point_calculate():
        current = gravitsapa.current()
        delay = gravitsapa.get_detector().get_last_collect().delay
        our_avg = 55 / (10 * delay)
        min_delay_select = select_by_min_delay(gravitsapa.get_all())
        min_delay_select()
        best_delay = gravitsapa.get_detector().get_last_collect().delay
        best_avg = 55 / (10 * best_delay)
        ping_range = best_delay - MIN_COLLECT_PING
        percent_of_shuffle = ((MIN_COLLECT_PING + ping_range) / 2 - 0.11) / 2.9
        value_range = 55 / (10 * ping_range)
        avg_range = (55 + value_range) / 2
        waiting_profit = avg_range * percent_of_shuffle
        current()
        return waiting_profit > our_avg

    # проверена
    def is_best_score_delta():
        curr = gravitsapa.current()
        main = gravitsapa.get_detector().calculate_prog_score()
        for select in gravitsapa.get_other():
            select()
            other = gravitsapa.get_detector().calculate_prog_score()
            delta = other - main
            if delta > 0:
                curr()
                return False
        curr()
        return True

    presser_starter_counter = 0

    def presser_starter(select_to_press=None):
        nonlocal presser_starter_counter

        if select_to_press is None:
            select_to_press = gravitsapa.get_all()
        current = gravitsapa.current()

        logging.info('def presser_starter')

        max_range = MAX_COLLECT_PING
        if presser_starter_counter == 1:
            max_range = 2.3
        if presser_starter_counter == 2:
            max_range = 1.8

        presser_starter_counter += 1

        for main_select in select_to_press:
            logging.info(f'main_select = {main_select}')
            main_select()
            gravitsapa.collect()
            min_range = 1.6
            while True:
                while gravitsapa.score <= MSHUFFLE.cost:
                    select_by_min_delay(select_to_press)()
                    gravitsapa.collect()
                main_select()
                delay = gravitsapa.get_detector().get_last_collect().delay
                if min_range <= delay <= max_range:
                    break
                else:
                    modified = gravitsapa.modifier(MSHUFFLE)
                    if modified.applied:
                        gravitsapa.collect()
                        if min_range > 1.0:
                            min_range -= 0.1
                        else:
                            break
        current()

    def adaptive_press_current_pipe():
        curr = gravitsapa.current()
        curr()

    azino_select = None

    def calculate_azino_select():
        if azino_select:
            select = select_by_max_delay(gravitsapa.get_other())
        else:
            select = select_by_middle_delay(gravitsapa.get_all())
        return select

    def recheck_azino_select():
        azino_select = make_recheck()
        azino_select()

    azino_select = None
    azino_in_progress = False
    azino_is_completed = False
    azino_startup = 0

    def init():
        nonlocal azino_select, azino_startup
        presser_starter()

        other_make_shuffle = False

        selects_to_press = []
        for select in gravitsapa.get_all():
            select()
            gravitsapa.collect()

        for select in gravitsapa.get_all():
            select()
            gravitsapa.collect()
            if gravitsapa.get_detector().passive_detect_shuffle().is_changed:
                other_make_shuffle = True
                selects_to_press.append(select)

        if other_make_shuffle and len(selects_to_press) > 0:
            presser_starter(select_to_press=selects_to_press)

        azino_startup = gravitsapa.gameSeconds + 14

    def initAzino():
        nonlocal azino_select, azino_startup, azino_in_progress
        logging.info(f'Init Azino')
        azino_in_progress = True
        azino_select = calculate_azino_select()
        azino_select()

    def make_recheck():
        logging.info(f'def make_recheck')
        for select in gravitsapa.get_other():
            select()
            gravitsapa.collect()
            if pipe_is_best():
                return select
        select = select_by_min_delay(gravitsapa.get_all())
        return select

    for select in gravitsapa.get_all():
        select()
        gravitsapa.collect()

    f_select_for_beat = select_by_max_delay(gravitsapa.get_all())
    f_member_escape = 0

    while True:
        if gravitsapa.score >= 200:
            logging.info(f'{gravitsapa.score} score collected!')
            break

        if f_member_escape >= 5:
            logging.info('f_member_escape and rechk')
            f_member_escape = 0
            make_recheck()

        current_select = select_by_min_delay(gravitsapa.get_all())
        current_select()

        last_collect = gravitsapa.get_detector().get_last_collect()
        if last_collect.delay <= 0.7:
            collected = gravitsapa.collect()
        elif gravitsapa.score >= MSHUFFLE.cost:
            f_select_for_beat()
            gravitsapa.modifier(MSHUFFLE)
            gravitsapa.collect()
            current_select()
        else:
            collected = gravitsapa.collect()


        patsaki = gravitsapa.get_detector().get_patsaki()
        if gravitsapa.get_detector().passive_detect_shuffle().is_changed:
            logging.info('shuffled is detected')
            make_recheck()
        elif patsaki < 4 and patsaki != 1:
            f_member_escape += 1

    init()

    f_member_escape = 0

    while True:
        logging.info(f'azino_is_completed={azino_is_completed}')
        logging.info(f'azino_in_progress={azino_in_progress}')

        if not azino_in_progress and azino_startup > 0 and gravitsapa.gameSeconds >= azino_startup:
            initAzino()
            azino_startup = 0

        if azino_in_progress:
            azino_select()

            make_shuffle = passive_ping_point_calculate()
            logging.info(f'make_shuffle = {make_shuffle}')
            if not azino_is_completed:
                if not make_shuffle:
                    logging.info('Azino is completed!')
                    azino_is_completed = True
                    recheck_azino_select()

            sosund_changes = gravitsapa.get_detector().sosuns_changed_from(r_value=1)
            only_my_patsak = sosund_changes == 0

            if not only_my_patsak:
                logging.info(f'{sosund_changes} peoples on pipe')
                if sosund_changes == 1:
                    last_delay = gravitsapa.get_detector().get_last_collect().delay
                    if last_delay < _get_min_delay():
                        pass
                    elif gravitsapa.score >= MSHUFFLE.cost:
                        pass
                elif sosund_changes >= 2:
                    logging.info(f"Guest detected")

                    # best_delta = is_best_score_delta()
                    # if best_delta:
                    #     logging.info(f"Delta is best")
                    # else:
                    #     logging.info(f"")
                    #     # mark_stalkerok_detector
                    #     # azino_select = calculate_azino_select()
                    #     # make_azino_collect()
                    #     # continue
                    #     pass

            if azino_in_progress:
                if azino_is_completed:
                    if gravitsapa.get_detector().passive_detect_shuffle().is_changed:
                        make_recheck()
                    gravitsapa.smart_collect()
                else:
                    shuffled = gravitsapa.modifier(MSHUFFLE)
                    if shuffled.applied:
                        gravitsapa.smart_collect()
                        continue

        else:
            patsaki = gravitsapa.get_detector().get_patsaki()
            logging.info(f'patsaki = {patsaki}')
            if patsaki < 4 and patsaki != 1 or gravitsapa.get_detector().passive_detect_shuffle().is_changed:
                f_member_escape += 1

            if gravitsapa.get_detector().passive_detect_shuffle().is_changed:
                make_recheck()
                pass
            elif f_member_escape >= 5:
                select = make_recheck()
                select()
                f_member_escape = 0

            select_by_min_delay(gravitsapa.get_all())()
            gravitsapa.smart_collect()

        logging.info('')

        # elif мы одни на трубе последние 8 коллектов:
        #     применить комбинацию shuffle + double
        # elif sosuns == 2:
        #     # переключаемся на четные
        #     pass
        # elif sosuns == 4:
        #     # играем в shuffle на средней трубе до лучшего пинга
        #     pass


# todo: два варианта пинга труб на старте используя value и collect

# todo: получение кол-ва игроков - DONE
# todo: вынести коллект в другой поток
# todo: считать время игры по пингам - DONE

# todo: считать ошибку в задерже через константные запросы и убрать ERROR_PING

# todo: использовать реверс для ошибочной калькуляции профита у соперника

# генерировать запросы в моменте задержки предыдущего коллекта
# todo никак не работает при малых задержках 0.2 0.4
def strategyCalcProfitBySailentValue():
    # strategyCalcProfitBySailentValuewITHOUTCollect()
    TIME_VALUE_CHECKS = 5.0
    def_select = gravitsapa.select2
    def_select()

    # pipes_to_check = gravitsapa.get_other()
    pipes_to_check = [gravitsapa.select3]
    time_to_stop_value_checks = TIME_VALUE_CHECKS

    while True:
        def_select()
        collected = gravitsapa.collect()
        gravitsapa.value()

        if len(pipes_to_check) > 0:
            rdelay = collected.delay

            ping_error = PING_ERROR

            # todo: делает больше запросов чем нужно и пропускает очередь
            print(f"rdelay = {rdelay}")
            print(f"VALUE_PING + ping_error = {VALUE_PING + ping_error}")
            print(f"ping_error * 2 = {ping_error * 2}")
            value_sends_possible_count = int(((rdelay / (VALUE_PING + ping_error)) + ping_error * 2)) - 2

            logging.info(f"Making {value_sends_possible_count} value requests")
            if value_sends_possible_count > 0:
                pipes_to_check[0]()
                for i in range(0, value_sends_possible_count):
                    valued = gravitsapa.value()
                    time_to_stop_value_checks -= valued.delay
                    if time_to_stop_value_checks <= 0:
                        gravitsapa.get_detector().pipe_alitycs_data()
                        time_to_stop_value_checks = TIME_VALUE_CHECKS
                        pipes_to_check.pop(0)

        else:
            logging.info("New checking all pipes is started")
            pipes_to_check = gravitsapa.get_other()
            time_to_stop_value_checks = TIME_VALUE_CHECKS


def strategyCalcProfitBySailentValuewITHOUTCollect():
    TIME_VALUE_CHECKS = 5.0
    def_select = gravitsapa.select2
    def_select()

    # pipes_to_check = gravitsapa.get_other()
    pipes_to_check = [gravitsapa.select3]
    time_to_stop_value_checks = TIME_VALUE_CHECKS

    while True:
        def_select()
        # collected = gravitsapa.collect()
        if len(pipes_to_check) > 0:
            rdelay = TIME_VALUE_CHECKS

            ping_error = PING_ERROR
            # todo: делает больше запросов чем нужно и пропускает очередь
            value_sends_possible_count = int(((rdelay / (VALUE_PING + ping_error)) + ping_error * 2))
            logging.info(f"Making {value_sends_possible_count} value requests")
            if value_sends_possible_count > 0:
                pipes_to_check[0]()
                for i in range(0, value_sends_possible_count):
                    valued = gravitsapa.value()
                    time_to_stop_value_checks -= valued.delay
                    if time_to_stop_value_checks <= 0:
                        gravitsapa.get_detector().pipe_alitycs_data()
                        time_to_stop_value_checks = TIME_VALUE_CHECKS
                        pipes_to_check.pop(0)

        else:
            logging.info("New checking all pipes is started")
            pipes_to_check = gravitsapa.get_other()
            time_to_stop_value_checks = TIME_VALUE_CHECKS


def experementDanilaKrazy():
    def update():
        gravitsapa.select1()
        gravitsapa.collect()
        gravitsapa.select2()
        gravitsapa.collect()
        gravitsapa.select3()
        gravitsapa.collect()
        best_pipe_by_delay()()

    update()

    iters = 0
    nmin = 0

    while True:
        if iters == 10:
            update()
            iters = 0

        delay = gravitsapa.get_detector().get_last_collect().delay + PING_ERROR

        if nmin == 0 and 150 < gravitsapa.gameSeconds < 170:
            gravitsapa.modifier(MMIN)
            time.sleep(delay * 3 * 1)
            nmin += 1
        elif nmin == 1 and 170 < gravitsapa.gameSeconds < 190:
            gravitsapa.modifier(MMIN)
            time.sleep(delay * 3)
            gravitsapa.modifier(MMIN)
            time.sleep(delay * 3)
            nmin += 1
        elif nmin == 2 and 190 < gravitsapa.gameSeconds < 210:
            gravitsapa.modifier(MMIN)
            time.sleep(delay * 3)
            gravitsapa.modifier(MMIN)
            time.sleep(delay * 3)
            gravitsapa.modifier(MMIN)
            time.sleep(delay * 3)
            nmin += 1
        elif nmin == 3 and 210 < gravitsapa.gameSeconds < 230:
            gravitsapa.modifier(MMIN)
            time.sleep(delay * 3)
            gravitsapa.modifier(MMIN)
            time.sleep(delay * 3)
            gravitsapa.modifier(MMIN)
            time.sleep(delay * 3)
            gravitsapa.modifier(MMIN)
            time.sleep(delay * 3)
            nmin += 1

        iters += 1
        gravitsapa.collect()


def experementSosunsChangedFrom():
    gravitsapa.select2()
    while True:
        logging.info(f"{gravitsapa.get_detector().sosuns_changed_from(1)}")
        gravitsapa.collect()


def experementDeltaScore():
    for select in gravitsapa.get_all():
        select()
        gravitsapa.collect()

    last_checked = None
    next_update_data = 60

    target_pipe = gravitsapa.select2
    target_pipe()

    while True:
        logging.info(f"Score = {gravitsapa.score}")

        if gravitsapa.gameSeconds >= next_update_data:
            next_update_data += 60
            o = gravitsapa.get_other()
            if last_checked is not None and last_checked in o:
                o.remove(last_checked)
            for select in o:
                select()
                gravitsapa.collect()
                last_checked = select
            target_pipe()

        target_pipe()
        css = gravitsapa.get_detector().calculate_prog_score()
        for select in gravitsapa.get_other():
            select()
            ss = gravitsapa.get_detector().calculate_prog_score()
            logging.info(f"delat {ss - css} for {select}")
        target_pipe()

        gravitsapa.collect()


def experementAzino777():
    # проверена
    def select_by_delay_on_start():
        curr = gravitsapa.current()
        for select in gravitsapa.get_all():
            select()
            gravitsapa.collect()
        delay_by_select = {}
        for select in gravitsapa.get_all():
            select()
            last_collect = gravitsapa.get_detector().get_last_collect()
            delay_by_select[select] = last_collect.delay
        curr()
        return min(delay_by_select, key=delay_by_select.get)

    # проверена
    def select_by_max_delay():
        curr = gravitsapa.current()
        delay_by_select = {}
        for select in gravitsapa.get_all():
            select()
            last_collect = gravitsapa.get_detector().get_last_collect()
            delay_by_select[select] = last_collect.delay
        curr()
        return max(delay_by_select, key=delay_by_select.get)

    # проверена
    def _select_by_delay(select_list):
        curr = gravitsapa.current()
        delay_by_select = {}
        for select in select_list:
            select()
            delay_by_select[select] = gravitsapa.get_detector().get_last_collect().delay
        curr()
        return delay_by_select

    # проверена
    def select_by_min_delay(select_list):
        delay_by_select = _select_by_delay(select_list)
        return min(delay_by_select, key=delay_by_select.get)

    # проверена
    def passive_ping_point_calculate():
        curr = gravitsapa.current()
        delay = gravitsapa.get_detector().get_last_collect().delay
        our_avg = 55 / (10 * delay)
        min_delay_select = select_by_min_delay(gravitsapa.get_all())
        min_delay_select()
        best_delay = gravitsapa.get_detector().get_last_collect().delay
        best_avg = 55 / (10 * best_delay)
        ping_range = best_delay - MIN_COLLECT_PING
        percent_of_shuffle = ((MIN_COLLECT_PING + ping_range) / 2 - 0.11) / 2.9
        value_range = 55 / (10 * ping_range)
        avg_range = (55 + value_range) / 2
        waiting_profit = avg_range * percent_of_shuffle
        curr()
        return waiting_profit > our_avg

    # проверена
    def update_delay_info():
        current = gravitsapa.current()
        for select in gravitsapa.get_other():
            select()
            gravitsapa.collect()
        current()

    # проверена
    def presser_starter():
        current = gravitsapa.current()
        all_selects = gravitsapa.get_all()
        for select in all_selects:
            select()
            min_range = 1
            max_range = 3
            while True:
                min_delay = select_by_min_delay(all_selects)
                while gravitsapa.score <= MSHUFFLE.cost:
                    min_delay()
                    gravitsapa.collect()
                select()
                delay = gravitsapa.get_detector().get_last_collect().delay
                if min_range <= delay <= max_range:
                    break
                else:
                    modified = gravitsapa.modifier(MSHUFFLE)
                    if modified.applied:
                        gravitsapa.collect()
        current()

    # проверена
    def make_money_with_checks(seconds):
        current = gravitsapa.current()
        select = select_by_min_delay(gravitsapa.get_all())
        select()
        wait_to = gravitsapa.gameSeconds + seconds
        collect_count = 0
        while gravitsapa.gameSeconds <= wait_to:
            collect_count += 0
            if collect_count % 10 == 0:
                collect_count = 0
                update_delay_info()
                select = select_by_min_delay(gravitsapa.get_all())
                select()
        current()

    # проверена
    def collect_empty_pipe():
        cur = gravitsapa.current()
        selectors = gravitsapa.get_all()
        for select in selectors:
            select()
            gravitsapa.collect()
        for select in selectors:
            select()
            gravitsapa.collect()
        potsaki_by_select = {}
        for select in selectors:
            potsaki_by_select[select] = gravitsapa.get_detector().get_patsaki()
        cur()
        return min(potsaki_by_select, key=potsaki_by_select.get)

    logging.info('Start collect')
    select_by_delay_on_start()()

    while gravitsapa.gameSeconds <= 10:
        logging.info(f'Ping {gravitsapa.get_detector().get_ping_error()}')
        gravitsapa.collect()

    select_by_delay_on_start()()
    while gravitsapa.gameSeconds <= 20:
        logging.info(f'Ping {gravitsapa.get_detector().get_ping_error()}')
        gravitsapa.collect()

    select_by_delay_on_start()()
    while gravitsapa.gameSeconds <= 30:
        logging.info(f'Ping {gravitsapa.get_detector().get_ping_error()}')
        gravitsapa.collect()

    select_by_delay_on_start()()
    while gravitsapa.gameSeconds <= 40:
        logging.info(f'Ping {gravitsapa.get_detector().get_ping_error()}')
        gravitsapa.collect()

    logging.info('Start update delays')
    update_delay_info()

    logging.info('Presser start')
    presser_starter()

    empty_select = collect_empty_pipe()
    empty_select()

    while True:
        logging.info(f'current {gravitsapa.current()}')
        collected = gravitsapa.collect()
        patsaki = gravitsapa.get_detector().get_patsaki()
        logging.info(f'Collected {collected.value}')
        logging.info(f'Score {gravitsapa.score}')

        logging.info(f'patsaki {patsaki}')
        if patsaki == 1 and passive_ping_point_calculate():
            logging.info('Shuffle to get goods')
            gravitsapa.modifier(MSHUFFLE)
        elif patsaki > 1:
            changes = gravitsapa.get_detector().sosuns_changed_from(patsaki - 1)
            logging.info(f'changes {changes}')
            if changes >= 3:
                logging.info(f'AaAaAaAa PEOPLE on the pipe! {patsaki}')
                logging.info('Presser start')
                presser_starter()
                make_money_with_checks(30)
                update_delay_info()
                empty_select = select_by_max_delay()
                empty_select()


def experementCollectFailureQueByValue():
    gravitsapa.select1()
    block_value_cup = False

    while True:
        gravitsapa.collect()
        gravitsapa.collect()
        collected = gravitsapa.collect()
        if block_value_cup == False:
            logging.info("start cup")
            posible_value = int(collected.delay / 0.23)
            logging.info(f"posible_value = {posible_value}")
            for i in range(0, posible_value):
                gravitsapa.value()
                block_value_cup = True
            logging.info("end cup")


def experementConcurency():
    # gravitsapa.select1()
    # collected = gravitsapa.collect()
    # while True:
    #     threading.Thread(target=gravitsapa.collect).start()
    #     # time.sleep(collected.delay - 0.1) не работает
    #     time.sleep(collected.delay - 0.01)
    #     gravitsapa.collect()
    gravitsapa.select1()
    valt = threading.Thread(target=gravitsapa.value)
    valt.start()
    gravitsapa.select2()
    valt = threading.Thread(target=gravitsapa.value)
    valt.start()
    gravitsapa.select3()
    valt = threading.Thread(target=gravitsapa.value)
    valt.start()

    valt.join()

    collt = threading.Thread(target=gravitsapa.collect)
    collt.start()
    valt = threading.Thread(target=gravitsapa.value)
    valt.start()

    collt.join()
    valt.join()

    collt = threading.Thread(target=gravitsapa.collect)
    collt.start()
    modt = threading.Thread(target=gravitsapa.modifier, args=[MMIN])
    modt.start()

    collt.join()
    modt.join()


def experementBaseBolda(pipe_index=1, changePipe=False, collectsToSwitch=6):
    gravitsapa.select(pipe_index)
    collects = 0
    while True:
        if collects == collectsToSwitch and changePipe:
            collects = 0
            random.choice(gravitsapa.get_other())()
        gravitsapa.collect()
        collects += 1


def experementHowReverseWork(timeout=None):
    gravitsapa.select1()
    while True:
        if gravitsapa.score >= MREVERSE.cost:
            gravitsapa.modifier(MREVERSE)
            if timeout:
                time.sleep(gravitsapa.get_detector().get_last_collect().delay)
        gravitsapa.collect()


def experementHowMinWork():
    gravitsapa.select1()
    while True:
        gravitsapa.modifier(MMIN)
        gravitsapa.collect()


def experementCalculatePipeProfitByCollect():
    gravitsapa.select1()
    while True:
        logging.info("")
        profit = gravitsapa.get_detector().passive_calculate_pipe_profit_by_collect()
        logging.info(f"Members = {gravitsapa.get_detector().get_patsaki()}")
        logging.info(f"Profit = {profit}")
        gravitsapa.collect()


def experementDetectSosuns():
    gravitsapa.select1()
    while True:
        if gravitsapa.score >= MREVERSE.cost:
            gravitsapa.modifier(MREVERSE)
        gravitsapa.collect()
        logging.info(f"Members = {gravitsapa.get_detector().get_patsaki()}")


def experementDetectRevert():
    gravitsapa.select1()
    while True:
        if gravitsapa.score >= MREVERSE.cost:
            gravitsapa.modifier(MREVERSE)
        gravitsapa.collect()
        logging.info(f"Revert detected = {gravitsapa.get_detector().passive_detect_revert()}")


def experementDetectSlow():
    gravitsapa.select1()
    while True:
        if gravitsapa.score >= MSLOW.cost:
            gravitsapa.modifier(MSLOW)
        gravitsapa.collect()
        logging.info(f"Slow detected = {gravitsapa.get_detector().passive_detect_slow()}")


def experementDetectShuffle():
    gravitsapa.select1()
    while True:
        if gravitsapa.score >= MSHUFFLE.cost:
            shuffled = gravitsapa.modifier(MSHUFFLE)
            gravitsapa.collect()
            logging.info(f"Slow detected = {gravitsapa.get_detector().passive_detect_shuffle()}")
            logging.info(f"Shuffled = {shuffled}")
        else:
            gravitsapa.collect()
            logging.info(f"Slow detected = {gravitsapa.get_detector().passive_detect_shuffle()}")


def experementBestPipeByCollect():
    def update_and_select_by_collect():
        for select in gravitsapa.get_all():
            select()
            gravitsapa.collect()
        best_pipe_by_delay()()

    t = time.time()
    update_and_select_by_collect()
    e = time.time() - t
    logging.info(f"search best pipe time = {e}")

    while True:
        if gravitsapa.get_detector().passive_detect_shuffle():
            update_and_select_by_collect()
        else:
            gravitsapa.collect()


def experementBestPipeByValue():
    def best_pipe_by_value():
        valstat = {}
        for select in gravitsapa.get_all():
            select()
            valstat[select] = gravitsapa.value().value
        return max(valstat, key=valstat.get)

    def update_and_best_by_collect():
        for select in gravitsapa.get_all():
            select()
            gravitsapa.collect()
        return best_pipe_by_delay()

    t = time.time()
    best_value_pipe = best_pipe_by_value()
    e = time.time() - t
    best_value_pipe()
    logging.info(f"search time = {e}")
    best_value_by_collect = update_and_best_by_collect()
    if best_value_pipe == best_value_by_collect:
        logging.info('found real best pipe')
    else:
        logging.info('found not best pipe')


def experementPipeToBestValue(best_ping):
    hist = {}
    shuffle_start_time = 0
    shuffle_try_count = 0
    while True:
        for select in gravitsapa.get_all():
            select()
            gravitsapa.collect()
            ping = gravitsapa.get_detector().get_last_collect().delay
            r = round(ping, 1)
            if r <= 1.0 and r not in hist:
                hist[r] = shuffle_try_count
            logging.info(f"hist = {hist}")
            if ping > best_ping:
                if gravitsapa.score >= MSHUFFLE.cost:
                    mod = gravitsapa.modifier(MSHUFFLE)
                    if mod.applied:
                        if shuffle_start_time == 0:
                            shuffle_start_time = gravitsapa.gameSeconds
                        shuffle_try_count += 1
            else:
                logging.info(
                    f"Best ping shuffled by {shuffle_try_count} try and {gravitsapa.gameSeconds - shuffle_start_time} secs")
                break

        # for select in gra.get_all():
        #     select()
        #     while True:
        #         shuffle_start_time = 0
        #         shuffle_try_count = 0
        #         while True:
        #             gra.collect()
        #             if gra.get_detector().get_last_collect().delay > best_ping:
        #                 if gra.score >= MSHUFFLE.cost:
        #                     mod = gra.modifier(MSHUFFLE)
        #                     if mod.applied:
        #                         if shuffle_start_time == 0:
        #                             shuffle_start_time = gra.gameTime
        #                         shuffle_try_count += 1
        #             else:
        #                 logging.info(
        #                     f"Best ping shuffled by {shuffle_try_count} try and {gra.gameTime - shuffle_start_time} secs")
        #                 break


def experementLogGetError():
    errors = []
    while True:
        error = gravitsapa.value().delay - VALUE_PING
        errors.append(error)
        logging.info(f"value get error = {error}")
        logging.info(f"min = {min(errors)}")
        logging.info(f"max = {max(errors)}")
        logging.info(f"mean = {mean(errors)}")
        gravitsapa.collect()


def shashekhi():
    # проверена
    def _select_by_delay(select_list):
        curr = gravitsapa.current()
        delay_by_select = {}
        for select in select_list:
            select()
            delay_by_select[select] = gravitsapa.get_detector().get_last_collect().delay
        curr()
        return delay_by_select

    # проверена
    def select_by_min_delay(select_list):
        delay_by_select = _select_by_delay(select_list)
        return min(delay_by_select, key=delay_by_select.get)

    def recheck_pipes_and_select_min():
        for select in gravitsapa.get_other():
            select()
            gravitsapa.collect()
        min_delay_select = select_by_min_delay(gravitsapa.get_all())
        min_delay_select()

    # for select in gravitsapa.get_all():
    #     select()
    #     gravitsapa.collect()
    #     gravitsapa.collect()
    #
    # min_delay_select = select_by_min_delay(gravitsapa.get_all())
    # min_delay_select()
    # logging.info(f'min_delay_select {min_delay_select}')

    wait_count = 0
    while True:
        gravitsapa.select1()
        # last_patsaki = gravitsapa.get_detector().get_patsaki()
        collected = gravitsapa.collect()
        patsaki = gravitsapa.get_detector().get_patsaki()
        # logging.info(f'last_patsaki {last_patsaki}')
        logging.info(f'patsaki {patsaki}')
        #
        # if last_patsaki != UNDEFINED_VALUE:
        #     if last_patsaki != patsaki:
        #         changes = gravitsapa.get_detector().sosuns_changed_from(r_value=last_patsaki)
        #         logging.info(f'changes {changes}')
        #         if changes > 1:
        #             recheck_pipes_and_select_min()

        if collected.value % 2:
            pass

        pirror = gravitsapa.get_detector().get_ping_error()
        logging.info(f'pingError = {pirror}')

        logging.info(f"cc={collected.value % 2}")

        if patsaki != UNDEFINED_VALUE:
            if patsaki == 2:
                if collected.value % 2 != 0:
                    logging.info(f'WAIT COUNT {wait_count}')
                    wait_count += 1
                    time.sleep(0.11)

        # pingError = 0.01836705207824707
        # 1.61
        # 100 * 0.1


if __name__ == '__main__':
    pepelats()
    # shashekhi()
