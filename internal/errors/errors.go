package errors

import sterrors "errors"

type Kind string

const (
	KindInternal       Kind = "internal"
	KindValidation     Kind = "validation"
	KindDependency     Kind = "dependency"
	KindClone          Kind = "clone"
	KindConfig         Kind = "config"
	KindIndex          Kind = "index"
	KindNotImplemented Kind = "not_implemented"
)

type CLIError struct {
	Kind    Kind
	Message string
	Cause   error
}

func (err *CLIError) Error() string {
	if err.Cause == nil {
		return err.Message
	}

	return err.Message + ": " + err.Cause.Error()
}

func (err *CLIError) Unwrap() error {
	return err.Cause
}

func New(kind Kind, message string) error {
	return &CLIError{Kind: kind, Message: message}
}

func Wrap(kind Kind, message string, cause error) error {
	return &CLIError{Kind: kind, Message: message, Cause: cause}
}

func ExitCode(err error) int {
	var cliErr *CLIError
	if !sterrors.As(err, &cliErr) {
		return 1
	}

	switch cliErr.Kind {
	case KindValidation:
		return 2
	case KindDependency:
		return 10
	case KindClone:
		return 20
	case KindConfig:
		return 30
	case KindIndex:
		return 40
	default:
		return 1
	}
}