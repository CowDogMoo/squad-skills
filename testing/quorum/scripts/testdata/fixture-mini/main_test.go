package main

import "testing"

func TestSumRange(t *testing.T) {
	if got := SumRange(1, 3); got != 6 {
		t.Errorf("SumRange(1, 3) = %d, want 6", got)
	}
	if got := SumRange(5, 2); got != 0 {
		t.Errorf("SumRange(5, 2) = %d, want 0", got)
	}
}
