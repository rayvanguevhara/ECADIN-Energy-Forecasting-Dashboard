class ForecastingError(Exception):
    """Base forecasting exception."""


class ContractError(ForecastingError):
    """Raised when a data or output contract is violated."""


class ConfigurationError(ForecastingError):
    """Raised when production configuration is invalid."""


class InsufficientHistoryError(ForecastingError):
    """Raised when a model cannot forecast from the supplied history."""
