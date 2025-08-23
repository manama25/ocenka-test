def cache_data(func=None, *args, **kwargs):
	def decorator(f):
		return f
	return decorator if func is None else decorator(func)


def error(*args, **kwargs):
	print("ST_ERROR:", *args)


def warning(*args, **kwargs):
	print("ST_WARN:", *args)


def info(*args, **kwargs):
	print("ST_INFO:", *args)


def success(*args, **kwargs):
	print("ST_OK:", *args)