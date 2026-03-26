# TODO: Add Chat Feature for Accepted Orders

## Steps to Complete
- [x] Add Message model in app.py: id, order_id, sender_id, text, created_at
- [x] Add chat route in app.py: /chat/<order_id> (GET/POST) with access control
- [x] Update templates/orders.html: Add "Chat" button for accepted orders
- [x] Create templates/chat.html: Display messages and send form
- [x] Restart Flask app to update database schema
- [ ] Test: Accept an order, access chat, send messages between buyer and seller
