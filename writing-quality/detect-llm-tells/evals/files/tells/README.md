---
title: pager
---

# pager

In today's fast-paced world, developers need tools that seamlessly integrate into their workflow. Pager is a robust, lightweight solution that empowers teams to navigate large outputs effortlessly — whether you're debugging, exploring logs, or simply reading. Let's dive in and explore how it can transform your terminal experience.

Fixed the off-by-one in pager.go that dropped the last line when the input didn't end in a newline. Repro: `printf 'a\nb' | pager`. Test added.

```bash
go install github.com/example/pager@latest
```

It's worth noting that pager supports several key features. First, it offers efficient scrolling. Second, it provides powerful search. Third, it ensures a delightful experience. Ultimately, these capabilities make it an invaluable addition to any developer's toolkit.

Config lives in `~/.config/pager/config.toml`. Only `wrap` and `tabstop` are read; anything else is ignored with a warning on stderr.
