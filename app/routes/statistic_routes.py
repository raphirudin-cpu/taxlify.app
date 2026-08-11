from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, UserStatistics
from app.security import require_role

statistics_bp = Blueprint('statistics', __name__)

@statistics_bp.route('/statistics', methods=['GET', 'POST'])
@login_required
@require_role('user')
def statistics():
    user = current_user

    if request.method == 'POST':
        date = request.form.get('date')
        taxable_income = request.form.get('taxable_income')
        taxable_assets = request.form.get('taxable_assets')
        paid_taxes = request.form.get('paid_taxes')

        new_entry = UserStatistics(
            user_id=user.id,
            date=date,
            taxable_income=taxable_income,
            taxable_assets=taxable_assets,
            paid_taxes=paid_taxes
        )
        db.session.add(new_entry)
        db.session.commit()
        flash('Data added successfully.', 'success')
        return redirect(url_for('statistics.statistics'))  # ✅ Prevents resubmission on refresh

    data_points = UserStatistics.query.filter_by(user_id=user.id).order_by(UserStatistics.date.desc()).all()
    
    return render_template('statistics.html', user=user, data_points=data_points)

@statistics_bp.route('/statistics/edit/<int:entry_id>', methods=['POST'])
@login_required
def edit_statistics(entry_id):
    # ensure only this user can edit their own data
    entry = UserStatistics.query.\
        filter_by(id=entry_id, user_id=current_user.id).\
        first_or_404()

    # pull updated values from the form
    entry.date = request.form['edit_date']
    entry.taxable_income = request.form['edit_taxable_income']
    entry.taxable_assets = request.form['edit_taxable_assets']
    entry.paid_taxes = request.form['edit_paid_taxes']

    db.session.commit()
    flash('Entry updated successfully.', 'success')
    return redirect(url_for('statistics.statistics'))