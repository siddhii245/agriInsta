# TODO for Order Management Dashboard

## 1. Update base.html
- Add "My Orders" link in navigation for logged-in users

## 2. Add Orders Route in app.py
- Create /orders route (GET): Query orders where user is buyer or seller, order by created_at desc

## 3. Add Accept/Reject Routes in app.py
- /accept_order/<order_id> (POST): Update order status to 'accepted' if user is seller
- /reject_order/<order_id> (POST): Update order status to 'rejected' if user is seller

## 4. Create templates/orders.html
- Display orders in sections: Pending, Accepted, Rejected
- Show details: Product title, Buyer/Seller name, Quantity, Amount, Date, Status
- Add Accept/Reject buttons for sellers on pending orders
- Add Rate button for buyers on accepted orders (link to rate_order)

## 5. Test Dashboard
- Access /orders, verify order listing
- Test accept/reject actions as seller
- Test rate link as buyer
- Ensure proper permissions (only seller can accept/reject)
