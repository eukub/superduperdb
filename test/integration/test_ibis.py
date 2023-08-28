import os
import ibis
import PIL.Image
import torchvision

import pytest

from superduperdb import CFG
from superduperdb.db import types
from superduperdb.db.base.build import build_vector_database
from superduperdb.container.document import Document as D
from superduperdb.db.ibis.db import IbisDB
from superduperdb.db.filesystem.artifacts import FileSystemArtifactStore
from superduperdb.db.ibis.data_backend import IbisDataBackend
from superduperdb.db.ibis.schema import IbisSchema
from superduperdb.db.sqlalchemy.metadata import SQLAlchemyMetadata
from superduperdb.db.ibis.query import Table
from superduperdb.ext.pillow.image import pil_image
from superduperdb.ext.torch.model import TorchModel

@pytest.fixture(scope='session')
def ibis_db():
    connection = ibis.sqlite.connect("mydb.sqlite")

    # Create data layer
    db = IbisDB(
        databackend=IbisDataBackend(conn=connection, name='ibis'),
        metadata=SQLAlchemyMetadata(conn=connection.con, name='ibis'),
        artifact_store=FileSystemArtifactStore(
            conn='./.tmp', name='ibis'
        ),
        vector_database=build_vector_database(CFG.vector_search.type),
    )
    yield db
    os.remove('mydb.sqlite')


def test_end2end(ibis_db):
    db = ibis_db
    schema = IbisSchema(
        identifier='my_table',
        fields={
            'id': 'int64',
            'health': 'int32',
            'age': 'int32',
            'image': pil_image,
        }
    )
    im = PIL.Image.open('test/material/data/test-image.jpeg')
    data_to_insert = [
        {'id': 1, 'health': 0, 'age': 25, 'image': im},
        {'id': 2, 'health': 0, 'age': 25, 'image': im},
        {'id': 3, 'health': 0, 'age': 25, 'image': im},
        {'id': 4, 'health': 0, 'age': 25, 'image': im},
    ]
    t = Table(identifier='my_table', schema=schema)
    t.create(db)

    db.add(t)
    db.execute(
        t.insert([D({'id': d['id'], 'health': d['health'], 'age': d['age'], 'image': d['image']}) for d in data_to_insert])
    )



    # -------------- retrieve data  from table ----------------
    imgs = db.execute(t.select("image", "age", "health"))
    for img in imgs:
        print(img)


    # preprocessing function
    preprocess = torchvision.transforms.Compose([
        torchvision.transforms.Resize(256),
        torchvision.transforms.CenterCrop(224),
        torchvision.transforms.ToTensor(),
        torchvision.transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )])

    def postprocess(x):
        return int(x.topk(1)[1].item())

    # create a torchvision model
    resnet = TorchModel(
            identifier='resnet18',
        preprocess=preprocess,
        postprocess=postprocess,

        object=torchvision.models.resnet18(pretrained=False),
        output_type=types.int32,
    )

    # Apply the torchvision model
    resnet.predict(X='image', db=db, select=t.select('id', 'image'), max_chunk_size=3000, overwrite=True)


    # Query the results back
    q = t.filter(t.age == 25).outputs('resnet18', db)
    curr = db.execute(q)

    for c in curr:
        assert all([ k in ['id', 'health', 'age', 'image', 'output', 'query_id', 'key', 'input_id'] for k in c.unpack().keys()])