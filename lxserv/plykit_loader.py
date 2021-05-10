"""

    Define Loader

    Links:

        https://modosdk.foundry.com/wiki/Scene_Saver:_STL


    Code:

        extra/scripts/lxserv/stl_loader.py


    This is the structure of a typical PLY file:

        - Header
        - Vertex List
        - Face List 
        - (lists of other elements)

    The header is a series of carraige-return terminated lines of text that 
    describe the remainder of the file. The header includes a description of 
    each element type, including the element's name (e.g. "edge"), how many
    such elements are in the object, and a list of the various properties
    associated with the element. The header also tells whether the file is
    binary or ASCII. Following the header is one list of elements for each
    element type, presented in the order described in the header.


"""


import struct


import lx
import lxifc
import lxu


# Dictionary to map ply property types to struct types
binary_property_types = {
    "char": "b",
    "uchar": "B",
    "short": "h",
    "ushort": "H",
    "int": "i",
    "uint": "I",
    "float": "f",
    "double": "d",
}

ascii_property_types = {
    "char": int,
    "uchar": int,
    "short": int,
    "ushort": int,
    "int": int,
    "uint": int,
    "float": float,
    "double": float,
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
        """ 

        :param loadInfo:
        :param monitor:
        :param dest:

        """

        # Set position of file at end of header,
        self.filehandle.seek(self.end_header)

        vertices = []
        faces = []

        if self.format == "ascii":
            for element in self.elements:
                if element.get('name') == "vertex":
                    # For this element, read expected types to list
                    types = []
                    for prop in element.get("properties"):
                        types.append(ascii_property_types.get(prop.get('type')))

                    # Each element is expected to be stored on one line, parse each
                    # line with expected property types.
                    for _ in range(element.get('count', 0)):
                        data = tuple(t(value) for t, value in zip(types, self.filehandle.readline().strip().split()))
                        vertices.append(data[:3]) # push the first three types, assuming here they are position xyz

                elif element.get('name') == "face":
                    for _ in range(element.get('count', 0)):
                        data = self.filehandle.readline().strip().split()
                        faces.append(tuple(int(d) for d in data[1:]))
        
        elif self.format == "binary_big_endian":
            pass

        elif self.format == "binary_little_endian":
            pass

        else:
            pass

        scene = lx.object.Scene(dest)

        item = scene.ItemAdd(
            self.scene_service.ItemTypeLookup(lx.symbol.sITYPE_MESH))

        chan_write = scene.Channels(lx.symbol.s_ACTIONLAYER_SETUP, 0.0)
        chan_write = lx.object.ChannelWrite(chan_write)

        mesh = chan_write.ValueObj(
                item, item.ChannelLookup(lx.symbol.sICHAN_MESH_MESH))
        mesh = lx.object.Mesh(mesh)
        if not mesh.test():
            lx.throw(lx.result.FALSE)

        point = mesh.PointAccessor()
        polygon = mesh.PolygonAccessor()
        if not point.test() and not polygon.test():
            lx.throw(lx.result.FALSE)

        # vertex should be a tuple for position,
        points = {}
        for index, position in enumerate(vertices):
            points[index] = point.New(position)

        for face in faces:
            vertIds = tuple(points[i] for i in face)
            storage = lx.object.storage('p', len(vertIds))
            for index, _id in enumerate(vertIds):
                storage[index] = _id
            polygon.New(lx.symbol.iPTYP_FACE, storage, len(vertIds), 0)

        # Add comments from header to the item
        if self.comments:
            tag = lx.object.StringTag(item)
            tag.Set(lx.symbol.iTAG_COMMENT, "\n".join(self.comments))

        mesh.SetMeshEdits(lx.symbol.f_MESHEDIT_POLYGONS)

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
                self.comments.append(str(line[8:].decode('ascii')))

            # Parse elements,
            elif line.startswith(b"element"):
                _, name, count = line.split()
                element = {"name": name, "count": int(count), "properties": []}
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

        info = lx.object.LoaderInfo(loadInfo)
        info.SetClass(lx.symbol.u_SCENE)

        self.load_target = lx.object.SceneLoaderTarget()
        self.load_target.set(loadInfo)
        self.load_target.SetRootType(lx.symbol.sITYPE_MESH)

        return lx.result.OK  # Tell Modo we've recognized the file.


tags = {
    lx.symbol.sLOD_CLASSLIST: lx.symbol.a_SCENE,
    lx.symbol.sLOD_DOSPATTERN: "*.ply",
    lx.symbol.sLOD_MACPATTERN: "*.ply",
    lx.symbol.sSRV_USERNAME: "Polygon File Format"
}


lx.bless(PLYLoader, "ply_Loader", tags)
