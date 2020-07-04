# starlette_jsonapi
A minimal "framework" intended to help write [json:api](https://jsonapi.org) compliant services in async Python,
written on top of [starlette](https://starlette.io) and [marshmallow-jsonapi](https://marshmallow-jsonapi.readthedocs.io/).

In the maintainer's view, REST frameworks that come with a complete data layer implementation are quite limiting 
and rarely usable in production systems due to business logic needs or authorization constraints. 
The default implementation they come with is usually getting in the way, more than helping.

Because of that, `starlette_jsonapi` does not contain a data layer implementation, so you should be able to pick 
any available async ORM. This also means that you are going to get a very basic interface for writing a REST resource, 
with some helpers to make your experience more pleasant, but nothing fancy.

### Features
- 99% tests coverage
- basic json:api serialization
- including related resources
- starlette friendly route generation
- exception handlers to serialize as json:api responses 

### Todo:
- sparse fields
- pagination helpers
- sorting helpers
- relationship resources
- documentation
- examples for other ORMs

## Docs
You should take a look at the [examples](examples) directory for implementation ideas.

After you've decided which ORM to use, you can start writing the associated schemas, 
using the marshmallow_jsonapi library (which itself is extending [marshmallow](https://marshmallow.readthedocs.io/)).  

```python
from marshmallow_jsonapi import fields
from starlette_jsonapi.fields import JSONAPIRelationship
from starlette_jsonapi.schema import JSONAPISchema

class ExampleSchema(JSONAPISchema):
    class Meta:
        type_ = 'examples'

    id = fields.Str(dump_only=True)
    some_optional_field = fields.Str()
    some_required_field = fields.Str(required=True)

class ChildExampleSchema(JSONAPISchema):
    class Meta:
        type_ = 'examples'

    id = fields.Str(dump_only=True)
    name = fields.Str()
    
    parent = JSONAPIRelationship(
        type_='examples',
        schema='ExampleSchema',
        include_resource_linkage=True,
        required=True,
        # `id_attribute` can be specified in order to allow serializing 
        # relationships even when the related object is not available. 
        # See the `sample-tortoise-orm` example for more information.
    )
```

You can also generate the associated `links` object by specifying more options in the Meta class of a schema:
```python
from marshmallow_jsonapi import fields
from starlette_jsonapi.schema import JSONAPISchema
class SomeSchema(JSONAPISchema):
    id = fields.Str(dump_only=True)
    name = fields.Str()

    class Meta:
        type_='some-resource'
        self_route = 'some-resource:get'
        self_route_kwargs = {'id': '<id>'}
        self_route_many = 'some-resource:get_all'
```


Once the schema is defined, we can move to adding the associated resource class
```python
from starlette_jsonapi.resource import BaseResource
from starlette_jsonapi.responses import JSONAPIResponse
from starlette_jsonapi.exceptions import ResourceNotFound

examples_db = {}
last_id = 0

class ExampleResource(BaseResource):
    type_ = 'examples'
    schema = ExampleSchema

    async def get(self, id=None, *args, **kwargs):
        example = examples_db.get(id)
        if not example:
            raise ResourceNotFound
        return await self.serialize(example)
    
    async def patch(self, id=None, *args, **kwargs):
        example = examples_db.get(id)
        if not example:
            raise ResourceNotFound
        
        body = await self.deserialize_body(partial=True)
        if body.get('some_optional_field'):
            example['some_optional_field'] = body.get('some_optional_field')
        if body.get('some_required_field'):
            example['some_required_field'] = body.get('some_required_field')

        return await self.serialize(example)

    async def delete(self, id=None, *args, **kwargs):
        example = examples_db.pop(id, None)
        if not example:
            raise ResourceNotFound
        return JSONAPIResponse(status_code=204)

    async def get_all(self, *args, **kwargs):
        examples = list(examples_db.values())
        return self.serialize(examples, many=True) 
    
    async def post(self, *args, **kwargs):
        global last_id
        body = await self.deserialize_body()
        last_id += 1
        example = {'id': last_id}
        if body.get('some_optional_field'):
            example['some_optional_field'] = body.get('some_optional_field')
        
        # We didn't ask for a partial deserialization, so a required field shouldn't throw a KeyError
        example['some_required_field'] = body['some_required_field']

        return await self.serialize(example)
```


## Contributing
This project is in its early days, so **any** help is appreciated.

### Running tests:
As simple as running ```tox```.

If you plan to use pyenv and want to run tox for multiple python versions, 
you can create multiple virtual environments and then make them available to tox by running 
something like: `pyenv shell starlette_jsonapi_venv36 starlette_jsonapi_venv37`.
