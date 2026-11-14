from app.core.errors import ApplicationError


class InvalidPageListRequestError(ApplicationError):
    status_code = 422
    code = "invalid_page_list_request"


class PageNotFoundError(ApplicationError):
    status_code = 404
    code = "page_not_found"


class InvalidPageLanguageError(ApplicationError):
    status_code = 422
    code = "invalid_page_language"
