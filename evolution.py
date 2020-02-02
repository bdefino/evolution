#!/usr/bin/env python3
import math
import os
import queue # `collections.deque`
import subprocess
import sys
import time

__doc__ = "flip bits until behavior is as expected"

def get_bit_count(n):
  """return the minimum number of bits required to store `n`"""
  bit_count = 0

  while n:
    bit_count += 1
    n >>= 1
  return bit_count

def get_bits(byte, n = 8):
  """generate bits from an UNSIGNED byte (big bit first)"""
  assert isinstance(n, int)

  i = 1 << n

  while n:
    yield (byte & i) >> n
    i >>= 1
    n -= 1

def get_byte(n):
  """get a byte from an integer"""
  return n.to_bytes(1, "big")

def get_whole(*bits):
  """return a whole number composed from the bits (big bit first)"""
  n = 0

  for bit in bits:
    n <<= 1
    n |= bit
  return n

def main(argv):###################################################################insufficient
  """evolve a program based on an argument vector"""
  evolver = None
  generational_flips = 1
  growth = False
  i = 1
  path = None
  sleep = 0
  test = None
  test_argv = ()

  while i < len(argv):
    if argv[i] in ("-g", "--growth"):
      growth = True
    elif argv[i] in ("-h", "--help"):
      print(__doc__)
      return
    elif argv[i].startswith("-t"):
      if len(argv[i]) > 2:
        test_argv = shlex.split(argv[i][len("-t"):])
      elif len(argv) == i + 1:
        print(__doc__)
        sys.exit(1)
      else:
        i += 1
        test_argv = shlex.split(argv[i])
    elif argv[i].startswith("--test="):
      if len(argv[i]) > 2:
        test_argv = shlex.split(argv[i][len("--test="):])
      elif len(argv) == i + 1:
        print(__doc__)
        sys.exit(1)
      else:
        i += 1
        test_argv = shlex.split(argv[i])
    else:
      path = argv[i]
    i += 1

  if path is None:
    print(__doc__)
    sys.exit(1)
  evolver = RandomEvolver(growth = growth, path = path)
  test = FauxDelegatingExitCodeTest(test_argv, path = path)
  Driver(path, evolver, sleep, test)()
  print("Done.")

class BitPool:
  """bit pool (queue)"""

  def __init__(self):
    self._pool = queue.Queue()

  def drain(self, n):
    """generate up to `n` bits from the pool"""
    while n:
      try:
        yield self._pool.get_nowait()
      except queue.Empty:
        break
      n -= 1

  def fill(self, *bits):
    """add bits into the pool"""
    for bit in bits:
      self._pool.put(bit)

class Driver:
  """evolve until the executable passes the test"""

  def __init__(self, path, evolve = None, sleep = 0, test = None):
    assert isinstance(evolve, Evolver)
    assert isinstance(test, Test)

    self.evolve = evolve if not evolve is None else RandomEvolver()
    self.path = path
    self.sleep = sleep
    self.test = test if not test is None else ExitCodeTest(path = path)

  def __call__(self):
    """evolve until the executable passes the test (could take a while)"""
    while not self.test():
      print("Evolving (evolver random whole number bit count: %u)..."
        % self.evolve.random_whole_bit_count)
      self.evolve()
      time.sleep(self.sleep)

class Evolver:
  """evolve an executable"""

  def __init__(self, path):
    self.path = path

  def __call__(self):
    """evolve the executable by 1 generation"""
    raise NotImplementedError()

class RandomBitPool(BitPool):
  """generate random bits from an entropy source"""

  def __init__(self, read_entropy = os.urandom):
    BitPool.__init__(self)
    self.read_entropy = read_entropy

  def drain(self, n):
    """generate `n` bits from the entropy source"""
    while n:
      bitt = tuple(BitPool.drain(self, n))

      if not bitt:
        self.fill(*tuple(get_bits(ord(self.read_entropy(1)))))
        continue
      
      for bit in bitt:
        yield bit
      n -= len(bitt)

class RandomEvolver(Evolver):
  """
  randomly evolve an executable

  each iteration of evolution (a generation) will ALWAYS flip bits,
  but MAY ALSO grow/shrink the program;
  the motivation is that execution is sequential,
  and a failure for the programs earlier bits to reach the intended path
  drastically decreases the likelihood that the program will actually
  be MORE successful than its previous generation
  (i.e. more moving parts are generally less productive)

  also supports improved randomness generation,
  so that variability between consecutive random integers
  """

  def __init__(self, generational_flips = 1, growth = True,
      randomize_random_whole_bit_count = True, random_whole_bit_count = 1,
      *args, **kwargs):
    assert isinstance(generational_flips, int) \
      and generational_flips > 0
    assert isinstance(random_whole_bit_count, int) \
      and random_whole_bit_count > 0

    Evolver.__init__(self, *args, **kwargs)
    self.generational_flips = generational_flips
    self.growth = growth
    self._pool = RandomBitPool()
    self.random_whole_bit_count = random_whole_bit_count
    self.randomize_random_whole_bit_count = randomize_random_whole_bit_count

  def __call__(self):
    """randomly evolve (possibly grow/shrink BUT ALWAYS flip bits)"""
    fp = open(self.path, "r+b" if os.path.exists(self.path) else "w+b")
    fp.seek(0, os.SEEK_END)
    size = fp.tell()
    fp.seek(0, os.SEEK_SET)

    if self.growth \
        and bool(*tuple(self._pool.drain(1))):
      # compute target size

      target = size + self._normal_random_whole()
      target = target if target >= 0 else 0

      # grow (accounts for positive and negative growth)

      fp.seek(0, os.SEEK_END)

      while fp.tell() < target:
        fp.write(get_byte(get_whole(*tuple(self._pool.drain(7)))))
      fp.truncate(target)
      os.fdatasync(fp.fileno())
      size = target

    if not size:
      fp.close()
      return
    bit_count = get_bit_count(size * 8)

    for i in range(self.generational_flips):
      # select a bit randomly

      fulli = self._raw_random_whole(bit_count) % (size * 8)
      bytei = fulli // 8
      biti = fulli % 8

      # toggle the bit

      fp.seek(bytei, os.SEEK_SET)
      byten = ord(fp.read(1)) ^ (1 << biti)
      fp.seek(bytei, os.SEEK_SET)
      fp.write(get_byte(byten))
      os.fdatasync(fp.fileno())
    fp.close()

  def _normal_random_whole(self):
    """
    return a normalized random whole number based on the configuration

    this function reduces variability between consecutive values
    by offsetting the output bit count along
    a severely logarithmic scale (base `math.e ** math.e`);
    EXCEPT when the random bit count isn't suitable for producing
    random output (e.g. `self.random_whole_bit_count < 2`):
    in which case the severe logarithm is omitted

    this function is especially useful for computing gradual offsets
    """
    n = self._random_whole()

    if self.random_whole_bit_count >= 2:
      n = math.ceil(self._severe_log(n))
    return n

  def _random_whole(self):
    """
    return a NON-normalized whole number based on the configuration

    based on the configuration, this may also modify the number
    of bits used in computing a random number using the severe logarithm
    to normalize the bit count (bit count shouldn't vary much)
    """
    random_whole = lambda: self._raw_random_whole(self.random_whole_bit_count)
    n = random_whole()

    if self.randomize_random_whole_bit_count:
      # modify the number of bits the next call will use

      offset = random_whole()
      
      if self.random_whole_bit_count >= 2:
        offset = math.ceil(self._severe_log(offset))
      offset *= -1 if bool(*tuple(self._pool.drain(1))) else 1
      self.random_whole_bit_count += offset

      if self.random_whole_bit_count <= 0:
        self.random_whole_bit_count = 1
    return n

  def _raw_random_whole(self, bit_count):
    """
    return a random whole number directly from the entropy pool,
    no strings attached

    this does NOT draw from, nor randomize the instance's bit count
    """
    return get_whole(*tuple(self._pool.drain(bit_count)))

  def _severe_log(self, n):
    """
    return a severe version of the natural log
    (`math.log(n, math.e ** math.e)`)
    """
    try:
      return math.log(n, math.e ** math.e)
    except ValueError:
      # `n` might be too small

      return 0

class Test:
  """test an executable"""

  def __init__(self, path):
    self.path = path

  def __call__(self):
    """return success"""
    raise NotImplementedError()

class DelegatingExitCodeTest(Test):
  """
  test for a particular exit code when passed to an external tester

  the external tester should be specified as an argument vector,
  where "%s" within arguments will be replaced by the executable path
  """

  def __init__(self, argv, code = 0, timeout = None, *args, **kwargs):
    Test.__init__(self, *args, **kwargs)
    self.argv = tuple([arg % self.path for arg in argv])
    self.code = code
    self.timeout = timeout # bypass halting problem

  def __call__(self):
    """return whether the executable exits properly"""
    try:
      child = subprocess.Popen(self.argv, executable = self.argv[0])
    except:
      return False
    code = child.wait(self.timeout)

    if isinstance(code, int):
      # exited in time

      return code == self.code
    return False

class FauxDelegatingExitCodeTest(DelegatingExitCodeTest):
  """don't delegate to a tester, rather delegate to the program itself"""

  def __init__(self, *args, **kwargs):
    DelegatingExitCodeTest.__init__(self, *args, **kwargs)
    self.argv = (self.path, ) + self.argv[1:]

if __name__ == "__main__":
  main(sys.argv)

