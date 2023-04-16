def get_collect_last_step(history):
    hlen = len(history)
    if hlen > 1:
        result = history[hlen-1-1] - history[hlen-1]
        if result > 0:
            return result
        else:
            return -result
    return 0


def get_collect_normal_step(history):
    history_len = len(history)
    history = history[history_len-10:history_len]
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
    return max(steps, key=steps.get)

if __name__ == "__main__":
    history = [9, 5, 9, 5, 10, 5, 10, 6, 6, 1, 6, 1, 6]
    get_collect_normal_step(history)
    history = [1, 6, 1, 6, 1, 6]
    get_collect_normal_step(history)
