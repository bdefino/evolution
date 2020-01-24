#!/usr/bin/env python3
import os
import queue
import subprocess
import sys
import tempfile

__doc__ = "evolutionary programming via a driver/tester model"

class Driver:
  """randomized driver for evolution of machine code"""

  def __init__(self, test, bit_flips = 1, fast_buflen = 1 << 20):
    assert isinstance(bit_flips, int) and bit_flips > 0
    assert isinstance(test, Test)
    
    self.bit_flips = bit_flips
    self.fast_buflen = fast_buflen
    self.test = test

  @staticmethod
  def generate_random_octets_in_bits(octets = 1):
    for o in range(octets):
      for b in bin(ord(os.urandom(1)))[2:].zfill(8):
        yield int(b)

  def _grow(self, include_bit = 0):
    """grow the temporary file to include a particular bit"""
    max_octet = include_bit / 8 + (1 if include_bit % 8 else 0)
    self._fp.seek(0, os.SEEK_END)

    if self._fp.tell() >= max_octet:
      return
    
    # grow in large increments

    while self._fp.tell() < max_octet - fast_buflen:
      self._fp.write(os.urandom(fast_buflen))

    # polish off growth

    if self._fp.tell() < max_octet:
      self._fp.write(os.urandom(max_octet - self._fp.tell())
    self._fp.sync()
    os.fdatasync(self._fp.fileno())

    # record size

    self._size = self._fp.tell()

  def __iter__(self):
    self._bit_pool = queue.Queue() # cryptographically-secure bits
    self._fp = tempfile.NamedTemporaryFile()
    self._iteration = 0
    self._size = 0
    
    # grow to include bit 0

    self._grow()
    return self

  def __next__(self):##################################################################################
    """
    test the program, and if successful, stop iterating;
    otherwise evolve the code
    """
    if self.test(self._fp.name):
      # successful evolution

      raise StopIteration()

    for i in range(self.bit_flips):
      # select a random bit

      num_bits = len(bin(self._size)[2:])
      bit = sum((b << (8 - i) for i in enumerate(self._random_bits(num_bits))))

      # accomodate the bit

      self._grow(bit)

      # flip the bit

      self._fp.seek(bit / 8 + (1 if bit % 8 else 0), os.SEEK_SET)
      cur = self._fp.read(1)
      self._fp.seek(-1, os.SEEK_CUR)
      self._fp.write(chr(ord(cur) ^ (1 << (bit % 8))))
    self._iteration += 1

  def _random_bits(self, n = 1):
    """return random bits"""
    for i in range(n):
      if self._bit_pool.empty():
        # grow the bit pool

        for b in Driver.generate_random_octets_in_bits():
          self._bit_pool.put(b)
      yield self._bit_pool.get()

class Test:
  """arbitrary test on a path's contents"""

  def __init__(self):
    pass

  def __call__(self, path):
    """return whether the path's contents satisfy the test"""
    raise NotImplementedError()

class DelegatingTest(Test):
  """
  test which delegates its evaluation to an executable

  the executable is expected to adhere to the following API:
    Usage: executable PATH
  """

  def __init__(self, executable):
    self.executable = executable

  def __call__(self, path):
    """delegate the test to the executable"""
    child = subprocess.Popen((path, ), executable = executable)
    return not child.wait()

if __name__ == "__main__":
  raise NotImplementedError()#################################################################################

