CMD = {
    'move': bytes('102 MOVE\a\b', 'ascii'),
    'turn_l': bytes('103 TURN LEFT\a\b', 'ascii'),
    'turn_r': bytes('104 TURN RIGHT\a\b', 'ascii'),
    'pick': bytes('105 GET MESSAGE\a\b', 'ascii'),
    'done': bytes('106 LOGOUT\a\b', 'ascii'),
    'ok': bytes('200 OK\a\b', 'ascii'),
    'login_fail': bytes('300 LOGIN FAILED\a\b', 'ascii'),
    'syntax': bytes('301 SYNTAX ERROR\a\b', 'ascii'),
    'logic': bytes('302 LOGIC ERROR\a\b', 'ascii')
}
