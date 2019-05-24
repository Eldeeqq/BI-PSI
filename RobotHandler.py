from commands import CMD
from tools import *
import socket
import re
import sys
import os
import random

stages = ['HASH_COMPUTE', 'CONF_CHECK', 'LOCATE', 'FIND_CORNER', 'MESSAGE' ]
stage_len = {'HASH_COMPUTE': 12, 'CONF_CHECK': 12, 'LOCATE': 12, 'FIND_CORNER': 12, 'MESSAGE': 100}
DIRECTIONS = ['UP', 'RIGHT', 'DOWN', 'LEFT']

class RobotHandler:

    def __init__(self, conn):
        self.connection = conn
        self.CHECKED = []
        self.actual_stage = 0
        self.message = ''
        self.buffered = ''

        self.hash = 0
        self.stage = 0
        self.random_id = random.randint(-1000,1000)
        self.robot_direction = 0

        self.desired_x = -2
        self.desired_y = -2
        self.recharging = False
        self.x, self.y = None, None
    """
    Method used to buffer messages
    It reads from connection untill the '\a\b' is found
    """
    def buffer(self):
        if '\a\b' not in self.message:
            while True:
                recieved = self.connection.recv(1024).decode('ascii')
                # client not responding
                if not recieved:
                    break
                #print("["+str(self.random_id)+"] ","recieved: ", bytes(recieved, 'ascii'), len(bytes(recieved, 'ascii')))
                self.message += recieved

                # message is larger than max size of message in stage
                if len(recieved) >= stage_len[stages[self.stage]] and '\a\b' not in recieved:
                    raise SyntaxError
                # at least one message has been loaded
                if '\a\b' in recieved or '\a\b' in self.message:
                    break

        return

    """
    Extracts single message from buffered string
    :returns decoded string message
    """
    def _get_message(self):
        self.buffer()
        delimeter_idx = self.message.find('\a\b')
        if delimeter_idx == -1:
            return ''
        delimeter_idx += 2
        message = self.message[:delimeter_idx]
        #print("["+str(self.random_id)+"] ","buffer ", self.message)
        self.message = self.message[delimeter_idx:]
        return message

    """
    Method tests correct behavior of client
    if client is recharging, it tests if it recieved 'FULL POWER\a\b' message 
    :param recieved message
    :raises LogicError if 
    :returns True if in recharging state, False otherwise    
    """
    def test_recharge(self, message):
        if self.recharging:
            if message == "FULL POWER\a\b":
                print("["+str(self.random_id)+"] ","full power")
                self.recharging = False
                self.connection.settimeout(1)
                return True
            else:
                raise LogicError
        if message == 'RECHARGING\a\b':
            print("["+str(self.random_id)+"] ","Start recharge")
            self.recharging = True
            self.connection.settimeout(5)
            message = self._get_message()
            print("["+str(self.random_id)+"] ","After recharging: ",bytes(message, 'ascii'))
            return self.test_recharge(message)
        print("["+str(self.random_id)+"] ","message ok", message)
        return False

    """
    Method reads messages via _get_message()
    it also encapsulates recharging test together with _get_message function
    """
    def get_message(self):
        message = self._get_message()
        if self.test_recharge(message):
            message = self._get_message()
        print("["+str(self.random_id)+"] ",message)
        return message

    """
    Method testing correct message len in step
    :returns boolean value
    """
    def incorrect_step_len(self, message):
        return len(message) <= stage_len[stages[self.actual_stage]]

    """
    Composite test of message len and termination char sequence
    """
    def test_response(self, response):
        return self.incorrect_step_len(response) and response[-2:] == '\a\b'

    """
    Method checks if the message recieved is '<int> <int> OK\a\b'
    :raises SyntaxError if message doesnt match
    """
    def check_ok(self, message):
        if message[:2] != 'OK':
            raise SyntaxError
        if message[-2:] != '\a\b':
            raise SyntaxError
        pattern = re.compile('^-?\d+\s-?\d+$')
        if not pattern.match(message[3:-2]):
            raise SyntaxError

    """
    Calculates which direction is the robot facing
    :parameters two pairs of coordinates
    """
    def direction(self, a, b):
        # vertical move
        if a[0] == b[0]:
            if a[1] > b[1]:
                self.robot_direction = 2
            if a[1] < b[1]:
                self.robot_direction = 0

        # horizontal move
        if a[1] == b[1]:
            if a[0] > b[0]:
                self.robot_direction = 3
            if a[0] < b[0]:
                self.robot_direction = 1

    """
    Check if user is in center array where the treasure is hidden somewhere
    """
    def in_range(self):
        return -2 <= self.x <= 2 and -2 <= self.y <= 2

    """
    Locates robot
    """
    def locate_robot(self):
        self.connection.send(CMD['move'])
        position = self.get_message()
        self.check_ok(position)
        self.connection.send(CMD['move'])
        position2 = self.get_message()
        self.check_ok(position2)
        pos1 = [int(x) for x in position[3:-2].split(' ')]
        pos2 = [int(x) for x in position2[3:-2].split(' ')]
        self.direction(pos1, pos2)
        self.x = pos2[0]
        self.y = pos2[1]

        print("["+str(self.random_id)+"] ","Robot direction: ", DIRECTIONS[self.robot_direction])
    """
    Properly rotates robot to desired direction
    :parameter desired direction
    """
    def rotate(self, desired):
        while DIRECTIONS[self.robot_direction] != desired:
            self.connection.sendall(CMD['turn_r'])
            message = self.get_message()
            print("Rotate message: ", message)
            self.check_ok(message)
            print("check")
            self.robot_direction += 1
            self.robot_direction %= 4
            print("["+str(self.random_id)+"] ","ROTATING, facing " + DIRECTIONS[self.robot_direction])

    """
    Sends robot forward
    if the robot is in middle square array, it also checks for treasure
    """
    def go(self):
        self.connection.sendall(CMD['move'])
        message = self.get_message()
        self.check_ok(message)
        pos = [int(x) for x in message[3:-2].split(' ')]
        self.x = pos[0]
        self.y = pos[1]
        if [self.x, self.y] not in self.CHECKED and self.in_range():
            self.connection.sendall(CMD['pick'])
            message = self.get_message()
            if message[:-2] != '':
                self.message = message[:-2]
                raise MessageFound
            self.CHECKED.append([self.x, self.y])
        print("["+str(self.random_id)+"] ","CURRENT ", self.x, self.y)

    """
    Navigates robot to [-2,-2] which is the left bottom corner of middle square array
    """
    def get_to_desired_location(self):
        print("["+str(self.random_id)+"] ","Actual location: ", self.x, ",", self.y)
        if self.y != self.desired_x:
            self.rotate('UP') if self.y < self.desired_y else self.rotate('DOWN')
            while self.y != self.desired_y:
                self.go()
                #print(self.y," -> ", self.desired_y)

        print("["+str(self.random_id)+"] ","Actual location: ", self.x, ",", self.y)
        if self.x != self.desired_x:
            self.rotate('RIGHT') if self.x < self.desired_x else self.rotate('LEFT')
            while self.x != self.desired_x:
                self.go()
                #print(self.x, " -> ", self.desired_x)

        print("["+str(self.random_id)+"] ","Corner - > ", self.x, ",", self.y)
        return

    """
    Method used for client authentication
    :raises Syntax error if message isn't correct or 
    """
    def auth(self):
        bot_name = self.get_message()
        if not self.test_response(bot_name):
            raise SyntaxError
        self.hash = compute_hash(bot_name)
        to_send = (self.hash + 54621) % 65536
        self.connection.sendall(wrap_and_encode(to_send))
        response = self.get_message()
        #print(bytes(response, 'ascii'))

        if not self.test_response(response):  # or len(response) > 7:
            raise SyntaxError

        if not response[:-2].isdigit():
            raise SyntaxError

        if int(response[:-2]) > 99999:
            raise SyntaxError

        to_check = (self.hash + 45328) % 65536
        if response[:-2] == str(to_check):
            self.connection.sendall(CMD['ok'])
            #print("User auth ok")
            return True
        else:
            self.connection.sendall(CMD['login_fail'])
            return False
    """
    Tries to pick the treassure (a secret message)
    It's brute force for checking all the middle array indexes
    Inspired by programming language Karel 
    """
    def pick_message(self):
        self.rotate('RIGHT')
        while self.x != 2:
            self.go()

        self.rotate('UP')
        while self.y != 2:
            self.go()

        self.rotate('LEFT')
        while self.x != -2:
            self.go()

        self.rotate('DOWN')
        while self.y != -1:
            self.go()

        self.rotate('RIGHT')
        while self.x != 1:
            self.go()

        self.rotate('UP')
        while self.y != 1:
            self.go()

        self.rotate('LEFT')
        while self.x != -1:
            self.go()

        self.rotate('DOWN')
        while self.y != 0:
            self.go()

        self.rotate('RIGHT')
        while self.x != 0:
            self.go()
    """
    Main method which handles all the communication with robot
    Works in infinite loop which breaks on either successful
    message pickup or on logic/syntax error / timeout
    """
    def handle(self):
        try:
            while True:
                if self.stage == 0:
                    if not self.auth():
                        break
                    print("auth")
                    self.stage += 1
                if self.stage == 1:
                    self.locate_robot()
                    print("locate")
                    self.stage += 1

                if self.stage == 2:
                    self.get_to_desired_location()
                    print("desired")

                    self.stage += 1
                if self.stage == 3:
                    self.pick_message()
                    print("pick")

        except socket.timeout:
            print("timeout")
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)

        except LogicError:
            self.connection.sendall(CMD['logic'])
            print("logic error")

        except SyntaxError:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            self.connection.sendall(CMD['syntax'])
            print("syntax error")

        except MessageFound:
            self.connection.sendall(CMD['done'])
            print("MESSAGE FOUND")

        finally:
            self.connection.close()
            print("Server closed.")
            return
