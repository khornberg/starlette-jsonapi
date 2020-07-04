import logging
from typing import Type, Any, List, Optional

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route, Mount

from starlette_jsonapi.exceptions import JSONAPIException, HTTPException
from starlette_jsonapi.responses import JSONAPIResponse
from starlette_jsonapi.schema import JSONAPISchema
from starlette_jsonapi.utils import parse_included_params, serialize_error

logger = logging.getLogger(__name__)


class BaseResource:
    """ A basic json:api resource implementation, data layer agnostic. """

    # The json:api type, used to compute the path for this resource
    # such that BaseResource.register_routes(app=app, base_path='/api/') will register
    # the following routes:
    # - GET `/api/<type_>/`
    # - POST `/api/<type_>/`
    # - GET `/api/<type_>/{id:str}`
    # - PATCH `/api/<type_>/{id:str}`
    # - DELETE `/api/<type_>/{id:str}`
    type_: str = ''

    # The json:api serializer, a subclass of JSONAPISchema.
    schema: Type[JSONAPISchema] = JSONAPISchema

    # High level filter for HTTP requests.
    # If you specify a smaller subset, any request that specifies a method
    # not listed here will result in a 405 error.
    allowed_methods = {'GET', 'PATCH', 'POST', 'DELETE'}

    # By default `str`, but other options are documented in Starlette:
    # 'str', 'int', 'float', 'uuid', 'path'
    id_mask: str = 'str'

    # Optional, by default this will equal `type_` and will be used to register the Mount name.
    # Impacts the result of `url_path_for`, so it can be used to support multiple resource versions.
    # For example:
    # ```
    # from starlette.applications import Starlette
    #
    # class SomeResource(BaseResource):
    #   type_ = 'examples'
    #   register_as = 'v2-examples'
    #
    # app = Starlette()
    # SomeResource.register_routes(app=app, base_path='/api/v2')
    # assert app.url_path_for('v2-examples:get_all') == '/api/v2/examples/'
    # ```
    # `url_path_for` will
    register_as: str = ''

    def __init__(self, request: Request, *args, **kwargs) -> None:
        self.request = request

    async def get(self, id=None, *args, **kwargs) -> Response:
        raise JSONAPIException(status_code=405)

    async def patch(self, id=None, *args, **kwargs) -> Response:
        raise JSONAPIException(status_code=405)

    async def delete(self, id=None, *args, **kwargs) -> Response:
        raise JSONAPIException(status_code=405)

    async def get_all(self, *args, **kwargs) -> Response:
        raise JSONAPIException(status_code=405)

    async def post(self, *args, **kwargs) -> Response:
        raise JSONAPIException(status_code=405)

    async def deserialize_body(self, partial=None) -> dict:
        """ Returns the request body as defined by this Resource's `schema`."""
        raw_body = await self.validate_body(partial=partial)
        deserialized_body = self.schema(app=self.request.app).load(raw_body, partial=partial)
        return deserialized_body

    async def validate_body(self, partial=None) -> dict:
        """
        Validates the raw request body, raising JSONAPIException 400 errors if the body is not valid.
        Otherwise, the request.json() content is returned.
        """
        content_type = self.request.headers.get('content-type')
        if self.request.method in ('POST', 'PATCH') and content_type != 'application/vnd.api+json':
            raise JSONAPIException(
                status_code=400,
                detail='Incorrect or missing Content-Type header, expected `application/vnd.api+json`.',
            )
        try:
            body = await self.request.json()
        except Exception:
            logger.debug('Could not read request body.', exc_info=True)
            raise JSONAPIException(status_code=400, detail='Could not read request body.')

        errors = self.schema(app=self.request.app).validate(body, partial=partial)
        if errors:
            logger.debug('Could not validate request body according to JSON:API spec: %s.', errors)
            raise JSONAPIException(status_code=400, errors=errors.get('errors'))
        return body

    async def serialize(self, data: Any, many=False) -> JSONAPIResponse:
        included_relations = await self._prepare_included(data=data, many=many)
        schema = self.schema(app=self.request.app, include_data=included_relations)
        body = schema.dump(data, many=many)
        return JSONAPIResponse(
            content=body,
        )

    @classmethod
    async def handle_error(cls, request: Request, exc: Exception) -> JSONAPIResponse:
        if not isinstance(exc, HTTPException):
            logger.exception('Encountered an error while handling request.')
        return serialize_error(exc)

    @classmethod
    async def handle_request(
            cls, handler_name: str, request: Request,
            extract_id: bool = False, *args, **kwargs
    ) -> Response:
        """
            Handles a request by calling the appropriate handler.
            Additional args and kwargs are passed to the handler method,
            which is usually one of: `get`, `put`, `patch`, `delete`, `get_all` or `post`.
        """
        if extract_id:
            id_ = request.path_params.get('id')
            kwargs.update({'id': id_})

        try:
            if request.method not in cls.allowed_methods:
                raise JSONAPIException(status_code=405)
            resource = cls(request)
            handler = getattr(resource, handler_name, None)
            response = await handler(*args, **kwargs)  # type: Response
        except Exception as e:
            response = await cls.handle_error(request=request, exc=e)
        return response

    @classmethod
    async def handle_get(cls, request: Request):
        return await cls.handle_request(handler_name='get', request=request, extract_id=True)

    @classmethod
    async def handle_patch(cls, request: Request):
        return await cls.handle_request(handler_name='patch', request=request, extract_id=True)

    @classmethod
    async def handle_delete(cls, request: Request):
        return await cls.handle_request(handler_name='delete', request=request, extract_id=True)

    @classmethod
    async def handle_get_all(cls, request: Request):
        return await cls.handle_request(handler_name='get_all', request=request)

    @classmethod
    async def handle_post(cls, request: Request):
        return await cls.handle_request(handler_name='post', request=request)

    @classmethod
    def register_routes(cls, app: Starlette, base_path: str):
        if not cls.type_:
            raise Exception('Cannot register a resource without specifying its `type_`.')
        name = cls.register_as or cls.type_
        app.routes.append(
            Mount(
                name=name,
                path='{}/{}'.format(base_path.rstrip('/'), cls.type_),
                routes=[
                    Route(
                        '/{{id:{}}}'.format(cls.id_mask), cls.handle_get,
                        methods=['GET'], name='get',
                    ),
                    Route(
                        '/{{id:{}}}'.format(cls.id_mask), cls.handle_patch,
                        methods=['PATCH'], name='patch',
                    ),
                    Route(
                        '/{{id:{}}}'.format(cls.id_mask), cls.handle_delete,
                        methods=['DELETE'], name='delete',
                    ),
                    Route(
                        '/', cls.handle_get_all,
                        methods=['GET'], name='get_all',
                    ),
                    Route(
                        '/', cls.handle_post,
                        methods=['POST'], name='post',
                    ),
                ],
            )
        )

    # Methods used to generate compound documents
    # https://jsonapi.org/format/#document-compound-documents
    async def _prepare_included(self, data: Any, many: bool) -> Optional[List[str]]:
        include_param = parse_included_params(self.request)
        if not include_param:
            return None
        include_param_list = list(include_param)
        if many is True:
            for item in data:
                try:
                    await self.prepare_relations(obj=item, relations=include_param_list)
                except _StopInclude:
                    return None
        else:
            try:
                await self.prepare_relations(obj=data, relations=include_param_list)
            except _StopInclude:
                return None
        return include_param_list

    async def prepare_relations(self, obj: Any, relations: List[str]) -> None:
        """
        Should be implemented by subclasses in order to support compound documents
        for asynchronous objects that may need fetching.

        Example `relations`:
            url = /some-url?include=resource1,resource2.resource3
            relations = ['resource1', 'resource2.resource3']

        :param obj: an object that was passed to `serialize`
        :param relations: list of relations, ex: ['resource1', 'resource2.resource3']
        """
        raise _StopInclude


class _StopInclude(Exception):
    pass