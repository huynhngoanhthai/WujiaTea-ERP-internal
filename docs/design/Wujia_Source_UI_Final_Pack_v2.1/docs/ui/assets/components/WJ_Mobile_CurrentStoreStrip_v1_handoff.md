# WJ_Mobile_CurrentStoreStrip_v1 — Handoff Note

## Purpose
Compact current-store context for Wujia/Ngô Gia mobile screens outside Home.

## Final display

```text
[H000] Cửa hàng Nguyễn Trãi                  Owner
```

## Placement
- Directly below `WJ_Mobile_Header_Primary`.
- Above page title / search / content.
- Not used on Home dashboard, where the store context is shown in the hero/card.

## Visual specs
- Width: 391px base, responsive 375–414px.
- Height: 48px.
- Background: #FFFFFF.
- Border bottom: #EEF2F5.
- Padding: 10px 16px.
- Store code badge: background #EAF7FD, text #28A9DF, 12px bold.
- Store name: #111827, 15px bold, one line with ellipsis.
- Role/status badge: right aligned pill, e.g. Owner / Manager / Staff.

## Rules
- Do not show the sentence “Đang thao tác cho cửa hàng này.”
- Do not show address, hotline, or representative name in this strip.
- Do not allow store switching directly on the strip in phase 1.
- Reuse this component across Product List, Cart, Order History, Delivery, Return, Ticket, and Debt screens.
