from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, BooleanField, SelectField, SelectMultipleField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional
from wtforms.widgets import ListWidget, CheckboxInput
from wtforms.validators import Optional

class AdminLoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

class EditProfileForm(FlaskForm):
    full_name = StringField('Full Name', validators=[Optional(), Length(max=100)])
    phone = StringField('Phone Number', validators=[Optional(), Length(max=20)])
    address = TextAreaField('Address', validators=[Optional()])
    submit = SubmitField('Update Profile')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', 
                                   validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Change Password')

class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

class ApplicationForm(FlaskForm):
    learnerships = MultiCheckboxField('Select Learnerships', coerce=int)
    email_body = TextAreaField('Email Body', validators=[DataRequired(), Length(min=50, max=2000)])
    attachments = SelectMultipleField('Select Documents to Attach', coerce=int)
    submit = SubmitField('Send Application')

class DocumentUploadForm(FlaskForm):
    document_type = SelectField('Document Type', choices=[
        ('cv', 'CV/Resume'),
        ('cover_letter', 'Cover Letter'),
        ('id', 'ID Document'),
        ('qualification', 'Qualification Certificate'),
        ('affidavit', 'Affidavit'),
        ('disability', 'Disability Letter'),
        ('other', 'Other Supporting Document')
    ], validators=[DataRequired()])
    document = FileField('Select Document', validators=[
        DataRequired(),
        FileAllowed(['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'], 'Only PDF, Word documents and images allowed!')
    ])
    submit = SubmitField('Upload Document')

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import Optional

class LearnershipSearchForm(FlaskForm):
    search = StringField('Search', validators=[Optional()])
    category = SelectField('Category', 
                           choices=[('all', 'All Categories')], 
                           validators=[Optional()])
    submit = SubmitField('Search')