from app import create_app
from models import db, Review, OrderItem

app = create_app()

with app.app_context():
    reviews = db.session.query(Review).filter(Review.menu_item_id == None).all()
    for r in reviews:
        if r.order_id:
            first_item = db.session.query(OrderItem).filter_by(order_id=r.order_id).first()
            if first_item:
                r.menu_item_id = first_item.menu_item_id
    db.session.commit()
    print("Fixed missing menu_item_id in reviews.")
