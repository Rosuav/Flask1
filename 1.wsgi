import sys, os
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
# from 1 import app as application # Doesn't work with a numeric name, heh!
application = __import__("1").app