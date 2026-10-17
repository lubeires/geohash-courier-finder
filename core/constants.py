import math

BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"

# Precisão usada para armazenar os entregadores na Trie (enunciado: até 8 níveis)
STORAGE_PRECISION = 8
MAX_PRECISION = 12

EARTH_RADIUS_KM = 6371.0088
METERS_PER_DEGREE = EARTH_RADIUS_KM * 1000 * math.pi / 180
