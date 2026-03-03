---
title: {{ title }}
date: {{ date.strftime("%Y-%m-%dT%H:%M:%S") }}
tags: [{% for tag in tags %}{{ tag }}{% if not loop.last %}, {% endif %}{% endfor %}]
description: {{ description }}
draft: {{ draft | lower }}
url: {{ url }}
aliases:
  - {{ alias }}
---

