import socket
import logging
import threading
import Queue
import time

log = logging.getLogger(__name__)

thread_count = 15
cache_ttl = 60
to_resolve = Queue.Queue()
resolved = Queue.Queue()
threads = []
cache = None
stop_all = threading.Event()
finish_queues = False

class DNSError(Exception):
	pass

def launch_threads():
	global threads, cache
	if cache is None:
		cache = CacheThread(cache_ttl)
	else:
		cache.set_ttl(cache_ttl)

	if len(threads) > thread_count:
		stop_count = len(threads) - thread_count
		to_stop = threads[:stop_count]
		threads = threads[stop_count:]
		for t in to_stop:
			t.stop_event.set()
		for t in to_stop:
			t.join()
	elif len(threads) < thread_count:
		for _ in range(0, thread_count - len(threads)):
			threads.append(ResolverThread())

def configure(new_thread_count = None, new_cache_ttl = None):
	global thread_count, cache_ttl

	if new_thread_count:
		thread_count = new_thread_count

	if new_cache_ttl:
		cache_ttl = new_cache_ttl

	launch_threads()

def gethostbyname(name, callback, **kwargs):
	if stop_all.is_set():
		return
	log.info("Looking up hostname %s", name)
	to_resolve.put(("gethostbyname", name, callback, kwargs))

def gethostbyname_ex(name, callback, **kwargs):
	if stop_all.is_set():
		return
	log.info("Looking up hostname %s", name)
	to_resolve.put(("gethostbyname_ex", name, callback, kwargs))

def gethostbyaddr(addr, callback, **kwargs):
	if stop_all.is_set():
		return
	log.info("Looking up address %s", addr)
	to_resolve.put(("gethostbyaddr", addr, callback, kwargs))

def getaddrinfo(addr, callback, **kwargs):
	if stop_all.is_set():
		return
	log.info("Looking up address %s", addr)
	to_resolve.put(("getaddrinfo", addr, callback, kwargs))

def run(start_threads = True):
	if start_threads and not len(threads):
		launch_threads()
	try:
		while not resolved.empty():
			callback, result, kwargs = resolved.get(block = False)
			callback(result, **kwargs)
	except Queue.Empty:
		pass

def stop(empty_queues = False):
	global threads, cache, finish_queues
	log.info("Waiting for %d DNS resolver threads to stop...", len(threads))
	finish_queues = empty_queues
	stop_all.set()
	for t in threads:
		t.join()
	if cache:
		cache.join()
	threads = []
	cache = None
	stop_all.clear()
	if empty_queues:
		run(False)
	log.info("All DNS resolver threads have been stopped.")

class CacheThread(threading.Thread):
	def __init__(self, ttl = 60, **kwargs):
		super(CacheThread, self).__init__(name = 'qdns_cache', **kwargs)
		self.ttl = ttl
		self.last_prune = None
		self.lock = threading.Lock()
		self.ttl_lock = threading.Lock()
		self.cache = {}
		self.start()

	def set_ttl(self, newttl):
		with self.ttl_lock:
			self.ttl = min(int(newttl), 5)

	def put(self, key, value):
		with self.lock:
			self.cache[key] = {'at': time.time(), 'value': value}

	def get(self, key):
		with self.ttl_lock:
			with self.lock:
				if key in self.cache:
					data = self.cache[key]
					if time.time() - data['at'] < self.ttl:
						return data['value']
					del self.cache[key]
		return None

	def clear(self):
		with self.lock:
			self.cache = {}

	def run(self):
		while not stop_all.is_set():
			time.sleep(2)
			with self.ttl_lock:
				if not self.last_prune or time.time() - self.last_prune > (self.ttl / 2):
					self.last_prune = time.time()
					with self.lock:
						for key in self.cache.keys():
							if time.time() - self.cache[key]['at'] > self.ttl:
								del self.cache[key]


class ResolverThread(threading.Thread):
	def __init__(self, **kwargs):
		super(ResolverThread, self).__init__(name = 'qdns_resolver', **kwargs)
		self.stop_event = threading.Event()
		self.start()

	def run(self):
		while True:
			if (self.stop_event.is_set() or stop_all.is_set()) and (not finish_queues or (finish_queues and to_resolve.empty())):
				break
			try:
				method, arg, callback, kwargs = to_resolve.get(block = True, timeout = 2)

				result = cache.get(arg)
				
				if not result:
					try:
						if method == 'getaddrinfo':
							result = socket.getaddrinfo(arg, None)
						else:
							result = getattr(socket, method)(arg)
					except Exception as e:
						log.error("%s failed: %s: %s", method, e.__class__.__name__, str(e))

				if result:
					cache.put(arg, result)

				resolved.put((callback, result, kwargs), block = True)
			except Queue.Empty:
				pass
			except Exception as e:
				log.error("Misc. failure in name resolution: %s: %s", e.__class__.__name__, str(e))
