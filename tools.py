"""
Custom exceptions used for control
"""
class LogicError(Exception):
    pass

class SyntaxError(Exception):
    pass

class MessageFound(Exception):
    pass

def wrap_and_encode(message):
    return (str(message) + '\a\b').encode('ascii')

'''
Hash compute function
uses SERVER and CLIENT key 
which is used to authenticate
'''
def compute_hash(bot_name):
    name_sum = 0
    name = bot_name[:-2]
    # sums int values of char
    for char in name:
        name_sum += ord(char)

    name_sum = name_sum * 1000
    name_sum = name_sum % 65536

    return name_sum

