#!/usr/bin/env python3
import argparse
import math
import os
import queue # `collections.deque`
import subprocess
import sys

__doc__ = "flip bits until behavior is as expected"

def get_int(*bits):
  """return an integer composed from the bits (big bit first)"""
  n = 0

  for bit in bits:
    n <<= 1
    n |= bit
  return n

def get_bits(byte, n = 8):
  """generate bits from a byte (big bit first)"""
  assert isinstance(n, int)

  i = 1 << n

  while i >= 0:
    yield byte & i
    i >>= 1

def main(argv):
  """evolve a program based on an argument vector"""
  raise NotImplementedError()##################################################################

class BitPool:
  """bit pool (queue)"""

  def __init__(self):
    self._pool = queue.Queue()

  def drain(self, n):
    """generate up to `n` bits from the pool"""
    while 1:
      try:
        yield self._pool.get()
      except ValueError:
        break

  def fill(self, *bits):
    """add bits into the pool"""
    for bit in bits:
      self._pool.put(bit)

class Driver:
  """evolve until the executable passes the test"""

  def __init__(self, path, evolve = None, test = None):
    assert isinstance(evolve, Evolver)
    assert isinstance(test, Test)

    self.evolve = evolve if not evolve is None else RandomEvolver()
    self.path = path
    self.test = test if not test is None else ExitCodeTest(path = path)

  def __call__(self):
    """evolve until the executable passes the test (could take a while)"""
    while not self.test():
      self.evolve()

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
    self.entropy = read_entropy

  def drain(self, n):
    """generate `n` bits from the entropy source"""
    while n:
      bitl = typle(BitPool.drain(self, n))

      if not bitt:
        self.fill(*tuple(get_bits(ord(self.read_entropy(1)))))
        continue
      yield bitt[0]
      n -= 1

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

  def __init__(self, base_normal_random_int_bits = 8,
      mean_generational_flips = 1, negative_growth = True,
      positive_growth = True, randomize_normal_random_int_bits = True, *args,
      **kwargs):
    assert isinstance(base_normal_random_int_bits, int) \
      and base_normal_random_int_bits >= 1
    assert isinstance(mean_generational_flips, int) \
      and mean_generational_flips > 0

    Evolver.__init__(self, *args, **kwargs)
    self.base_normal_random_int_bits = base_normal_random_int_bits
    self.mean_generational_flips = mean_generational_flips
    self.negative_growth = negative_growth
    self._pool = RandomBitPool()
    self.positive_growth = positive_growth
    self._random_int_bits = self.base_random_int_bits
    self.randomize_normal_random_int_bits = randomize_normal_random_int_bits

  def __call__(self):
    """randomly evolve (possibly grow/shrink BUT ALWAYS flip bits)"""
    # flip bits

    fp = open(self.path, "r+b" if os.path.exists(self.path) else "w+b")
    remaining_flips = self.mean_generational_flips
    
    fp.seek(0, os.SEEK_END)
    size = fp.tell()
    fp.seek(0, os.SEEK_SET)

    while remaining_flips > 0:
      # flip a random bit (via an offset)

      offset = self._normal_random_int()

      if self._pool.drain(1):
        offset *= -1
      i = fp.tell() + offset
      
      ###################################################################################

      # randomly modify the number of remaining bit flips

      offset = self._normal_random_int()

      if self._pool.drain(1):
        offset *= -1
      remaining_flips += offset
    fp.close()

  def _normal_random_int(self):
    """
    return a normalized random integer based on the configuration

    this function reduces variability between consecutive values
    by offsetting the output bit count along a logarithmic scale
    """
    random_int_bits = self.random_int_bits

    if self.randomize_random_int_bits:
      # randomize the number of bits in a controllable fashion
      # (i.e. as the random offset increases, the actual number of bits
      # should change less)

      offset = int(math.log(get_int(*tuple(self._pool.drain(
        random_int_bits)))))

      if self._pool.drain(1):
        offset *= -1
      self._random_int_bits += offset
    return get_int(*tuple(self._pool.drain(random_int_bits)))

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
    self.tester = tuple([arg % self.path for arg in argv])
    self.code = code
    self.timeout = timeout # bypass halting problem

  def __call__(self):
    """return whether the executable exits properly"""
    child = subprocess.Popen(self.argv, executable = self.argv[0])
    code = child.wait(self.timeout)

    if isinstance(code, int):
      # exited in time

      return code == self.code
    return False

if __name__ == "__main__":
  main(sys.argv)

