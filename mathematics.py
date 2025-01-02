import math


class MapProjection:
    origin_x = None
    origin_y = None
    
    def __init__(self, origin_lat, origin_lon):
        self.scale_factor = MercatorProjection.earth_circumference(origin_lat)
        self.origin_y = MercatorProjection.lat_to_y(origin_lat) * self.scale_factor
        self.origin_x = MercatorProjection.lon_to_x(origin_lon) * self.scale_factor

    def to_yx(self, lat, lon):
        if self.origin_x is None:
            raise ValueError("The origin needs to be set first")

        x = MercatorProjection.lon_to_x(lon) * self.scale_factor - self.origin_x
        y = MercatorProjection.lat_to_y(lat) * self.scale_factor - self.origin_y

        # Snap to mm precision, seems to reduce geometry exceptions
        x = round(x * 1000) / 1000.0
        y = round(y * 1000) / 1000.0

        return (y, x)  

    def to_lat_lon(self, y, x):
        if self.origin_x is None:
            raise ValueError("The origin needs to be set first")

        return (MercatorProjection.y_to_lat((y + self.origin_y) / self.scale_factor), 
            MercatorProjection.x_to_lon((x + self.origin_x) / self.scale_factor))
    

class MercatorProjection:

    R_MAJOR = 6378137.0
    R_MINOR = 6356752.3142
    RATIO = R_MINOR / R_MAJOR
    ECCENT = math.sqrt(1.0 - (RATIO * RATIO))
    COM = 0.5 * ECCENT
    EARTH_CIRCUMFERENCE = 40075016.686

    @staticmethod
    def earth_circumference(latitude):
        """ Calculate earth circumference at given latitude. """
        return MercatorProjection.EARTH_CIRCUMFERENCE * math.cos(math.radians(latitude))

    @staticmethod
    def lon_to_x(longitude):
        """ Convert longitude to Mercator projection (range [0..1]). """
        return (longitude + 180.0) / 360.0

    @staticmethod
    def x_to_lon(x):
        """ Convert from Mercator projection (range [0..1]) to longitude. """
        return 360.0 * (x - 0.5)

    @staticmethod
    def lat_to_y(latitude):
        """ Convert latitude to Mercator projection (range [0..1]). """
        sin_lat = math.sin(math.radians(latitude))
        return math.log((1.0 + sin_lat) / (1.0 - sin_lat)) / (4.0 * math.pi) + 0.5

    @staticmethod
    def y_to_lat(y):
        """ Convert from Mercator projection (range [0..1]) to latitude. """
        return 360.0 * math.atan(math.exp((y - 0.5) * (2.0 * math.pi))) / math.pi - 90.0

    @staticmethod
    def lat_to_y_elliptical(lat):
        """ This is for the Elliptical Mercator version """
        lat = min(89.5, max(lat, -89.5))
        phi = math.radians(lat)
        sinphi = math.sin(phi)
        con = MercatorProjection.ECCENT * sinphi
        con = math.pow((1.0 - con) / (1.0 + con), MercatorProjection.COM)
        ts = math.tan(0.5 * ((math.pi * 0.5) - phi)) / con
        return 0 - MercatorProjection.R_MAJOR * math.log(ts)

    @staticmethod
    def y_to_lat_elliptical(y):
        """ This is for the Elliptical Mercator version """
        ts = math.exp(-y / MercatorProjection.R_MAJOR)
        phi = math.pi / 2 - 2 * math.atan(ts)
        dphi = 1.0
        i = 0
        while abs(dphi) > 0.000000001 and i < 15:
            con = MercatorProjection.ECCENT * math.sin(phi)
            dphi = math.pi / 2 - 2 * math.atan(ts * math.pow((1.0 - con) / (1.0 + con), MercatorProjection.COM)) - phi
            phi += dphi
            i += 1
        return math.degrees(phi)
