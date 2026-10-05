"""Use case: Represents expected product-rule failures.

What it does: Gives application and presentation layers stable error categories.
"""


class ExecPlusError(Exception):
    pass


class AuthorizationError(ExecPlusError):
    pass


class ClarificationRequiredError(ExecPlusError):
    pass


class UnsupportedQuestionError(ExecPlusError):
    pass


class UnsafeQueryError(ExecPlusError):
    pass


class QueryDataError(UnsafeQueryError):
    pass


class ProviderUnavailableError(ExecPlusError):
    pass


class UnverifiedAnswerError(ExecPlusError):
    pass
