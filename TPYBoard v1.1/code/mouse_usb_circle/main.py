import math
def osc(n,d):
    for i in range(n):
        hid.send((0,int(20*math.sin(i/10)),int(20*math.cos(i/10)),0))
        pyb.delay(d)
osc(100,50)
