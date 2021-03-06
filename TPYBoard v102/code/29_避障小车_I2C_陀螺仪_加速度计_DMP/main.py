import pyb
from pyb import UART
from pyb import Pin
from pyb import Timer
from pyb import ExtInt
from mpu6050 import MPU6050

import micropython
micropython.alloc_emergency_exception_buf(100)

''' 电机驱动模块'''

#电机驱动管脚定义
left_motor1 = Pin('Y1', Pin.OUT_PP)#L298N,IN1 左侧电机1
left_motor2 = Pin('Y2', Pin.OUT_PP)#L298N,IN2 左侧电机2
right_motor1 = Pin('Y4', Pin.OUT_PP)#L298N,IN3,右侧电机1,前后反向，所以交换Y4,Y3定义
right_motor2 = Pin('Y3', Pin.OUT_PP)#L298N,IN4,右侧电机2

left_motor_forward_flag = 1 #左电机正转标志位
right_motor_forward_flag = 1 #右电机正转标志位


#设置电机PWM调速定时器
tim1 = Timer(1 , freq=125)
left_pwm = 0
right_pwm = 0

#设置左电机PWM通道，PWM_INVERTED时候占空比0-100为高电平比例
left_channel = tim1.channel(1, Timer.PWM_INVERTED, pin = Pin('Y6'))

#设置右电机PWM通道
right_channel = tim1.channel(2, Timer.PWM_INVERTED, pin = Pin('Y7'))

#左侧电机正转：
def left_motor_forward(left_pwm = 80):#默认PWM参数为80
    global left_motor_forward_flag
    left_motor_forward_flag = 1 #正转为1
    left_motor1.high()
    left_motor2.low()
    left_channel.pulse_width_percent(left_pwm)
    
#左侧电机反转：
def left_motor_reverse(left_pwm = 80):#默认PWM参数为80
    global left_motor_forward_flag
    left_motor_forward_flag = 0 #反转为0
    left_motor1.low()
    left_motor2.high()
    left_channel.pulse_width_percent(left_pwm)
    
#左侧电机停止：    
def left_motor_stop():
    left_motor1.high()
    left_motor2.high()

#右侧电机正转：
def right_motor_forward(right_pwm = 80):#默认PWM参数为80
    global right_motor_forward_flag
    right_motor_forward_flag = 1 #正转为1
    right_motor1.high()
    right_motor2.low()
    right_channel.pulse_width_percent(right_pwm)
    
#右侧电机正转：
def right_motor_reverse(right_pwm = 80):#默认PWM参数为80
    global right_motor_forward_flag
    right_motor_forward_flag = 0 #反转为0
    right_motor1.low()
    right_motor2.high()
    right_channel.pulse_width_percent(right_pwm)

#右侧电机停止：    
def right_motor_stop():
    right_motor1.high()
    right_motor2.high()


'''编码器模块'''

left_encoder = 0 #声明全局变量，左电机码盘脉冲值
right_encoder =0 #声明全局变量，右电机码盘脉冲值

#左编码器中断函数
def callback_left_encoder(line): 
    global left_encoder #再次声明，表示这里使用是全局变量
    global left_motor_forward_flag
    if left_motor_forward_flag: #判断正反转
        left_encoder += 1
    else:
        left_encoder -=1    
    
#右编码器中断函数    
def callback_right_encoder(line): 
    global right_encoder #再次声明，表示这里使用是全局变量
    global right_motor_forward_flag
    if right_motor_forward_flag: #判断正反转
        right_encoder += 1
    else:
        right_encoder -=1    

#定义左侧编码器中断
extint10 = pyb.ExtInt(Pin("B10"), ExtInt.IRQ_FALLING, pyb.Pin.PULL_UP,
    callback_left_encoder)  #左侧编码器中断，Y9脚

extint15 = pyb.ExtInt(Pin("B15"), ExtInt.IRQ_FALLING, pyb.Pin.PULL_UP,
    callback_right_encoder)  #右侧侧编码器中断，Y8脚

'''编码器测速'''
'''读取编码器，转化为rpm每分钟转速'''
#转速全局变量申明
left_rpm = 0 #左轮转速
right_rpm =0 #右轮转速

#通过一定时间内的编码器来计算每分钟的转速，0.5s周期
def caculate_speed(): 
    global left_rpm #左轮转速
    global right_rpm #右轮转速
    global left_encoder #左电机码盘脉冲值
    global right_encoder #右电机码盘脉冲值
    extint10.disable() #关闭编码器中断
    extint15.disable() #关闭编码器中断
    left_rpm = left_encoder*2*60/20 #每分钟转的圈数=0.5s编码器计数*2*每分钟60秒/码盘一圈20格子
    right_rpm = right_encoder*2*60/20 #每分钟转的圈数=0.5s编码器计数*2*每分钟60秒/码盘一圈20格子
    print
    left_encoder = 0 #编码器清零
    right_encoder = 0 #编码器清零
    #print("left_rpm=", left_rpm) #USB打印编码器数值
    #print("right_rpm=", right_rpm) #USB打印编码器数值
    #bluetooth.write("left_rpm="+str(left_rpm)+"\r\n") #蓝牙发送编码器数值
    #bluetooth.write("right_rpm="+str(right_rpm)+"\r\n") #蓝牙发送编码器数值
    extint10.enable() #开启编码器中断
    extint15.enable() #开启编码器中断   


speed_count = 0 #速度控制计数值，100，控制周期0.5s
speed_cotrol_flag = 0 #速度控制标志位置，置为1的时候运行caculate_speed()


#控制主程序 5ms定时器中断函数
#中断函数中要尽量减少语句，保证执行时间，另外中断函数中不支持浮点运算，所以将运算放在主循环中
def control(t): #中断函数需要有一个参数t
    global speed_count #代表使用的是全局变量
    global speed_cotrol_flag #代表使用的是全局变量
    if speed_count >=100: #速度控制计数值，100*5ms，控制周期0.5s
        speed_cotrol_flag = 1 #速度控制标志位置1
        speed_count = 0
    else:
        speed_count += 1
        
#定时器中断，定时5ms，每5ms执行control函数
#tim1已被电机PWM使用,我们这里选用定时器8
#频率为20Hz，回调函数为control
timer_control = Timer(8, freq=200 ,callback = control)#使用定时器8创建一个定时器对象    

'''蓝牙BLE模块'''
#使用串口4，蓝牙模块RX接X1，TX接X2,VCC接VIN，GND接GND
bluetooth = UART(4,115200)
bluetooth.init(115200, bits=8, parity=None, stop=1, timeout=50) #设置串口波特率及等待延时50ms


'''定义行走函数'''
def Stop():#停车
    left_motor_stop()
    right_motor_stop()
def Forward():#向前
    left_motor_forward(90)
    right_motor_forward(90)

def Backward():#向后
    left_motor_reverse(90)
    right_motor_reverse(90)    
    
def Left():#连续向左转
    left_motor_reverse(90)
    right_motor_forward(90)
    
def Right():#连续向右转
    left_motor_forward(90)
    right_motor_reverse(90)
    
def Left_90():#向左转90度
    Left()
    pyb.delay(700)
    Stop()  

def Right_90():#向右转90度
    Right()
    pyb.delay(700)
    Stop()   
    
'''陀螺仪、加速度计MPU6050'''       
#连接MPU6050到I2C1(SCL接X9,，SDA接X10)VCC接VIN,GND接GND
#可以使用MPU6050内部的数字运动处理器DMP(Digital Motion Processor)
#来处理运动感测的复杂数据，降低了运动处理运算对操作系统的负荷
mpu = MPU6050()
mpu.dmpInitialize()
mpu.setDMPEnabled(True)
packetSize = mpu.dmpGetFIFOPacketSize() 

'''主循环'''
#主循环程序
while True:
    #编码器计算速度
    if speed_cotrol_flag:#速度控制标志位置，置为1的时候运行caculate_speed()，每0.5s
        caculate_speed()
        speed_cotrol_flag = 0
    
    #蓝牙控制行走
    if bluetooth.any()>0:#蓝牙接收数据，控制行走
        data = bluetooth.read().decode()
        print(data)        
        if data.find('0')>-1:#0-停车
            Stop()
            print("stop") #USB打印
            bluetooth.write("stop\r\n") #蓝牙发送           
        if data.find('1')>-1:#1-向前
            Forward()
            print("forward")
            bluetooth.write("forward\r\n")       
        if data.find('2')>-1:#2-向后
            Backward()
            print("backward")
            bluetooth.write("backward\r\n")        
        if data.find('3')>-1:#0-向左
            Left_90()
            print("left")
            bluetooth.write("left\r\n")
        if data.find('4')>-1:#0-向左
            Right_90()
            print("right")
            bluetooth.write("right\r\n")           
            
    #MPU数据读取
    mpuIntStatus = mpu.getIntStatus()
    fifoCount = mpu.getFIFOCount()
    if mpuIntStatus < 2 or fifoCount == 1024:
        mpu.resetFIFO()
        print('FIFO overflow!')
        continue
    while fifoCount < packetSize:
        fifoCount = mpu.getFIFOCount()
    fifoCount -= packetSize
    fifoBuffer = mpu.getFIFOBytes(packetSize)
    yaw, rol, pit = mpu.dmpGetEuler(*mpu.dmpGetQuaternion(fifoBuffer))
    g_pit, g_rol, g_yaw = mpu.dmpGetGyro(fifoBuffer)
    yaw -= 6
    print(rol, pit, yaw, g_rol, g_pit, g_yaw)
                              
'''
在主循环前开启电机，尝试不同PWM测试速度值
发现给定相同的PWM下，左右电机有可能转速不一样，这样会导致小车走不直。
left_motor_forward()
right_motor_forward()
left_motor_reverse()
right_motor_reverse()
left_motor_stop()
right_motor_stop()
'''
