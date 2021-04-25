"""

    Define Loader

    Links:

        https://modosdk.foundry.com/wiki/Scene_Saver:_STL


    Code:

        extra/scripts/lxserv/stl_loader.py


"""


import struct


import lx
import lxifc
import lxu


# Dictionary to map ply property types to struct types
property_types = {
    "char": "c",
    "uchar": "B",
    "short": "h",
    "ushort": "H",
    "int": "i",
    "uint": "I",
    "float": "f",
    "double": "d",
}


class PLYLoader(lxifc.Loader):
    def __init__(self):
        self.filehandle = None
        self.scene_service = lx.service.Scene()
        self.load_target = None

        # ply recognized formats include
        # ( ascii | binary_big_endian | binary_little_endian )
        self.format = None

        self.comments = []  # Store comments as lists of strings

        # List of found elements as dictionaries, with properties stored
        # [{
        #   "name": "vertex",
        #   "count": 8,
        #   "properties": [{'name': x, "type": "float"}],
        # }]
        self.elements = []

        self.end_header = 0  # final byte of the header,

    def load_Cleanup(self):
        if self.filehandle:
            self.filehandle.close()
        return lx.result.OK

    def load_LoadInstance(self, loadInfo, monitor):
        pass

    def load_LoadObject(self, loadInfo, monitor, dest):
        print("load_LoadObject")
        scene = lx.object.Scene(dest)
        print("made a scene")
        item = scene.ItemAdd(
            self.scene_service.ItemTypeLookup(lx.symbol.sITYPE_MESH))
        print("added item")
        chan_write = scene.Channels(lx.symbol.s_ACTIONLAYER_SETUP, 0.0)
        chan_write = lx.object.ChannelWrite(chan_write)
        print("wrote to channel")
        mesh_loc = chan_write.ValueObj(
                item, item.ChannelLookup(lx.symbol.sICHAN_MESH_MESH))
        mesh_loc = lx.object.Mesh(mesh_loc)
        if not mesh_loc.test():
            print("Mesh failed test")
            lx.throw(lx.result.FALSE)
        mesh_loc.SetMeshEdits(lx.symbol.f_MESHEDIT_POLYGONS)
        return lx.result.OK

    def load_Recognize(self, filename, loadInfo):
        """ If we don't recognize the format, we should return
        lx.result.NOTFOUND

        :param filename: path to the file
        :param loadInfo: info object

        """

        self.filehandle = open(filename, "rb")

        # Early exit if magic number not found,
        magicnumber = self.filehandle.readline().strip()
        if magicnumber != b"ply":
            lx.throw(lx.result.NOTFOUND)

        # Line after magic number should define the format,
        # not doing full check, only looking for the second value
        # to match the allowed format types
        _, format, version = self.filehandle.readline().split()
        if format == b"ascii":
            self.format = "ascii"
        elif format == b"binary_big_endian":
            self.format = "binary_big_endian"
        elif format == b"binary_little_endian":
            self.format = "binary_little_endian"
        else:
            lx.throw(lx.result.NOTFOUND)

        element = None  # remember the previously defined element,

        # Read rest of the headers, raising lookup error when header
        # couldn't be parsed.
        while self.filehandle:
            line = self.filehandle.readline().strip()

            if line == b"":
                lx.throw(lx.result.NOTFOUND)

            if line == b"end_header":
                break  # We've reached the end of header,

            # Check for comments and read to a list.
            if line.startswith(b"comment"):
                self.comments.append(line[8:])

            # Parse elements,
            elif line.startswith(b"element"):
                _, name, count = line.split()
                element = {"name": name, "count": count, "properties": []}
                self.elements.append(element)

            # Parse properties for elements,
            elif line.startswith(b"property"):
                fields = line.split()
                if len(fields) == 3:  # regular 'scalar' property
                    _, datatype, name = fields
                    element["properties"].append(
                            {"name": name, "type": datatype})

                elif len(fields) == 5:  # list type property
                    _, _, size, datatype, name = fields
                    element["properties"].append(
                            {"name": name, "type": datatype, "size": size})
                else:
                    lx.throw(lx.result.NOTFOUND)

            else:
                lx.throw(lx.result.NOTFOUND)

        self.end_header = self.filehandle.tell()
        print("parsed headers")

        info = lx.object.LoaderInfo(loadInfo)
        info.SetClass(lx.symbol.u_SCENE)
        print("set up info")

        self.load_target = lx.object.SceneLoaderTarget()
        self.load_target.set(loadInfo)
        self.load_target.SetRootType(lx.symbol.sITYPE_MESH)
        print("set load target")

        return lx.result.OK  # Tell Modo we've recognized the file.

    def parse_ascii(self):
        """ Read the data from the file. """
        pass

    def parse_binary(self):
        """ Read the binary data from the file. """
        pass


tags = {
    lx.symbol.sLOD_CLASSLIST: lx.symbol.a_SCENE,
    lx.symbol.sLOD_DOSPATTERN: "*.ply",
    lx.symbol.sLOD_MACPATTERN: "*.ply",
    lx.symbol.sSRV_USERNAME: "Polygon File Format"
}


lx.bless(PLYLoader, "ply_Loader", tags)
