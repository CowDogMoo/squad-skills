package calc

import "errors"

// ErrDivZero is returned by Div when the divisor is zero.
var ErrDivZero = errors.New("divide by zero")

// Add returns a+b.
func Add(a, b int) int { return a + b }

// Div returns a/b or ErrDivZero.
func Div(a, b int) (int, error) {
	if b == 0 {
		return 0, ErrDivZero
	}
	return a / b, nil
}

// Clamp limits v to [lo, hi].
func Clamp(v, lo, hi int) int {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}

// Mean returns the arithmetic mean, or 0 for an empty slice.
func Mean(xs []int) float64 {
	if len(xs) == 0 {
		return 0
	}
	sum := 0
	for _, x := range xs {
		sum += x
	}
	return float64(sum) / float64(len(xs))
}
