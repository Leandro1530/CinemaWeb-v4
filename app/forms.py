from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, TextAreaField, DateField
from wtforms.validators import DataRequired, Length

class MovieForm(FlaskForm):
    title = StringField('Título', validators=[DataRequired(), Length(max=100)])
    genre = SelectField('Género', choices=[('action', 'Acción'), ('comedy', 'Comedia'), ('drama', 'Drama'), ('horror', 'Terror')], validators=[DataRequired()])
    description = TextAreaField('Descripción', validators=[Length(max=500)])
    release_date = DateField('Fecha de Estreno', format='%Y-%m-%d', validators=[DataRequired()])
    submit = SubmitField('Agregar Película')