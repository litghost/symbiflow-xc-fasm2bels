""" Utilities for match VPR route names with xc7 site pin sources. """
from collections import namedtuple
from lib.parse_route import find_net_sources
import re


class Net(namedtuple('Net', 'name wire_pkey tile site_pin')):
    """
    Args:
        name (str): VPR net name
        wire_pkey (int): Wire table primary key.  This is unique in the part.
        tile (str): Name of tile this wire belongs too.  This is redundant
            information wire_pkey uniquely indentifies the tile.
        site_pin (str): Name of site pin this wire belongs. This is redundant
            information wire_pkey uniquely indentifies the site pin.
    """
    pass


# BLK_TI-CLBLL_L.CLBLL_LL_A1[0] -> (CLBLL_L, CLBLL_LL_A1)
PIN_NAME_TO_PARTS = re.compile(r'^BLK_TI-([^\.]+)\.([^\]]+)\[0\]$')


def create_net_list(conn, graph, route_file):
    """ From connection database, rrgraph and VPR route file, yields net_map.Net.
    """
    c = conn.cursor()

    for net, node in find_net_sources(route_file):
        graph_node = graph.nodes[node.inode]
        assert graph_node.loc.x_low == node.x_low
        assert graph_node.loc.x_high == node.x_high
        assert graph_node.loc.y_low == node.y_low
        assert graph_node.loc.y_high == node.y_high

        gridloc = graph.loc_map[(node.x_low, node.y_low)]
        pin_name = graph.pin_ptc_to_name_map[(gridloc.block_type_id, node.ptc)]

        # Do not add synthetic nets to map.
        if pin_name.startswith('BLK_SY-'):
            continue

        m = PIN_NAME_TO_PARTS.match(pin_name)
        assert m is not None, pin_name

        pin = m.group(2)

        c.execute(
            "SELECT pkey, name, tile_type_pkey FROM tile WHERE grid_x = ? AND grid_y = ?",
            (node.x_low, node.y_low)
        )
        tile_pkey, tile_name, tile_type_pkey = c.fetchone()

        c.execute(
            """
SELECT
  pkey, site_pkey
FROM
  wire_in_tile
WHERE
  tile_type_pkey = ? AND name = ?;""", (tile_type_pkey, pin)
        )
        result = c.fetchone()
        assert result is not None, (tile_name, pin, node, tile_type_pkey)
        wire_in_tile_pkey, site_pkey = result

        c.execute("SELECT name FROM site WHERE pkey = ?", (site_pkey, ))
        site_name = c.fetchone()[0]

        c.execute(
            "SELECT pkey FROM wire WHERE wire_in_tile_pkey = ? AND tile_pkey = ?",
            (wire_in_tile_pkey, tile_pkey)
        )
        wire_pkey = c.fetchone()[0]

        yield Net(name=net, wire_pkey=wire_pkey, tile=tile_name, site_pin=pin)
