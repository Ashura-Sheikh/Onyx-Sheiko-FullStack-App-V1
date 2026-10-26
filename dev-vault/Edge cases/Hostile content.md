---
synthetic: true
tags:
  - test-data
dateModified: 2031-04-02T10:05:00Z
---

# Hostile content

Test data: this text must always be shown as text, never run.

<script>alert("xss")</script>

<img src="x" onerror="alert(1)">

[click me](javascript:alert(1))
