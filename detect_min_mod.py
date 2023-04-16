# [x,x,x,x,x,x,x,8,9,10]
# [x,x,x,x,x,x,x,8,1,1]
from get_collect_step import get_collect_normal_step


def detect_min_mod(chistory):
    nstep = get_collect_normal_step(chistory)
    len_h = len(chistory)
    if len_h >= 2:
        if (nstep == 1 or nstep == 2) and chistory[len_h-1] == 1 and chistory[len_h-2] == 1:
            return True
        for i in range(0, len_h):
            print(i)
    return False


if __name__ == '__main__':
    print(detect_min_mod([10, 1, 2, 3, 4, 5, 6, 7, 8, 9]))
    print(detect_min_mod([10, 1, 2, 3, 4, 5, 6, 7, 1, 1]))
    print(detect_min_mod([10, 9, 8, 7, 6, 5, 4, 3, 2, 1]))