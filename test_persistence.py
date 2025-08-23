import importlib
import json
import threading

app = importlib.import_module('app')

USERS_FILE = app.USERS_FILE

# Basic registration
print(app.register_user('test_a','aa11'))
print(app.register_user('test_b','bb22'))

# Concurrency add
names = [f'c{i}' for i in range(20)]

def reg(n):
	app.register_user(n, 'pw')

threads = [threading.Thread(target=reg, args=(n,)) for n in names]
[t.start() for t in threads]
[t.join() for t in threads]

with open(USERS_FILE, 'r', encoding='utf-8') as f:
	data = json.load(f)

print('total users:', len(data))
print('contains all concurrency users:', all(n in data for n in names))