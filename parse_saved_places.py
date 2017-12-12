
import os
from geojson_utils import point_in_polygon, centroid
import json
from operator import itemgetter
import re
import sys


class PlaceSorter:
    DELEGACIONES = {
        'Cuauhtémoc': { 'order': 12, 'file': 'Cuauhtemoc'},
        'Venustiano Carranza': { 'order': 13, 'file': None },
        'Miguel Hidalgo': { 'order': 20, 'file': 'MiguelHidalgo' },
        'Cuajimalpa de Morelos': { 'order': 23, 'file': 'CuajimalpaDeMorelos' },
        'Benito Juarez': { 'order': 29, 'file': 'BenitoJuarez' },
        'Alvaro Obregón': { 'order': 30, 'file': 'AlvaroObregon' },
        'Coyoacán': { 'order': 35, 'file': 'Coyoacan' },
        'Tlalpan': { 'order': 40, 'file': None },
        'Xochimilco': { 'order': 45, 'file': None },
    }
    COLONIAS = [
        ('Santa Maria la Ribera', 1, [ '15-075', '15-076', '15-078' ]),
        ('Tlateloco', 2, [ '15-035', '15-050', '15-051', '15-061' ]),
        ('Tepito', 3, [ '15-056', '15-057', '15-058' ]),
        ('Centro', 4, [ '15-037', '15-039', '15-040', '15-041', '15-043', '15-044' ]),
        ('Guerrero', 5, [ '15-036', '15-052', '15-053' ]),
        ('San Rafael/Tabacalera', 6, [ '15-031', '15-073']),
        ('Cuauhtemoc', 7, [ '15-009' ]),
        ('Zona Rosa', 8, [ '15-017' ]),
        ('La Condesa', 9, [ '15-008', '15-016', '15-055', '15-054' ]),
        ('Roma Norte', 10, [ '15-068', '15-069', '15-070' ]),
        ('Roma Sur', 11, [ '15-071', '15-072' ]),
        ('Argentina', 14, [ '16-027', '16-014' ]),
        ('Polanco', 15, [ '16-035', '16-032', '16-031', '16-055', '16-054', '16-065', '16-021', '16-059', '16-022', '16-018' ]),
        ('Bosque de Chapultepec', 16, [ '16-015' ]),
        ('San Miguel Chapultepec', 17, [ '16-094', '16-095' ]),
        ('Daniel Garza', 18, [ '16-086', '16-003', '16-025', '16-058' ]),
        ('Lomas de Chapultepec', 19, [ '16-042' ]),
        ('Santa Fe', 21, [ '04-025', '04-028' ]),
        ('Narvarte', 25, [ '14-063' ]),
        ('Insurgentes Sur/Napoles', 26, [ '14-014', '14-028']),
        ('Xoco', 27, [ '14-049' ]),
        ('San Angel', 31, [ '10-193', '10-192', '10-042', '03-019' ]),
        ('Coyoacan', 32, [ '03-037', '03-065', '03-105', '03-106', '03-114', '03-107', '03-012', '03-099' ]),
        ('Ciudad Universitaria', 33, [ '03-021' ]),
        ('Jardines del Pedregal', 34, [ '10-091', '03-088', '03-062' ])
    ]

    MIN_LAT = 18.0
    MAX_LAT = 20.0
    MIN_LNG = -100.0
    MAX_LNG = -98.0

    def __init__(self):
        self.delegaciones = []
        self.colonias = []
        self.all_places = []
        self.sorting = { }
        self.build_sorting()


    def build_sorting(self):
        for (k, o, v) in self.COLONIAS:
            for cve in v:
                self.sorting[cve] = { 'label': k, 'order': o }


    def filtered_feature(self, feature):
        if feature['geometry']['type'] == 'Point' and 'properties' in feature and 'Location' in feature['properties']:
            lng = feature['geometry']['coordinates'][0]
            lat = feature['geometry']['coordinates'][1]
            if lng >= self.MIN_LNG and lng <= self.MAX_LNG and lat >= self.MIN_LAT and lat <= self.MAX_LAT:
                return True
        return False


    def parse_delegaciones(self):
        fname = os.path.join('geojson', 'DELEGACIONES.geojson')
        with open(fname) as f:
            collection = json.load(f)
            for feature in collection['features']:
                name = feature['properties']['name']
                order = 90
                if name in self.DELEGACIONES:
                    order = self.DELEGACIONES[name]['order']
                if feature['geometry']['type'] == 'Polygon':
                    self.delegaciones.append({
                        'polygons': [ feature['geometry'] ],
                        'properties': {
                            'delegacion': name,
                        }
                    })
                elif feature['geometry']['type'] == 'GeometryCollection':
                    polygons = []
                    for geo in feature['geometry']['geometries']:
                        if geo['type'] == 'Polygon':
                            polygons.append(geo)
                    if len(polygons) == 0:
                        print('{}, no polygons'.format(name))
                        sys.exit(1)
                    self.delegaciones.append({
                        'polygons': polygons,
                        'properties': {
                            'delegacion': name,
                            'order': order
                        }
                    })
                else:
                    print('{}, geometry type is {}'.format(name, feature['geometry']['type']))
                    sys.exit(1)


    def parse_delegacion(self, delegacion, fname):
        with open(fname) as f:
            collection = json.load(f)
            for feature in collection['features']:
                if feature['geometry']['type'] == 'Polygon':
                    colonia = feature['properties']['NOMBRE_COLONIA']
                    cve = feature['properties']['CVE_COL']
                    center = centroid(feature['geometry'])
                    # print('delegacion: {}\ncolonia: {}\ncenter: {}'.format(delegacion, colonia, center))

                    self.colonias.append({
                        'geometry': feature['geometry'],
                        'properties': {
                            'delegacion': delegacion,
                            'colonia': colonia,
                            'cve': cve,
                            'center': center
                        }
                    })


    def find_delegacion(self, feature):
        for delegacion in self.delegaciones:
            for geo in delegacion['polygons']:
                if point_in_polygon(feature['geometry'], geo):
                    return delegacion
        return None


    def find_colonia(self, feature):
        for colonia in self.colonias:
            if point_in_polygon(feature['geometry'], colonia['geometry']):
                return colonia
        return None


    def filter_places(self):
        self.parse_delegaciones()

        for name, d in self.DELEGACIONES.items():
            if d['file']:
                fname = os.path.join('geojson', d['file'] + '.geojson')
                self.parse_delegacion(name, fname)

        print('Parsed {} colonias'.format(len(self.colonias)))

        with open('Saved Places.json') as f:
            collection = json.load(f)
            print('{} places'.format(len(collection['features'])))
            print()

            for feature in [f for f in collection['features'] if self.filtered_feature(f)]:
                loc = feature['properties']['Location']
                name = feature['properties']['Title']
                if 'Business Name' in loc:
                    name = loc['Business Name']
                address_lines = []
                if 'Address' in loc:
                    address_lines = re.split(',\s+', loc['Address'])
                    if len(address_lines) > 1 and address_lines[-1] == 'Mexico':
                        address_lines = address_lines[:-1]
                lng = feature['geometry']['coordinates'][0]
                lat = feature['geometry']['coordinates'][1]
                cve = ''
                order = 99
                c_name = ''
                d_name = ''
                delegacion = self.find_delegacion(feature)
                colonia = self.find_colonia(feature)
                if colonia:
                    c_name = colonia['properties']['colonia']
                    d_name = colonia['properties']['delegacion']
                    cve = colonia['properties']['cve']
                    if cve in self.sorting:
                        c_name = self.sorting[cve]['label']
                        order = self.sorting[cve]['order']
                    else:
                        print('No sort for colonia {} - {}'.format(cve, c_name), file = sys.stderr)
                elif delegacion:
                    d_name = delegacion['properties']['delegacion']
                    order = 90
                    if d_name in self.DELEGACIONES:
                        order = self.DELEGACIONES[d_name]['order']
                else:
                    d_name = 'Beyond CDMX'
                place = {
                    'name': name,
                    'address': address_lines,
                    'url': feature['properties']['Google Maps URL'],
                    'lng': lng,
                    'lat': lat,
                    'cve': cve,
                    'order': order,
                    'c_name': c_name,
                    'd_name': d_name
                }
                self.all_places.append(place)

    def sort_and_print_places(self):
        colonia = ''
        s1 = sorted(self.all_places, key = itemgetter('lng'))
        s2 = sorted(s1, key = itemgetter('lat'), reverse = True)
        s3 = sorted(s2, key = itemgetter('order'))
        for place in s3:
            title = place['c_name']
            if title == '':
                title = place['d_name']
            else:
                title = '{} - {}'.format(place['d_name'], title)
            if title and title != colonia:
                colonia = title
                print(title)
                print()

            print(place['name'])
            for line in place['address']:
                print(line)
            print(place['url'])
            print()


ps = PlaceSorter()
ps.filter_places()
ps.sort_and_print_places()
