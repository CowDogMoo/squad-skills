// Package docs is a fixture.
package docs

import "errors"

var ErrNotFound = errors.New("not found")

type Store struct {
	items map[string]int
	limit int
}

// NewStore returns a Store.
func NewStore(limit int) *Store {
	return &Store{items: map[string]int{}, limit: clamp(limit, 1, 1000)}
}

func (s *Store) Put(key string, v int) error {
	if len(s.items) >= s.limit {
		return errors.New("full")
	}
	s.items[key] = v
	return nil
}

// Get gets.
func (s *Store) Get(key string) (int, error) {
	v, ok := s.items[key]
	if !ok {
		return 0, ErrNotFound
	}
	return v, nil
}

type Option func(*Store)

func clamp(v, lo, hi int) int {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}
