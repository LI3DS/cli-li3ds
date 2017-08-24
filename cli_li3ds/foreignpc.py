from . import api


def create_foreignpc_table(foreignpc_table, foreignpc_server, driver):
    table = '{schema}.{table}'.format(**foreignpc_table)
    del foreignpc_table['schema']
    del foreignpc_table['table']

    options = {'patch_size': 100}
    if 'time_offset' in foreignpc_table:
        options['time_offset'] = foreignpc_table['time_offset']
        del foreignpc_table['time_offset']

    if driver == 'fdwli3ds.Sbet':
        options['sources'] = foreignpc_table['filepath']
    elif driver == 'fdwli3ds.EchoPulse':
        options['directory'] = foreignpc_table['filepath']

    del foreignpc_table['filepath']

    return api.ForeignpcTable(foreignpc_server, foreignpc_table, table=table, options=options)


def create_foreignpc_view(foreignpc_view, foreignpc_table):
    view = '{schema}.{view}'.format(**foreignpc_view)
    del foreignpc_view['schema']
    del foreignpc_view['view']
    return api.ForeignpcView(foreignpc_table, foreignpc_view, view=view)


def create_datasource(datasource, session, referential, name, type_):
    uri = 'column:{}.{}_view.points'.format(datasource['schema'], name)
    del datasource['schema']
    return api.Datasource(session, referential, datasource, type=type_, uri=uri)
