#!/usr/bin/python2

import sys
import os
import getopt

def read_token(src="token.txt"):
	src = open(src, 'r')
	lines = src.readlines()
	src.close()

	token=lines[0].replace("\n","")

	return token

if __name__ == '__main__':

	token = read_token()

	print token