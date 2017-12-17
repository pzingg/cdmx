#!/usr/bin/python3

import click
from geojson_utils import point_in_polygon, centroid
import json
from operator import itemgetter
import os
import re
import sys
from xml.sax import saxutils


class PlaceSorter:
    DELEGACIONES = {
        'Cuauhtémoc': { 'order': 13, 'file': 'Cuauhtemoc'},
        'Venustiano Carranza': { 'order': 14, 'file': None },
        'Miguel Hidalgo': { 'order': 20, 'file': 'MiguelHidalgo' },
        'Cuajimalpa de Morelos': { 'order': 32, 'file': 'CuajimalpaDeMorelos' },
        'Alvaro Obregón': { 'order': 45, 'file': 'AlvaroObregon' },
        'Benito Juarez': { 'order': 46, 'file': 'BenitoJuarez' },
        'Coyoacán': { 'order': 55, 'file': 'Coyoacan' },
        'Tlalpan': { 'order': 61, 'file': None },
        'Xochimilco': { 'order': 62, 'file': None },
    }
    COLONIAS = [
        ('Santa Maria la Ribera', 1, [ '15-075', '15-076', '15-078' ]),
        ('Tlateloco', 2, [ '15-035', '15-050', '15-051', '15-061' ]),
        ('Tepito', 3, [ '15-056', '15-057', '15-058' ]),
        ('Centro', 4, [ '15-037', '15-039', '15-040', '15-041', '15-043', '15-044' ]),
        ('Guerrero', 5, [ '15-036', '15-052', '15-053' ]),
        ('San Rafael/Tabacalera', 6, [ '15-031', '15-073']),
        ('Cuauhtemoc', 7, [ '15-009' ]),
        ('Zona Rosa/Juarez', 8, [ '15-017' ]),
        ('La Condesa', 9, [ '15-008', '15-016', '15-055', '15-054' ]),
        ('Roma Norte', 10, [ '15-068', '15-069', '15-070' ]),
        ('Roma Sur', 11, [ '15-071', '15-072' ]),
        ('Doctores', 12, [ '15-045']),
        ('Argentina', 21, [ '16-027', '16-014' ]),
        ('Polanco', 22, [ '16-035', '16-032', '16-031', '16-055', '16-054', '16-065', '16-021', '16-059', '16-022', '16-018' ]),
        ('Bosque de Chapultepec', 23, [ '16-015' ]),
        ('San Miguel Chapultepec', 24, [ '16-094', '16-095' ]),
        ('Daniel Garza', 25, [ '16-086', '16-003', '16-025', '16-058' ]),
        ('Lomas de Chapultepec', 26, [ '16-042' ]),
        ('Santa Fe', 31, [ '04-025', '04-028' ]),
        ('Narvarte', 41, [ '14-063' ]),
        ('Insurgentes Sur/Napoles', 42, [ '14-014', '14-028']),
        ('Xoco', 43, [ '14-049' ]),
        ('San Angel', 51, [ '10-193', '10-192', '10-042', '03-019' ]),
        ('Coyoacan', 52, [ '03-037', '03-065', '03-105', '03-106', '03-114', '03-107', '03-012', '03-099' ]),
        ('Ciudad Universitaria', 53, [ '03-021' ]),
        ('Jardines del Pedregal', 54, [ '10-091', '03-088', '03-062' ])
    ]

    MIN_LAT = 18.0
    MAX_LAT = 20.0
    MIN_LNG = -100.0
    MAX_LNG = -98.0

    MAPS_ME_HEADER = """<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://earth.google.com/kml/2.2">
    <Document>
      <Style id="placemark-blue">
        <IconStyle>
          <Icon>
            <href>http://mapswith.me/placemarks/placemark-blue.png</href>
          </Icon>
        </IconStyle>
      </Style>
      <Style id="placemark-brown">
        <IconStyle>
          <Icon>
            <href>http://mapswith.me/placemarks/placemark-brown.png</href>
          </Icon>
        </IconStyle>
      </Style>
      <Style id="placemark-green">
        <IconStyle>
          <Icon>
            <href>http://mapswith.me/placemarks/placemark-green.png</href>
          </Icon>
        </IconStyle>
      </Style>
      <Style id="placemark-orange">
        <IconStyle>
          <Icon>
            <href>http://mapswith.me/placemarks/placemark-orange.png</href>
          </Icon>
        </IconStyle>
      </Style>
      <Style id="placemark-pink">
        <IconStyle>
          <Icon>
            <href>http://mapswith.me/placemarks/placemark-pink.png</href>
          </Icon>
        </IconStyle>
      </Style>
      <Style id="placemark-purple">
        <IconStyle>
          <Icon>
            <href>http://mapswith.me/placemarks/placemark-purple.png</href>
          </Icon>
        </IconStyle>
      </Style>
      <Style id="placemark-red">
        <IconStyle>
          <Icon>
            <href>http://mapswith.me/placemarks/placemark-red.png</href>
          </Icon>
        </IconStyle>
      </Style>
      <Style id="placemark-yellow">
        <IconStyle>
          <Icon>
            <href>http://mapswith.me/placemarks/placemark-yellow.png</href>
          </Icon>
        </IconStyle>
      </Style>"""

    MAPS_ME_FOOTER = """    </Document>
    </kml>"""


    def __init__(self, ofname):
        self.delegaciones = []
        self.colonias = []
        self.all_places = []
        self.sorting = { }
        self.build_sorting()
        if ofname is not None:
            self.of = open(ofname, 'wt', encoding = 'utf-8')
        else:
            self.of = sys.stdout


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
                        print('{}, no polygons'.format(name), file = sys.stderr)
                        sys.exit(1)
                    self.delegaciones.append({
                        'polygons': polygons,
                        'properties': {
                            'delegacion': name,
                            'order': order
                        }
                    })
                else:
                    print('{}, geometry type is {}'.format(name, feature['geometry']['type']), file = sys.stderr)
                    sys.exit(1)


    def parse_delegacion(self, delegacion, fname):
        with open(fname) as f:
            collection = json.load(f)
            for feature in collection['features']:
                if feature['geometry']['type'] == 'Polygon':
                    colonia = feature['properties']['NOMBRE_COLONIA']
                    cve = feature['properties']['CVE_COL']
                    center = centroid(feature['geometry'])

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

        print('Parsed {} colonias'.format(len(self.colonias)), file = sys.stderr)

        with open('Saved Places.json') as f:
            collection = json.load(f)
            print('Parsing {} places'.format(len(collection['features'])), file = sys.stderr)

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
                    'published': feature['properties']['Published'],
                    'lng': lng,
                    'lat': lat,
                    'cve': cve,
                    'order': order,
                    'c_name': c_name,
                    'd_name': d_name
                }
                self.all_places.append(place)

        print('Filtered to {} places'.format(len(self.all_places)), file = sys.stderr)


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
                print(title, file = self.of)
                print('', file = self.of)

            print(place['name'], file = self.of)
            for line in place['address']:
                print(line, file = self.of)
            print(place['url'], file = self.of)
            print('', file = self.of)


    def export_to_maps_me(self, set_name):
        print(self.MAPS_ME_HEADER, file = self.of)
        print("""    <name>{}</name>
    <visibility>1</visibility>""".format(set_name), file = self.of)
        for place in self.all_places:
            description = '\n'.join(place['address'])
            description = description.strip()
            d = ''
            if description != '':
                d = '\n      <description>{}</description>'.format(saxutils.escape(description))
            print("""    <Placemark>
      <name>{}</name>{}
      <TimeStamp><when>{}</when></TimeStamp>
      <styleUrl>#placemark-blue</styleUrl>
      <Point><coordinates>{},{}</coordinates></Point>
      <ExtendedData xmlns:mwm="http://mapswith.me">
         <mwm:scale>18</mwm:scale>
      </ExtendedData>
    </Placemark>""".format(saxutils.escape(place['name']), d,
        place['published'], place['lng'], place['lat']), file = self.of)
        print(self.MAPS_ME_FOOTER, file = self.of)


def text(ofname):
    click.echo('Outputting places as text')
    ps = PlaceSorter(ofname)
    ps.filter_places()
    ps.sort_and_print_places()


def kml(ofname, set_name):
    click.echo('Ouputting places as kml')
    ps = PlaceSorter(ofname)
    ps.filter_places()
    ps.export_to_maps_me(set_name)


@click.command()
@click.option('--kml-set-name', '-k', 'set_name', default = '', help = 'kml output: set name')
@click.option('--output', '-o', 'ofname', default = None, help = 'output file name')
def places(ofname, set_name):
    if set_name != '':
        kml(ofname, set_name)
    else:
        text(ofname)

if __name__ == '__main__':
    places()
