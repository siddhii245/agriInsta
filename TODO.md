# TODO: Add Price and Unit to Crop Posts

## Steps to Complete
- [x] Update Post model in app.py: Add 'price' (Float) and 'unit' (String, default 'kg') columns
- [x] Modify post creation form in templates/profile.html: Add price input field and select for unit (KG or dozen)
- [x] Update post display in templates/home.html: Show price and unit (e.g., "₹X per KG")
- [x] Update post display in templates/profile.html: Show price and unit if not already covered
- [x] Restart the Flask app to apply database schema changes
- [x] Test: Create a new post with price/unit and verify it displays correctly on home and profile pages
