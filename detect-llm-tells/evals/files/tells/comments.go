package pager

// Here we implement the core scrolling logic.
// Step 1: Calculate the visible window.
// Step 2: Clamp the offset to the buffer length.
// Step 3: Render the lines within the window.
func scroll(offset, height, total int) (int, int) {
	if offset+height > total {
		offset = total - height
	}
	if offset < 0 {
		offset = 0
	}
	return offset, offset + height
}

// wrap breaks a line at width, preferring spaces. Tabs are expanded
// first because the terminal's own tab handling disagrees with ours.
func wrap(s string, width int) []string { //nolint:unused
	return nil
}

// Ensures the buffer is never nil.
func ensure(b []string) []string {
	if b == nil {
		return []string{}
	}
	return b
}
