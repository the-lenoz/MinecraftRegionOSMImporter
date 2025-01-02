import numpy as np

EPS = 1e-5
INSIDE = 0
OUTSIDE = 1

class Point3:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def as_array(self):
        return np.array([self.x, self.y, self.z])

class Triangle3:
    def __init__(self, v1, v2, v3):
        self.v1 = v1
        self.v2 = v2
        self.v3 = v3

def sign3(vec):
    vec = np.array(vec)
    signs = (vec < EPS).astype(int) * [4, 2, 1] + (vec > -EPS).astype(int) * [32, 16, 8]
    return sum(signs)

def cross(a, b):
    return np.cross(a, b)

def sub(a, b):
    return a - b

def lerp(alpha, a, b):
    return b + alpha * (a - b)

def min3(a, b, c):
    return min(a, b, c)

def max3(a, b, c):
    return max(a, b, c)

def face_plane(p):
    outcode = 0
    if p.x > 0.5: outcode |= 0x01
    if p.x < -0.5: outcode |= 0x02
    if p.y > 0.5: outcode |= 0x04
    if p.y < -0.5: outcode |= 0x08
    if p.z > 0.5: outcode |= 0x10
    if p.z < -0.5: outcode |= 0x20
    return outcode

def bevel_2d(p):
    outcode = 0
    outcode |= 0x001 if (p.x + p.y > 1.0) else 0
    outcode |= 0x002 if (p.x - p.y > 1.0) else 0
    outcode |= 0x004 if (-p.x + p.y > 1.0) else 0
    outcode |= 0x008 if (-p.x - p.y > 1.0) else 0
    outcode |= 0x010 if (p.x + p.z > 1.0) else 0
    outcode |= 0x020 if (p.x - p.z > 1.0) else 0
    outcode |= 0x040 if (-p.x + p.z > 1.0) else 0
    outcode |= 0x080 if (-p.x - p.z > 1.0) else 0
    outcode |= 0x100 if (p.y + p.z > 1.0) else 0
    outcode |= 0x200 if (p.y - p.z > 1.0) else 0
    outcode |= 0x400 if (-p.y + p.z > 1.0) else 0
    outcode |= 0x800 if (-p.y - p.z > 1.0) else 0
    return outcode

def bevel_3d(p):
    outcode = 0
    outcode |= 0x01 if (p.x + p.y + p.z > 1.5) else 0
    outcode |= 0x02 if (p.x + p.y - p.z > 1.5) else 0
    outcode |= 0x04 if (p.x - p.y + p.z > 1.5) else 0
    outcode |= 0x08 if (p.x - p.y - p.z > 1.5) else 0
    outcode |= 0x10 if (-p.x + p.y + p.z > 1.5) else 0
    outcode |= 0x20 if (-p.x + p.y - p.z > 1.5) else 0
    outcode |= 0x40 if (-p.x - p.y + p.z > 1.5) else 0
    outcode |= 0x80 if (-p.x - p.y - p.z > 1.5) else 0
    return outcode

def check_point(p1, p2, alpha, mask):
    plane_point = Point3(*lerp(alpha, p1.as_array(), p2.as_array()))
    return face_plane(plane_point) & mask

def check_line(p1, p2, outcode_diff):
    tests = [
        (0x01, (0.5 - p1.x) / (p2.x - p1.x), 0x3e),
        (0x02, (-0.5 - p1.x) / (p2.x - p1.x), 0x3d),
        (0x04, (0.5 - p1.y) / (p2.y - p1.y), 0x3b),
        (0x08, (-0.5 - p1.y) / (p2.y - p1.y), 0x37),
        (0x10, (0.5 - p1.z) / (p2.z - p1.z), 0x2f),
        (0x20, (-0.5 - p1.z) / (p2.z - p1.z), 0x1f)
    ]
    for mask, alpha, face_mask in tests:
        if (outcode_diff & mask) != 0 and check_point(p1, p2, alpha, face_mask) == INSIDE:
            return INSIDE
    return OUTSIDE

def point_triangle_intersection(p, t):
    v1, v2, v3 = t.v1.as_array(), t.v2.as_array(), t.v3.as_array()
    p = p.as_array()

    if np.any(p > np.maximum.reduce([v1, v2, v3])) or np.any(p < np.minimum.reduce([v1, v2, v3])):
        return OUTSIDE

    vect12 = sub(v1, v2)
    vect1h = sub(v1, p)
    cross12_1p = cross(vect12, vect1h)
    sign12 = sign3(cross12_1p)

    vect23 = sub(v2, v3)
    vect2h = sub(v2, p)
    cross23_2p = cross(vect23, vect2h)
    sign23 = sign3(cross23_2p)

    vect31 = sub(v3, v1)
    vect3h = sub(v3, p)
    cross31_3p = cross(vect31, vect3h)
    sign31 = sign3(cross31_3p)

    return INSIDE if (sign12 & sign23 & sign31) != 0 else OUTSIDE

def t_c_intersection(t):
    v1_test = face_plane(t.v1)
    v2_test = face_plane(t.v2)
    v3_test = face_plane(t.v3)

    if any(test == INSIDE for test in [v1_test, v2_test, v3_test]):
        return True

    if v1_test & v2_test & v3_test:
        return False

    v1_test |= bevel_2d(t.v1) << 8
    v2_test |= bevel_2d(t.v2) << 8
    v3_test |= bevel_2d(t.v3) << 8
    if v1_test & v2_test & v3_test:
        return False

    v1_test |= bevel_3d(t.v1) << 24
    v2_test |= bevel_3d(t.v2) << 24
    v3_test |= bevel_3d(t.v3) << 24
    if v1_test & v2_test & v3_test:
        return False

    edges = [
        (t.v1, t.v2, v1_test | v2_test),
        (t.v1, t.v3, v1_test | v3_test),
        (t.v2, t.v3, v2_test | v3_test)
    ]

    for p1, p2, outcode_diff in edges:
        if not (v1_test & v2_test) and check_line(p1, p2, outcode_diff) == INSIDE:
            return True

    norm = cross(sub(t.v1.as_array(), t.v2.as_array()), sub(t.v1.as_array(), t.v3.as_array()))
    d = np.dot(norm, t.v1.as_array())

    for denom, point in [(norm.sum(), Point3(d / denom, d / denom, d / denom)) for denom in [norm.sum(), norm.sum() - 2 * norm[2], norm.sum() - 2 * norm[1], norm.sum() - 2 * norm[0]]]:
        if abs(denom) > EPS and abs(point.x) <= 0.5 and point_triangle_intersection(point, t) == INSIDE:
            return True

    return False
