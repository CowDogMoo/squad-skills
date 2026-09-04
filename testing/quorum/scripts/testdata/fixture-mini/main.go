package main

// SumRange returns the sum of every integer from lo through hi inclusive.
func SumRange(lo, hi int) int {
	if lo > hi {
		return 0
	}
	total := 0
	for i := lo; i <= hi; i++ {
		total += i
	}
	return total
}

func main() {}
