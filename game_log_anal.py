import json

if __name__ == '__main__':
    with open('game_log.jsonl', 'r') as json_file:
        json_list = filter(lambda s: s is not "\n", list(json_file))


    # разницу между CollectEnd и CollectStart
    # разницу между score в UpdateUser
    # разницу между pipe_id в CollectStart

    logs = []
    for json_str in json_list:
        log = json.loads(json_str)
        logs.append(log)

    # logs = list(map(lambda s: json.loads(s), json_list))

    def find_log(list, type):
        list.reverse()
        for log in list:
            if log['msg']['type'] == type:
                return log
        return None

    ll = len(logs)
    for i in range(ll):
        log = logs[i]
        msg = log['msg']
        time = log['time']
        type = msg['type']
        if type == 'CollectStart':
            fl = find_log(logs[:i], 'CollectEnd')
            if fl is not None:
                print(f"{time}")
                lag = time - fl["time"]
                if lag > 0.02:
                    if lag > 0.2:
                        print(f'Value check {lag}')
                    else:
                        print(f'Lag {lag}')


    import json
    with open('game_log_out.json', 'w') as f:
        json.dump(logs, f, indent=' ')


    # logs = []
    # for json_str in json_list:
    #     log = json.loads(json_str)
    #     logs.append(log)
    #
    # def find_log(i, type):
    #     lr = logs[:i]
    #     lr.reverse()
    #     for l in lr:
    #         m = l['msg']
    #         t = m['type']
    #         if t == type:
    #             return l['time']
    #     return None
    #
    # for log_i in range(len(logs)):
    #     log = logs[log_i]
    #     msg = log['msg']
    #     type = msg['type']
    #     time = log['time']
    #     if type == 'CollectStart':
    #         t = find_log(log_i, 'CollectEnd')
    #         if t is not None:
    #             time_diff = time - t
    #             log['time_diff'] = time_diff
    #             logs[log_i] = log
    #             print(f"time_diff={time_diff}")
    #         pass
    #     elif type == 'UpdateUser':
    #         d = find_log(log_i, 'UpdateUser')
    #         'score_diff'
    #         pass

    # import json
    # with open('game_log_out.json', 'w') as f:
    #     json.dump(logs, f, indent=' ')



    # решение 1
    # users = {}

    # for json_str in json_list:
    #     log = json.loads(json_str)
    #     msg = log['msg']
    #     if 'user' in msg:
    #         user = msg['user']
    #         if user not in users:
    #             users[user] = []
    #         type = msg['type']
    #         if type == 'UpdateUser':
    #             users[user].append(log)

    # for user in users:
    #     user = users[user]
    #     for i in range(len(user)):
    #         log = user[i]
    #         time = log['time']
    #         msg = log['msg']
    #         if i == 0:
    #             pass
    #         else:
    #             prev_log = user[i - 1]
    #             prev_msg = prev_log['msg']
    #             msg['change'] = msg["score"] - prev_msg["score"]
    #             log['msg'] = msg
    #             users[user][i] = msg

    # print(f"{users}")



