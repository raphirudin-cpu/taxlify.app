import os
from flask import (
    Blueprint,
    request,
    render_template,
    redirect,
    url_for,
    flash,
    current_app,
    send_from_directory
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import db, Advisor, TeamMember, User  # Import User model
from app.security import require_role, current_advisor
from app.helpers import serve_advisor_logo, commit_or_rollback

admin_settings_bp = Blueprint('admin_settings', __name__, url_prefix='/admin/settings')

@admin_settings_bp.route('/', methods=['GET', 'POST'])
@login_required
@require_role('admin')
def advisor_settings():
    # Fetch advisor record linked to this admin user
    advisor = current_advisor()

    # ---- 1) Update Company Settings ----
    if request.method == 'POST' and 'update_settings' in request.form:
        company_name   = request.form.get('company_name')
        city           = request.form.get('city')
        phone          = request.form.get('phone')
        website        = request.form.get('website')
        company_email  = request.form.get('company_email')

        if advisor is None:
            advisor = Advisor(user_id=current_user.id)
            db.session.add(advisor)

        advisor.name    = company_name
        advisor.city    = city
        advisor.phone   = phone
        advisor.website = website
        advisor.email   = company_email

        # Handle logo upload
        if 'logo' in request.files:
            logo_file = request.files['logo']
            if logo_file and logo_file.filename:
                original_filename = secure_filename(logo_file.filename)
                _, ext = os.path.splitext(original_filename)
                filename = f"company_logo{ext}"

                # Ensure advisor.id exists
                if advisor.id is None:
                    try:
                        db.session.commit()
                    except Exception as e:
                        db.session.rollback()
                        flash("Fehler beim Speichern der Kanzlei.", "danger")
                        return redirect(url_for('admin_settings.advisor_settings'))

                # Save logo to filesystem
                upload_dir = os.path.join(
                    current_app.root_path,
                    'uploads',
                    str(advisor.id),
                    'Logo'
                )
                os.makedirs(upload_dir, exist_ok=True)
                logo_path = os.path.join(upload_dir, filename)
                try:
                    logo_file.save(logo_path)
                    advisor.logo = os.path.join(str(advisor.id), 'Logo', filename)
                except Exception as e:
                    flash("Fehler beim Hochladen des Logos.", "danger")
                    return redirect(url_for('admin_settings.advisor_settings'))

        # Commit company settings
        try:
            db.session.commit()
            flash("Einstellungen gespeichert.", "success")
        except Exception as e:
            db.session.rollback()
            flash("Fehler beim Speichern der Einstellungen.", "danger")

        return redirect(url_for('admin_settings.advisor_settings'))

    # ---- 2) Add Team Member ----
    if request.method == 'POST' and 'add_team_member' in request.form:
        # Ensure advisor exists
        if advisor is None:
            flash("Bitte vervollständige zuerst die Kanzlei-Angaben.", "danger")
            return redirect(url_for('admin_settings.advisor_settings'))

        email = request.form.get('team_member_email')
        # Check if already added for this advisor
        already = TeamMember.query.filter_by(email=email, advisor_id=advisor.id).first()
        # Check User exists and has advisor role
        user_exists = User.query.filter_by(email=email, role='advisor').first()

        if already:
            flash("Dieses Teammitglied ist bereits hinzugefügt.", "danger")
        elif not user_exists:
            flash("Kein Treuhänder-Konto mit dieser E-Mail gefunden.", "danger")
        else:
            tm = TeamMember(advisor_id=advisor.id, email=email)
            db.session.add(tm)
            try:
                db.session.commit()
                flash("Teammitglied hinzugefügt.", "success")
            except Exception as e:
                db.session.rollback()
                flash("Fehler beim Hinzufügen des Teammitglieds.", "danger")

        return redirect(url_for('admin_settings.advisor_settings'))

    # ---- Remove Team Member ----
    # Listing
    team_members = []
    if advisor:
        team_members = TeamMember.query.filter_by(advisor_id=advisor.id).all()

    return render_template(
        'admin_settings.html',
        advisor=advisor,
        team_members=team_members
    )

@admin_settings_bp.route('/remove_member', methods=['POST'])
@login_required
@require_role('admin')
def remove_team_member():
    advisor = current_advisor()
    if not advisor:
        flash("Zugriff verweigert.", "danger")
        return redirect(url_for('admin_settings.advisor_settings'))

    member_id = request.form.get('member_id')
    member    = TeamMember.query.filter_by(id=member_id, advisor_id=advisor.id).first()

    if not member:
        flash("Teammitglied nicht gefunden.", "danger")
    else:
        db.session.delete(member)
        if commit_or_rollback():
            flash("Teammitglied entfernt.", "success")
        else:
            flash("Fehler beim Entfernen des Teammitglieds.", "danger")

    return redirect(url_for('admin_settings.advisor_settings'))

@admin_settings_bp.route('/uploads/<int:advisor_id>/Logo/<filename>')
def uploaded_logo(advisor_id, filename):
    return serve_advisor_logo(advisor_id, filename)

@admin_settings_bp.route('/delete_logo', methods=['POST'])
@login_required
@require_role('admin')
def delete_logo():
    advisor = current_advisor()
    if advisor and advisor.logo:
        logo_path = os.path.join(current_app.root_path, 'uploads', advisor.logo)
        advisor.logo = None

        if not commit_or_rollback():
            flash("Fehler beim Speichern.", "danger")
            return redirect(url_for('admin_settings.advisor_settings'))

        if os.path.exists(logo_path):
            try:
                os.remove(logo_path)
                flash("Logo gelöscht.", "success")
            except Exception as e:
                flash("Logo entfernt, aber die Datei konnte nicht gelöscht werden.", "danger")
        else:
            flash("Logo entfernt, aber die Datei wurde nicht gefunden.", "warning")
    else:
        flash("Kein Logo zum Löschen vorhanden.", "info")

    return redirect(url_for('admin_settings.advisor_settings'))
