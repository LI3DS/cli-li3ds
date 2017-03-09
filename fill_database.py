#!/usr/bin/python2

import sys
import os
import getopt

import requests
import json

def get_earth():
	r = requests.get('http://api.li3ds.io/sensors/')
	data = json.loads(r.text)	


	for i,sensor in enumerate(data):
		for j, attr in enumerate(sensor):
			if(attr=='short_name'):
				name = sensor['short_name']
				if(name=="Earth"):
					return True

	return False

def post_earth():
	print "post_earth"

def read_token(src="token.txt"):
	src = open(src, 'r')
	lines = src.readlines()
	src.close()

	token=lines[0].replace("\n","")

	return token

if __name__ == '__main__':

	token = read_token()

	inDatabase = get_earth()

	if(inDatabase==False):
		post_earth()

	#print token

	
