def calculate_pipe_k():
    collect_list = [3, 5, 7, 9,
                    1, 3, 5, 7, 9,
                    1, 3, 5,
                    3, 5, 7, 9,
                    1, 3, 5, 7, 9,
                    1, 3, 5, 7,
                    6, 8, 10,
                    2, 4, 6, 8, 10,
                    2, 4,
                    3, 5, 7, 9,
                    1, 3, 5, 7, 9,
                    1, 3, 5, 7, 9,
                    8, 10,
                    2, 4, 6, 8, 10,
                    2, 4, 6, 8,
                    6, 8, 10,
                    2, 4, 6, 8, 10,
                    2, 4,
                    3, 5, 7, 9,
                    1, 3, 5, 7, 9,
                    1, 3, 5, 7, 6, 8, 10,
                    2, 4, 6, 8, 10,
                    2, 4, 6,
                    5, 7, 9,
                    1, 3, 5]
    collect_len = len(collect_list)

    _batch = []
    batches = []
    for i in range(collect_len):
        curr = collect_list[i]
        if i == 0:
            _batch.append(curr)
        elif i == collect_len - 1:
            prev = collect_list[i - 1]
            if prev < curr:
                _batch.append(curr)
                batches.append(_batch)
            else:
                batches.append([curr])
        else:
            next = collect_list[i+1]
            if curr < next:
                _batch.append(curr)
            else:
                _batch.append(curr)
                batches.append(_batch)
                _batch = []

    for batch in batches:
        print(f"batch={batch}")
        m = batch + batch + batch + batch + batch
        print(f"benefit={sum(m[:10])}")


    print(batches)

if __name__ == '__main__':
    calculate_pipe_k()