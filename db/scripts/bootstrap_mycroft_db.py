# Mycroft Server - Backend
# Copyright (C) 2019 Mycroft AI Inc
# SPDX-License-Identifier: 	AGPL-3.0-or-later
#
# This file is part of the Mycroft Server.
#
# The Mycroft Server is free software: you can redistribute it and/or
# modify it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

from glob import glob
from os import environ, path, remove
from zipfile import ZipFile

from markdown import markdown
from psycopg2 import connect

MYCROFT_DB_DIR = path.join(path.abspath('..'), 'mycroft')
MYCROFT_DB_NAME = environ.get('DB_NAME', 'mycroft')
SCHEMAS = ('account', 'skill', 'device', 'geography', 'metric')
DB_DESTROY_FILES = (
    'drop_mycroft_db.sql',
    'drop_template_db.sql',
)
DB_CREATE_FILES = (
    'create_template_db.sql',
)
ACCOUNT_TABLE_ORDER = (
    'account',
    'agreement',
    'account_agreement',
    'membership',
    'account_membership',
)
SKILL_TABLE_ORDER = (
    'skill',
    'settings_display',
    'display',
    'oauth_credential',
    'oauth_token'
)
DEVICE_TABLE_ORDER = (
    'category',
    'geography',
    'text_to_speech',
    'wake_word',
    'wake_word_settings',
    'account_preferences',
    'account_defaults',
    'device',
    'device_skill',
)
GEOGRAPHY_TABLE_ORDER = (
    'country',
    'timezone',
    'region',
    'city'
)

METRIC_TABLE_ORDER = (
    'api',
    'api_history',
    'job',
    'core'
)

schema_directory = '{}_schema'


def get_sql_from_file(file_path: str) -> str:
    with open(path.join(MYCROFT_DB_DIR, file_path)) as sql_file:
        sql = sql_file.read()

    return sql


class PostgresDB(object):
    def __init__(self, db_name, user=None):
        db_host = environ.get('DB_HOST', '127.0.0.1')
        db_port = environ.get('DB_PORT', 5432)
        db_ssl_mode = environ.get('DB_SSLMODE')
        if db_name in ('postgres', 'defaultdb', 'mycroft_template'):
            db_user = environ.get('POSTGRES_USER', 'postgres')
            db_password = environ.get('POSTGRES_PASSWORD')
        else:
            db_user = environ.get('DB_USER', 'selene')
            db_password = environ['DB_PASSWORD']

        if user is not None:
            db_user = user

        self.db = connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
            sslmode=db_ssl_mode
        )
        self.db.autocommit = True

    def close_db(self):
        self.db.close()

    def execute_sql(self, sql: str, args=None):
        _cursor = self.db.cursor()
        _cursor.execute(sql, args)
        return _cursor


postgres_db = PostgresDB(db_name='postgres')

print('Destroying any objects we will be creating later.')
for db_destroy_file in DB_DESTROY_FILES:
    postgres_db.execute_sql(
        get_sql_from_file(db_destroy_file)
    )

print('Creating the mycroft database')
for db_setup_file in DB_CREATE_FILES:
    postgres_db.execute_sql(
        get_sql_from_file(db_setup_file)
    )

postgres_db.close_db()


template_db = PostgresDB(db_name='mycroft_template')

print('Creating the extensions')
template_db.execute_sql(
    get_sql_from_file(path.join('create_extensions.sql'))
)

print('Creating user-defined data types')
type_directory = path.join(MYCROFT_DB_DIR, 'types')
for type_file in glob(type_directory + '/*.sql'):
    template_db.execute_sql(
        get_sql_from_file(path.join(type_directory, type_file))
    )

print('Create the schemas and grant access')
for schema in SCHEMAS:
    template_db.execute_sql(
        get_sql_from_file(schema + '_schema/create_schema.sql')
    )

print('Creating the account schema tables')
# These are created first as other schemas have tables with
# foreign keys to these tables.
for table in ACCOUNT_TABLE_ORDER:
    create_table_file = path.join(
        'account_schema',
        'tables',
        table + '.sql'
    )
    template_db.execute_sql(
        get_sql_from_file(create_table_file)
    )

print('Creating the skill schema tables')
# Create the skill schema tables second as other schemas have tables with
# foreign keys to these tables.
for table in SKILL_TABLE_ORDER:
    create_table_file = path.join(
        'skill_schema',
        'tables',
        table + '.sql'
    )
    template_db.execute_sql(
        get_sql_from_file(create_table_file)
    )

print('Creating the geography schema tables')
for table in GEOGRAPHY_TABLE_ORDER:
    create_table_file = path.join(
        'geography_schema',
        'tables',
        table + '.sql'
    )
    template_db.execute_sql(
        get_sql_from_file(create_table_file)
    )

print('Creating the device schema tables')
for table in DEVICE_TABLE_ORDER:
    create_table_file = path.join(
        'device_schema',
        'tables',
        table + '.sql'
    )
    template_db.execute_sql(
        get_sql_from_file(create_table_file)
    )

print('Creating the metrics schema tables')
for table in METRIC_TABLE_ORDER:
    create_table_file = path.join(
        'metric_schema',
        'tables',
        table + '.sql'
    )
    template_db.execute_sql(
        get_sql_from_file(create_table_file)
    )

print('Granting access to schemas and tables')
for schema in SCHEMAS:
    template_db.execute_sql(
        get_sql_from_file(schema + '_schema/grants.sql')
    )

template_db.close_db()


print('Copying template to new database.')
postgres_db = PostgresDB(db_name='postgres')
postgres_db.execute_sql(get_sql_from_file('create_mycroft_db.sql'))
postgres_db.close_db()


mycroft_db = PostgresDB(db_name=MYCROFT_DB_NAME)
insert_files = [
    dict(schema_dir='account_schema', file_name='membership.sql'),
    dict(schema_dir='device_schema', file_name='text_to_speech.sql'),

]
for insert_file in insert_files:
    insert_file_path = path.join(
        insert_file['schema_dir'],
        'data',
        insert_file['file_name']
    )
    try:
        mycroft_db.execute_sql(
            get_sql_from_file(insert_file_path)
        )
    except FileNotFoundError:
        pass

print('Building geography.country table')
data_dir = environ.get('MYCROFT_DOC_DIR', '/opt/selene/data')
country_file = 'countryInfo.txt'
country_insert = """
INSERT INTO
    geography.country (iso_code, name)
VALUES
    ('{iso_code}', '{country_name}')
"""

with open(path.join(data_dir, country_file)) as countries:
    while True:
        rec = countries.readline()
        if rec.startswith('#ISO'):
            break

    for country in countries.readlines():
        country_fields = country.split('\t')
        insert_args = dict(
            iso_code=country_fields[0],
            country_name=country_fields[4]
        )
        mycroft_db.execute_sql(country_insert.format(**insert_args))

print('Building geography.region table')
region_file = 'admin1CodesASCII.txt'
region_insert = """
INSERT INTO
    geography.region (country_id, region_code, name)
VALUES
    (
        (SELECT id FROM geography.country WHERE iso_code = %(iso_code)s),
        %(region_code)s,
        %(region_name)s)
"""
with open(path.join(data_dir, region_file)) as regions:
    for region in regions.readlines():
        region_fields = region.split('\t')
        country_iso_code = region_fields[0][:2]
        insert_args = dict(
            iso_code=country_iso_code,
            region_code=region_fields[0],
            region_name=region_fields[1]
        )
        mycroft_db.execute_sql(region_insert, insert_args)

print('Building geography.timezone table')
timezone_file = 'timeZones.txt'
timezone_insert = """
INSERT INTO
    geography.timezone (country_id, name, gmt_offset, dst_offset)
VALUES
    (
        (SELECT id FROM geography.country WHERE iso_code = %(iso_code)s),
        %(timezone_name)s,
        %(gmt_offset)s,
        %(dst_offset)s
    )
"""
with open(path.join(data_dir, timezone_file)) as timezones:
    timezones.readline()
    for timezone in timezones.readlines():
        timezone_fields = timezone.split('\t')
        insert_args = dict(
            iso_code=timezone_fields[0],
            timezone_name=timezone_fields[1],
            gmt_offset=timezone_fields[2],
            dst_offset=timezone_fields[3]
        )
        mycroft_db.execute_sql(timezone_insert, insert_args)

print('Building geography.city table')
cities_file = 'cities500.zip'
region_query = "SELECT id, region_code FROM geography.region"
query_result = mycroft_db.execute_sql(region_query)
region_lookup = dict()
for row in query_result.fetchall():
    region_lookup[row[1]] = row[0]

timezone_query = "SELECT id, name FROM geography.timezone"
query_result = mycroft_db.execute_sql(timezone_query)
timezone_lookup = dict()
for row in query_result.fetchall():
    timezone_lookup[row[1]] = row[0]
with ZipFile(path.join(data_dir, cities_file)) as cities_zip:
    with cities_zip.open('cities500.txt') as cities:
        with open(path.join(data_dir, 'city.dump'), 'w') as dump_file:
            for city in cities.readlines():
                city_fields = city.decode().split('\t')
                city_region = city_fields[8] + '.' + city_fields[10]
                region_id = region_lookup.get(city_region)
                timezone_id = timezone_lookup[city_fields[17]]
                if region_id is not None:
                    dump_file.write('\t'.join([
                        region_id,
                        timezone_id,
                        city_fields[1],
                        city_fields[4],
                        city_fields[5]
                    ]) + '\n')
with open(path.join(data_dir, 'city.dump')) as dump_file:
    cursor = mycroft_db.db.cursor()
    cursor.copy_from(dump_file, 'geography.city', columns=(
        'region_id', 'timezone_id', 'name', 'latitude', 'longitude')
                     )
remove(path.join(data_dir, 'city.dump'))

mycroft_db.close_db()
