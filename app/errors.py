"""Application errors that map cleanly to structured API responses."""


class GPISException(Exception):
    code = "gpis_error"
    status_code = 500


class DistrictNotFound(GPISException):
    code = "district_not_found"
    status_code = 404


class InvalidCategory(GPISException):
    code = "invalid_category"
    status_code = 400


class MissingScoreInputs(GPISException):
    code = "missing_score_inputs"
    status_code = 422


class TrendUnavailable(GPISException):
    code = "trend_unavailable"
    status_code = 422


class InvalidComparison(GPISException):
    code = "invalid_comparison"
    status_code = 422


class RepositoryUnavailable(GPISException):
    code = "repository_unavailable"
    status_code = 503


class SessionNotFound(GPISException):
    code = "session_not_found"
    status_code = 404


class SessionExpired(GPISException):
    code = "session_expired"
    status_code = 410
