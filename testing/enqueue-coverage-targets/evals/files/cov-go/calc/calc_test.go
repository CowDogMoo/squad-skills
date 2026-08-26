package calc_test

import (
	"testing"

	"example.com/covgo/calc"
)

func TestAdd(t *testing.T) {
	if got := calc.Add(2, 3); got != 5 {
		t.Fatalf("Add(2,3) = %d, want 5", got)
	}
}
