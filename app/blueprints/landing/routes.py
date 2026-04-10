from flask import render_template, abort

from app.blueprints.landing import landing_bp
from app.extensions import db
from app.models.landing import LandingPage


@landing_bp.route('/<slug>')
def page(slug):
    """Публичная страница лендинга — без авторизации."""
    lp = db.session.scalars(
        db.select(LandingPage).where(
            LandingPage.slug == slug,
            LandingPage.is_active == True,
        )
    ).first()
    if not lp:
        abort(404)
    return render_template('landing/page.html', landing=lp, campaign=lp.campaign)
